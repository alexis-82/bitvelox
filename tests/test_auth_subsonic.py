import hashlib

from app.auth import verify_subsonic_credentials


def test_token_auth_success():
    password = "hunter2"
    salt = "s0me-salt"
    token = hashlib.md5((password + salt).encode()).hexdigest()
    assert verify_subsonic_credentials(password, t=token, s=salt) is True


def test_token_auth_wrong_token():
    assert verify_subsonic_credentials("hunter2", t="deadbeef" * 4, s="salt") is False


def test_password_plain_success():
    assert verify_subsonic_credentials("hunter2", p="hunter2") is True


def test_password_plain_wrong():
    assert verify_subsonic_credentials("hunter2", p="wrong") is False


def test_password_enc_hex_success():
    p = "hunter2"
    enc = "enc:" + p.encode().hex()
    assert verify_subsonic_credentials(p, p=enc) is True


def test_password_enc_hex_invalid_hex():
    assert verify_subsonic_credentials("x", p="enc:not-hex") is False


def test_no_creds_provided():
    assert verify_subsonic_credentials("x") is False
