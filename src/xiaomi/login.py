"""
Xiaomi Login Module
Handles interactive login with captcha and 2FA support
Includes complete MiCloud authentication implementation
"""

import base64
import hashlib
import json
import logging
import os
import random
import string
import sys
import time
import webbrowser
from pathlib import Path
from typing import Dict, Optional, TypedDict

import requests
from cryptography.hazmat.primitives import ciphers
from cryptography.hazmat.primitives.ciphers import algorithms

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from xiaomi.config import ConfigManager

_LOGGER = logging.getLogger(__name__)

# Constants
SDK_VERSION = "4.2.29"
FLAG_PHONE = 4
FLAG_EMAIL = 8


class AuthResult(TypedDict, total=False):
    ok: bool
    captcha: bytes | None
    verify: str | None
    token: str | None
    exception: Exception | None


def parse_auth_response(body: bytes) -> dict:
    """Parse Xiaomi auth response"""
    assert body.startswith(b"&&&START&&&")
    return json.loads(body[11:])


def get_random_string(length: int) -> str:
    """Generate random string for device ID"""
    seq = string.ascii_uppercase + string.digits
    return "".join(random.choice(seq) for _ in range(length))


class MiCloudSync:
    """Synchronous MiCloud authentication client"""

    def __init__(self, sid: str = "xiaomiio"):
        self.session = requests.Session()
        self.sid = sid
        self.device_id = get_random_string(16)
        self.auth: dict = {}
        self.cookies: dict = {}
        self.ssecurity: bytes = None

    @property
    def ok(self):
        return self.cookies is not None and self.ssecurity is not None

    def close(self):
        return self.session.close()

    def login(self, username: str, password: str, **kwargs) -> AuthResult:
        """Perform login with username and password"""
        try:
            res1 = self._service_login(username, password, **kwargs)

            if captcha_url := res1.get("captchaUrl"):
                data = self._get_captcha_url(captcha_url)
                self.auth = {
                    "username": username,
                    "password": password,
                    "ick": data["ick"],
                }
                return {"ok": False, "captcha": data["image"]}

            if notification_url := res1.get("notificationUrl"):
                return self._get_notification_url(notification_url)

            return self._get_credentials(res1)

        except Exception as e:
            return {"ok": False, "exception": e}

    def login_captcha(self, code: str) -> AuthResult:
        """Submit captcha code"""
        if "flag" in self.auth and "identity_session" in self.auth:
            return self._send_ticket(
                self.auth["flag"], self.auth["identity_session"], code
            )

        return self.login(
            self.auth["username"], self.auth["password"], captcha_code=code
        )

    def login_verify(self, ticket: str) -> AuthResult:
        """Verify 2FA code"""
        flag = self.auth["flag"]
        key = "Phone" if flag == FLAG_PHONE else "Email"

        r = self.session.post(
            f"https://account.xiaomi.com/identity/auth/verify{key}",
            cookies={"identity_session": self.auth["identity_session"]},
            params={"_flag": flag, "ticket": ticket, "trust": "false", "_json": "true"},
        )
        res1 = parse_auth_response(r.content)
        assert res1["code"] == 0, res1

        return self._get_credentials(res1)

    def _service_login(
        self, username: str, password: str, captcha_code: str = None
    ) -> dict:
        """Perform service login"""
        r = self.session.get(
            "https://account.xiaomi.com/pass/serviceLogin",
            cookies={"sdkVersion": SDK_VERSION, "deviceId": self.device_id},
            params={"_json": "true", "sid": self.sid},
        )
        res1 = parse_auth_response(r.content)

        cookies = {"sdkVersion": SDK_VERSION, "deviceId": self.device_id}
        data = {
            "_json": "true",
            "sid": res1["sid"],
            "callback": res1["callback"],
            "_sign": res1["_sign"],
            "qs": res1["qs"],
            "user": username,
            "hash": hashlib.md5(password.encode()).hexdigest().upper(),
        }

        if captcha_code:
            cookies["ick"] = self.auth["ick"]
            data["captCode"] = captcha_code

        r = self.session.post(
            "https://account.xiaomi.com/pass/serviceLoginAuth2",
            cookies=cookies,
            data=data,
        )
        return parse_auth_response(r.content)

    def _get_captcha_url(self, captcha_url: str) -> dict:
        """Get captcha image"""
        r = self.session.get("https://account.xiaomi.com" + captcha_url)
        body = r.content
        return {"image": body, "ick": r.cookies["ick"]}

    def _get_credentials(self, data: dict) -> AuthResult:
        """Extract credentials from response"""
        assert data.get("location"), data

        r1 = self.session.get(data["location"])
        assert r1.content == b"ok"

        self.cookies = {k: v for k, v in r1.cookies.items()}

        if hasattr(r1, 'history'):
            for r2 in r1.history:
                data.update({k: v for k, v in r2.cookies.items()})
                if ext := r2.headers.get("extension-pragma"):
                    data.update(json.loads(ext))

        self.ssecurity = base64.b64decode(data["ssecurity"])

        return {"ok": True, "token": f"{data['userId']}:{data['passToken']}"}

    def _get_notification_url(self, notification_url: str) -> AuthResult:
        """Handle notification URL for 2FA"""
        assert "/fe/service/identity/authStart" in notification_url, notification_url
        notification_url = notification_url.replace(
            "/fe/service/identity/authStart", "/identity/list"
        )

        r = self.session.get(notification_url)
        res1 = parse_auth_response(r.content)
        assert res1["code"] == 2, res1

        flag = res1["flag"]
        assert flag in (FLAG_EMAIL, FLAG_PHONE), res1

        return self._send_ticket(flag, r.cookies["identity_session"])

    def _send_ticket(
        self, flag: int, identity_session, captcha_code: str = None
    ) -> AuthResult:
        """Send verification ticket"""
        key = "Phone" if flag == FLAG_PHONE else "Email"

        r = self.session.get(
            f"https://account.xiaomi.com/identity/auth/verify{key}",
            cookies={"identity_session": identity_session},
            params={"_flag": flag, "_json": "true"},
        )
        res1 = parse_auth_response(r.content)
        assert res1["code"] == 0, res1

        if captcha_code:
            cookies = {"identity_session": identity_session, "ick": self.auth["ick"]}
            data = {"retry": 0, "icode": captcha_code, "_json": "true"}
        else:
            cookies = {"identity_session": identity_session}
            data = {"retry": 0, "icode": "", "_json": "true"}

        r = self.session.post(
            f"https://account.xiaomi.com/identity/auth/send{key}Ticket",
            cookies=cookies,
            data=data,
        )
        res2 = parse_auth_response(r.content)

        self.auth = {"flag": flag, "identity_session": identity_session}

        if captcha_url := res2.get("captchaUrl"):
            data = self._get_captcha_url(captcha_url)
            self.auth["ick"] = data["ick"]
            return {"ok": False, "captcha": data["image"]}

        assert res2["code"] == 0, res2

        return {"ok": False, "verify": res1[f"masked{key}"]}

    def get_devices(self) -> list:
        """Get device list (stub for compatibility)"""
        # This would require full request encryption implementation
        # For login purposes, we don't need this
        return []


