import pytest
from fastapi.testclient import TestClient

from app.auth import bootstrap_admin_user
from app.config import get_settings
from app.db import Base, get_engine, get_session, init_db
from app.main import app

AUTH = {"u": "admin", "p": "test-password", "v": "1.13.0", "c": "test"}


@pytest.fixture(autouse=True)
def _fresh_db():
    settings = get_settings()
    init_db(settings.db_path)
    Base.metadata.drop_all(get_engine())
    Base.metadata.create_all(get_engine())
    s = get_session()
    bootstrap_admin_user(s, settings.admin_user, settings.admin_password)
    s.close()


def test_ping_json():
    with TestClient(app) as client:
        r = client.get("/rest/ping.view", params={**AUTH, "f": "json"})
        assert r.status_code == 200
        body = r.json()
        assert body["subsonic-response"]["status"] == "ok"
        assert body["subsonic-response"]["version"] == "1.13.0"


def test_ping_xml_default():
    with TestClient(app) as client:
        r = client.get("/rest/ping.view", params=AUTH)
        assert r.status_code == 200
        assert "application/xml" in r.headers["content-type"]
        assert 'status="ok"' in r.text
        assert 'version="1.13.0"' in r.text


def test_ping_wrong_password_returns_error_40():
    with TestClient(app) as client:
        r = client.get("/rest/ping.view", params={**AUTH, "p": "WRONG", "f": "json"})
        assert r.status_code == 200
        body = r.json()
        assert body["subsonic-response"]["status"] == "failed"
        assert body["subsonic-response"]["error"]["code"] == 40


def test_ping_missing_params_returns_error_10():
    with TestClient(app) as client:
        r = client.get("/rest/ping.view", params={"f": "json"})
        body = r.json()
        assert body["subsonic-response"]["status"] == "failed"
        assert body["subsonic-response"]["error"]["code"] == 10
