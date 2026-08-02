"""Tests for the filesystem-based Library browser."""
import pytest
from fastapi.testclient import TestClient

from app.admin import rate_limit
from app.auth import bootstrap_admin_user
from app.config import get_settings
from app.db import Base, get_engine, get_session, init_db
from app.main import app
from app.scanner import full_scan
from tests.fixtures import _minimal_mp3_frame, make_mp3

AUTH_FORM = {"username": "admin", "password": "test-password"}


@pytest.fixture
def music_tree(tmp_path, monkeypatch):
    """/music with 2 loose files, 1 subfolder containing 1 file, 1 nested folder with tags."""
    music = tmp_path / "music"
    music.mkdir()
    monkeypatch.setenv("MUSIC_DIR", str(music))
    (music / "loose1.mp3").write_bytes(_minimal_mp3_frame() * 30)
    (music / "loose2.mp3").write_bytes(_minimal_mp3_frame() * 30)
    (music / "sub").mkdir()
    (music / "sub" / "in-folder.mp3").write_bytes(_minimal_mp3_frame() * 30)
    make_mp3(music / "AlbumA" / "song.mp3", "Real Title", "SomeArtist", "AlbumA", 1)
    # Noise files
    (music / "notes.txt").write_text("skip me")
    (music / ".hidden.mp3").write_bytes(b"hidden")

    settings = get_settings()
    init_db(settings.db_path)
    Base.metadata.drop_all(get_engine())
    Base.metadata.create_all(get_engine())
    s = get_session()
    bootstrap_admin_user(s, settings.admin_user, settings.admin_password)
    full_scan(s, music, settings.covers_dir)
    s.close()
    rate_limit.clear_all()
    yield music


def _login(client):
    return client.post("/login", data=AUTH_FORM, follow_redirects=False)


def test_library_requires_login(music_tree):
    with TestClient(app) as client:
        r = client.get("/library", follow_redirects=False)
        assert r.status_code == 302
        assert "/login" in r.headers["location"]


def test_library_root_shows_folders_and_files(music_tree):
    with TestClient(app) as client:
        _login(client)
        r = client.get("/library")
        assert r.status_code == 200
        # Loose files at root
        assert "loose1.mp3" in r.text
        assert "loose2.mp3" in r.text
        # Folders at root
        assert "sub" in r.text
        assert "AlbumA" in r.text
        # Non-mp3 and dotfiles are hidden
        assert "notes.txt" not in r.text
        assert ".hidden.mp3" not in r.text
        # The nested files are NOT shown at root — only direct entries.
        assert "in-folder.mp3" not in r.text
        assert "song.mp3" not in r.text


def test_library_enters_folder(music_tree):
    with TestClient(app) as client:
        _login(client)
        r = client.get("/library", params={"path": "sub"})
        assert r.status_code == 200
        assert "in-folder.mp3" in r.text
        # Root files not shown here
        assert "loose1.mp3" not in r.text


def test_library_shows_metadata_when_indexed(music_tree):
    with TestClient(app) as client:
        _login(client)
        r = client.get("/library", params={"path": "AlbumA"})
        assert r.status_code == 200
        assert "song.mp3" in r.text
        # Title from the ID3 tag should appear
        assert "Real Title" in r.text


def test_library_breadcrumb_present(music_tree):
    with TestClient(app) as client:
        _login(client)
        r = client.get("/library", params={"path": "sub"})
        # Breadcrumb should link back to Library root
        assert 'href="/library"' in r.text
        assert ">Library<" in r.text
        assert ">sub" in r.text


def test_library_rejects_path_traversal(music_tree):
    with TestClient(app) as client:
        _login(client)
        r = client.get("/library", params={"path": "../etc"})
        assert r.status_code == 404
        r = client.get("/library", params={"path": "sub/../../boot"})
        assert r.status_code == 404


def test_library_rejects_absolute_path(music_tree):
    with TestClient(app) as client:
        _login(client)
        r = client.get("/library", params={"path": "/etc"})
        assert r.status_code == 404


def test_library_missing_folder_404(music_tree):
    with TestClient(app) as client:
        _login(client)
        r = client.get("/library", params={"path": "does-not-exist"})
        assert r.status_code == 404


def test_library_no_action_buttons_on_files(music_tree):
    with TestClient(app) as client:
        _login(client)
        r = client.get("/library")
        # No download, play, stream buttons around file entries.
        # A crude but effective check: no <button> tags in the fs-list area.
        assert "download.view" not in r.text
        assert "stream.view" not in r.text


def test_library_size_shown(music_tree):
    with TestClient(app) as client:
        _login(client)
        r = client.get("/library")
        assert "MB" in r.text


def test_file_row_no_duplicate_when_title_matches_stem(music_tree):
    """When the DB title == filename stem (scanner fallback), don't show it twice."""
    with TestClient(app) as client:
        _login(client)
        # loose1.mp3 has no ID3 tags → scanner falls back to stem "loose1" as title
        r = client.get("/library")
        # The row should contain "loose1.mp3" once, not "loose1.mp3 · loose1"
        assert r.text.count("loose1.mp3") == 1
        assert "loose1.mp3 · loose1" not in r.text
        assert "loose1.mp3</span>\n      <span class=\"fs-meta\">· loose1<" not in r.text


def test_file_row_shows_title_when_different_from_filename(music_tree):
    """When title tag is genuinely different, show it alongside the filename."""
    with TestClient(app) as client:
        _login(client)
        r = client.get("/library", params={"path": "AlbumA"})
        # song.mp3 has title tag "Real Title" — different from "song"
        assert "song.mp3" in r.text
        assert "Real Title" in r.text


def test_removed_routes_are_gone(music_tree):
    """The old metadata-based routes must be 404."""
    with TestClient(app) as client:
        _login(client)
        assert client.get("/library/tracks").status_code == 404
        assert client.get("/library/artist/1").status_code == 404
        assert client.get("/library/album/1").status_code == 404
        assert client.get("/admin/cover/1").status_code == 404
