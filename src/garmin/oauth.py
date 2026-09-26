"""
自研 Garmin OAuth 兜底模块（决策 7）

参考 garmin-connect-plugin-for-dsh/src/auth.ts 与 garth 库 sso.py 的实现，
手动完成 SSO 登录 → OAuth1 → OAuth2 全流程，不依赖 garth 库。

触发条件：仅当 garth 判定为失效类型 B（库本身与 Garmin OAuth 流程不兼容）
时由 GarminClient 自动切换调用。

token 文件兼容：读写与 garth 完全相同的目录结构
（data/auth/garmin/{email}/oauth1_token.json + oauth2_token.json），
读旧文件即可无缝接管，用户无感知。
"""
import json
import logging
import time
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple
from urllib.parse import parse_qs

import requests
from requests_oauthlib import OAuth1Session

logger = logging.getLogger(__name__)

# 与 garth sso.py 保持一致的常量
CLIENT_ID = "GCM_ANDROID_DARK"
OAUTH_CONSUMER_URL = "https://thegarth.s3.amazonaws.com/oauth_consumer.json"
OAUTH_USER_AGENT = {"User-Agent": "com.garmin.android.apps.connectmobile"}
_SSO_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
)
SSO_PAGE_HEADERS = {
    "User-Agent": _SSO_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Dest": "document",
}

OAUTH1_TOKEN_FILE = "oauth1_token.json"
OAUTH2_TOKEN_FILE = "oauth2_token.json"


class GarminOAuthError(Exception):
    """自研 OAuth 流程失败"""
    pass


