
import json
import os
from typing import Dict, List, Optional

class ConfigManager:
    def __init__(self, config_file: str = "users.json"):
        self.config_file = config_file
        self.config_data = self._load_config()

    def _load_config(self) -> Dict:
        if not os.path.exists(self.config_file):
            return {"users": []}
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            return {"users": []}

    def save_config(self):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get_users(self) -> List[Dict]:
        return self.config_data.get("users", [])

    def update_user_token(self, username: str, token_data: Dict):
        for user in self.config_data.get("users", []):
            if user.get("username") == username:
                if "token" not in user:
                    user["token"] = {}
                user["token"].update(token_data)
                self.save_config()
                return
        
        # If user not found (should generally be found if config drives the loop)
        print(f"User {username} not found in config to update token.")

    def get_user_token(self, username: str) -> Optional[Dict]:
        for user in self.config_data.get("users", []):
            if user.get("username") == username:
                return user.get("token")
        return None
