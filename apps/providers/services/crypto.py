import json
from typing import Any, Dict

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


class CredentialEncryptionError(RuntimeError):
    pass


def _get_fernet() -> Fernet:
    key = getattr(settings, "ENCRYPTION_KEY", "") or ""
    if not key or key == "CHANGE_ME_GENERATE_A_FERNET_KEY":
        raise CredentialEncryptionError(
            "ENCRYPTION_KEY is missing. Set ENCRYPTION_KEY in your .env using a Fernet key."
        )
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as exc:
        raise CredentialEncryptionError("Invalid ENCRYPTION_KEY format.") from exc


def encrypt_json(payload: Dict[str, Any]) -> str:
    data = json.dumps(payload).encode("utf-8")
    token = _get_fernet().encrypt(data)
    return token.decode("utf-8")


def decrypt_json(token: str) -> Dict[str, Any]:
    """
    Returns a dict of credentials.

    IMPORTANT:
    - If ENCRYPTION_KEY changes, older stored tokens become undecryptable.
    - In that case we raise a clear error so the UI tells the user to reconnect.
    """
    if not token:
        return {}
    try:
        raw = _get_fernet().decrypt(token.encode("utf-8"))
        return json.loads(raw.decode("utf-8"))
    except InvalidToken as exc:
        raise CredentialEncryptionError(
            "Could not decrypt saved credentials. "
            "This usually happens if ENCRYPTION_KEY changed. "
            "Fix: delete the provider connection row (or wipe DB) and reconnect."
        ) from exc
