from pathlib import Path

from ..config import DATA_DIR

KEY_FILE = DATA_DIR / ".secrets_key"

SENSITIVE_KEYS = {"openai_api_key", "openrouter_api_key", "github_token"}


def _load_or_create_key() -> bytes:
    if KEY_FILE.exists():
        return KEY_FILE.read_text(encoding="utf-8").strip().encode()
    from cryptography.fernet import Fernet

    key = Fernet.generate_key()
    KEY_FILE.write_text(key.decode("utf-8"), encoding="utf-8")
    try:
        import os

        os.chmod(KEY_FILE, 0o600)
    except OSError:
        pass
    return key


_cipher = None


def _get_cipher():
    global _cipher
    if _cipher is None:
        from cryptography.fernet import Fernet

        _cipher = Fernet(_load_or_create_key())
    return _cipher


def encrypt_value(value: str) -> str:
    if not value:
        return value
    return "enc:" + _get_cipher().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_value(value: str) -> str:
    if not value:
        return value
    if not value.startswith("enc:"):
        return value
    try:
        return _get_cipher().decrypt(value[4:].encode("utf-8")).decode("utf-8")
    except Exception:
        return value


def is_encrypted(value: str) -> bool:
    return bool(value and value.startswith("enc:"))
