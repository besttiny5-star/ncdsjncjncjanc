from __future__ import annotations

import base64
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken


class CredentialEncryptor:
    def __init__(self, key: Optional[bytes]) -> None:
        self._fernet: Optional[Fernet]
        if key:
            try:
                # allow base64 urlsafe strings or raw key material
                decoded = base64.urlsafe_b64decode(key)
                if len(decoded) == 32:
                    self._fernet = Fernet(base64.urlsafe_b64encode(decoded))
                else:
                    self._fernet = Fernet(key)
            except Exception:  # noqa: BLE001 - best effort, fallback to disabled encryption
                self._fernet = None
        else:
            self._fernet = None

    def encrypt(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return value
        if self._fernet is None:
            return value
        token = self._fernet.encrypt(value.encode("utf-8"))
        return token.decode("utf-8")

    def decrypt(self, token: Optional[str]) -> Optional[str]:
        if not token:
            return token
        if self._fernet is None:
            return token
        try:
            value = self._fernet.decrypt(token.encode("utf-8"))
            return value.decode("utf-8")
        except InvalidToken:
            return None


def mask_secret(value: Optional[str]) -> str:
    if not value:
        return "—"
    if len(value) <= 4:
        return "***"
    return f"***{value[-4:]}"
