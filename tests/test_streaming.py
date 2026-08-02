import pytest
from fastapi.testclient import TestClient

from app.auth import bootstrap_admin_user
from app.config import get_settings
from app.db import Base, get_engine, get_session, init_db
from app.main import app
from app.scanner import full_scan
from app.subsonic.streaming import range_response
from tests.fixtures import make_mp3

AUTH = {"u": "admin", "p": "test-password", "v": "1.13.0", "c": "test", "f": "json"}


@pytest.fixture
def populated(tmp_path, monkeypatch):
    music = tmp_path / "music"
    monkeypatch.setenv("MUSIC_DIR", str(music))
    make_mp3(music / "A" / "Al" / "1.mp3", "T1", "A", "Al", 1, with_cover=True)

    settings = get_settings()
    init_db(settings.db_path)
    Base.metadata.drop_all(get_engine())
    Base.metadata.create_all(get_engine())
    s = get_session()
    bootstrap_admin_user(s, settings.admin_user, settings.admin_password)
    full_scan(s, music, settings.covers_dir)
    s.close()
    yield music


def test_range_response_no_range(tmp_path):
    f = tmp_path / "x.bin"
    data = bytes(range(256)) * 4
    f.write_bytes(data)
    r = range_response(f, None)
    assert r.status_code == 200
    assert r.headers["Accept-Ranges"] == "bytes"
    assert int(r.headers["Content-Length"]) == len(data)


def test_range_response_partial(tmp_path):
    f = tmp_path / "x.bin"
    data = bytes(1000)
    f.write_bytes(data)
    r = range_response(f, "bytes=100-199")
    assert r.status_code == 206
    assert r.headers["Content-Range"] == "bytes 100-199/1000"
    assert int(r.headers["Content-Length"]) == 100


def test_range_response_open_ended(tmp_path):
    f = tmp_path / "x.bin"
    f.write_bytes(bytes(1000))
    r = range_response(f, "bytes=900-")
    assert r.status_code == 206
    assert r.headers["Content-Range"] == "bytes 900-999/1000"


def test_range_response_suffix(tmp_path):
    f = tmp_path / "x.bin"
    f.write_bytes(bytes(1000))
    r = range_response(f, "bytes=-100")
    assert r.status_code == 206
    assert r.headers["Content-Range"] == "bytes 900-999/1000"


def test_range_response_malformed_returns_416(tmp_path):
    f = tmp_path / "x.bin"
    f.write_bytes(bytes(500))
    r = range_response(f, "chunks=0-10")
    assert r.status_code == 416


def test_range_response_out_of_bounds_returns_416(tmp_path):
    f = tmp_path / "x.bin"
    f.write_bytes(bytes(100))
    r = range_response(f, "bytes=200-300")
    assert r.status_code == 416


def test_stream_endpoint_full(populated):
    with TestClient(app) as client:
        r = client.get("/rest/getAlbumList2.view", params=AUTH)
        first_album = r.json()["subsonic-response"]["albumList2"]["album"][0]
        r = client.get("/rest/getAlbum.view", params={**AUTH, "id": first_album["id"]})
        tid = r.json()["subsonic-response"]["album"]["song"][0]["id"]

        r = client.get("/rest/stream.view", params={**AUTH, "id": tid})
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("audio/mpeg")
        assert r.headers["accept-ranges"] == "bytes"


def test_stream_endpoint_partial(populated):
    with TestClient(app) as client:
        r = client.get("/rest/getAlbumList2.view", params=AUTH)
        first_album = r.json()["subsonic-response"]["albumList2"]["album"][0]
        r = client.get("/rest/getAlbum.view", params={**AUTH, "id": first_album["id"]})
        tid = r.json()["subsonic-response"]["album"]["song"][0]["id"]

        r = client.get("/rest/stream.view", params={**AUTH, "id": tid},
                       headers={"Range": "bytes=100-199"})
        assert r.status_code == 206
        assert "bytes 100-199" in r.headers["content-range"]


def test_stream_unknown_id(populated):
    with TestClient(app) as client:
        r = client.get("/rest/stream.view", params={**AUTH, "id": "tr-99999"})
        assert r.json()["subsonic-response"]["error"]["code"] == 70


def test_download_forces_attachment(populated):
    with TestClient(app) as client:
        r = client.get("/rest/getAlbumList2.view", params=AUTH)
        first_album = r.json()["subsonic-response"]["albumList2"]["album"][0]
        r = client.get("/rest/getAlbum.view", params={**AUTH, "id": first_album["id"]})
        tid = r.json()["subsonic-response"]["album"]["song"][0]["id"]

        r = client.get("/rest/download.view", params={**AUTH, "id": tid})
        assert r.status_code == 200
        assert "attachment" in r.headers.get("content-disposition", "")


def test_get_cover_art(populated):
    with TestClient(app) as client:
        r = client.get("/rest/getAlbumList2.view", params=AUTH)
        alid = r.json()["subsonic-response"]["albumList2"]["album"][0]["id"]

        r = client.get("/rest/getCoverArt.view", params={**AUTH, "id": alid})
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("image/")

        r = client.get("/rest/getCoverArt.view", params={**AUTH, "id": alid, "size": 100})
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("image/")
