"""
同步服务编排器
提供统一的同步接口，供 GUI 和 CLI 调用
"""
import json
import logging
import datetime
from typing import Generator, Optional, List, Dict, Any
from pathlib import Path

from .models import SyncProgress, SyncResult, UserModel
from .config_manager import EnhancedConfigManager

logger = logging.getLogger(__name__)

# Import existing modules
import sys
sys.path.append(str(Path(__file__).parent.parent))

from xiaomi.client import XiaomiClient, fetch_merged_weights
from garmin.client import GarminClient
from garmin.fit_generator import create_weight_fit_file
from utils.paths import get_app_data_dir, get_garmin_auth_dir, get_output_dir


class SyncOrchestrator:
    """同步编排器 - 协调整个同步流程"""

    def __init__(self, config_path: str = "users.json"):
        """
        初始化同步编排器

        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.config_mgr = EnhancedConfigManager(config_path)
        self._should_stop = False

    def reload_config(self, new_config_path: str):
        """
        重新加载配置文件

        Args:
            new_config_path: 新的配置文件路径
        """
        self.config_path = new_config_path
        self.config_mgr = EnhancedConfigManager(new_config_path)
        logger.info(f"配置文件已重新加载：{new_config_path}")

    def list_users(self) -> List[UserModel]:
        """获取所有用户列表"""
        return self.config_mgr.get_users()

    def get_user(self, username: str) -> Optional[UserModel]:
        """获取指定用户"""
        return self.config_mgr.get_user(username)

    def save_user(self, user: UserModel) -> bool:
        """保存用户（添加或更新）"""
        return self.config_mgr.add_or_update_user(user)

    def delete_user(self, username: str) -> bool:
        """删除用户"""
        return self.config_mgr.delete_user(username)

    def sync_user(
        self,
        username: str,
        chunk_size: int = 500,
        input_callback=None
    ) -> Generator[SyncProgress, None, None]:
        """
        执行同步，返回进度生成器

        Args:
            username: 用户名
            chunk_size: 分块大小（默认 500）
            input_callback: 用户输入回调函数（用于登录时需要用户输入）

        Yields:
            SyncProgress: 同步进度信息
        """
        try:
            self._should_stop = False

            # 获取用户配置
            user = self.get_user(username)
            if not user:
                yield SyncProgress(
                    stage="error",
                    current=0,
                    total=100,
                    message=f"❌ 用户不存在: {username}",
                    timestamp=datetime.datetime.now().strftime("%H:%M:%S"),
                    username=username
                )
                return

            # 脱敏标识：有前缀用前缀，无则回退到账号短哈希（B，不再用明文账号）
            from core.account import resolve_prefix
            xiaomi_prefix = resolve_prefix(user.xiaomi_prefix, user.username)
            garmin_prefix = resolve_prefix(
                user.garmin_prefix,
                user.garmin.email if user.garmin else user.username)

            # 阶段 1: 登录小米并获取数据
            yield SyncProgress(
                stage="fetching",
                current=10,
                total=100,
                message="📱 正在登录小米...",
                timestamp=datetime.datetime.now().strftime("%H:%M:%S"),
                username=username
            )

            xiaomi_client = XiaomiClient(username=user.username)

            # 决策 2：token 从独立会话文件读取（含账号哈希绑定校验 A）
            from core.session_store import (load_xiaomi_auth,
                                            save_xiaomi_auth,
                                            SessionAccountMismatchError)
            try:
                session_token = load_xiaomi_auth(
                    xiaomi_prefix, xiaomi_account=user.username,
                    custom_base=getattr(self.config_mgr, 'custom_data_dir', None))
            except SessionAccountMismatchError as e:
                yield SyncProgress(
                    stage="error", current=0, total=100,
                    message=f"❌ 小米会话文件账号绑定不匹配: {e}",
                    timestamp=datetime.datetime.now().strftime("%H:%M:%S"),
                    username=username)
                return

            # 兼容：旧版 users.json 内嵌 token 优先迁移到会话文件
            if not session_token and user.token and user.token.userId and user.token.passToken:
                from core.session_store import migrate_token_from_users_json
                migrate_token_from_users_json(
                    self.config_mgr, user.to_dict(), xiaomi_prefix,
                    custom_base=getattr(self.config_mgr, 'custom_data_dir', None))
                session_token = load_xiaomi_auth(
                    xiaomi_prefix, xiaomi_account=user.username,
                    custom_base=getattr(self.config_mgr, 'custom_data_dir', None))

            has_valid_token = bool(
                session_token and session_token.get("userId")
                and session_token.get("passToken"))

            if not has_valid_token:
                # 尝试用户名密码登录
                yield SyncProgress(
                    stage="fetching",
                    current=15,
                    total=100,
                    message="🔐 需要登录小米账号...",
                    timestamp=datetime.datetime.now().strftime("%H:%M:%S"),
                    username=username
                )

                # 通过回调请求 GUI 弹出登录对话框
                if not input_callback:
                    yield SyncProgress(
                        stage="error",
                        current=0,
                        total=100,
                        message="❌ 未配置小米 Token 且无法进行交互式登录",
                        timestamp=datetime.datetime.now().strftime("%H:%M:%S"),
                        username=username
                    )
                    return

                login_result = input_callback({
                    "action": "xiaomi_login",
                    "username": user.username,
                    "password": user.password if user.password else None
                })

                if not login_result.get("success"):
                    error_msg = login_result.get("error", "未知错误")
                    yield SyncProgress(
                        stage="error",
                        current=0,
                        total=100,
                        message=f"❌ 小米登录失败: {error_msg}",
                        timestamp=datetime.datetime.now().strftime("%H:%M:%S"),
                        username=username
                    )
                    return

                # 决策 2：保存 token 到独立会话文件（不再写 users.json）
                token_data = login_result["token"]
                save_xiaomi_auth(xiaomi_prefix, token_data,
                                    xiaomi_account=user.username,
                                    custom_base=getattr(self.config_mgr, 'custom_data_dir', None))
                logger.info(f"用户 {xiaomi_prefix} 登录成功,Token 已保存到会话文件")

                # 设置凭证到 client
                xiaomi_client.set_credentials(
                    user_id=token_data["userId"],
                    ssecurity_encoded=token_data["ssecurity"],
                    pass_token=token_data["passToken"]
                )

                # 刷新 token
                try:
                    new_token_data = xiaomi_client.login_from_token()
                    if new_token_data:
                        save_xiaomi_auth(xiaomi_prefix, new_token_data,
                                            xiaomi_account=user.username,
                                            custom_base=getattr(self.config_mgr, 'custom_data_dir', None))
                        logger.info(f"用户 {xiaomi_prefix} 的 Token 已刷新")
                except Exception as e:
                    # Token 刷新失败,但继续使用刚获取的 token
                    logger.warning(f"Token 刷新失败,但继续使用: {e}")

            else:
                # 使用会话文件中的现有 token
                xiaomi_client.set_credentials(
                    user_id=session_token["userId"],
                    ssecurity_encoded=session_token.get("ssecurity"),
                    pass_token=session_token["passToken"]
                )

                try:
                    # 刷新 Token
                    yield SyncProgress(
                        stage="fetching",
                        current=20,
                        total=100,
                        message="🔄 正在刷新小米 Token...",
                        timestamp=datetime.datetime.now().strftime("%H:%M:%S"),
                        username=username
                    )

                    new_token_data = xiaomi_client.login_from_token()
                    if new_token_data:
                        save_xiaomi_auth(xiaomi_prefix, new_token_data,
                                            xiaomi_account=user.username,
                                            custom_base=getattr(self.config_mgr, 'custom_data_dir', None))
                        logger.info(f"用户 {xiaomi_prefix} 的 Token 已刷新")

                except Exception as e:
                    yield SyncProgress(
                        stage="error",
                        current=0,
                        total=100,
                        message=f"❌ 小米登录失败: {str(e)}",
                        timestamp=datetime.datetime.now().strftime("%H:%M:%S"),
                        username=username
                    )
                    return

            # 获取体重数据
            yield SyncProgress(
                stage="fetching",
                current=30,
                total=100,
                message="📊 正在获取小米体脂秤数据...",
                timestamp=datetime.datetime.now().strftime("%H:%M:%S"),
                username=username
            )

            weights = []
            try:
                # 双源合并：旧 API 优先（实时），新 API 按时间戳补充（Zeeplife 导入数据）
                weights, legacy_count, supplement_count = fetch_merged_weights(
                    xiaomi_client, user.model)

                if not weights:
                    yield SyncProgress(
                        stage="error",
                        current=0,
                        total=100,
                        message="❌ 未获取到任何小米体脂秤数据",
                        timestamp=datetime.datetime.now().strftime("%H:%M:%S"),
                        username=username
                    )
                    return

            except Exception as e:
                yield SyncProgress(
                    stage="error",
                    current=0,
                    total=100,
                    message=f"❌ 获取体重数据失败: {str(e)}",
                    timestamp=datetime.datetime.now().strftime("%H:%M:%S"),
                    username=username
                )
                return

            yield SyncProgress(
                stage="fetching",
                current=40,
                total=100,
                message=f"✅ 成功获取 {len(weights)} 条小米体脂秤数据（旧 API {legacy_count} + 新 API 补充 {supplement_count}）",
                timestamp=datetime.datetime.now().strftime("%H:%M:%S"),
                username=username,
                details={"total_weights": len(weights)}
            )

            # 落盘小米体脂秤数据（与 CLI 一致：body_data_<prefix>.json，尊重自定义数据目录）
            try:
                custom_base = getattr(self.config_mgr, 'custom_data_dir', None)
                data_dir = Path(custom_base) if custom_base else get_app_data_dir()
                body_data_path = data_dir / 'body' / f"body_data_{xiaomi_prefix}.json"
                body_data_path.parent.mkdir(parents=True, exist_ok=True)
                with open(body_data_path, 'w', encoding='utf-8') as f:
                    json.dump(weights, f, indent=2, ensure_ascii=False)
                logger.info(f"小米体脂秤数据已保存: {body_data_path}")
            except Exception as e:
                logger.warning(f"小米体脂秤数据落盘失败（不影响同步）: {e}")

            # 检查是否有 Garmin 配置
            if not user.garmin or not user.garmin.email:
                yield SyncProgress(
                    stage="error",
                    current=0,
                    total=100,
                    message="❌ 未配置 Garmin 账号信息",
                    timestamp=datetime.datetime.now().strftime("%H:%M:%S"),
                    username=username
                )
                return

            # 阶段 2: 生成 FIT 文件并分块
            yield SyncProgress(
                stage="generating",
                current=50,
                total=100,
                message="📝 正在生成 FIT 文件...",
                timestamp=datetime.datetime.now().strftime("%H:%M:%S"),
                username=username
            )

            # 分块处理
            weight_chunks = [weights[i:i+chunk_size]
                            for i in range(0, len(weights), chunk_size)]
            total_chunks = len(weight_chunks)

            yield SyncProgress(
                stage="generating",
                current=55,
                total=100,
                message=f"📦 数据将分为 {total_chunks} 个批次处理",
                timestamp=datetime.datetime.now().strftime("%H:%M:%S"),
                username=username,
                details={"total_chunks": total_chunks}
            )

            # 创建输出目录（使用可写路径）
            output_dir = get_output_dir(
                custom_base=getattr(self.config_mgr, 'custom_data_dir', None)
            )
            timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')

            # 阶段 3: 登录 Garmin
            yield SyncProgress(
                stage="uploading",
                current=60,
                total=100,
                message="🏃 正在登录 Garmin...",
                timestamp=datetime.datetime.now().strftime("%H:%M:%S"),
                username=username
            )

            # 获取可写的会话基础目录（修复打包后的只读文件系统问题）
            # GarminClient 会在其下按 session_name（脱敏 prefix）建子目录：auth/garmin/<prefix>/
            session_dir = get_garmin_auth_dir(
                custom_base=getattr(self.config_mgr, 'custom_data_dir', None)
            )

            # 决策 4：佳明密码惰性获取（仅会话失效时触发）
            # GUI 模式走 input_callback 弹窗，CLI 模式走 getpass
            def _garmin_password_provider():
                if input_callback:
                    pw_result = input_callback({
                        "action": "garmin_password",
                        "username": username,
                        "email": user.garmin.email
                    })
                    return pw_result.get("password", "")
                from core.bootstrap import prompt_password
                return prompt_password("佳明密码")

            garmin_client = GarminClient(
                email=user.garmin.email,
                password_provider=_garmin_password_provider,
                auth_domain=user.garmin.domain,
                session_dir=str(session_dir),  # 关键：传入可写路径
                session_name=garmin_prefix
            )

            # 登录 Garmin - 根据是否有 input_callback 选择登录方法
            if input_callback:
                # UI 模式：使用 login_for_ui，支持 MFA 对话框
                yield SyncProgress(
                    stage="uploading",
                    current=60,
                    total=100,
                    message="🏃 正在登录 Garmin（如启用了两步验证，请输入验证码）...",
                    timestamp=datetime.datetime.now().strftime("%H:%M:%S"),
                    username=username
                )

                # 通过 input_callback 获取 MFA 验证码
                def get_mfa_code():
                    logger.info(f"[DEBUG] get_mfa_code 被调用，正在请求用户输入...")
                    mfa_result = input_callback({
                        "action": "garmin_mfa",
                        "username": username,
                        "email": user.garmin.email
                    })
                    logger.info(f"[DEBUG] 收到 MFA 结果: {mfa_result}")
                    return mfa_result.get("mfa_code", "")

                login_success = garmin_client.login_for_ui(get_mfa_code)
            else:
                # CLI 模式：使用原有 login 方法
                login_success = garmin_client.login()

            if not login_success:
                yield SyncProgress(
                    stage="error",
                    current=0,
                    total=100,
                    message="❌ Garmin 登录失败",
                    timestamp=datetime.datetime.now().strftime("%H:%M:%S"),
                    username=username
                )
                return

            # 上传结果统计
            upload_results = {
                'success': 0,
                'failed': 0,
                'duplicate': 0,
                'failed_chunks': []
            }

            # 阶段 4: 逐个处理和上传
            for idx, chunk in enumerate(weight_chunks, 1):
                if self._should_stop:
                    yield SyncProgress(
                        stage="stopped",
                        current=0,
                        total=100,
                        message="⏸️ 同步已停止",
                        timestamp=datetime.datetime.now().strftime("%H:%M:%S"),
                        username=username
                    )
                    return

                chunk_filename = output_dir / f"body_{xiaomi_prefix}_{timestamp}_{idx}.fit"

                yield SyncProgress(
                    stage="generating",
                    current=60 + (idx * 30 // total_chunks),
                    total=100,
                    message=f"📝 生成 FIT 文件: 批次 {idx}/{total_chunks}",
                    timestamp=datetime.datetime.now().strftime("%H:%M:%S"),
                    username=username,
                    details={
                        "chunk": idx,
                        "total_chunks": total_chunks,
                        "records": len(chunk),
                        "filename": str(chunk_filename)
                    }
                )

                # 生成 FIT 文件
                filter_config = user.garmin.filter if user.garmin else None
                created_path = create_weight_fit_file(
                    chunk,
                    chunk_filename,
                    filter_config=filter_config
                )

                if not created_path:
                    upload_results['failed'] += 1
                    upload_results['failed_chunks'].append({
                        'chunk': idx,
                        'filename': str(chunk_filename),
                        'error': 'Failed to generate FIT file',
                        'records': len(chunk)
                    })
                    continue

                # 上传到 Garmin
                yield SyncProgress(
                    stage="uploading",
                    current=60 + (idx * 30 // total_chunks),
                    total=100,
                    message=f"⬆️ 上传批次 {idx}/{total_chunks} 到 Garmin...",
                    timestamp=datetime.datetime.now().strftime("%H:%M:%S"),
                    username=username,
                    details={"chunk": idx, "total_chunks": total_chunks}
                )

                status = garmin_client.upload_fit(chunk_filename)

                if status == "SUCCESS":
                    upload_results['success'] += 1
                    yield SyncProgress(
                        stage="uploading",
                        current=60 + ((idx + 1) * 30 // total_chunks),
                        total=100,
                        message=f"✅ 批次 {idx}/{total_chunks} 上传成功",
                        timestamp=datetime.datetime.now().strftime("%H:%M:%S"),
                        username=username,
                        details={"chunk": idx, "status": status}
                    )
                elif status == "DUPLICATE":
                    upload_results['duplicate'] += 1
                    yield SyncProgress(
                        stage="uploading",
                        current=60 + ((idx + 1) * 30 // total_chunks),
                        total=100,
                        message=f"ℹ️ 批次 {idx}/{total_chunks} 数据已存在",
                        timestamp=datetime.datetime.now().strftime("%H:%M:%S"),
                        username=username,
                        details={"chunk": idx, "status": status}
                    )
                else:
                    upload_results['failed'] += 1
                    upload_results['failed_chunks'].append({
                        'chunk': idx,
                        'filename': str(chunk_filename),
                        'error': status,
                        'records': len(chunk)
                    })
                    yield SyncProgress(
                        stage="uploading",
                        current=60 + ((idx + 1) * 30 // total_chunks),
                        total=100,
                        message=f"❌ 批次 {idx}/{total_chunks} 上传失败: {status}",
                        timestamp=datetime.datetime.now().strftime("%H:%M:%S"),
                        username=username,
                        details={"chunk": idx, "status": status}
                    )

            # 完成
            self.config_mgr.update_last_sync(username)

            if upload_results['failed'] == 0:
                yield SyncProgress(
                    stage="completed",
                    current=100,
                    total=100,
                    message=f"✅ 同步完成！成功 {upload_results['success']} 个批次",
                    timestamp=datetime.datetime.now().strftime("%H:%M:%S"),
                    username=username,
                    details=upload_results
                )
            else:
                yield SyncProgress(
                    stage="completed",
                    current=100,
                    total=100,
                    message=f"⚠️ 同步完成，但有 {upload_results['failed']} 个批次失败",
                    timestamp=datetime.datetime.now().strftime("%H:%M:%S"),
                    username=username,
                    details=upload_results
                )

        except Exception as e:
            logger.exception(f"同步失败: {e}")
            yield SyncProgress(
                stage="error",
                current=0,
                total=100,
                message=f"❌ 同步失败: {str(e)}",
                timestamp=datetime.datetime.now().strftime("%H:%M:%S"),
                username=username
            )

    def stop_sync(self):
        """停止同步"""
        self._should_stop = True
        logger.info("已设置停止标志")
