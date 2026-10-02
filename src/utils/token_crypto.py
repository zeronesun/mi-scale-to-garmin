"""
Token 设备绑定加密

AES-256-GCM 加密 token 落盘，设备标识参与密钥派生。
token 文件离开原设备后解密失败（InvalidTag），走重新认证流程。

落盘格式（v=1）：
{
    "v": 1,
    "salt": "<32 hex>",
    "nonce": "<24 hex>",
    "ciphertext": "<hex>",
    "tag": "<32 hex>"
}
"""
import json
import os
from typing import Any, Dict, Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

from utils.device_id import get_device_key

_INFO = b"mi-scale-to-garmin/v1"
_SALT_LEN = 16
_NONCE_LEN = 12
_TAG_LEN = 16  # GCM tag 固定 16 字节


def _derive_key(device_key: bytes, salt: bytes) -> bytes:
    """HKDF-SHA256 派生 AES-256 密钥"""
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=_INFO,
    )
    return hkdf.derive(device_key)


def encrypt_token(plaintext: Dict[str, Any]) -> Dict[str, str]:
    """
    加密 token dict → 落盘格式 dict

    Args:
        plaintext: 要加密的 token 字典（如 {"userId": ..., "passToken": ...}）

    Returns:
        {"v": 1, "salt": ..., "nonce": ..., "ciphertext": ..., "tag": ...}
    """
    device_key = get_device_key()
    salt = os.urandom(_SALT_LEN)
    nonce = os.urandom(_NONCE_LEN)
    enc_key = _derive_key(device_key, salt)

    plaintext_bytes = json.dumps(plaintext, ensure_ascii=False).encode('utf-8')
    aesgcm = AESGCM(enc_key)
    # AESGCM.encrypt 返回 ciphertext + tag（tag 在最后 16 字节）
    ct_with_tag = aesgcm.encrypt(nonce, plaintext_bytes, None)
    ciphertext = ct_with_tag[:-_TAG_LEN]
    tag = ct_with_tag[-_TAG_LEN:]

    return {
        "v": 1,
        "salt": salt.hex(),
        "nonce": nonce.hex(),
        "ciphertext": ciphertext.hex(),
        "tag": tag.hex(),
    }


def decrypt_token(data: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """
    解密落盘格式 dict → token dict

    Args:
        data: 落盘格式（含 v/salt/nonce/ciphertext/tag）

    Returns:
        解密后的 token dict；设备不匹配或格式无效时返回 None
    """
    if data.get("v") != 1:
        return None
    try:
        salt = bytes.fromhex(data["salt"])
        nonce = bytes.fromhex(data["nonce"])
        ciphertext = bytes.fromhex(data["ciphertext"])
        tag = bytes.fromhex(data["tag"])
    except (KeyError, ValueError):
        return None

    device_key = get_device_key()
    enc_key = _derive_key(device_key, salt)

    try:
        aesgcm = AESGCM(enc_key)
        plaintext_bytes = aesgcm.decrypt(nonce, ciphertext + tag, None)
        return json.loads(plaintext_bytes.decode('utf-8'))
    except Exception:
        # InvalidTag 或任何解密失败 → 视为无有效 token
        return None


def is_encrypted(data: Dict[str, Any]) -> bool:
    """判断 token 数据是否为加密格式（v=1）"""
    return data.get("v") == 1


def load_token_file(path) -> Optional[Dict[str, Any]]:
    """
    读取 token 文件（自动识别明文/加密格式）

    - 加密格式（v=1）：解密返回明文 dict；设备不匹配返回 None
    - 明文格式（无 v 字段）：直接返回（兼容旧文件）

    Args:
        path: token 文件路径（Path 或 str）

    Returns:
        明文 token dict 或 None（不存在/无效/设备不匹配）
    """
    from pathlib import Path
    path = Path(path)
    if not path.exists():
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return None

    if is_encrypted(data):
        return decrypt_token(data)
    else:
        # 旧明文格式：直接返回
        return data


def save_token_file(path, token_data: Dict[str, Any]) -> None:
    """
    写入 token 文件（加密格式 v=1）

    Args:
        path: token 文件路径（Path 或 str）
        token_data: 明文 token dict
    """
    from pathlib import Path
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    encrypted = encrypt_token(token_data)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(encrypted, f, indent=4, ensure_ascii=False)


# 佳明 session 目录中不加密的文件（只含哈希，不敏感，且需明文读取）
_SKIP_FILES = {'account.json'}


def encrypt_session_dir(session_dir) -> None:
    """
    加密目录下 token .json 文件（佳明 session 目录用）

    对每个 .json 文件（排除 _SKIP_FILES）：读取 → 判断是否已加密 → 未加密则加密写回。
    已加密的文件跳过（幂等）。
    """
    from pathlib import Path
    session_dir = Path(session_dir)
    if not session_dir.exists():
        return
    for f in session_dir.glob('*.json'):
        if f.name in _SKIP_FILES:
            continue
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
            if is_encrypted(data):
                continue  # 已加密，跳过
            encrypted = encrypt_token(data)
            with open(f, 'w', encoding='utf-8') as fh:
                json.dump(encrypted, fh, indent=4, ensure_ascii=False)
        except Exception:
            pass  # 非 JSON 或读取失败，跳过


def decrypt_session_dir(session_dir) -> None:
    """
    解密目录下 token .json 文件（佳明 session 目录用）

    对每个 .json 文件（排除 _SKIP_FILES）：读取 → 判断是否加密 → 加密则解密写回明文。
    明文文件跳过（幂等）。garth 需要读明文，所以解密后 garth 正常 load。
    设备不匹配时删除 token 文件（让 garth 走重新登录）。
    """
    from pathlib import Path
    session_dir = Path(session_dir)
    if not session_dir.exists():
        return
    for f in session_dir.glob('*.json'):
        if f.name in _SKIP_FILES:
            continue
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
            if not is_encrypted(data):
                continue  # 明文，跳过
            plaintext = decrypt_token(data)
            if plaintext is None:
                # 设备不匹配，无法解密 → 删除文件（让 garth 走重新登录）
                f.unlink(missing_ok=True)
                continue
            with open(f, 'w', encoding='utf-8') as fh:
                json.dump(plaintext, fh, indent=4, ensure_ascii=False)
        except Exception:
            pass  # 非 JSON 或读取失败，跳过
