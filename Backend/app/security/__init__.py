from __future__ import annotations

"""Security helpers for device password encryption.

Migration plan:
* New writes always use Fernet with the active key (first key in DEVICE_PASSWORD_KEYS).
* Reads detect legacy values (no fernet:v1: prefix), decrypt using legacy mode, and
  re-encrypt on access when a key is available.
* To rotate keys, prepend the new key in DEVICE_PASSWORD_KEYS and keep older keys
  in the list until all data has been re-encrypted.
"""

import os
from functools import lru_cache
from typing import List, Optional, Tuple

from cryptography.fernet import Fernet, InvalidToken

FERNET_PREFIX = "fernet:v1:"
LEGACY_MODE_ENV = "DEVICE_PASSWORD_LEGACY_MODE"
KEYS_ENV = "DEVICE_PASSWORD_KEYS"
KEY_ENV = "DEVICE_PASSWORD_KEY"
KEYS_FILE_ENV = "DEVICE_PASSWORD_KEYS_FILE"
KEY_FILE_ENV = "DEVICE_PASSWORD_KEY_FILE"


def _split_keys(raw: str) -> List[str]:
    return [item.strip() for item in raw.replace("\n", ",").split(",") if item.strip()]


def _read_keys_from_file(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as handle:
        return _split_keys(handle.read())


@lru_cache(maxsize=1)
def _load_key_strings() -> List[str]:
    keys: List[str] = []
    file_path = os.getenv(KEYS_FILE_ENV) or os.getenv(KEY_FILE_ENV)
    if file_path:
        keys.extend(_read_keys_from_file(file_path))
    raw_keys = os.getenv(KEYS_ENV) or os.getenv(KEY_ENV) or ""
    if raw_keys:
        keys.extend(_split_keys(raw_keys))
    return keys


@lru_cache(maxsize=1)
def _load_fernets() -> List[Fernet]:
    return [Fernet(key) for key in _load_key_strings()]


def _require_fernets() -> List[Fernet]:
    fernets = _load_fernets()
    if not fernets:
        raise RuntimeError(
            "Encryption key(s) missing. Set DEVICE_PASSWORD_KEYS or DEVICE_PASSWORD_KEY "
            "or provide DEVICE_PASSWORD_KEYS_FILE/DEVICE_PASSWORD_KEY_FILE."
        )
    return fernets


def _legacy_decrypt(value: str) -> str:
    mode = os.getenv(LEGACY_MODE_ENV, "reverse").strip().lower()
    if mode == "plaintext":
        return value
    return value[::-1]


def _decrypt_with_fernets(token: bytes) -> Tuple[str, int]:
    fernets = _require_fernets()
    for index, fernet in enumerate(fernets):
        try:
            return fernet.decrypt(token).decode("utf-8"), index
        except InvalidToken:
            continue
    raise ValueError("Unable to decrypt device password with configured keys.")


def encrypt_password(password: str) -> str:
    if not password:
        return ""
    primary = _require_fernets()[0]
    token = primary.encrypt(password.encode("utf-8")).decode("utf-8")
    return f"{FERNET_PREFIX}{token}"


def decrypt_password_with_migration(password: str) -> Tuple[str, Optional[str]]:
    if not password:
        return "", None
    if password.startswith(FERNET_PREFIX):
        token = password[len(FERNET_PREFIX):].encode("utf-8")
        plaintext, index = _decrypt_with_fernets(token)
        if index == 0:
            return plaintext, None
        return plaintext, encrypt_password(plaintext)
    plaintext = _legacy_decrypt(password)
    try:
        return plaintext, encrypt_password(plaintext)
    except RuntimeError:
        return plaintext, None


def decrypt_password(password: str) -> str:
    plaintext, _ = decrypt_password_with_migration(password)
    return plaintext
