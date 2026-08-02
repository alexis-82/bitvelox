from sqlalchemy import inspect

from app.db import Base, get_engine, get_session, init_db


def test_init_db_in_memory_creates_all_tables():
    init_db("sqlite:///:memory:")
    engine = get_engine()
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    expected = {
        "artist", "album", "track",
        "playlist", "playlist_entry",
        "scan_error", "admin_user", "scan_state",
    }
    assert expected.issubset(tables), f"missing: {expected - tables}"


def test_init_db_writes_file(tmp_path):
    db_file = tmp_path / "sub" / "library.db"
    init_db(db_file)
    assert db_file.exists()


def test_indexes_created():
    init_db("sqlite:///:memory:")
    engine = get_engine()
    insp = inspect(engine)
    artist_idx = {i["name"] for i in insp.get_indexes("artist")}
    album_idx = {i["name"] for i in insp.get_indexes("album")}
    track_idx = {i["name"] for i in insp.get_indexes("track")}
    assert "ix_artist_name_lower" in artist_idx
    assert "ix_album_name_lower" in album_idx
    assert "ix_track_title_lower" in track_idx


def test_session_roundtrip():
    from app.models import Artist
    init_db("sqlite:///:memory:")
    s = get_session()
    a = Artist(name="Pink Floyd", name_lower="pink floyd")
    s.add(a)
    s.commit()
    got = s.query(Artist).filter_by(name="Pink Floyd").one()
    assert got.name_lower == "pink floyd"
    s.close()
