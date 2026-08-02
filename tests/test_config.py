from pathlib import Path

from app.config import Settings


def test_defaults(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    for var in ("MUSIC_DIR", "DATA_DIR", "ADMIN_USER", "ADMIN_PASSWORD", "HTTP_PORT"):
        monkeypatch.delenv(var, raising=False)

    s = Settings()
    assert s.music_dir == Path("/music")
    assert s.data_dir == Path("/data")
    assert s.admin_user == "admin"
    assert s.admin_password is None
    assert s.http_port == 4040
    assert s.db_path == Path("/data/library.db")
    assert s.covers_dir == Path("/data/covers")
    assert s.logs_dir == Path("/data/logs")


def test_env_override(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MUSIC_DIR", "/srv/music")
    monkeypatch.setenv("DATA_DIR", "/var/lib/bitvelox")
    monkeypatch.setenv("ADMIN_USER", "root")
    monkeypatch.setenv("ADMIN_PASSWORD", "s3cr3t")
    monkeypatch.setenv("HTTP_PORT", "8080")

    s = Settings()
    assert s.music_dir == Path("/srv/music")
    assert s.data_dir == Path("/var/lib/bitvelox")
    assert s.admin_user == "root"
    assert s.admin_password == "s3cr3t"
    assert s.http_port == 8080
