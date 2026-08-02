import pytest
from fastapi.testclient import TestClient

from app.auth import bootstrap_admin_user
from app.config import get_settings
from app.db import Base, get_engine, get_session, init_db
from app.main import app
from app.models import Playlist, PlaylistEntry
from app.scanner import full_scan
from tests.fixtures import make_mp3

AUTH = {"u": "admin", "p": "test-password", "v": "1.13.0", "c": "test", "f": "json"}


@pytest.fixture
def populated_with_playlists(tmp_path, monkeypatch):
    music = tmp_path / "music"
    monkeypatch.setenv("MUSIC_DIR", str(music))

    make_mp3(music / "A" / "Al" / "01.mp3", "Song1", "A", "Al", 1)
    make_mp3(music / "A" / "Al" / "02.mp3", "Song2", "A", "Al", 2)
    make_mp3(music / "B" / "Bl" / "01.mp3", "Song3", "B", "Bl", 1)

    (music / "mix.m3u").write_text(
        "# my playlist\n"
        "A/Al/01.mp3\n"
        "B/Bl/01.mp3\n"
        "does/not/exist.mp3\n",
        encoding="utf-8",
    )

    settings = get_settings()
    init_db(settings.db_path)
    Base.metadata.drop_all(get_engine())
    Base.metadata.create_all(get_engine())
    s = get_session()
    bootstrap_admin_user(s, settings.admin_user, settings.admin_password)
    full_scan(s, music, settings.covers_dir)
    s.close()
    yield music


def test_scan_creates_playlist(populated_with_playlists):
    from app.db import get_session
    s = get_session()
    pls = s.query(Playlist).all()
    assert len(pls) == 1
    assert pls[0].name == "mix"
    entries = s.query(PlaylistEntry).filter_by(playlist_id=pls[0].id).all()
    assert len(entries) == 2  # unresolved entry skipped
    s.close()


def test_get_playlists_endpoint(populated_with_playlists):
    with TestClient(app) as client:
        r = client.get("/rest/getPlaylists.view", params=AUTH)
        pls = r.json()["subsonic-response"]["playlists"]["playlist"]
        assert len(pls) == 1
        assert pls[0]["name"] == "mix"
        assert pls[0]["songCount"] == 2


def test_get_playlist_detail(populated_with_playlists):
    with TestClient(app) as client:
        r = client.get("/rest/getPlaylists.view", params=AUTH)
        pid = r.json()["subsonic-response"]["playlists"]["playlist"][0]["id"]

        r = client.get("/rest/getPlaylist.view", params={**AUTH, "id": pid})
        detail = r.json()["subsonic-response"]["playlist"]
        assert detail["songCount"] == 2
        assert [e["title"] for e in detail["entry"]] == ["Song1", "Song3"]
