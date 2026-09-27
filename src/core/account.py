"""
账号标识工具（参考 garmin-connect-plugin-for-dsh 的 usernameHash 设计）

- A（账号哈希绑定）：会话文件内存账号 SHA256 哈希，加载时校验，
  防止会话文件被改名/换内容后错配到其他账号
- B（前缀缺省哈希）：未配置脱敏前缀时，文件名/目录名回退到
  账号 SHA256 前 8 位（而非明文账号），堵住明文泄露点
"""
import hashlib
from typing import Optional


def account_hash(account: str) -> str:
    """账号的 SHA256 哈希（规范化：去首尾空白 + 小写）"""
    # 规范化保证同一账号不同写法（大小写/空格）哈希一致，
    # 否则绑定校验（A）会因写法差异误判为"账号不匹配"
    return hashlib.sha256(
        (account or "").strip().lower().encode("utf-8")).hexdigest()


def short_account_hash(account: str) -> str:
    """账号 SHA256 前 8 位，用作缺省脱敏前缀（可读性弱但无泄露）"""
    # 取前 8 位（32 bit）：文件名长度够用，碰撞概率对个人单账号场景可忽略
    return account_hash(account)[:8]


def resolve_prefix(prefix: Optional[str], account: str) -> str:
    """
    解析脱敏前缀：配置了用配置，未配置回退到账号短哈希（B）

    Args:
        prefix: 用户配置的脱敏前缀（xiaomi_prefix / garmin_prefix）
        account: 真实账号（手机号/邮箱）

    Returns:
        str: 用于文件名/目录名的脱敏标识
    """
    # 用户显式配置的前缀优先（如 "sun_xiaomi"，可读性好）
    if prefix:
        return prefix
    # 未配置 → 短哈希兜底（B）：永不回退明文账号（铁律 3）
    return short_account_hash(account)


def mask_account(account: str) -> str:
    """
    账号脱敏显示（GUI 列表/日志/对话框用，铁律 3）

    - 11 位手机号：138****1234
    - 邮箱：s***@example.com（保留域名，便于区分多账号）
    - 其他：长度 >4 时首 2 尾 2（ab****yz），否则全掩码
    """
    a = (account or "").strip()
    if not a:
        return ""
    if a.isdigit() and len(a) == 11:
        return f"{a[:3]}****{a[-4:]}"
    if "@" in a:
        name, _, domain = a.partition("@")
        return f"{name[:1]}***@{domain}" if name else f"***@{domain}"
    if len(a) > 4:
        return f"{a[:2]}****{a[-2:]}"
    return "****"
