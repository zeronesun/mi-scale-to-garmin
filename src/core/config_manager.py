"""
增强的配置管理器
复制并扩展现有的 xiaomi.config.ConfigManager
"""
import json
import os
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime
import logging

from .models import UserModel

logger = logging.getLogger(__name__)


class EnhancedConfigManager:
    """增强的配置管理器"""

    def __init__(self, config_file: str = "users.json"):
        self.config_file = Path(config_file)
        self.config_dir = self.config_file.parent
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self._config_data = self._load_config()

        # 读取自定义数据目录配置（如果有）
        settings = self._config_data.get("settings", {})
        self.custom_data_dir = settings.get("data_dir")
        if self.custom_data_dir:
            logger.info(f"使用自定义数据目录: {self.custom_data_dir}")

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        if not self.config_file.exists():
            logger.info(f"配置文件不存在，创建新文件: {self.config_file}")
            return {"users": []}

        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.info(f"成功加载配置文件: {self.config_file}")
                return data
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return {"users": []}

    def _save_config(self):
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config_data, f, indent=4, ensure_ascii=False)
            logger.info(f"配置已保存到: {self.config_file}")
        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")
            raise

    def get_users(self) -> List[UserModel]:
        """获取所有用户"""
        users_data = self._config_data.get("users", [])
        return [UserModel.from_dict(u) for u in users_data]

    def get_user(self, username: str) -> Optional[UserModel]:
        """获取指定用户"""
        for user_data in self._config_data.get("users", []):
            if user_data.get("username") == username:
                return UserModel.from_dict(user_data)
        return None

    def add_user(self, user: UserModel) -> bool:
        """添加用户"""
        try:
            # 检查用户是否已存在
            if self.get_user(user.username):
                logger.warning(f"用户已存在: {user.username}")
                return False

            # 设置创建时间
            if not user.created_at:
                user.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 添加用户
            if "users" not in self._config_data:
                self._config_data["users"] = []

            self._config_data["users"].append(user.to_dict())
            self._save_config()
            logger.info(f"成功添加用户: {user.username}")
            return True
        except Exception as e:
            logger.error(f"添加用户失败: {e}")
            return False

    def update_user(self, user: UserModel) -> bool:
        """更新用户"""
        try:
            users = self._config_data.get("users", [])
            for i, u in enumerate(users):
                if u.get("username") == user.username:
                    users[i] = user.to_dict()
                    self._config_data["users"] = users
                    self._save_config()
                    logger.info(f"成功更新用户: {user.username}")
                    return True

            logger.warning(f"用户不存在: {user.username}")
            return False
        except Exception as e:
            logger.error(f"更新用户失败: {e}")
            return False

    def add_or_update_user(self, user: UserModel) -> bool:
        """添加或更新用户"""
        existing = self.get_user(user.username)
        if existing:
            return self.update_user(user)
        else:
            return self.add_user(user)

    def delete_user(self, username: str) -> bool:
        """删除用户"""
        try:
            users = self._config_data.get("users", [])
            original_count = len(users)

            # 过滤掉要删除的用户
            users = [u for u in users if u.get("username") != username]

            if len(users) == original_count:
                logger.warning(f"用户不存在: {username}")
                return False

            self._config_data["users"] = users
            self._save_config()
            logger.info(f"成功删除用户: {username}")
            return True
        except Exception as e:
            logger.error(f"删除用户失败: {e}")
            return False

    def update_user_token(self, username: str, token_data: Dict[str, Any]) -> bool:
        """更新用户 Token"""
        try:
            user = self.get_user(username)
            if not user:
                logger.warning(f"用户不存在: {username}")
                return False

            # 更新 Token
            from .models import TokenData
            user.token = TokenData(
                userId=token_data.get("userId", ""),
                passToken=token_data.get("passToken", ""),
                ssecurity=token_data.get("ssecurity", "")
            )

            return self.update_user(user)
        except Exception as e:
            logger.error(f"更新 Token 失败: {e}")
            return False

    def update_last_sync(self, username: str, timestamp: Optional[str] = None) -> bool:
        """更新最后同步时间"""
        try:
            user = self.get_user(username)
            if not user:
                logger.warning(f"用户不存在: {username}")
                return False

            user.last_sync = timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return self.update_user(user)
        except Exception as e:
            logger.error(f"更新最后同步时间失败: {e}")
            return False

    def get_sync_history(self) -> List[Dict[str, Any]]:
        """获取同步历史（如果存在）"""
        return self._config_data.get("sync_history", [])

    def add_sync_history(self, record: Dict[str, Any]) -> bool:
        """添加同步历史记录"""
        try:
            if "sync_history" not in self._config_data:
                self._config_data["sync_history"] = []

            self._config_data["sync_history"].insert(0, record)  # 最新的在前

            # 保留最近 100 条记录
            history = self._config_data["sync_history"]
            if len(history) > 100:
                self._config_data["sync_history"] = history[:100]

            self._save_config()
            return True
        except Exception as e:
            logger.error(f"添加同步历史失败: {e}")
            return False

    def set_custom_data_dir(self, data_dir: str) -> bool:
        """
        设置自定义数据目录

        Args:
            data_dir: 自定义数据目录路径

        Returns:
            bool: 是否设置成功
        """
        try:
            if "settings" not in self._config_data:
                self._config_data["settings"] = {}

            self._config_data["settings"]["data_dir"] = data_dir
            self.custom_data_dir = data_dir
            self._save_config()

            logger.info(f"已设置自定义数据目录: {data_dir}")
            return True
        except Exception as e:
            logger.error(f"设置自定义数据目录失败: {e}")
            return False

    def get_custom_data_dir(self) -> Optional[str]:
        """获取自定义数据目录"""
        return self.custom_data_dir

    def reset_data_dir(self) -> bool:
        """
        重置为默认数据目录

        Returns:
            bool: 是否重置成功
        """
        try:
            if "settings" in self._config_data and "data_dir" in self._config_data["settings"]:
                del self._config_data["settings"]["data_dir"]
                self.custom_data_dir = None
                self._save_config()
                logger.info("已重置为默认数据目录")
            return True
        except Exception as e:
            logger.error(f"重置数据目录失败: {e}")
            return False
