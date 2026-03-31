"""
Cryptography utilities — encryption of sensitive data (api_secret etc.)
"""

from helpers.path import Paths
from helpers.globals import GlobalStore

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import logging
import os
import base64
from pathlib import Path


logger = logging.getLogger(__name__)


def _get_master_key() -> bytes:
    """Получает или создаёт master key."""
    config = GlobalStore.get().require("config")
    key_file = Path(config.get("db.masterkey_file", str(Paths.DB_MASTERKEY_FILE)))

    if key_file.is_file():
        return key_file.read_bytes()

    # Генерируем новый мастер-ключ
    master_key = os.urandom(32)
    key_file.write_bytes(master_key)
    key_file.chmod(0o600)

    logger.info(f"Generated new master key: {key_file}")
    return master_key


def encrypt(data: str) -> str:
    """Шифрует строку с помощью AES-GCM."""
    master_key = _get_master_key()
    aesgcm = AESGCM(master_key)

    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, data.encode("utf-8"), None)

    combined = nonce + ciphertext
    return base64.urlsafe_b64encode(combined).decode("utf-8")


def decrypt(encrypted_data: str) -> str:
    """Расшифровывает строку."""
    master_key = _get_master_key()
    aesgcm = AESGCM(master_key)

    combined = base64.urlsafe_b64decode(encrypted_data)
    nonce = combined[:12]
    ciphertext = combined[12:]

    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")