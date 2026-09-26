"""
路径工具函数
处理打包后的应用路径问题
"""
import json
import logging
import os
import stat
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def get_app_data_dir() -> Path:
    """
    获取应用数据目录（可写）

    在开发环境：返回项目根目录的 data 文件夹
    在打包后：
      - macOS: ~/Library/Application Support/mi-scale-to-garmin
      - Windows: %APPDATA%/mi-scale-to-garmin
      - Linux: ~/.local/share/mi-scale-to-garmin

    Returns:
        Path: 可写的应用数据目录
    """
    # 检测是否在打包环境中运行
    if getattr(sys, 'frozen', False):
        # 打包后的应用
        if sys.platform == 'darwin':
            # macOS
            app_data = Path.home() / 'Library' / 'Application Support' / 'mi-scale-to-garmin'
        elif sys.platform == 'win32':
            # Windows
            app_data = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming')) / 'mi-scale-to-garmin'
        else:
            # Linux
            app_data = Path.home() / '.local' / 'share' / 'mi-scale-to-garmin'
    else:
        # 开发环境：使用项目根目录的 data 文件夹
        # 获取项目根目录（src 的父目录）
        project_root = Path(__file__).parent.parent.parent
        app_data = project_root / 'data'

    # 确保目录存在
    app_data.mkdir(parents=True, exist_ok=True)

    return app_data


def get_garmin_auth_dir(custom_base: str = None) -> Path:
    """
    获取 Garmin 会话基础目录（auth/garmin/）

    具体会话子目录由 GarminClient 按 session_name（脱敏 prefix）拼接，
    最终路径：auth/garmin/<prefix>/（CLI/GUI 一致，不含 email）

    Args:
        custom_base: 自定义基础路径（可选）

    Returns:
        Path: 会话基础目录
    """
    if custom_base:
        # 使用自定义路径
        base_path = Path(custom_base)
    else:
        # 使用默认的应用数据目录
        base_path = get_app_data_dir()

    session_dir = base_path / 'auth' / 'garmin'
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def get_output_dir(custom_base: str = None) -> Path:
    """
    获取输出目录（用于 FIT 文件等）

    Args:
        custom_base: 自定义基础路径（可选）

    Returns:
        Path: 输出目录路径
    """
    if custom_base:
        # 使用自定义路径
        base_path = Path(custom_base)
    else:
        # 使用默认的应用数据目录
        base_path = get_app_data_dir()

    output_dir = base_path / 'fit'
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def get_config_dir() -> Path:
    """
    获取配置目录

    在打包后的应用中，配置文件应该在可执行文件所在目录

    Returns:
        Path: 配置目录路径
    """
    if getattr(sys, 'frozen', False):
        # 打包后的应用：使用可执行文件所在目录
        if sys.platform == 'darwin':
            # macOS .app 包
            # 可执行文件在 .app/Contents/MacOS/
            # 配置文件应该和 .app 在同一目录
            exe_path = Path(sys.executable)
            app_bundle = exe_path.parent.parent
            config_dir = app_bundle.parent
        else:
            # Windows/Linux：使用可执行文件所在目录
            config_dir = Path(sys.executable).parent
    else:
        # 开发环境：使用项目根目录
        config_dir = Path(__file__).parent.parent.parent

    return config_dir


def get_default_config_path() -> Path:
    """
    获取默认 users.json 配置路径

    - 开发环境：项目根 users.json
    - 打包后：数据目录下的 users.json（与 token 同处，免疫打包目录清理）

    Returns:
        Path: 默认配置路径
    """
    if not getattr(sys, 'frozen', False):
        return get_config_dir() / 'users.json'
    return get_app_data_dir() / 'users.json'


def harden_file_permissions(path) -> bool:
    """
    加固敏感文件权限：仅当前用户可读写（参考 garmin-connect-plugin-for-dsh 的 0o600 做法）

    - POSIX: chmod 0o600
    - Windows: icacls 移除继承权限并仅保留当前用户 Full

    失败不抛异常（权限加固是尽力而为，不应阻断主流程）。

    Args:
        path: 文件或目录路径

    Returns:
        bool: 是否加固成功
    """
    p = Path(path)
    if not p.exists():
        return False
    try:
        if os.name == 'posix':
            os.chmod(p, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
            return True
        # Windows：icacls 移除继承，仅保留当前用户完全控制
        # 注意：必须用 (F) 而非 (R,W)——(R,W) 不含删除权限，会导致文件无法移动/删除
        username = os.environ.get("USERNAME", "")
        result = subprocess.run(
            ['icacls', str(p), '/inheritance:r', '/grant:r', f'{username}:(F)'],
            capture_output=True, text=True, timeout=15
        )
        return result.returncode == 0
    except Exception as e:
        logger.debug(f"权限加固失败（忽略）: {p}: {e}")
        return False


def get_captcha_dir() -> Path:
    """
    获取验证码图片目录（<数据目录>/captcha/）

    Returns:
        Path: 验证码目录（自动创建）
    """
    captcha_dir = get_app_data_dir() / 'captcha'
    captcha_dir.mkdir(parents=True, exist_ok=True)
    return captcha_dir


def get_xiaomi_auth_path(xiaomi_prefix: str, custom_base: str = None) -> Path:
    """
    获取小米 token 会话文件路径（不含 token 的 users.json 之外的独立存储）

    文件内容: {"userId": ..., "passToken": ..., "ssecurity": ...}

    Args:
        xiaomi_prefix: 脱敏前缀（用于文件名，避免暴露手机号）
        custom_base: 自定义基础路径（可选）

    Returns:
        Path: 会话文件路径（不创建文件）
    """
    if custom_base:
        base_path = Path(custom_base)
    else:
        base_path = get_app_data_dir()
    return base_path / 'auth' / f'xiaomi_auth_{xiaomi_prefix}.json'


def harden_garmin_session_dir(session_dir) -> bool:
    """
    加固 garth 会话目录（auth/garmin/{email}/）：目录本身 + 内部 token 文件

    Args:
        session_dir: garth 会话目录

    Returns:
        bool: 是否全部加固成功
    """
    d = Path(session_dir)
    if not d.exists():
        return False
    ok = harden_file_permissions(d)
    for f in d.iterdir():
        if f.is_file():
            ok = harden_file_permissions(f) and ok
    return ok
