"""
PyInstaller 打包脚本
用于将 mi-scale-to-garmin 打包成独立可执行文件
"""
import PyInstaller.__main__
import os
import sys
from pathlib import Path

# 项目根目录（packaging/ 的上一级）：构建参数中的相对路径（src/、dist/ 等）均以此为基准
PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Runtime hook 与本脚本同目录，用绝对路径引用，从任何工作目录调用都不会断
RUNTIME_HOOK = str(Path(__file__).resolve().parent / 'pyi_rth_inspect.py')
# PyInstaller 中间产物（workpath）与 spec 文件（specpath）统一落 .pyinstaller/（gitignore，可再生）
WORKPATH = '.pyinstaller'
SPEC_PATH = '.pyinstaller/spec'
# 注意：--add-data 源路径、入口脚本、--icon 会被 PyInstaller 相对 spec 文件所在目录解析，
# 因此必须用绝对路径（spec 已不在项目根）
SRC_DIR = str(PROJECT_ROOT / 'src')


def _distpath(release: bool = False) -> str:
    """
    产物输出目录：dist/<dev|release>/<platform>/

    - dev：本地开发验证产物（默认）
    - release：发布候选产物（--release）
    - platform：windows / linux / darwin（自动检测，PyInstaller 不支持交叉编译）
    """
    stage = 'release' if release else 'dev'
    # sys.platform 归一化：win32→windows，darwin→macos，linux 不变
    platform = {'win32': 'windows', 'darwin': 'macos'}.get(sys.platform, sys.platform)
    return f'dist/{stage}/{platform}'


def build_gui(release: bool = False):
    """打包 GUI 版本"""
    print("=" * 60)
    print("开始打包 GUI 版本...")
    print("=" * 60)

    # 精简的隐藏导入列表（优化启动速度）
    hidden_imports = [
        # PyQt6
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        # 自定义模块
        'garmin',
        'xiaomi',
        'core',
        'core.models',
        'core.config_manager',
        'core.sync_service',
        # pkg_resources 核心依赖（精简后）
        'jaraco.collections',
        'jaraco.functools',
        'importlib_metadata',
        'pkg_resources',
        'packaging',
    ]

    args = [
        '--name=mi-scale-to-garmin-gui',
        '--windowed',  # 无控制台窗口
        '--onedir',    # 打包成目录（启动更快）
        '--clean',     # 清理缓存
        '--noconfirm', # 不询问确认
        f'--distpath={_distpath(release)}',
        f'--workpath={WORKPATH}',
        f'--specpath={SPEC_PATH}',
        f'--add-data={SRC_DIR}:src',
        f'--runtime-hook={RUNTIME_HOOK}',  # runtime hook 修复打包后 inspect 问题
    ]

    # 添加所有隐藏导入
    for imp in hidden_imports:
        args.append(f'--hidden-import={imp}')

    # 收集所有依赖
    args.extend([
        '--collect-all=fit_tool',
        '--collect-all=garth',
        # 排除不需要的模块
        '--exclude-module=tkinter',
        '--exclude-module=matplotlib',
        '--exclude-module=numpy',
        '--exclude-module=pandas',
        '--exclude-module=scipy',
        '--exclude-module=PIL',
        '--exclude-module=logfire',
        # 入口文件（必须放在最后，绝对路径）
        str(PROJECT_ROOT / 'src' / 'gui' / 'main.py'),
    ])

    # 添加图标（如果存在，绝对路径）
    icon_path = PROJECT_ROOT / 'src' / 'gui' / 'resources' / 'icons' / 'app_icon.ico'
    if icon_path.exists():
        args.insert(1, f'--icon={icon_path}')

    PyInstaller.__main__.run(args)

    print()
    print("=" * 60)
    print("[OK] GUI 版本打包完成！")
    print(f"输出目录: {_distpath(release)}/mi-scale-to-garmin-gui/")
    print("=" * 60)


