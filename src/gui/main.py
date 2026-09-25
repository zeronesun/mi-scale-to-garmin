"""
GUI 应用入口
"""
import sys
import logging
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from gui.main_window import MainWindow

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """主函数"""
    # 启用高 DPI 缩放
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    # 创建应用
    app = QApplication(sys.argv)
    app.setApplicationName("Garmin Weight Sync")
    app.setOrganizationName("GarminSync")

    # 获取配置文件路径（支持命令行参数）
    config_path = "users.json"  # 默认配置
    if len(sys.argv) > 1:
        # 如果提供了命令行参数，使用第一个参数作为配置文件路径
        config_path = sys.argv[1]
        logger.info(f"使用指定的配置文件：{config_path}")

    # 创建主窗口，传入配置文件路径
    window = MainWindow(config_path=config_path)
    window.show()

    logger.info("Garmin 体重同步管理 GUI 已启动")

    # 运行应用
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
