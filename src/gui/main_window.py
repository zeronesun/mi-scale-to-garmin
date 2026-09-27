"""
主窗口实现
"""
import sys
import logging
import json
import queue
from pathlib import Path
from typing import Optional, Dict, Any
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QLabel, QStatusBar,
    QTextEdit, QMessageBox, QProgressBar, QListWidgetItem,
    QSplitter, QFileDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon, QAction

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from core.sync_service import SyncOrchestrator, SyncProgress
from core.models import UserModel
from core.account import mask_account

logger = logging.getLogger(__name__)


class SyncWorker(QThread):
    """同步工作线程"""
    progress_signal = pyqtSignal(object)  # SyncProgress
    finished_signal = pyqtSignal(bool, str)  # success, message

    def __init__(self, username: str, orchestrator: SyncOrchestrator):
        super().__init__()
        self.username = username
        self.orchestrator = orchestrator
        self.input_queue = queue.Queue()  # 用于接收用户输入
        self.waiting_for_input = False   # 标记是否在等待输入
        self._input_callback = None      # 输入回调函数

    def run(self):
        """在后台线程执行同步"""
        try:
            # 传递输入回调给 orchestrator
            for progress in self.orchestrator.sync_user(
                self.username,
                input_callback=self.get_user_input
            ):
                self.progress_signal.emit(progress)
            self.finished_signal.emit(True, "同步完成")
        except Exception as e:
            logger.exception(f"同步线程异常: {e}")
            self.finished_signal.emit(False, str(e))

    def get_user_input(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        同步等待用户输入

        Args:
            input_data: 需要传递给 GUI 的输入请求数据

        Returns:
            用户输入的结果
        """
        self.waiting_for_input = True

        # 通过信号请求 GUI 获取输入
        self.progress_signal.emit(SyncProgress(
            stage="awaiting_input",
            current=0,
            total=100,
            message="等待用户输入...",
            timestamp="",
            username=self.username,
            details=input_data
        ))

        # 阻塞等待用户输入
        result = self.input_queue.get()

        self.waiting_for_input = False
        return result

    def provide_input(self, result: Dict[str, Any]):
        """
        提供用户输入 (从 GUI 调用)

        Args:
            result: 用户输入的结果
        """
        self.input_queue.put(result)


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self, config_path: str = "users.json"):
        """
        初始化主窗口

        Args:
            config_path: 配置文件路径
        """
        super().__init__()
        self.config_path = Path(config_path)  # 保存当前配置路径
        self.config_loaded = True  # 跟踪配置是否已加载
        self.orchestrator = SyncOrchestrator(config_path)
        self.sync_workers = {}  # username -> SyncWorker
        self.init_ui()
        self.load_users()
        self.update_status_bar_config()  # 显示当前配置

    def init_ui(self):
        """初始化 UI"""
        self.setWindowTitle("mi-scale-to-garmin")
        self._set_window_icon()
        self.setMinimumSize(1000, 700)

    def _set_window_icon(self):
        """设置窗口图标（开发版/打包版路径自适应，图标缺失时静默跳过）"""
        try:
            if getattr(sys, "frozen", False):
                # 打包版：资源在 _MEIPASS 临时解压目录（spec 已把 src/ 整体打入 datas）
                base = Path(sys._MEIPASS) / "src"
            else:
                base = Path(__file__).parent.parent
            icon_path = base / "gui" / "resources" / "icons" / "app_icon.ico"
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))
        except Exception:
            logger.debug("窗口图标设置失败（忽略）", exc_info=True)

        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        main_layout = QVBoxLayout(central_widget)

        # 工具栏
        toolbar = self.create_toolbar()
        main_layout.addWidget(toolbar)

        # 使用分割器
        splitter = QSplitter(Qt.Orientation.Vertical)

        # 上半部分：用户列表 + 统计
        top_widget = self.create_top_widget()
        splitter.addWidget(top_widget)

        # 下半部分：日志
        bottom_widget = self.create_log_widget()
        splitter.addWidget(bottom_widget)

        # 设置分割比例
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

        # 创建菜单栏
        self.create_menu_bar()

    def create_toolbar(self) -> QWidget:
        """创建工具栏"""
        toolbar = QWidget()
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(5, 5, 5, 5)

        btn_add = QPushButton("➕ 添加用户")
        btn_add.setMinimumHeight(35)
        btn_add.clicked.connect(self.add_user)

        btn_sync_selected = QPushButton("🔄 同步选中用户")
        btn_sync_selected.setMinimumHeight(35)
        btn_sync_selected.clicked.connect(self.sync_selected_users)

        btn_sync_all = QPushButton("🔄 全部同步")
        btn_sync_all.setMinimumHeight(35)
        btn_sync_all.clicked.connect(self.sync_all_users)

        # 新增：切换配置按钮
        btn_switch_config = QPushButton("⚙️ 切换配置")
        btn_switch_config.setMinimumHeight(35)
        btn_switch_config.setToolTip("切换到其他配置文件")
        btn_switch_config.clicked.connect(self.switch_config_file)

        btn_settings = QPushButton("📖 设置")
        btn_settings.setMinimumHeight(35)
        btn_settings.clicked.connect(self.open_settings)

        btn_refresh = QPushButton("🔄 刷新")
        btn_refresh.setMinimumHeight(35)
        btn_refresh.clicked.connect(self.load_users)

        layout.addWidget(btn_add)
        layout.addWidget(btn_sync_selected)
        layout.addWidget(btn_sync_all)
        layout.addWidget(btn_switch_config)  # 添加切换配置按钮
        layout.addWidget(btn_settings)
        layout.addWidget(btn_refresh)
        layout.addStretch()

        return toolbar

    def create_top_widget(self) -> QWidget:
        """创建上半部分：统计 + 用户列表"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 快速统计
        stats_layout = QHBoxLayout()

        self.label_total_users = QLabel("总用户: 0")
        self.label_total_users.setStyleSheet("QLabel { font-size: 14px; font-weight: bold; padding: 10px; }")

        self.label_syncing = QLabel("正在同步: 0")
        self.label_syncing.setStyleSheet("QLabel { font-size: 14px; font-weight: bold; padding: 10px; }")

        stats_layout.addWidget(self.label_total_users)
        stats_layout.addWidget(self.label_syncing)
        stats_layout.addStretch()

        layout.addLayout(stats_layout)

        # 用户列表
        list_label = QLabel("👥 用户列表")
        list_label.setStyleSheet("QLabel { font-size: 14px; font-weight: bold; }")
        layout.addWidget(list_label)

        self.user_list = QListWidget()
        self.user_list.setStyleSheet("""
            QListWidget {
                font-size: 13px;
                border: 1px solid #ccc;
                border-radius: 5px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
                color: #000;
            }
        """)
        layout.addWidget(self.user_list)

        return widget

    def create_log_widget(self) -> QWidget:
        """创建日志窗口"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        log_label = QLabel("📋 同步日志")
        log_label.setStyleSheet("QLabel { font-size: 14px; font-weight: bold; }")
        layout.addWidget(log_label)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # 日志文本框
        self.log_viewer = QTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setStyleSheet("""
            QTextEdit {
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
                border: 1px solid #ccc;
                border-radius: 5px;
                padding: 5px;
                background-color: #f5f5f5;
            }
        """)
        layout.addWidget(self.log_viewer)

        # 清空日志按钮
        btn_clear_log = QPushButton("🗑️ 清空日志")
        btn_clear_log.clicked.connect(self.log_viewer.clear)
        layout.addWidget(btn_clear_log)

        return widget

    def create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件(&F)")

        exit_action = QAction("退出(&X)", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 编辑菜单
        edit_menu = menubar.addMenu("编辑(&E)")

        add_user_action = QAction("添加用户(&A)", self)
        add_user_action.setShortcut("Ctrl+N")
        add_user_action.triggered.connect(self.add_user)
        edit_menu.addAction(add_user_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助(&H)")

        about_action = QAction("关于(&A)", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def load_users(self):
        """加载用户列表"""
        try:
            self.user_list.clear()
            users = self.orchestrator.list_users()

            self.label_total_users.setText(f"总用户: {len(users)}")

            from core.account import resolve_prefix
            from core.session_store import load_xiaomi_auth

            for user in users:
                item = QListWidgetItem()

                # 构建显示文本（决策 2：授权状态查独立会话文件，不再查 users.json 内嵌 token）
                xiaomi_prefix = resolve_prefix(user.xiaomi_prefix, user.username)
                session_token = load_xiaomi_auth(xiaomi_prefix, xiaomi_account=user.username)
                status = "✅ 已授权" if session_token else "❌ 未授权"
                last_sync = user.last_sync if user.last_sync else "从未同步"
                garmin_domain = user.garmin.domain if user.garmin else "N/A"

                text = f"""{mask_account(user.username)}
📱 {user.model} | 🏷️ {garmin_domain} | {status}
🕒 最后同步: {last_sync}"""

                item.setText(text)
                item.setData(Qt.ItemDataRole.UserRole, user.username)
                self.user_list.addItem(item)

            self.log_message(f"✅ 已加载 {len(users)} 个用户")
            self.status_bar.showMessage(f"已加载 {len(users)} 个用户", 3000)

        except Exception as e:
            logger.exception("加载用户列表失败")
            QMessageBox.critical(self, "错误", f"加载用户列表失败:\n{str(e)}")

    def add_user(self):
        """添加用户"""
        # 检查配置文件是否已加载
        if not self.config_path or not self.config_path.exists():
            QMessageBox.warning(
                self,
                "未加载配置",
                "请先加载配置文件后再添加用户。\n"
                '点击"切换配置"按钮选择配置文件。'
            )
            return

        # 导入并创建添加用户对话框
        from gui.add_user_dialog import AddUserDialog
        from core.models import UserModel, GarminConfig, TokenData

        dialog = AddUserDialog(self.orchestrator.config_mgr, self)

        if dialog.exec() == 1:  # Accepted
            try:
                # 获取用户数据
                user_data = dialog.get_user_data()
                if not user_data:
                    QMessageBox.warning(self, "错误", "未能获取用户数据")
                    return

                # 构建 TokenData
                token_data_dict = user_data.get("token", {})
                token_data = TokenData(
                    userId=token_data_dict.get("userId", ""),
                    passToken=token_data_dict.get("passToken", ""),
                    ssecurity=token_data_dict.get("ssecurity", "")
                )

                # 构建 GarminConfig
                garmin_dict = user_data.get("garmin", {})
                garmin_config = GarminConfig(
                    email=garmin_dict.get("email", ""),
                    password=garmin_dict.get("password", ""),
                    domain=garmin_dict.get("domain", "CN"),
                    filter=None
                )

                # 构建 UserModel（脱敏前缀可选，空则回退账号哈希）
                user = UserModel(
                    username=user_data.get("username", ""),
                    password=user_data.get("password", ""),
                    model=user_data.get("model", "yunmai.scales.ms103"),
                    token=token_data,
                    garmin=garmin_config,
                    xiaomi_prefix=user_data.get("xiaomi_prefix") or None,
                    garmin_prefix=garmin_dict.get("garmin_prefix") or None,
                    created_at=None,
                    last_sync=None
                )

                # 保存用户到配置文件
                success = self.orchestrator.config_mgr.add_user(user)

                if success:
                    # 刷新用户列表
                    self.load_users()
                    QMessageBox.information(
                        self,
                        "添加成功",
                        f"用户 {mask_account(user.username)} 已成功添加！\n\n"
                        f"小米账号: {mask_account(user.username)}\n"
                        f"设备型号: {user.model}\n"
                        f"Garmin 账号: {mask_account(user.garmin.email)}"
                    )
                    self.log_message(f"✅ 成功添加用户: {mask_account(user.username)}")
                else:
                    QMessageBox.warning(
                        self,
                        "添加失败",
                        f"添加用户失败:\n{mask_account(user.username)}\n\n"
                        "可能用户名已存在或配置文件写入失败。"
                    )
                    self.log_message(f"❌ 添加用户失败: {mask_account(user.username)}")

            except Exception as e:
                logger.exception("添加用户时发生错误")
                QMessageBox.critical(
                    self,
                    "错误",
                    f"添加用户时发生错误:\n{str(e)}"
                )
                self.log_message(f"❌ 添加用户错误: {str(e)}")

    def sync_selected_users(self):
        """同步选中的用户"""
        selected_items = self.user_list.selectedItems()

        if not selected_items:
            QMessageBox.warning(self, "提示", "请先选择要同步的用户")
            return

        for item in selected_items:
            username = item.data(Qt.ItemDataRole.UserRole)
            if username:
                self.start_sync(username)

    def sync_all_users(self):
        """同步所有用户"""
        reply = QMessageBox.question(
            self,
            "确认",
            "确定要同步所有用户吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            users = self.orchestrator.list_users()
            for user in users:
                self.start_sync(user.username)

    def start_sync(self, username: str):
        """启动同步"""
        if username in self.sync_workers and self.sync_workers[username].isRunning():
            self.log_message(f"⚠️ 用户 {mask_account(username)} 正在同步中")
            return

        self.log_message(f"🚀 开始同步用户: {mask_account(username)}")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        # 创建工作线程
        worker = SyncWorker(username, self.orchestrator)
        worker.progress_signal.connect(self.on_sync_progress)
        worker.finished_signal.connect(lambda success, msg, un=username: self.on_sync_finished(un, success, msg))
        worker.start()

        self.sync_workers[username] = worker
        self.update_syncing_count()

    def on_sync_progress(self, progress: SyncProgress):
        """处理同步进度"""
        if progress.username:
            self.progress_bar.setValue(progress.current)

        # 根据阶段使用不同的图标
        stage_icons = {
            "fetching": "📱",
            "generating": "📝",
            "uploading": "⬆️",
            "completed": "✅",
            "error": "❌",
            "stopped": "⏸️",
            "awaiting_input": "🔐"
        }

        icon = stage_icons.get(progress.stage, "ℹ️")
        self.log_message(f"[{progress.timestamp}] {icon} {progress.message}")

        # 检测需要用户输入的情况
        if progress.stage == "awaiting_input" and progress.details:
            self.handle_user_input_request(progress)

        # 滚动到底部
        self.log_viewer.verticalScrollBar().setValue(
            self.log_viewer.verticalScrollBar().maximum()
        )

    def on_sync_finished(self, username: str, success: bool, message: str):
        """同步完成"""
        if username in self.sync_workers:
            del self.sync_workers[username]

        self.update_syncing_count()

        if success:
            self.log_message(f"✅ 用户 {mask_account(username)} 同步完成")
            self.progress_bar.setValue(100)
        else:
            self.log_message(f"❌ 用户 {mask_account(username)} 同步失败: {message}")

        # 延迟隐藏进度条
        QTimer.singleShot(2000, lambda: self.progress_bar.setVisible(False))

        # 重新加载用户列表（更新最后同步时间）
        QTimer.singleShot(1000, self.load_users)

    def update_syncing_count(self):
        """更新正在同步的用户数"""
        count = sum(1 for w in self.sync_workers.values() if w.isRunning())
        self.label_syncing.setText(f"正在同步: {count}")

    def log_message(self, message: str):
        """输出日志"""
        self.log_viewer.append(message)

    def open_settings(self):
        """打开设置对话框"""
        from utils.paths import get_app_data_dir

        # 获取当前数据目录
        current_dir = self.orchestrator.config_mgr.get_custom_data_dir()
        if not current_dir:
            current_dir = str(get_app_data_dir())

        # 创建设置对话框
        dialog = QMessageBox(self)
        dialog.setWindowTitle("数据目录设置")
        dialog.setText("当前数据目录：")
        dialog.setInformativeText(current_dir)
        dialog.setStandardButtons(
            QMessageBox.StandardButton.Reset
            | QMessageBox.StandardButton.Ok
            | QMessageBox.StandardButton.Cancel
        )
        dialog.setDefaultButton(QMessageBox.StandardButton.Ok)

        # 自定义按钮文本
        dialog.button(QMessageBox.StandardButton.Reset).setText("重置为默认")
        dialog.button(QMessageBox.StandardButton.Ok).setText("自定义...")
        dialog.button(QMessageBox.StandardButton.Cancel).setText("关闭")

        result = dialog.exec()

        if result == QMessageBox.StandardButton.Reset:
            # 重置为默认目录
            reply = QMessageBox.question(
                self,
                "确认重置",
                "确定要重置为默认数据目录吗？\n"
                "当前的自定义路径将被清除。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                success = self.orchestrator.config_mgr.reset_data_dir()
                if success:
                    # 重新加载配置
                    self.orchestrator.reload_config(self.config_path)
                    QMessageBox.information(
                        self,
                        "重置成功",
                        f"已重置为默认数据目录：\n{get_app_data_dir()}"
                    )
                else:
                    QMessageBox.warning(self, "重置失败", "重置数据目录失败，请查看日志。")

        elif result == QMessageBox.StandardButton.Ok:
            # 选择自定义目录
            new_dir = QFileDialog.getExistingDirectory(
                self,
                "选择数据目录",
                current_dir
            )

            if new_dir:
                # 设置自定义目录
                success = self.orchestrator.config_mgr.set_custom_data_dir(new_dir)
                if success:
                    # 重新加载配置
                    self.orchestrator.reload_config(self.config_path)
                    QMessageBox.information(
                        self,
                        "设置成功",
                        f"数据目录已设置为：\n{new_dir}\n\n"
                        f"注意：新的目录将在下次同步时生效。"
                    )
                else:
                    QMessageBox.warning(self, "设置失败", "设置数据目录失败，请查看日志。")

    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self,
            "关于 mi-scale-to-garmin",
            """
            <h3>mi-scale-to-garmin</h3>
            <p>将小米体脂秤测量数据（体重、BMI、体脂率等身体成分）自动同步到 Garmin Connect</p>
            <p><b>功能特性:</b></p>
            <ul>
                <li>支持多用户管理</li>
                <li>分块上传，避免超限</li>
                <li>实时同步进度显示</li>
                <li>数据过滤支持</li>
            </ul>
            <p><b>开发者:</b> zeronesun</p>
            <p><b>许可:</b> MIT License</p>
            """
        )

    def closeEvent(self, event):
        """关闭事件"""
        # 检查是否有正在进行的同步
        if self.sync_workers:
            reply = QMessageBox.question(
                self,
                "确认退出",
                "有正在进行的同步任务，确定要退出吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                # 停止所有同步
                for worker in self.sync_workers.values():
                    if worker.isRunning():
                        worker.terminate()
                        worker.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    def switch_config_file(self):
        """切换配置文件"""
        # 检查是否有正在运行的同步任务
        if self.sync_workers:
            reply = QMessageBox.question(
                self,
                "确认切换",
                "有同步任务正在运行，确定要切换配置吗？\n"
                "正在运行的同步将被取消。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return

            # 停止所有同步任务
            for worker in self.sync_workers.values():
                if worker.isRunning():
                    worker.terminate()
                    worker.wait()
            self.sync_workers.clear()

        # 打开文件选择对话框
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择配置文件",
            str(self.config_path.parent),  # 默认打开当前配置所在目录
            "JSON Files (*.json);;All Files (*)"
        )

        if not file_path:  # 用户取消
            return

        # 验证并加载配置文件
        try:
            self.validate_and_load_config(file_path)
        except Exception as e:
            QMessageBox.critical(
                self,
                "配置文件错误",
                f"无法加载配置文件：\n{str(e)}"
            )

    def validate_and_load_config(self, file_path: str):
        """验证并加载配置文件"""
        path = Path(file_path)

        # 检查文件是否存在
        if not path.exists():
            raise FileNotFoundError(f"配置文件不存在：{file_path}")

        # 验证 JSON 格式
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"配置文件格式错误：\n{e}")

        # 验证必需字段
        if "users" not in data:
            raise ValueError("配置文件缺少 'users' 字段")

        if not isinstance(data["users"], list):
            raise ValueError("'users' 字段必须是数组")

        # 重新加载配置
        old_config = self.config_path
        self.config_path = path
        try:
            self.orchestrator.reload_config(file_path)
            self.load_users()

            # 更新状态栏
            self.update_status_bar_config()

            # 显示成功消息
            self.status_bar.showMessage(
                f"✅ 已切换到配置：{path.name}",
                5000
            )

            # 记录日志
            logger.info(f"已切换配置文件：{old_config} → {file_path}")

            # 更新窗口标题
            config_name = path.stem
            self.setWindowTitle(f"mi-scale-to-garmin - {config_name}")
        except Exception as e:
            # 加载失败，恢复旧配置
            self.config_path = old_config
            raise e

    def update_status_bar_config(self):
        """更新状态栏显示当前配置"""
        config_name = self.config_path.name
        user_count = len(self.orchestrator.list_users())

        # 格式化配置路径（如果太长则缩短）
        config_display = str(self.config_path)
        if len(config_display) > 40:
            config_display = "..." + config_display[-37:]

        self.status_bar.showMessage(
            f"📄 {config_display} | 👥 {user_count} 用户 | 就绪"
        )

    def handle_user_input_request(self, progress: SyncProgress):
        """处理用户输入请求"""
        details = progress.details
        action = details.get("action")

        # 日志脱敏：details 可能含明文账号（铁律 3）
        safe_details = {k: (mask_account(v) if k in ("username", "email") and isinstance(v, str) else v)
                        for k, v in details.items()}
        logger.info(f"[DEBUG] handle_user_input_request 被调用, action={action}, details={safe_details}")

        if action == "xiaomi_login":
            # 直接在主线程中处理登录(同步方式)
            result = self._handle_xiaomi_login(progress.username, details)
            # 将结果发送回工作线程
            self._send_login_result(progress.username, result)
        elif action == "garmin_mfa":
            # 处理 Garmin MFA 请求
            result = self._handle_garmin_mfa(progress.username, details)
            # 将结果发送回工作线程
            self._send_login_result(progress.username, result)
        elif action == "garmin_password":
            # 决策 4：佳明会话失效时弹窗输入密码（仅内存中使用）
            result = self._handle_password_input(
                progress.username, details, service="佳明")
            self._send_login_result(progress.username, result)

    def _handle_xiaomi_login(self, username: str, details: Dict[str, Any]) -> Dict[str, Any]:
        """处理小米登录(在主线程中同步执行)"""
        try:
            from xiaomi.login import MiCloudSync
            from gui.auth_dialogs import CaptchaDialog, MfaDialog

            username_param = details.get("username")
            password_param = details.get("password")

            if not username_param:
                return {
                    "success": False,
                    "error": "缺少用户名"
                }

            # 决策 4：users.json 不再存密码，缺失时弹窗输入（仅内存中使用）
            if not password_param:
                from gui.auth_dialogs import PasswordDialog
                dialog = PasswordDialog(username_param, service="小米", parent=self)
                if dialog.exec() != 1:
                    return {"success": False, "error": "用户取消密码输入"}
                password_param = dialog.get_password()
                if not password_param:
                    return {"success": False, "error": "密码为空"}

            # 创建 MiCloudSync 实例
            micloud_sync = MiCloudSync(sid="miothealth")

            # 尝试登录
            result = micloud_sync.login(username_param, password_param)

            if result.get("ok"):
                # 登录成功,提取 token 数据
                token_data = self._extract_token_data(result, micloud_sync)
                return {
                    "success": True,
                    "token": token_data
                }

            if captcha_image := result.get("captcha"):
                # 需要验证码 - 显示对话框
                return self._show_captcha_dialog_sync(username, captcha_image, micloud_sync)

            if verify_info := result.get("verify"):
                # 需要 2FA - 显示对话框
                return self._show_mfa_dialog_sync(username, verify_info, micloud_sync)

            # 登录失败
            error_msg = str(result.get("exception", "未知错误"))
            return {
                "success": False,
                "error": error_msg
            }

        except Exception as e:
            logger.exception(f"小米登录处理失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _show_captcha_dialog_sync(self, username: str, captcha_image: bytes, micloud_sync, retry_count: int = 0) -> Dict[str, Any]:
        """显示验证码对话框(同步版本,返回结果)"""
        from gui.auth_dialogs import CaptchaDialog

        # 最多重试 3 次
        if retry_count >= 3:
            return {
                "success": False,
                "error": "验证码错误次数过多"
            }

        dialog = CaptchaDialog(captcha_image, self)

        if dialog.exec() == 1:  # Accepted
            code = dialog.get_code()

            # 提交验证码
            result = micloud_sync.login_captcha(code)

            if result.get("ok"):
                # 登录成功
                token_data = self._extract_token_data(result, micloud_sync)
                return {
                    "success": True,
                    "token": token_data
                }
            elif verify_info := result.get("verify"):
                # 需要 2FA - 显示对话框
                return self._show_mfa_dialog_sync(username, verify_info, micloud_sync)
            elif captcha := result.get("captcha"):
                # 验证码错误,重新显示
                QMessageBox.warning(self, "验证码错误", f"验证码输入错误,请重试 ({retry_count + 1}/3)")
                return self._show_captcha_dialog_sync(username, captcha, micloud_sync, retry_count + 1)
            else:
                # 其他错误
                error_msg = str(result.get("exception", "验证码错误"))
                QMessageBox.critical(self, "验证码错误", error_msg)
                return {
                    "success": False,
                    "error": "验证码错误"
                }
        else:
            # 用户取消
            return {
                "success": False,
                "error": "用户取消"
            }

    def _show_mfa_dialog_sync(self, username: str, verify_info: str, micloud_sync, retry_count: int = 0) -> Dict[str, Any]:
        """显示 2FA 对话框(同步版本,返回结果)"""
        from gui.auth_dialogs import MfaDialog

        # 最多重试 3 次
        if retry_count >= 3:
            return {
                "success": False,
                "error": "验证码错误次数过多"
            }

        dialog = MfaDialog(verify_info, self)

        if dialog.exec() == 1:  # Accepted
            ticket = dialog.get_ticket()

            # 提交 2FA 验证码
            result = micloud_sync.login_verify(ticket)

            if result.get("ok"):
                # 登录成功
                token_data = self._extract_token_data(result, micloud_sync)
                return {
                    "success": True,
                    "token": token_data
                }
            else:
                # 验证码错误
                if retry_count < 2:
                    QMessageBox.warning(self, "验证失败", f"二次验证码错误,请重试 ({retry_count + 1}/3)")
                    return self._show_mfa_dialog_sync(username, verify_info, micloud_sync, retry_count + 1)
                else:
                    QMessageBox.critical(self, "验证失败", "二次验证码错误次数过多")
                    return {
                        "success": False,
                        "error": "2FA 验证失败"
                    }
        else:
            # 用户取消
            return {
                "success": False,
                "error": "用户取消"
            }

    def _extract_token_data(self, result: Dict[str, Any], micloud_sync) -> Dict[str, str]:
        """从登录结果中提取 token 数据"""
        import base64

        # MiCloudSync 返回的 token 格式是 "userId:passToken"
        token_string = result.get("token", "")

        if not token_string:
            return {
                "userId": "",
                "passToken": "",
                "ssecurity": ""
            }

        # 解析 token 字符串
        if ":" in token_string:
            user_id, pass_token = token_string.split(":", 1)
        else:
            user_id = token_string
            pass_token = ""

        # 从 micloud_sync 实例获取 ssecurity (已经是 bytes,需要 base64 编码)
        if micloud_sync.ssecurity:
            ssecurity = base64.b64encode(micloud_sync.ssecurity).decode('utf-8')
        else:
            ssecurity = ""

        return {
            "userId": user_id,
            "passToken": pass_token,
            "ssecurity": ssecurity
        }

    def _handle_garmin_mfa(self, username: str, details: Dict[str, Any]) -> Dict[str, Any]:
        """处理 Garmin MFA 验证码输入(在主线程中同步执行)"""
        try:
            from gui.auth_dialogs import GarminMfaDialog

            email = details.get("email", "")
            logger.info(f"[DEBUG] _handle_garmin_mfa 被调用, email={email}")

            # 显示 MFA 对话框
            dialog = GarminMfaDialog(email, self)
            logger.info(f"[DEBUG] GarminMfaDialog 已创建，准备显示")

            result_code = dialog.exec()
            logger.info(f"[DEBUG] 对话框返回结果: {result_code}")

            if result_code == 1:  # Accepted
                mfa_code = dialog.get_mfa_code()
                logger.info(f"[DEBUG] 用户输入的 MFA 验证码: {mfa_code}")
                return {
                    "mfa_code": mfa_code
                }
            else:
                # 用户取消
                logger.info(f"[DEBUG] 用户取消了 MFA 输入")
                return {
                    "mfa_code": ""
                }

        except Exception as e:
            logger.exception(f"Garmin MFA 处理失败: {e}")
            return {
                "mfa_code": ""
            }

    def _handle_password_input(self, username: str, details: Dict[str, Any],
                               service: str = "佳明") -> Dict[str, Any]:
        """处理密码输入请求(在主线程中同步执行，决策 4)"""
        try:
            from gui.auth_dialogs import PasswordDialog

            account = details.get("email") or details.get("username") or username
            dialog = PasswordDialog(account, service=service, parent=self)
            if dialog.exec() == 1:  # Accepted
                return {"password": dialog.get_password()}
            return {"password": ""}
        except Exception as e:
            logger.exception(f"密码输入处理失败: {e}")
            return {"password": ""}

    def _send_login_result(self, username: str, result: Dict[str, Any]):
        """将登录结果发送回同步线程"""
        worker = self.sync_workers.get(username)
        if worker and worker.waiting_for_input:
            worker.provide_input(result)
        else:
            logger.warning(f"无法发送登录结果到用户 {mask_account(username)}: 工作线程不存在或未在等待输入")