class GarminOAuth:
    """自研 Garmin OAuth 客户端（garth 失效类型 B 时的兜底）"""

    def __init__(self, domain: str = "garmin.cn", timeout: int = 30):
        self.domain = domain
        self.timeout = timeout
        self.sess = requests.Session()
        self.oauth1: Optional[Dict] = None
        self.oauth2: Optional[Dict] = None

    # ---------- 登录流程 ----------

    def login(self, email: str, password: str,
              prompt_mfa: Optional[Callable[[], str]] = None) -> Tuple[Dict, Dict]:
        """
        完整登录：SSO → (MFA) → OAuth1 → OAuth2

        Args:
            email: 佳明邮箱
            password: 佳明密码（仅内存中使用）
            prompt_mfa: MFA 验证码回调（返回验证码字符串）；None 时 MFA 直接报错

        Returns:
            (oauth1_dict, oauth2_dict)
        """
        service_url = f"https://mobile.integration.{self.domain}/gcm/android"
        login_params = {
            "clientId": CLIENT_ID,
            "locale": "en-US",
            "service": service_url,
        }

        # 1. 设置 SSO cookies
        self.sess.get(
            f"https://sso.{self.domain}/mobile/sso/en/sign-in",
            params={"clientId": CLIENT_ID},
            headers={**SSO_PAGE_HEADERS, "Sec-Fetch-Site": "none"},
            timeout=self.timeout,
        )

        # 2. 提交登录
        resp = self.sess.post(
            f"https://sso.{self.domain}/mobile/api/login",
            params=login_params,
            headers=SSO_PAGE_HEADERS,
            json={
                "username": email,
                "password": password,
                "rememberMe": False,
                "captchaToken": "",
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        resp_type = data.get("responseStatus", {}).get("type")

        if resp_type == "SUCCESSFUL":
            ticket = data["serviceTicketId"]
        elif resp_type == "MFA_REQUIRED":
            if prompt_mfa is None:
                raise GarminOAuthError(
                    "Garmin 需要 MFA 验证码，但当前环境无法交互输入")
            mfa_info = data.get("customerMfaInfo") or {}
            mfa_method = mfa_info.get("mfaLastMethodUsed") or "email"
            code = prompt_mfa()
            if not code:
                raise GarminOAuthError("MFA 验证码为空")
            mfa_resp = self.sess.post(
                f"https://sso.{self.domain}/mobile/api/mfa/verifyCode",
                params=login_params,
                headers=SSO_PAGE_HEADERS,
                json={
                    "mfaMethod": mfa_method,
                    "mfaVerificationCode": code,
                    "rememberMyBrowser": False,
                    "reconsentList": [],
                    "mfaSetup": False,
                },
                timeout=self.timeout,
            )
            mfa_resp.raise_for_status()
            mfa_data = mfa_resp.json()
            if mfa_data.get("responseStatus", {}).get("type") != "SUCCESSFUL":
                raise GarminOAuthError(
                    f"MFA 验证失败: {mfa_data.get('responseStatus')}")
            ticket = mfa_data["serviceTicketId"]
        else:
            raise GarminOAuthError(
                f"SSO 登录失败: {data.get('responseStatus')}")

        # 3. OAuth1 + OAuth2 交换
        return self._complete_login(ticket)

    def _complete_login(self, ticket: str) -> Tuple[Dict, Dict]:
        """SSO ticket → OAuth1 → OAuth2（与 garth _complete_login 等价）"""
        # Cloudflare LB cookie 固定（尽力而为）
        try:
            self.sess.get(
                f"https://sso.{self.domain}/portal/sso/embed",
                headers={**SSO_PAGE_HEADERS, "Sec-Fetch-Site": "same-origin"},
                timeout=self.timeout,
            )
        except Exception:
            pass

        self.oauth1 = self._get_oauth1_token(ticket)
        self.oauth2 = self._exchange(self.oauth1, login=True)
        return self.oauth1, self.oauth2

    def _get_oauth1_token(self, ticket: str) -> Dict:
        """SSO ticket → OAuth1 token（preauthorized）"""
        consumer = requests.get(OAUTH_CONSUMER_URL, timeout=self.timeout).json()
        sess = OAuth1Session(
            consumer["consumer_key"], consumer["consumer_secret"],
            redirect_uri="oob",
        )
        sess.cookies.update(self.sess.cookies)
        base_url = f"https://connectapi.{self.domain}/oauth-service/oauth/"
        login_url = f"https://mobile.integration.{self.domain}/gcm/android"
        url = (
            f"{base_url}preauthorized?ticket={ticket}"
            f"&login-url={login_url}&accepts-mfa-tokens=true"
        )
        resp = sess.get(url, headers=OAUTH_USER_AGENT, timeout=self.timeout)
        resp.raise_for_status()
        token = {k: v[0] for k, v in parse_qs(resp.text).items()}
        token["domain"] = self.domain
        return token

    def _exchange(self, oauth1: Dict, login: bool = False) -> Dict:
        """OAuth1 → OAuth2 交换"""
        sess = OAuth1Session(
            oauth1["oauth_token"], oauth1["oauth_token_secret"],
            redirect_uri="oob",
        )
        sess.cookies.update(self.sess.cookies)
        data: Dict[str, str] = {}
        if login:
            data["audience"] = "GARMIN_CONNECT_MOBILE_ANDROID_DI"
        if oauth1.get("mfa_token"):
            data["mfa_token"] = oauth1["mfa_token"]
        url = f"https://connectapi.{self.domain}/oauth-service/oauth/exchange/user/2.0"
        resp = sess.post(
            url,
            headers={**OAUTH_USER_AGENT,
                     "Content-Type": "application/x-www-form-urlencoded"},
            data=data,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        token = resp.json()
        token["expires_at"] = int(time.time() + token["expires_in"])
        token["refresh_token_expires_at"] = int(
            time.time() + token["refresh_token_expires_in"])
        return token

    # ---------- 会话有效性 ----------

    def is_valid(self) -> bool:
        """用当前 oauth2 token 验证会话是否有效（访问 socialProfile）"""
        if not self.oauth2:
            return False
        try:
            resp = self.sess.get(
                f"https://connectapi.{self.domain}/userprofile-service/socialProfile",
                headers={"Authorization": f"Bearer {self.oauth2['access_token']}"},
                timeout=self.timeout,
            )
            return resp.status_code == 200
        except Exception:
            return False

    # ---------- token 文件读写（与 garth dump/load 同格式） ----------

    def save(self, session_dir) -> None:
        """写入 token 文件（格式与 garth dump 完全一致）"""
        d = Path(session_dir)
        d.mkdir(parents=True, exist_ok=True)
        oauth1_payload = {
            "oauth_token": self.oauth1.get("oauth_token", ""),
            "oauth_token_secret": self.oauth1.get("oauth_token_secret", ""),
            "mfa_token": self.oauth1.get("mfa_token"),
            "mfa_expiration_timestamp": None,
            "domain": self.domain,
        }
        with open(d / OAUTH1_TOKEN_FILE, "w", encoding="utf-8") as f:
            json.dump(oauth1_payload, f, indent=4)
        with open(d / OAUTH2_TOKEN_FILE, "w", encoding="utf-8") as f:
            json.dump(self.oauth2, f, indent=4)
        logger.info(f"自研 OAuth token 已保存到 {d}")

    def load(self, session_dir) -> bool:
        """
        读取 token 文件（兼容 garth 写的旧文件，无缝接管）

        Returns:
            bool: 是否读取成功
        """
        d = Path(session_dir)
        try:
            with open(d / OAUTH1_TOKEN_FILE, encoding="utf-8") as f:
                self.oauth1 = json.load(f)
            with open(d / OAUTH2_TOKEN_FILE, encoding="utf-8") as f:
                self.oauth2 = json.load(f)
            self.domain = self.oauth1.get("domain") or self.domain
            # 兼容 garth 旧文件：mfa_expiration_timestamp 可能是 ISO 字符串，
            # 自研模块只用 mfa_token 字段，该字段归一化为 None 避免类型问题
            if not isinstance(self.oauth1.get("mfa_expiration_timestamp"), type(None)):
                self.oauth1["mfa_expiration_timestamp"] = None
            return True
        except Exception as e:
            logger.warning(f"读取自研 OAuth token 文件失败: {e}")
            return False
