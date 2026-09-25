"""
Xiaomi Authentication Module
Handles login and token management for Xiaomi accounts
"""

import logging
from typing import Dict, Optional
from micloud import MiCloud

_LOGGER = logging.getLogger(__name__)

class XiaomiAuth:
    """Handles Xiaomi account authentication"""
    
    def __init__(self, username: str, password: str, region: str = "cn"):
        """
        Initialize Xiaomi Auth
        
        Args:
            username: Xiaomi account username (email or phone)
            password: Xiaomi account password
            region: Server region (cn, de, us, etc.)
        """
        self.username = username
        self.password = password
        self.region = region
        self.mc = None
        
    def login(self) -> Dict:
        """
        Perform login and get authentication tokens
        
        Returns:
            Dict containing userId, passToken, ssecurity, and serviceToken
        """
        try:
            _LOGGER.info(f"Attempting login for {self.username} in region {self.region}")
            
            # Create MiCloud instance
            self.mc = MiCloud(self.username, self.password)
            
            # Perform login
            login_result = self.mc.login()
            
            if not login_result:
                raise Exception("Login failed - no result returned")
            
            _LOGGER.info("Login successful!")
            
            # Get authentication data
            user_id = self.mc.user_id
            service_token = self.mc.service_token
            ssecurity = self.mc.ssecurity
            
            # Try to extract passToken from session cookies
            pass_token = None
            if hasattr(self.mc, 'session') and self.mc.session:
                cookies = self.mc.session.cookies.get_dict()
                pass_token = cookies.get('passToken') or cookies.get('serviceToken')
            
            # If we can't get passToken from cookies, use serviceToken as fallback
            if not pass_token:
                pass_token = service_token
            
            token_data = {
                "userId": str(user_id) if user_id else "",
                "passToken": pass_token if pass_token else "",
                "ssecurity": ssecurity if ssecurity else "",
                "serviceToken": service_token if service_token else ""
            }
            
            _LOGGER.info(f"Retrieved tokens - userId: {token_data['userId']}")
            
            return token_data
            
        except Exception as e:
            _LOGGER.error(f"Login failed: {e}")
            raise
    
    def get_devices(self, country: Optional[str] = None) -> list:
        """
        Get list of devices from Xiaomi cloud
        
        Args:
            country: Country code (defaults to region)
            
        Returns:
            List of device information
        """
        if not self.mc:
            raise Exception("Not logged in - call login() first")
        
        country = country or self.region
        
        try:
            devices = self.mc.get_devices(country=country)
            _LOGGER.info(f"Retrieved {len(devices) if devices else 0} devices")
            return devices or []
        except Exception as e:
            _LOGGER.error(f"Failed to get devices: {e}")
            return []
