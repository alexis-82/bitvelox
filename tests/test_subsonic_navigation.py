import pytest
from fastapi.testclient import TestClient

from app.auth import bootstrap_admin_user
from app.config import get_settings
from app.db import get_session, init_db
from app.main import app
from app.scanner import full_scan
from tests.fixtures import make_mp3

AUTH = {"u": "admin", "p": "test-password", "v": "1.13.0", "c": "test", "f": "json"}


@pytest.fixture
def populated(tmp_path, monkeypatch):
    music = tmp_path / "music"
    monkeypatch.setenv("MUSIC_DIR", str(music))
    make_mp3(music / "Alfa" / "First" / "01.mp3", "Song A1", "Alfa", "First", 1, 2001, with_cover=True)
    make_mp3(music / "Alfa" / "First" / "02.mp3", "Song A2", "Alfa", "First", 2, 2001)
    make_mp3(music / "Beta" / "Debut" / "01.mp3", "Song B1", "Beta", "Debut", 1, 2005)
    make_mp3(music / "The Charlies" / "Zenith" / "01.mp3", "Song C1", "The Charlies", "Zenith", 1, 2010)

    settings = get_settings()
    init_db(settings.db_path)
    # Drop and recreate all tables so each test starts fresh (Windows-friendly:
    # avoids unlinking a file that SQLite may still hold a handle to).
    from app.db import Base, get_engine
    Base.metadata.drop_all(get_engine())
    Base.metadata.create_all(get_engine())
    s = get_session()
    bootstrap_admin_user(s, settings.admin_user, settings.admin_password)
    full_scan(s, music, settings.covers_dir)
    s.close()
    yield music


def test_ping_ok(populated):
    with TestClient(app) as client:
        r = client.get("/rest/ping.view", params=AUTH)
        assert r.json()["subsonic-response"]["status"] == "ok"


def test_get_music_folders(populated):
    with TestClient(app) as client:
        r = client.get("/rest/getMusicFolders.view", params=AUTH)
        folders = r.json()["subsonic-response"]["musicFolders"]["musicFolder"]
        assert folders[0]["name"] == "Music"


def test_get_indexes_groups_by_letter(populated):
    with TestClient(app) as client:
        r = client.get("/rest/getIndexes.view", params=AUTH)
        idx = r.json()["subsonic-response"]["indexes"]["index"]
        letters = {g["name"] for g in idx}
        assert {"A", "B", "C"}.issubset(letters)


def test_get_artists_ignores_the_prefix(populated):
    with TestClient(app) as client:
        r = client.get("/rest/getArtists.view", params=AUTH)
        idx = r.json()["subsonic-response"]["artists"]["index"]
        by_letter = {g["name"]: g["artist"] for g in idx}
        assert "C" in by_letter
        assert any(a["name"] == "The Charlies" for a in by_letter["C"])


def test_get_album_list2_alphabetical(populated):
    with TestClient(app) as client:
        r = client.get("/rest/getAlbumList2.view", params={**AUTH, "type": "alphabeticalByName", "size": 10})
        albums = r.json()["subsonic-response"]["albumList2"]["album"]
        names = [a["name"] for a in albums]
        assert names == sorted(names, key=str.lower)


def test_search3_prefix_match(populated):
    with TestClient(app) as client:
        r = client.get("/rest/search3.view", params={**AUTH, "query": "Song"})
        songs = r.json()["subsonic-response"]["searchResult3"].get("song", [])
        assert len(songs) == 4


def test_search3_case_insensitive(populated):
    with TestClient(app) as client:
        r = client.get("/rest/search3.view", params={**AUTH, "query": "ALFA"})
        artists = r.json()["subsonic-response"]["searchResult3"].get("artist", [])
        assert any(a["name"] == "Alfa" for a in artists)


def test_get_artist_details(populated):
    with TestClient(app) as client:
        r = client.get("/rest/getArtists.view", params=AUTH)
        first_artist = r.json()["subsonic-response"]["artists"]["index"][0]["artist"][0]
        aid = first_artist["id"]

        r = client.get("/rest/getArtist.view", params={**AUTH, "id": aid})
        body = r.json()["subsonic-response"]["artist"]
        assert body["name"] == first_artist["name"]
        assert body["albumCount"] >= 1


def test_get_album_returns_songs(populated):
    with TestClient(app) as client:
        r = client.get("/rest/getAlbumList2.view", params={**AUTH, "size": 20})
        first = r.json()["subsonic-response"]["albumList2"]["album"][0]

        r = client.get("/rest/getAlbum.view", params={**AUTH, "id": first["id"]})
        songs = r.json()["subsonic-response"]["album"]["song"]
        assert len(songs) >= 1
        assert all(s["id"].startswith("tr-") for s in songs)


def test_xml_format_works(populated):
    with TestClient(app) as client:
        r = client.get("/rest/ping.view", params={**AUTH, "f": "xml"})
        assert "application/xml" in r.headers["content-type"]
        assert 'status="ok"' in r.text


def test_not_found_returns_70(populated):
    with TestClient(app) as client:
        r = client.get("/rest/getAlbum.view", params={**AUTH, "id": "al-99999"})
        assert r.json()["subsonic-response"]["error"]["code"] == 70