class XiaomiLogin:
    """Handles Xiaomi account login with interactive prompts"""
    
    def __init__(self):
        self.cloud = MiCloudSync()
    
    def perform_login(self, username: str, password: str) -> Optional[Dict]:
        """
        Perform interactive login with captcha and 2FA support
        
        Args:
            username: Xiaomi account username
            password: Xiaomi account password
            
        Returns:
            Dict with token data if successful, None otherwise
        """
        print(f"\n🔐 Attempting login for {username}...")
        result = self.cloud.login(username, password)
        
        if result.get("ok"):
            return self._handle_success(result)
        
        elif result.get("captcha"):
            return self._handle_captcha(result)
        
        elif result.get("verify"):
            return self._handle_verify(result)
        
        else:
            print(f"\n❌ Login Failed")
            print(f"Result: {result}")
            if result.get("exception"):
                print(f"Exception: {result.get('exception')}")
            return None
    
    def _handle_success(self, result: Dict) -> Dict:
        """Handle successful login"""
        print("\n✅ Login SUCCESS!")
        
        # Extract token information
        token_str = result.get('token', '')
        
        # Parse token (format: "userId:passToken")
        user_id = ""
        pass_token = ""
        
        if ':' in token_str:
            parts = token_str.split(':', 1)
            user_id = parts[0]
            pass_token = parts[1]
        
        # Get ssecurity from cloud object
        ssecurity = ""
        if self.cloud.ssecurity:
            ssecurity = base64.b64encode(self.cloud.ssecurity).decode('utf-8')
        
        token_data = {
            "userId": user_id,
            "passToken": pass_token,
            "ssecurity": ssecurity
        }
        
        print(f"Token: {token_str}")
        
        # Try to fetch devices to verify
        print("\n📱 Fetching devices...")
        try:
            devices = self.cloud.get_devices()
            if devices:
                print(f"Found {len(devices)} devices:")
                for device in devices[:5]:  # Show first 5
                    print(f"  - {device.get('name')} ({device.get('model')}) - DID: {device.get('did')}")
            else:
                print("Device list not available (login successful)")
        except Exception as e:
            _LOGGER.debug(f"Could not fetch devices: {e}")
            print("Device list not available (login successful)")
        
        return token_data
    
    def _handle_captcha(self, result: Dict) -> Optional[Dict]:
        """Handle captcha challenge"""
        print("\n🖼️  Captcha Required")

        captcha_image = result.get("captcha")

        # Create data/captcha directory if it doesn't exist
        captcha_dir = Path("data/captcha")
        captcha_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename with timestamp
        timestamp = int(time.time())
        captcha_path = captcha_dir / f"captcha_{timestamp}.png"

        # Write captcha image to file
        captcha_path.write_bytes(captcha_image)

        print(f"📸 Captcha image saved to: {captcha_path}")

        # Get absolute path for browser
        captcha_abs_path = captcha_path.resolve()

        # Try to open in browser
        try:
            webbrowser.open(f"file://{captcha_abs_path}")
            print("✅ Captcha image opened in browser")
        except Exception as e:
            print(f"⚠️  Could not open browser: {e}")
            print(f"Please open the file manually: {captcha_abs_path}")

        # Get user input
        code = input("\nEnter the captcha code: ").strip()

        # Note: Keeping captcha file for debugging purposes (not deleting)
        
        if not code:
            print("❌ No code entered. Aborting.")
            return None
        
        print("🔄 Submitting captcha...")
        captcha_result = self.cloud.login_captcha(code)
        
        if captcha_result.get("ok"):
            return self._handle_success(captcha_result)
        
        elif captcha_result.get("verify"):
            # Captcha passed, now need 2FA
            return self._handle_verify(captcha_result)
        
        elif captcha_result.get("captcha"):
            print("\n❌ Captcha Incorrect!")
            print("Please try again later.")
            return None
        
        else:
            print(f"\n❌ Login Failed!")
            print(f"Result: {captcha_result}")
            if captcha_result.get("exception"):
                print(f"Exception: {captcha_result.get('exception')}")
            return None
    
    def _handle_verify(self, result: Dict) -> Optional[Dict]:
        """Handle 2FA verification"""
        print("\n⚠️  Two-Factor Authentication Required")
        print(f"📱 Verification code sent to: {result.get('verify')}")
        
        code = input("\nEnter the verification code: ").strip()
        
        if not code:
            print("❌ No code entered. Aborting.")
            return None
        
        print("🔄 Verifying code...")
        verify_result = self.cloud.login_verify(code)
        
        if verify_result.get("ok"):
            return self._handle_success(verify_result)
        else:
            print(f"\n❌ Verification Failed!")
            print(f"Result: {verify_result}")
            if verify_result.get("exception"):
                print(f"Exception: {verify_result.get('exception')}")
            
            if verify_result.get("captcha"):
                print("\n⚠️  Captcha triggered after failed verification.")
                print("Please wait a few minutes and try again.")
            
            return None
    
    def close(self):
        """Close the cloud session"""
        if self.cloud:
            self.cloud.close()


def main():
    """Main entry point for login tool"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Xiaomi Login Tool")
    parser.add_argument("--config", default="users.json", help="Path to users.json config file")
    args = parser.parse_args()
    
    config_mgr = ConfigManager(args.config)
    users = config_mgr.get_users()
    
    if not users:
        print(f"❌ No users found in {args.config}")
        print("Please add users to the configuration file first.")
        return
    
    for user in users:
        username = user.get("username")
        password = user.get("password")
        
        if not username or not password:
            print(f"⚠️  Skipping incomplete user profile")
            continue
        
        login = XiaomiLogin()
        
        try:
            token_data = login.perform_login(username, password)
            
            if token_data:
                print("\n💾 Saving token to config...")
                config_mgr.update_user_token(username, token_data)
                print(f"✅ Token saved for {username}")
            else:
                print(f"❌ Login failed for {username}")
        
        except Exception as e:
            print(f"❌ Error during login: {e}")
            _LOGGER.exception("Login error")
        
        finally:
            login.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
