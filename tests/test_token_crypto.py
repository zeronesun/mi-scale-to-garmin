"""
Unit tests for utils.token_crypto (设备绑定 token 加密) + utils.device_id.

覆盖：
- 加解密往返
- 设备不匹配（mock device_key）
- 旧明文格式兼容
- session 目录加解密 + account.json 跳过
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils import token_crypto
from utils.token_crypto import (
    encrypt_token,
    decrypt_token,
    is_encrypted,
    load_token_file,
    save_token_file,
    encrypt_session_dir,
    decrypt_session_dir,
)
from utils.device_id import get_device_key


def _sample_token():
    return {
        "userId": "12345",
        "passToken": "abc-def-ghi",
        "ssecurity": "sec-token",
        "account_hash": "deadbeef",
    }


class TestDeviceId(unittest.TestCase):
    """device_id 基本行为。"""

    def test_returns_32_bytes(self):
        key = get_device_key()
        self.assertEqual(len(key), 32)
        self.assertIsInstance(key, bytes)

    def test_deterministic(self):
        # 同一设备多次调用结果一致
        self.assertEqual(get_device_key(), get_device_key())


class TestEncryptDecryptRoundtrip(unittest.TestCase):
    """加解密往返。"""

    def test_roundtrip(self):
        plaintext = _sample_token()
        encrypted = encrypt_token(plaintext)
        self.assertTrue(is_encrypted(encrypted))
        self.assertEqual(encrypted["v"], 1)
        # 密文不应包含明文 token 值
        self.assertNotIn("abc-def-ghi", json.dumps(encrypted))
        decrypted = decrypt_token(encrypted)
        self.assertEqual(decrypted, plaintext)

    def test_different_salt_each_time(self):
        e1 = encrypt_token(_sample_token())
        e2 = encrypt_token(_sample_token())
        # 每次 salt/nonce 不同
        self.assertNotEqual(e1["salt"], e2["salt"])
        self.assertNotEqual(e1["nonce"], e2["nonce"])
        # 但都能解回同一明文
        self.assertEqual(decrypt_token(e1), decrypt_token(e2))


class TestDeviceMismatch(unittest.TestCase):
    """设备不匹配 → 解密失败返回 None。"""

    def test_wrong_device_key(self):
        plaintext = _sample_token()
        encrypted = encrypt_token(plaintext)
        # mock 一个不同的 device_key 模拟换设备
        with patch.object(token_crypto, "get_device_key",
                          return_value=b"\x00" * 32):
            self.assertIsNone(decrypt_token(encrypted))

    def test_load_file_wrong_device(self):
        plaintext = _sample_token()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "xiaomi_auth_test.json"
            save_token_file(path, plaintext)
            # 换设备读取 → None
            with patch.object(token_crypto, "get_device_key",
                              return_value=b"\x00" * 32):
                self.assertIsNone(load_token_file(path))


class TestLegacyPlaintextCompat(unittest.TestCase):
    """旧明文格式兼容（无 v 字段）。"""

    def test_load_plaintext(self):
        plaintext = _sample_token()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "xiaomi_auth_test.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(plaintext, f)
            # 明文格式直接返回（不解密）
            self.assertEqual(load_token_file(path), plaintext)

    def test_is_encrypted_false_for_plaintext(self):
        self.assertFalse(is_encrypted(_sample_token()))
        self.assertFalse(is_encrypted({}))
        self.assertFalse(is_encrypted({"v": 2}))

    def test_load_nonexistent(self):
        self.assertIsNone(load_token_file("/nonexistent/path.json"))

    def test_load_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text("not json {", encoding="utf-8")
            self.assertIsNone(load_token_file(path))


class TestSaveLoadFile(unittest.TestCase):
    """save_token_file / load_token_file 文件往返。"""

    def test_file_roundtrip(self):
        plaintext = _sample_token()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sub" / "xiaomi_auth_test.json"
            save_token_file(path, plaintext)
            # 文件内容是加密格式
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(is_encrypted(raw))
            # 读回明文
            self.assertEqual(load_token_file(path), plaintext)


class TestSessionDir(unittest.TestCase):
    """佳明 session 目录加解密。"""

    def _make_session_dir(self, tmp):
        d = Path(tmp) / "garmin" / "testuser"
        d.mkdir(parents=True)
        # oauth1_token.json（token，应加密）
        (d / "oauth1_token.json").write_text(
            json.dumps({"oauth_token": "t1", "oauth_token_secret": "s1"}),
            encoding="utf-8")
        # oauth2_token.json（token，应加密）
        (d / "oauth2_token.json").write_text(
            json.dumps({"access_token": "a1", "refresh_token": "r1"}),
            encoding="utf-8")
        # account.json（绑定，应跳过不加密）
        (d / "account.json").write_text(
            json.dumps({"account_hash": "deadbeef"}),
            encoding="utf-8")
        return d

    def test_encrypt_skips_account(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = self._make_session_dir(tmp)
            encrypt_session_dir(d)
            # token 文件已加密
            self.assertTrue(is_encrypted(
                json.loads((d / "oauth1_token.json").read_text(encoding="utf-8"))))
            self.assertTrue(is_encrypted(
                json.loads((d / "oauth2_token.json").read_text(encoding="utf-8"))))
            # account.json 保持明文
            self.assertFalse(is_encrypted(
                json.loads((d / "account.json").read_text(encoding="utf-8"))))

    def test_decrypt_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = self._make_session_dir(tmp)
            encrypt_session_dir(d)
            decrypt_session_dir(d)
            # token 文件恢复明文
            self.assertEqual(
                json.loads((d / "oauth1_token.json").read_text(encoding="utf-8")),
                {"oauth_token": "t1", "oauth_token_secret": "s1"})
            self.assertEqual(
                json.loads((d / "oauth2_token.json").read_text(encoding="utf-8")),
                {"access_token": "a1", "refresh_token": "r1"})
            # account.json 不受影响
            self.assertEqual(
                json.loads((d / "account.json").read_text(encoding="utf-8")),
                {"account_hash": "deadbeef"})

    def test_decrypt_wrong_device_deletes_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = self._make_session_dir(tmp)
            encrypt_session_dir(d)
            # 换设备解密 → token 文件被删除，account.json 保留
            with patch.object(token_crypto, "get_device_key",
                              return_value=b"\x00" * 32):
                decrypt_session_dir(d)
            self.assertFalse((d / "oauth1_token.json").exists())
            self.assertFalse((d / "oauth2_token.json").exists())
            self.assertTrue((d / "account.json").exists())

    def test_encrypt_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = self._make_session_dir(tmp)
            encrypt_session_dir(d)
            first = (d / "oauth1_token.json").read_text(encoding="utf-8")
            # 再次加密（幂等，已加密跳过）
            encrypt_session_dir(d)
            second = (d / "oauth1_token.json").read_text(encoding="utf-8")
            self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
