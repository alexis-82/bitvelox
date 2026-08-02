import pytest
from fastapi.testclient import TestClient

from app.admin import rate_limit
from app.auth import bootstrap_admin_user, verify_password
from app.config import get_settings
from app.db import Base, get_engine, get_session, init_db
from app.main import app
from app.models import AdminUser


@pytest.fixture(autouse=True)
def _fresh():
    settings = get_settings()
    init_db(settings.db_path)
    Base.metadata.drop_all(get_engine())
    Base.metadata.create_all(get_engine())
    s = get_session()
    bootstrap_admin_user(s, settings.admin_user, settings.admin_password)
    s.close()
    rate_limit.clear_all()


def test_login_success_and_dashboard():
    with TestClient(app) as client:
        r = client.get("/", follow_redirects=False)
        assert r.status_code == 302
        assert "/login" in r.headers["location"]

        r = client.post(
            "/login",
            data={"username": "admin", "password": "test-password"},
            follow_redirects=False,
        )
        assert r.status_code == 302
        assert r.headers["location"] == "/"

        r = client.get("/")
        assert r.status_code == 200
        assert "Library" in r.text


def test_dashboard_shows_version():
    from app import __version__
    with TestClient(app) as client:
        client.post(
            "/login",
            data={"username": "admin", "password": "test-password"},
            follow_redirects=False,
        )
        r = client.get("/")
        assert f"v{__version__}" in r.text


def test_dashboard_shows_brand():
    with TestClient(app) as client:
        client.post(
            "/login",
            data={"username": "admin", "password": "test-password"},
            follow_redirects=False,
        )
        r = client.get("/")
        assert "BitVelox" in r.text
        assert "mp3-server" not in r.text


def test_changelog_requires_login():
    with TestClient(app) as client:
        r = client.get("/changelog", follow_redirects=False)
        assert r.status_code == 302
        assert "/login" in r.headers["location"]


def test_changelog_renders_markdown_to_html():
    with TestClient(app) as client:
        client.post(
            "/login",
            data={"username": "admin", "password": "test-password"},
            follow_redirects=False,
        )
        r = client.get("/changelog")
        assert r.status_code == 200
        # Markdown headers (#, ##) get converted to <h1>/<h2>
        assert "<h1>" in r.text or "<h2>" in r.text
        # Contains recent version marker
        assert "0.3.0" in r.text or "Unreleased" in r.text


def test_dashboard_shows_changelog_link():
    with TestClient(app) as client:
        client.post(
            "/login",
            data={"username": "admin", "password": "test-password"},
            follow_redirects=False,
        )
        r = client.get("/")
        assert 'href="/changelog"' in r.text


def test_changelog_uses_env_var_override(monkeypatch, tmp_path):
    custom = tmp_path / "MY_CHANGELOG.md"
    custom.write_text("# Custom Changelog\n\n- special-marker-abc123\n", encoding="utf-8")
    monkeypatch.setenv("CHANGELOG_PATH", str(custom))
    with TestClient(app) as client:
        client.post(
            "/login",
            data={"username": "admin", "password": "test-password"},
            follow_redirects=False,
        )
        r = client.get("/changelog")
        assert r.status_code == 200
        assert "special-marker-abc123" in r.text


def test_changelog_404_when_no_file_found(monkeypatch, tmp_path, capsys):
    # Force all candidate paths to non-existent locations.
    monkeypatch.setenv("CHANGELOG_PATH", str(tmp_path / "does-not-exist.md"))
    from app.admin import routes as admin_routes
    monkeypatch.setattr(
        admin_routes,
        "_changelog_candidates",
        lambda: [tmp_path / "does-not-exist.md",
                 tmp_path / "also-missing.md"],
    )
    with TestClient(app) as client:
        client.post(
            "/login",
            data={"username": "admin", "password": "test-password"},
            follow_redirects=False,
        )
        r = client.get("/changelog")
    assert r.status_code == 404
    assert "CHANGELOG_PATH" in r.text
    # setup_logging installs a stdout handler; the WARNING is captured by capsys.
    out = capsys.readouterr().out
    assert "tried" in out.lower()
    assert "does-not-exist.md" in out


def test_login_wrong_password_flashes():
    with TestClient(app) as client:
        r = client.post(
            "/login",
            data={"username": "admin", "password": "nope"},
            follow_redirects=False,
        )
        assert r.status_code == 302
        r = client.get("/login")
        assert "Wrong username or password" in r.text


def test_login_rate_limit():
    with TestClient(app) as client:
        for _ in range(5):
            client.post(
                "/login",
                data={"username": "admin", "password": "nope"},
                follow_redirects=False,
            )
        r = client.post(
            "/login",
            data={"username": "admin", "password": "test-password"},
            follow_redirects=False,
        )
        assert r.status_code == 429


def test_rescan_endpoint(monkeypatch, tmp_path):
    monkeypatch.setenv("MUSIC_DIR", str(tmp_path))
    with TestClient(app) as client:
        client.post(
            "/login",
            data={"username": "admin", "password": "test-password"},
            follow_redirects=False,
        )
        r = client.post("/admin/rescan", follow_redirects=False)
        assert r.status_code == 302
        assert r.headers["location"] == "/"


def test_change_password_success():
    with TestClient(app) as client:
        client.post(
            "/login",
            data={"username": "admin", "password": "test-password"},
            follow_redirects=False,
        )
        r = client.post(
            "/admin/password",
            data={"current": "test-password", "new": "new-password"},
            follow_redirects=False,
        )
        assert r.status_code == 302
        assert r.headers["location"] == "/login"

    s = get_session()
    user = s.query(AdminUser).one()
    assert verify_password("new-password", user.password_hash)
    assert user.plain_password == "new-password"
    s.close()


def test_change_password_wrong_current():
    with TestClient(app) as client:
        client.post(
            "/login",
            data={"username": "admin", "password": "test-password"},
            follow_redirects=False,
        )
        r = client.post(
            "/admin/password",
            data={"current": "WRONG", "new": "new-password"},
            follow_redirects=False,
        )
        assert r.status_code == 302
        r = client.get("/")
        assert "Current password is wrong" in r.text
