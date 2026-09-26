"""
PyInstaller 打包脚本
用于将 mi-scale-to-garmin 打包成独立可执行文件
"""
import PyInstaller.__main__
import os
import sys
from pathlib import Path


def build_gui():
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
        '--add-data=src:src',
        '--runtime-hook=pyi_rth_pyqt6.py',  # 添加 runtime hook 修复 inspect 问题
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
        # 入口文件（必须放在最后）
        'src/gui/main.py',
    ])

    # 添加图标（如果存在）
    icon_path = 'src/gui/resources/icons/app_icon.ico'
    if os.path.exists(icon_path):
        args.insert(1, f'--icon={icon_path}')

    PyInstaller.__main__.run(args)

    print()
    print("=" * 60)
    print("[OK] GUI 版本打包完成！")
    print("输出文件: dist/mi-scale-to-garmin-gui/mi-scale-to-garmin-gui.exe")
    print("=" * 60)


def build_cli():
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
        '--add-data=src:src',
        '--runtime-hook=pyi_rth_pyqt6.py',  # 添加 runtime hook 修复 inspect 问题
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
        # 入口文件（必须放在最后）
        'src/main.py',
    ])

    PyInstaller.__main__.run(args)

    print()
    print("=" * 60)
    print("[OK] CLI 版本打包完成！")
    print("输出文件: dist/mi-scale-to-garmin-cli")
    print("=" * 60)


def build_all():
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
        build_gui()
    elif choice == '2':
        build_cli()
    elif choice == '3':
        print()
        print("开始打包所有版本...")
        print()
        build_gui()
        print()
        build_cli()
        print()
        print("=" * 60)
        print("[OK] 所有版本打包完成！")
        print("  - GUI: dist/mi-scale-to-garmin-gui/mi-scale-to-garmin-gui.exe")
        print("  - CLI: dist/mi-scale-to-garmin-cli")
        print("=" * 60)
    elif choice == '0':
        print("退出")
    else:
        print("[ERR] 无效选项")


def main():
    """入口：支持命令行参数（gui|cli|all），无参数时进入交互菜单"""
    if len(sys.argv) > 1:
        target = sys.argv[1].strip().lower()
        if target == 'gui':
            build_gui()
        elif target == 'cli':
            build_cli()
        elif target == 'all':
            build_gui()
            print()
            build_cli()
        else:
            print(f"[ERR] 无效选项: {sys.argv[1]}（可用: gui | cli | all）")
            sys.exit(1)
    else:
        build_all()


if __name__ == '__main__':
    main()