def build_cli(release: bool = False):
    """打包 CLI 版本"""
    print("=" * 60)
    print("开始打包 CLI 版本...")
    print("=" * 60)

    # 精简的隐藏导入列表（优化启动速度）
    hidden_imports = [
        # 自定义模块
        'garmin',
        'xiaomi',
        'core',
        'core.models',
        'core.config_manager',
        'core.sync_service',
        # pkg_resources 核心依赖（精简后）
        'jaraco.collections',
        'jaraco.functools',
        'importlib_metadata',
        'pkg_resources',
        'packaging',
    ]

    args = [
        '--name=mi-scale-to-garmin-cli',
        '--onefile',
        '--clean',
        '--noconfirm',
        f'--distpath={_distpath(release)}',
        f'--workpath={WORKPATH}',
        f'--specpath={SPEC_PATH}',
        f'--add-data={SRC_DIR}:src',
        f'--runtime-hook={RUNTIME_HOOK}',  # runtime hook 修复打包后 inspect 问题
    ]

    # 添加所有隐藏导入
    for imp in hidden_imports:
        args.append(f'--hidden-import={imp}')

    # 收集所有依赖
    args.extend([
        '--collect-all=fit_tool',
        '--collect-all=garth',
        # 排除不需要的模块
        '--exclude-module=PyQt6',
        '--exclude-module=tkinter',
        '--exclude-module=matplotlib',
        '--exclude-module=numpy',
        '--exclude-module=pandas',
        '--exclude-module=scipy',
        '--exclude-module=PIL',
        # 入口文件（必须放在最后，绝对路径）
        str(PROJECT_ROOT / 'src' / 'main.py'),
    ])

    PyInstaller.__main__.run(args)

    print()
    print("=" * 60)
    print("[OK] CLI 版本打包完成！")
    print(f"输出文件: {_distpath(release)}/mi-scale-to-garmin-cli")
    print("=" * 60)


def build_all(release: bool = False):
    """打包所有版本"""
    print()
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "mi-scale-to-garmin 打包工具" + " " * 13 + "║")
    print("╚" + "=" * 58 + "╝")
    print()

    # 检查 PyInstaller
    try:
        import PyInstaller
        print(f"[OK] PyInstaller 版本: {PyInstaller.__version__}")
    except ImportError:
        print("[ERR] PyInstaller 未安装")
        print()
        print("请先安装 PyInstaller:")
        print("  pip install pyinstaller")
        return

    print()
    print("请选择要打包的版本:")
    print("  1. GUI 版本 (推荐)")
    print("  2. CLI 版本")
    print("  3. 全部打包")
    print("  0. 退出")
    print()

    choice = input("请输入选项 (0-3): ").strip()

    if choice == '1':
        build_gui(release)
    elif choice == '2':
        build_cli(release)
    elif choice == '3':
        print()
        print("开始打包所有版本...")
        print()
        build_gui(release)
        print()
        build_cli(release)
        print()
        print("=" * 60)
        print("[OK] 所有版本打包完成！")
        print(f"  - GUI: {_distpath(release)}/mi-scale-to-garmin-gui/")
        print(f"  - CLI: {_distpath(release)}/mi-scale-to-garmin-cli")
        print("=" * 60)
    elif choice == '0':
        print("退出")
    else:
        print("[ERR] 无效选项")


def main():
    """入口：支持命令行参数（gui|cli|all）+ --release，无参数时进入交互菜单

    产物目录：dist/<dev|release>/<platform>/（platform 自动检测）
    """
    # 固定工作目录为项目根：保证 src/、dist/ 等相对路径与调用位置无关
    os.chdir(PROJECT_ROOT)

    args = [a for a in sys.argv[1:] if a != '--release']
    release = '--release' in sys.argv[1:]
    if args:
        target = args[0].strip().lower()
        if target == 'gui':
            build_gui(release)
        elif target == 'cli':
            build_cli(release)
        elif target == 'all':
            build_gui(release)
            print()
            build_cli(release)
        else:
            print(f"[ERR] 无效选项: {args[0]}（可用: gui | cli | all，加 --release 输出到 dist/release/）")
            sys.exit(1)
    else:
        build_all(release)


if __name__ == '__main__':
    main()
