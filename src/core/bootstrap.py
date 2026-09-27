"""
引导式初始化（决策 6）+ 密码输入（决策 4）+ 非交互保护

启动判定流程 ①→④：
  ① users.json 不存在 → 提示进入引导配置
  ② 身份字段为空 → 只问空的字段，输入后写回 users.json（持久化）
  ③ token 缺失/失效 → getpass 输入密码（不持久化）
  ④ 全部就绪 → 直接同步（零交互）

非交互保护：stdin 非 TTY（计划任务/CI）时 ②③ 不弹提示，
直接抛 NonInteractiveError 报错退出，避免卡死在等待输入。
"""
import getpass
import logging
import sys
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_interactive_override: Optional[bool] = None

# 占位符值：模板/示例中的假值，视为"未配置"，启动时引导用户输入真实值
_PLACEHOLDER_VALUES = {
    "your_xiaomi_username", "your_xiaomi_password",
    "your_garmin_email", "your_garmin_password",
    "填手机号", "填邮箱", "填密码",
    "your_xiaomi_username", "your_garmin_email",
}


def _is_placeholder(value) -> bool:
    """判断值是否为占位符/示例假值（视为未配置）"""
    if not value:
        return True
    s = str(value).strip().lower()
    return s in _PLACEHOLDER_VALUES or s.startswith("your_")


class NonInteractiveError(Exception):
    """非交互环境下需要用户输入（身份/密码）时抛出，调用方应报错退出"""
    pass


def set_interactive_override(value: Optional[bool]):
    """显式覆盖交互检测（如 --non-interactive 参数）"""
    global _interactive_override
    _interactive_override = value


def is_interactive() -> bool:
    """检测是否运行在交互终端（计划任务/CI 的 stdin 非 TTY）"""
    if _interactive_override is not None:
        return _interactive_override
    try:
        return sys.stdin is not None and sys.stdin.isatty()
    except Exception:
        return False


def _require_interactive(what: str):
    """非交互环境下需要输入时抛错（不等待，避免卡死计划任务）"""
    if not is_interactive():
        raise NonInteractiveError(
            f"需要输入{what}，但当前为非交互环境（计划任务/CI）。"
            f"请先在终端手动运行一次完成认证，例如：python src/main.py --sync")


def _prompt(label: str, default: str = "", secret: bool = False) -> str:
    """终端提示输入；secret=True 用 getpass 隐藏输入"""
    suffix = f"（回车默认: {default}）" if default else ""
    if secret:
        value = getpass.getpass(f"{label}{suffix}: ")
    else:
        value = input(f"{label}{suffix}: ").strip()
    return value or default


def ensure_identity(user: Dict[str, Any], config_mgr,
                    interactive: Optional[bool] = None) -> Dict[str, Any]:
    """
    ② 身份字段完整性检查 + 引导式输入（只问空的，已填的跳过）

    检查字段：username、garmin.email、garmin.domain、
              xiaomi_prefix（可选，默认回退短哈希）、garmin_prefix（可选）

    输入后写回 users.json（一次性，下次不再问）。

    Args:
        user: users.json 中的用户字典（原地修改）
        config_mgr: xiaomi.config.ConfigManager 实例
        interactive: 是否交互（None=自动检测 stdin TTY）

    Returns:
        更新后的用户字典

    Raises:
        NonInteractiveError: 非交互环境下存在空字段
    """
    if interactive is None:
        interactive = is_interactive()

    missing = []
    if _is_placeholder(user.get("username")):
        missing.append("username")
    garmin = user.get("garmin") or {}
    if _is_placeholder(garmin.get("email")):
        missing.append("garmin.email")

    if not missing:
        return user

    if not interactive:
        raise NonInteractiveError(
            f"users.json 缺少身份字段: {', '.join(missing)}。"
            f"请先在终端手动运行一次完成配置。")

    # 注意：不用 emoji（GBK 控制台无法编码 U+1F4DD 等会崩溃）
    print("\n" + "=" * 60)
    print("[引导配置] 以下字段未填写，请输入（输入后写入 users.json）")
    print("=" * 60)

    if "username" in missing:
        user["username"] = _prompt("小米账号（手机号/邮箱）")
        while not user["username"]:
            user["username"] = _prompt("小米账号（手机号/邮箱，必填）")

    if "garmin.email" in missing:
        user.setdefault("garmin", {})
        user["garmin"]["email"] = _prompt("佳明邮箱")
        while not user["garmin"]["email"]:
            user["garmin"]["email"] = _prompt("佳明邮箱（必填）")
        if not user["garmin"].get("domain"):
            user["garmin"]["domain"] = _prompt(
                "佳明服务器区域（CN/COM）", default="CN") or "CN"

    # 昵称（可选，这一组（小米+佳明）的显示名，纯显示用）
    if not user.get("nickname"):
        nickname = _prompt("昵称（可选，这一组的显示名，如 我/老婆）")
        if len(nickname) > 20:
            print("[WARN] 昵称超过 20 字符，已忽略")
            nickname = ""
        if nickname:
            # 昵称查重（输入时拦截）
            from core.account import find_duplicate_nickname
            existing = config_mgr.get_users()
            if find_duplicate_nickname(nickname, existing):
                print(f"[WARN] 昵称 \"{nickname}\" 已被其他用户使用，已忽略")
                nickname = ""
        user["nickname"] = nickname

    # 可选前缀：留空自动用昵称（创建那一刻固化）；无昵称则留空走账号哈希
    # （修复：旧默认值写死 xiaomi/garmin，多用户都按回车会共用同一 token 文件）
    if not user.get("xiaomi_prefix"):
        user["xiaomi_prefix"] = _prompt(
            "小米脱敏前缀（可选，用于文件名，留空自动用昵称）",
            default=user.get("nickname") or "")
    if not user.get("garmin_prefix"):
        user["garmin_prefix"] = _prompt(
            "佳明脱敏前缀（可选，用于会话目录，留空自动用昵称）",
            default=user.get("nickname") or "")

    config_mgr.save_config()
    print("[完成] 配置已写入 users.json（下次启动不再询问）\n")
    return user


def prompt_password(label: str, interactive: Optional[bool] = None) -> str:
    """
    ③ 密码输入（getpass 隐藏，仅内存中使用，不落盘）

    Args:
        label: 提示标签（如"小米密码"）
        interactive: 是否交互（None=自动检测）

    Returns:
        密码字符串

    Raises:
        NonInteractiveError: 非交互环境
    """
    if interactive is None:
        interactive = is_interactive()
    _require_interactive(f"（{label}）")
    password = _prompt(label, secret=True)
    while not password:
        password = _prompt(f"{label}（必填）", secret=True)
    return password
