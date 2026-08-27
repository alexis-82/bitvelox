from __future__ import annotations

import hashlib
import logging
import secrets

from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.models import AdminUser

logger = logging.getLogger(__name__)

_pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _pwd_context.verify(password, password_hash)
    except Exception:
        return False


def _generate_random_password() -> str:
    return secrets.token_urlsafe(16)


def bootstrap_admin_user(
    session: Session, username: str, password: str | None
) -> AdminUser:
    existing = session.query(AdminUser).first()

    if existing is None:
        if password is None or password == "":
            password = _generate_random_password()
            logger.warning(
                "ADMIN_PASSWORD not set — generated random password: %s (save this, "
                "it will NOT be shown again)",
                password,
            )
        user = AdminUser(
            username=username,
            password_hash=hash_password(password),
            plain_password=password,
        )
        session.add(user)
        session.commit()
        return user

    changed = False
    if existing.username != username:
        existing.username = username
        changed = True
    if password and existing.plain_password != password:
        existing.password_hash = hash_password(password)
        existing.plain_password = password
        changed = True
    if changed:
        session.commit()
        logger.info("admin credentials synced from environment")
    return existing


def _decode_enc_hex(value: str) -> str | None:
    if not value.startswith("enc:"):
        return None
    try:
        return bytes.fromhex(value[4:]).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None


def verify_subsonic_credentials(
    plain_password: str,
    *,
    p: str | None = None,
    t: str | None = None,
    s: str | None = None,
) -> bool:
    """Verify Subsonic API auth against the known plaintext admin password.

    Subsonic supports:
    - p=<password> in plain text
    - p=enc:<hex-of-password> obfuscated
    - t=md5(password + salt), s=<salt> (token auth)
    """
    if t and s:
        expected = hashlib.md5((plain_password + s).encode("utf-8")).hexdigest()
        return secrets.compare_digest(expected, t)
    if p is not None:
        decoded = _decode_enc_hex(p) if p.startswith("enc:") else p
        if decoded is None:
            return False
        return secrets.compare_digest(decoded, plain_password)
    return False
