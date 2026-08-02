import logging

from app.auth import bootstrap_admin_user, verify_password
from app.db import get_session, init_db
from app.models import AdminUser


def _fresh_db():
    init_db("sqlite:///:memory:")
    return get_session()


def test_bootstrap_creates_user_with_env_password():
    s = _fresh_db()
    bootstrap_admin_user(s, "admin", "s3cr3t")
    user = s.query(AdminUser).one()
    assert user.username == "admin"
    assert user.password_hash.startswith("$argon2")
    assert verify_password("s3cr3t", user.password_hash)
    s.close()


def test_bootstrap_generates_random_password_when_missing(caplog):
    caplog.set_level(logging.WARNING)
    s = _fresh_db()
    bootstrap_admin_user(s, "admin", None)
    user = s.query(AdminUser).one()
    assert user.password_hash.startswith("$argon2")
    assert "generated random password" in caplog.text
    s.close()


def test_bootstrap_no_override_on_second_call():
    s = _fresh_db()
    bootstrap_admin_user(s, "admin", "first-password")
    first_hash = s.query(AdminUser).one().password_hash

    bootstrap_admin_user(s, "admin", "different-password")
    users = s.query(AdminUser).all()
    assert len(users) == 1
    assert users[0].password_hash == first_hash
    assert verify_password("first-password", users[0].password_hash)
    assert not verify_password("different-password", users[0].password_hash)
    s.close()
