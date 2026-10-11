"""
跨平台设备标识获取（三级回退链）

返回 32 字节 device_key（SHA-256 of 设备标识）。
回退链：系统级标识 → 本地持久化 UUID → hostname+MAC（最后兜底）。
保证 get_device_key() 永远返回 32 字节，不抛异常。
"""
import hashlib
import logging
import platform
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


def get_device_key() -> bytes:
    """返回 32 字节设备密钥（SHA-256 of raw device identifier）

    三级回退：
    1. 系统级标识（MachineGuid / IOPlatformUUID / machine-id）
    2. 本地持久化 UUID（data/.device_id，首次生成后复用）
    3. hostname + MAC（最后兜底，不稳定但不崩溃）
    """
    raw = _try_system_id()
    if raw is None:
        raw = _try_persisted_id()
    if raw is None:
        raw = _fallback_id()
    return hashlib.sha256(raw.encode('utf-8')).digest()


def _try_system_id() -> Optional[str]:
    """第 1 级：尝试获取系统级设备标识，失败返回 None"""
    system = platform.system()
    try:
        if system == 'Windows':
            return _windows_machine_guid()
        elif system == 'Darwin':
            return _macos_platform_uuid()
        elif system == 'Linux':
            return _linux_machine_id()
    except Exception as e:
        logger.debug("系统级设备标识获取失败 (%s): %s", system, e)
    return None


def _try_persisted_id() -> Optional[str]:
    """第 2 级：本地持久化 UUID（data/.device_id）

    系统标识不可用时，用本地持久化 UUID 兜底。
    首次生成后持久化，后续复用（只要 data/ 目录在，UUID 就在）。
    UUID 本身不是密钥（跟 salt 一样公开无所谓），安全性靠 SHA-256 后的 device_key。
    """
    try:
        from utils.paths import get_app_data_dir
        id_file = get_app_data_dir() / '.device_id'
        if id_file.exists():
            content = id_file.read_text(encoding='utf-8').strip()
            if content:
                return content
        # 首次：生成随机 UUID 并持久化
        import uuid
        new_id = str(uuid.uuid4())
        id_file.parent.mkdir(parents=True, exist_ok=True)
        id_file.write_text(new_id, encoding='utf-8')
        logger.info("已生成持久化设备标识: %s", id_file)
        return new_id
    except Exception as e:
        logger.debug("持久化设备标识获取失败: %s", e)
        return None


def _fallback_id() -> str:
    """第 3 级：hostname + MAC（最后兜底，不稳定但总比崩溃强）"""
    import uuid
    return f"{platform.node()}-{uuid.getnode():012x}"


def _windows_machine_guid() -> str:
    """Windows: HKLM\\SOFTWARE\\Microsoft\\Cryptography\\MachineGuid"""
    import winreg
    key = winreg.OpenKey(
        winreg.HKEY_LOCAL_MACHINE,
        r'SOFTWARE\Microsoft\Cryptography'
    )
    try:
        guid, _ = winreg.QueryValueEx(key, 'MachineGuid')
        return guid
    finally:
        winreg.CloseKey(key)


def _macos_platform_uuid() -> str:
    """macOS: IOPlatformUUID（ioreg）"""
    out = subprocess.check_output(
        ['ioreg', '-rd1', '-c', 'IOPlatformExpertDevice'],
        text=True, stderr=subprocess.DEVNULL
    )
    for line in out.splitlines():
        if 'IOPlatformUUID' in line:
            # 格式: "IOPlatformUUID" = "XXXX-XXXX-XXXX-XXXX-XXXX"
            parts = line.split('"')
            if len(parts) >= 4:
                return parts[3]
    raise RuntimeError("IOPlatformUUID not found in ioreg output")


def _linux_machine_id() -> str:
    """Linux: /etc/machine-id"""
    try:
        with open('/etc/machine-id', 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        # 回退：/var/lib/dbus/machine-id
        with open('/var/lib/dbus/machine-id', 'r') as f:
            return f.read().strip()
