"""
Token encryption/decryption using AES-256-GCM with per-user key derivation.

Key = PBKDF2(MASTER_SECRET + discord_uid, salt, iterations=260000)
Stored = base64(salt + nonce + ciphertext + tag)
"""

import os
import base64
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from bot.config import MASTER_SECRET

SALT_SIZE = 16
NONCE_SIZE = 12
KEY_LENGTH = 32  # AES-256
ITERATIONS = 260_000


def _derive_key(discord_uid: str, salt: bytes) -> bytes:
    """Derive a 256-bit key from MASTER_SECRET + discord_uid."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_LENGTH,
        salt=salt,
        iterations=ITERATIONS,
    )
    material = (MASTER_SECRET + discord_uid).encode("utf-8")
    return kdf.derive(material)


def encrypt_token(token: str, discord_uid: str) -> str:
    """
    Encrypt a token with a per-user key.
    Returns base64-encoded string: salt(16) + nonce(12) + ciphertext + tag(16).
    """
    salt = os.urandom(SALT_SIZE)
    key = _derive_key(discord_uid, salt)
    nonce = os.urandom(NONCE_SIZE)

    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, token.encode("utf-8"), None)

    # ciphertext already includes the 16-byte tag (appended by AESGCM)
    blob = salt + nonce + ciphertext
    return base64.b64encode(blob).decode("ascii")


def decrypt_token(encrypted: str, discord_uid: str) -> str:
    """
    Decrypt a token encrypted by encrypt_token().
    """
    blob = base64.b64decode(encrypted)
    salt = blob[:SALT_SIZE]
    nonce = blob[SALT_SIZE : SALT_SIZE + NONCE_SIZE]
    ciphertext = blob[SALT_SIZE + NONCE_SIZE :]

    key = _derive_key(discord_uid, salt)
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")


def get_token_hint(token: str) -> str:
    """Return last 4 characters of a token for display (e.g. '...a1b2')."""
    if len(token) <= 4:
        return token
    return f"...{token[-4:]}"
