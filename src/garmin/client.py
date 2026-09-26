
import logging
import os
import sys
import json
from enum import Enum, auto
from pathlib import Path
from typing import Dict, List, Optional, Union
import requests

from garth.http import Client

# Ensure we can import from the parent package
sys.path.insert(0, str(Path(__file__).parent.parent))
from garmin.url_dict import GARMIN_URL_DICT
from garmin.oauth import GarminOAuth, GarminOAuthError
from utils.paths import harden_garmin_session_dir
# 注意：core.session_store 在方法内延迟导入，避免
# garmin.client → core/__init__ → sync_service → garmin.client 循环导入

logger = logging.getLogger(__name__)

class ActivityUploadFormat(Enum):
    FIT = auto()
    GPX = auto()
    TCX = auto()

class GarminClient:
    def __init__(self, email, password=None, auth_domain="CN", session_dir=None, session_name=None, password_provider=None):
        self.email = email
        # 决策 4：密码可选；password_provider 为惰性回调（会话失效时才调用，
        # 避免会话有效时白问一次密码）
        self.password = password
        self._password_provider = password_provider
        self.auth_domain = auth_domain
        self.session_name = session_name or email  # 脱敏标识，默认用 email
        # 会话目录默认走 get_app_data_dir（开发=项目根 data/，打包=%APPDATA%）；
        # GUI 可显式传入 get_garmin_auth_dir() 的结果（行为一致）
        # 最终路径：auth/garmin/<session_name>/（CLI/GUI 一致，不含 email）
        if session_dir is None:
            from utils.paths import get_app_data_dir
            session_dir = get_app_data_dir() / 'auth' / 'garmin'
        self.session_dir = Path(session_dir) / self.session_name  # Segregate sessions by name
        # Create independent Client instance to avoid conflicts with global garth singleton
        self._client = Client()
        self._oauth = None  # 自研 OAuth 兜底实例（类型 B 失效时启用）
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.88 Safari/537.36",
            "origin": GARMIN_URL_DICT.get("SSO_URL_ORIGIN", "https://sso.garmin.com"),
            "nk": "NT"
        }

    def login(self):
        """Log in to Garmin Connect and handle session persistence"""
        return self._login_impl(lambda: input("Enter Garmin MFA code: "))

    def login_for_ui(self, mfa_callback):
        """
        Log in to Garmin Connect with MFA callback for UI integration.

        Args:
            mfa_callback: A callable that returns the MFA code when invoked.
                         This allows the UI to prompt the user for input.

        Returns:
            bool: True if login successful, False otherwise.
        """
        return self._login_impl(mfa_callback)

    def _login_impl(self, mfa_provider):
        """
        Internal login implementation with configurable MFA provider.

        Args:
            mfa_provider: A callable that returns the MFA code when invoked.

        Returns:
            bool: True if login successful, False otherwise.
        """
        try:
            # Try to resume from saved session
            if self.session_dir.exists() and any(self.session_dir.iterdir()):
                # A：账号哈希绑定校验（防会话文件被改名/换内容错配）
                from core.session_store import verify_garmin_session_binding
                if not verify_garmin_session_binding(self.session_dir, self.email):
                    logger.error(
                        f"Garmin 会话目录 {self.session_name} 的账号绑定与当前邮箱不匹配，拒绝使用。请删除该目录后重新认证。")
                    return False
                logger.info(f"Attempting to resume Garmin session for {self.session_name} from {self.session_dir}")
                try:
                    self._client.load(str(self.session_dir))
                    # Check if session is still valid by accessing username
                    # (访问 username 属性会触发 API 调用验证会话，但不打印账号)
                    _ = self._client.username
                    logger.info(f"Garmin session resumed successfully for user: {self.session_name}")
                    # 补写绑定文件（旧会话无 account.json 时）+ 权限加固
                    from core.session_store import save_garmin_session_binding
                    save_garmin_session_binding(self.session_dir, self.email)
                    harden_garmin_session_dir(self.session_dir)
                    return True
                except Exception as e:
                    logger.warning(f"Failed to resume session: {e}. Performing fresh login.")

            # 无有效会话 → 需要密码重新认证（惰性获取）
            if not self.password and self._password_provider is not None:
                try:
                    self.password = self._password_provider()
                except Exception as e:
                    logger.error(f"获取佳明密码失败: {e}")
                    return False
            if not self.password:
                logger.error(
                    f"Garmin 会话缺失/失效，且未提供密码（非交互环境无法输入）。请先在终端手动运行完成认证。")
                return False

            # 失效类型 A：garth 重新登录（token 过期，OAuth 流程本身可走通）
            logger.info(f"Logging in to Garmin for {self.session_name}...")
            domain = "garmin.cn" if self.auth_domain and self.auth_domain.upper() == "CN" else "garmin.com"
            self._client.configure(domain=domain)

            try:
                self._client.login(self.email, self.password, prompt_mfa=mfa_provider)
            except Exception as garth_err:
                # 失效类型 B：garth 库本身与当前 OAuth 流程不兼容 → 自动切换自研 OAuth
                logger.warning(
                    f"garth 登录失败（{garth_err}），尝试自研 OAuth 兜底模块...")
                if not self._login_via_custom_oauth(domain, mfa_provider):
                    logger.error(f"Garmin login failed for {self.session_name}: {garth_err}")
                    return False
            else:
                # Save session
                self.session_dir.mkdir(parents=True, exist_ok=True)
                self._client.dump(str(self.session_dir))
                logger.info(f"Garmin session saved to {self.session_dir}")

                # Clean up headers as required by some Garmin versions
                if 'User-Agent' in self._client.sess.headers:
                    del self._client.sess.headers['User-Agent']

            # A：写账号绑定 + 权限加固（两条路径都执行）
            from core.session_store import save_garmin_session_binding
            save_garmin_session_binding(self.session_dir, self.email)
            harden_garmin_session_dir(self.session_dir)
            return True
        except Exception as e:
            logger.error(f"Garmin login failed for {self.session_name}: {e}")
            return False

    def _login_via_custom_oauth(self, domain: str, mfa_provider) -> bool:
        """
        失效类型 B 兜底：自研 OAuth 模块（参考 auth.ts）

        成功时 token 写入与 garth 同格式的目录，后续 garth 可继续读（双向兼容）。
        """
        try:
            oauth = GarminOAuth(domain=domain)
            oauth1, oauth2 = oauth.login(
                self.email, self.password, prompt_mfa=mfa_provider)
            oauth.save(self.session_dir)
            # 把 token 同步到 garth Client，让后续 upload 等 API 调用可用
            from garth.auth_tokens import OAuth1Token, OAuth2Token
            self._client.configure(
                oauth1_token=OAuth1Token(**{
                    k: oauth1.get(k) for k in
                    ("oauth_token", "oauth_token_secret", "mfa_token",
                     "mfa_expiration_timestamp", "domain")
                    if k in oauth1}),
                oauth2_token=OAuth2Token(**{k: v for k, v in oauth2.items()
                                           if k in OAuth2Token.__dataclass_fields__}),
                domain=domain,
            )
            self._oauth = oauth
            logger.info(f"自研 OAuth 登录成功，token 已保存到 {self.session_dir}")
            return True
        except Exception as e:
            logger.error(f"自研 OAuth 登录也失败: {e}")
            return False

    def upload_fit(self, fit_path: Union[str, Path]):
        """Upload FIT file to Garmin Connect."""
        fit_path = Path(fit_path)
        if not fit_path.exists():
            logger.error(f"FIT file not found: {fit_path}")
            return "FILE_NOT_FOUND"

        file_base_name = fit_path.name
        file_extension = fit_path.suffix[1:].upper()
        
        if file_extension not in ActivityUploadFormat.__members__:
            logger.error(f"Unsupported file format: {file_extension}")
            return "UNSUPPORTED_FORMAT"

        try:
            logger.info(f"Uploading {file_base_name} to Garmin Connect...")
            with open(fit_path, 'rb') as f:
                file_data = f.read()
            
            fields = {
                'file': (file_base_name, file_data, 'application/octet-stream')
            }

            url_path = GARMIN_URL_DICT["garmin_connect_upload"]
            upload_url = f"https://connectapi.{self._client.domain}{url_path}"

            # Update headers with dynamic tokens from client
            headers = self.headers.copy()
            headers['Authorization'] = str(self._client.oauth2_token)
            
            # Using requests for the upload part as in the original code
            response = requests.post(upload_url, headers=headers, files=fields)
            
            if response.status_code == 202 or response.status_code == 201 :
                logger.info(f"Successfully uploaded {file_base_name}")
                return "SUCCESS"
            elif response.status_code == 409:
                logger.warning(f"Duplicate file detected on Garmin Connect: {file_base_name}")
                return "DUPLICATE"
            else:
                logger.error(f"Upload failed with status {response.status_code}: {response.text}")
                return f"ERROR_{response.status_code}"
                
        except Exception as e:
            logger.error(f"Error during FIT upload: {e}")
            return "UPLOAD_EXCEPTION"
