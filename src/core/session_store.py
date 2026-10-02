"""
小米 token 会话存储

token 三件套（userId/passToken/ssecurity）独立于 users.json 存储：
- users.json 只留身份（无密码、无 token），可安全备份/分享
- token 存 data/auth/xiaomi_auth_{xiaomi_prefix}.json（已 gitignore + 权限加固）
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from utils.paths import get_xiaomi_auth_path, harden_file_permissions
from utils.token_crypto import load_token_file, save_token_file, is_encrypted
from core.account import account_hash

logger = logging.getLogger(__name__)


class SessionAccountMismatchError(Exception):
    """会话文件的账号哈希与当前账号不匹配（可能被改名/换内容错配）"""
    pass


def load_xiaomi_auth(xiaomi_prefix: str, xiaomi_account: str = "",
                        custom_base: str = None) -> Optional[Dict[str, str]]:
    """
    读取小米 token 会话文件（含账号哈希绑定校验，A）

    Args:
        xiaomi_prefix: 脱敏前缀（决定文件名）
        xiaomi_account: 真实账号（用于哈希绑定校验；为空则跳过校验）
        custom_base: 自定义基础路径（可选）

    Returns:
        {"userId": ..., "passToken": ..., "ssecurity": ...} 或 None（不存在/无效）

    Raises:
        SessionAccountMismatchError: 账号哈希不匹配（拒绝使用，需重新认证）
    """
    path = get_xiaomi_auth_path(xiaomi_prefix, custom_base)
    if not path.exists():
        return None
    try:
        # 自动识别明文/加密格式；加密格式设备不匹配时返回 None
        data = load_token_file(path)
        if data is None:
            logger.info(f"小米会话文件 {path.name} 无效或设备不匹配，需重新认证")
            return None
        if not (data.get("userId") and data.get("passToken")):
            logger.warning(f"小米会话文件缺少关键字段: {path.name}")
            return None
        # A：账号哈希绑定校验（旧文件无 account_hash 字段时跳过，兼容迁移）
        saved_hash = data.get("account_hash")
        if saved_hash and xiaomi_account:
            if saved_hash != account_hash(xiaomi_account):
                raise SessionAccountMismatchError(
                    f"小米会话文件 {path.name} 的账号绑定与当前账号不匹配，请重新认证")
        return data
    except SessionAccountMismatchError:
        raise
    except Exception as e:
        logger.warning(f"读取小米会话文件失败: {path.name}: {e}")
        return None


def save_xiaomi_auth(xiaomi_prefix: str, token_data: Dict[str, Any],
                        xiaomi_account: str = "",
                        custom_base: str = None) -> Path:
    """
    写入小米 token 会话文件（含账号哈希绑定，A）并加固权限

    Args:
        xiaomi_prefix: 脱敏前缀
        token_data: {"userId": ..., "passToken": ..., "ssecurity": ...}
        xiaomi_account: 真实账号（写入 account_hash 绑定；为空则不写）
        custom_base: 自定义基础路径（可选）

    Returns:
        Path: 写入的文件路径
    """
    path = get_xiaomi_auth_path(xiaomi_prefix, custom_base)
    payload = {
        "userId": token_data.get("userId", ""),
        "passToken": token_data.get("passToken", ""),
        "ssecurity": token_data.get("ssecurity", ""),
    }
    if xiaomi_account:
        payload["account_hash"] = account_hash(xiaomi_account)
    # 加密落盘（v=1 格式）
    save_token_file(path, payload)
    if harden_file_permissions(path):
        logger.debug(f"小米会话文件权限已加固: {path.name}")
    return path


def save_garmin_session_binding(session_dir, garmin_account: str) -> Path:
    """
    在 garth 会话目录内写入账号绑定文件（A，佳明侧）

    garth 自己管理 oauth1/oauth2 token 文件，我们不碰；
    绑定信息单独存 account.json，加载会话时校验。

    Args:
        session_dir: garth 会话目录（data/auth/garmin/{email}/）
        garmin_account: 佳明邮箱

    Returns:
        Path: 绑定文件路径
    """
    d = Path(session_dir)
    d.mkdir(parents=True, exist_ok=True)
    binding_file = d / "account.json"
    payload = {"account_hash": account_hash(garmin_account)}
    with open(binding_file, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=4, ensure_ascii=False)
    harden_file_permissions(binding_file)
    return binding_file


def verify_garmin_session_binding(session_dir, garmin_account: str) -> bool:
    """
    校验 garth 会话目录的账号绑定（A，佳明侧）

    绑定文件不存在（旧会话）→ 返回 True（兼容，下次登录时补写）
    绑定存在但不匹配 → 返回 False（拒绝使用该会话）
    """
    binding_file = Path(session_dir) / "account.json"
    if not binding_file.exists():
        return True
    try:
        with open(binding_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        saved_hash = data.get("account_hash", "")
        if not saved_hash:
            return True
        return saved_hash == account_hash(garmin_account)
    except Exception as e:
        logger.warning(f"读取佳明会话绑定文件失败: {e}")
        return False


def migrate_token_from_users_json(config_mgr, user: Dict[str, Any],
                                  xiaomi_prefix: str,
                                  custom_base: str = None) -> bool:
    """
    一次性迁移：旧版 users.json 内嵌的 token 字段 → 独立会话文件

    迁移成功后从 users.json 中移除 token 字段（users.json 变为无密文件）。

    Args:
        config_mgr: xiaomi.config.ConfigManager 实例
        user: users.json 中的用户字典（原地修改）
        xiaomi_prefix: 脱敏前缀
        custom_base: 自定义数据目录（可选）

    Returns:
        bool: 是否执行了迁移
    """
    token = user.get("token")
    if not token or not (token.get("userId") and token.get("passToken")):
        return False
    save_xiaomi_auth(xiaomi_prefix, token,
                        xiaomi_account=user.get("username", ""),
                        custom_base=custom_base)
    user.pop("token", None)
    # 决策 1：users.json 变为无密文件——顺带清除密码字段
    #（认证优化后已无任何代码从 users.json 读取密码）
    user.pop("password", None)
    garmin = user.get("garmin")
    if isinstance(garmin, dict):
        garmin.pop("password", None)
    # 写回 users.json，兼容两种 ConfigManager：
    # - core.config_manager.EnhancedConfigManager：get_users() 返回副本，
    #   必须经 update_user() 写回内部数据
    # - xiaomi.config.ConfigManager：get_users() 返回内部 dict 本身，save_config() 即可
    update_user = getattr(config_mgr, "update_user", None)
    if update_user is not None:
        from core.models import UserModel
        update_user(UserModel.from_dict(user))
    else:
        saver = getattr(config_mgr, "save_config", None)
        if saver is not None:
            saver()
    logger.info(f"已将 {xiaomi_prefix} 的小米 token 从 users.json 迁移到独立会话文件")
    return True
