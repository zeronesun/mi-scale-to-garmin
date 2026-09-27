"""
Unit tests for core.account (mask_account / resolve_display_name / find_duplicate_nickname).
"""

import unittest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.account import (
    mask_account,
    resolve_display_name,
    find_duplicate_nickname,
    find_user_by_username,
)
from core.models import UserModel


def make_user(username="13800005678", nickname=None, **kw):
    return UserModel(username=username, password="", nickname=nickname, **kw)


class TestMaskAccount(unittest.TestCase):
    """mask_account 脱敏规则。"""

    def test_phone(self):
        self.assertEqual(mask_account("13800005678"), "138****5678")

    def test_email(self):
        self.assertEqual(mask_account("sun@example.com"), "s***@example.com")

    def test_long_other(self):
        self.assertEqual(mask_account("abcdef"), "ab****ef")

    def test_short(self):
        self.assertEqual(mask_account("ab"), "****")

    def test_empty(self):
        self.assertEqual(mask_account(""), "")
        self.assertEqual(mask_account(None), "")


class TestResolveDisplayName(unittest.TestCase):
    """resolve_display_name：昵称 → 脱敏兜底 → 重名消歧。"""

    def test_with_nickname(self):
        user = make_user(nickname="老婆")
        self.assertEqual(resolve_display_name(user), "老婆")

    def test_without_nickname_falls_back_to_masked(self):
        user = make_user()
        self.assertEqual(resolve_display_name(user), "138****5678")

    def test_duplicate_disambiguation(self):
        a = make_user(username="13800005678", nickname="老婆")
        b = make_user(username="13900001234", nickname="老婆")
        self.assertEqual(resolve_display_name(a, [a, b]), "老婆·138****5678")
        self.assertEqual(resolve_display_name(b, [a, b]), "老婆·139****1234")

    def test_duplicate_case_insensitive(self):
        a = make_user(username="13800005678", nickname="老婆")
        b = make_user(username="13900001234", nickname="老婆 ")
        self.assertEqual(resolve_display_name(a, [a, b]), "老婆·138****5678")

    def test_unique_nickname_no_suffix(self):
        a = make_user(username="13800005678", nickname="老婆")
        b = make_user(username="13900001234", nickname="我")
        self.assertEqual(resolve_display_name(a, [a, b]), "老婆")

    def test_dict_user(self):
        user = {"username": "13800005678", "nickname": "老婆"}
        self.assertEqual(resolve_display_name(user), "老婆")
        user2 = {"username": "13800005678"}
        self.assertEqual(resolve_display_name(user2), "138****5678")

    def test_empty_nickname_treated_as_unset(self):
        user = make_user(nickname="   ")
        self.assertEqual(resolve_display_name(user), "138****5678")


class TestFindDuplicateNickname(unittest.TestCase):
    """find_duplicate_nickname 查重（输入时拦截）。"""

    def test_no_duplicate(self):
        users = [make_user(nickname="我")]
        self.assertFalse(find_duplicate_nickname("老婆", users))

    def test_duplicate(self):
        users = [make_user(nickname="老婆")]
        self.assertTrue(find_duplicate_nickname("老婆", users))

    def test_case_and_space_insensitive(self):
        users = [make_user(nickname="老婆")]
        self.assertTrue(find_duplicate_nickname(" 老婆 ", users))

    def test_empty_nickname_never_duplicates(self):
        users = [make_user(nickname="老婆")]
        self.assertFalse(find_duplicate_nickname("", users))

    def test_exclude_username(self):
        users = [make_user(username="13800005678", nickname="老婆")]
        self.assertFalse(
            find_duplicate_nickname("老婆", users, exclude_username="13800005678"))

    def test_dict_users(self):
        users = [{"username": "13800005678", "nickname": "老婆"}]
        self.assertTrue(find_duplicate_nickname("老婆", users))


class TestFindUserByUsername(unittest.TestCase):
    """find_user_by_username 按功能键查找。"""

    def test_found(self):
        user = make_user()
        self.assertIs(find_user_by_username([user], "13800005678"), user)

    def test_not_found(self):
        user = make_user()
        self.assertIsNone(find_user_by_username([user], "13900001234"))

    def test_dict_users(self):
        d = {"username": "13800005678"}
        self.assertIs(find_user_by_username([d], "13800005678"), d)


class TestUserModelNicknameRoundTrip(unittest.TestCase):
    """UserModel nickname 字段 to_dict/from_dict 往返。"""

    def test_roundtrip_with_nickname(self):
        user = make_user(nickname="老婆")
        d = user.to_dict()
        self.assertEqual(d.get("nickname"), "老婆")
        restored = UserModel.from_dict(d)
        self.assertEqual(restored.nickname, "老婆")

    def test_roundtrip_without_nickname(self):
        user = make_user()
        d = user.to_dict()
        self.assertNotIn("nickname", d)  # 空昵称不写入（避免残留空键）
        restored = UserModel.from_dict(d)
        self.assertIsNone(restored.nickname)


if __name__ == "__main__":
    unittest.main()
