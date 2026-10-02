"""
跨平台设备标识获取

返回 32 字节 device_key（SHA-256 of 系统级设备标识）。
设备标识只在内存中短暂存在，不落盘、不上传、不进日志。
"""
import hashlib
import platform
import subprocess
from typing import Optional


def get_device_key() -> bytes:
    """返回 32 字节设备密钥（SHA-256 of raw device identifier）"""
    raw = _get_raw_id()
    return hashlib.sha256(raw.encode('utf-8')).digest()


def _get_raw_id() -> str:
    """获取系统级设备标识原始值"""
    system = platform.system()
    if system == 'Windows':
        return _windows_machine_guid()
    elif system == 'Darwin':
        return _macos_platform_uuid()
    elif system == 'Linux':
        return _linux_machine_id()
    else:
        # 兜底：hostname + MAC（不稳定但总比没有强）
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
