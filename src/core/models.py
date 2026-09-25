"""
数据模型定义
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from datetime import datetime


@dataclass
class GarminConfig:
    """Garmin 配置"""
    email: str
    password: str
    domain: str = "CN"  # CN or COM
    filter: Optional[Dict[str, Any]] = None


@dataclass
class TokenData:
    """小米 Token 数据"""
    userId: str
    passToken: str
    ssecurity: str


@dataclass
class UserModel:
    """用户数据模型"""
    username: str
    password: str
    model: str = "yunmai.scales.ms103"
    token: Optional[TokenData] = None
    garmin: Optional[GarminConfig] = None
    created_at: Optional[str] = None
    last_sync: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "username": self.username,
            "password": self.password,
            "model": self.model,
        }

        if self.token:
            result["token"] = {
                "userId": self.token.userId,
                "passToken": self.token.passToken,
                "ssecurity": self.token.ssecurity,
            }

        if self.garmin:
            result["garmin"] = {
                "email": self.garmin.email,
                "password": self.garmin.password,
                "domain": self.garmin.domain,
            }
            if self.garmin.filter:
                result["garmin"]["filter"] = self.garmin.filter

        if self.created_at:
            result["created_at"] = self.created_at

        if self.last_sync:
            result["last_sync"] = self.last_sync

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserModel':
        """从字典创建"""
        token_data = data.get("token")
        token = None
        if token_data and isinstance(token_data, dict):
            token = TokenData(
                userId=token_data.get("userId", ""),
                passToken=token_data.get("passToken", ""),
                ssecurity=token_data.get("ssecurity", "")
            )

        garmin_data = data.get("garmin")
        garmin = None
        if garmin_data and isinstance(garmin_data, dict):
            garmin = GarminConfig(
                email=garmin_data.get("email", ""),
                password=garmin_data.get("password", ""),
                domain=garmin_data.get("domain", "CN"),
                filter=garmin_data.get("filter")
            )

        return cls(
            username=data.get("username", ""),
            password=data.get("password", ""),
            model=data.get("model", "yunmai.scales.ms103"),
            token=token,
            garmin=garmin,
            created_at=data.get("created_at"),
            last_sync=data.get("last_sync")
        )


@dataclass
class SyncProgress:
    """同步进度数据类"""
    stage: str  # "fetching", "generating", "uploading", "completed", "error"
    current: int
    total: int
    message: str
    timestamp: str
    username: str = ""
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "stage": self.stage,
            "current": self.current,
            "total": self.total,
            "message": self.message,
            "timestamp": self.timestamp,
            "username": self.username,
            "details": self.details
        }


@dataclass
class SyncResult:
    """同步结果"""
    username: str
    success: bool
    total_records: int = 0
    uploaded_chunks: int = 0
    failed_chunks: int = 0
    duplicate_chunks: int = 0
    failed_details: List[Dict[str, Any]] = field(default_factory=list)
    error_message: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
