from pathlib import Path

import pytest

from app.db import get_session, init_db
from app.models import Album, Artist, ScanError, Track
from app.scanner import AlreadyRunning, _scan_lock, full_scan, iter_mp3_files, read_tags
from tests.fixtures import make_corrupt_mp3, make_cover_file, make_mp3


@pytest.fixture
def music_dir(tmp_path):
    root = tmp_path / "music"
    make_mp3(root / "Pink Floyd" / "The Wall" / "01 - Comfortably Numb.mp3",
             "Comfortably Numb", "Pink Floyd", "The Wall", 1, 1979, with_cover=True)
    make_mp3(root / "Pink Floyd" / "The Wall" / "02 - Hey You.mp3",
             "Hey You", "Pink Floyd", "The Wall", 2, 1979)
    make_mp3(root / "Beatles" / "Abbey Road" / "01 - Come Together.mp3",
             "Come Together", "Beatles", "Abbey Road", 1, 1969)
    make_cover_file(root / "Beatles" / "Abbey Road")
    (root / "Beatles" / "note.txt").write_text("not an mp3")
    (root / ".hidden.mp3").write_bytes(b"skip me")
    return root


def test_iter_mp3_files_skips_dot_and_non_mp3(music_dir):
    files = sorted(iter_mp3_files(music_dir), key=lambda p: p.name)
    names = [p.name for p in files]
    assert "01 - Comfortably Numb.mp3" in names
    assert "02 - Hey You.mp3" in names
    assert "01 - Come Together.mp3" in names
    assert ".hidden.mp3" not in names
    assert "note.txt" not in names
    assert len(files) == 3


def test_read_tags_id3v2(music_dir):
    mp3 = music_dir / "Pink Floyd" / "The Wall" / "01 - Comfortably Numb.mp3"
    meta = read_tags(mp3, music_root=music_dir)
    assert meta.title == "Comfortably Numb"
    assert meta.artist == "Pink Floyd"
    assert meta.album == "The Wall"
    assert meta.track_no == 1
    assert meta.year == 1979


def test_read_tags_fallback_from_path(tmp_path):
    root = tmp_path / "music"
    p = root / "SomeArtist" / "SomeAlbum" / "01-track.mp3"
    p.parent.mkdir(parents=True)
    from tests.fixtures import _minimal_mp3_frame
    p.write_bytes(_minimal_mp3_frame() * 20)  # no tags
    meta = read_tags(p, music_root=root)
    assert meta.artist == "SomeArtist"
    assert meta.album == "SomeAlbum"
    assert meta.title == "01-track"


def test_read_tags_fallback_single_folder_uses_folder_as_album(tmp_path):
    root = tmp_path / "music"
    p = root / "MyAlbumFolder" / "song.mp3"
    p.parent.mkdir(parents=True)
    from tests.fixtures import _minimal_mp3_frame
    p.write_bytes(_minimal_mp3_frame() * 20)
    meta = read_tags(p, music_root=root)
    assert meta.album == "MyAlbumFolder"
    assert meta.artist == ""
    assert meta.title == "song"
    assert "Unknown" not in meta.artist
    assert "Unknown" not in meta.album


def test_read_tags_fallback_loose_file_has_empty_artist_and_album(tmp_path):
    root = tmp_path / "music"
    root.mkdir()
    p = root / "loose.mp3"
    from tests.fixtures import _minimal_mp3_frame
    p.write_bytes(_minimal_mp3_frame() * 20)
    meta = read_tags(p, music_root=root)
    assert meta.artist == ""
    assert meta.album == ""
    assert meta.title == "loose"
    assert "Unknown" not in meta.artist
    assert "Unknown" not in meta.album


def test_read_tags_uses_tpe2_when_tpe1_missing(tmp_path):
    from mutagen.id3 import ID3, TALB, TIT2, TPE2
    from tests.fixtures import _minimal_mp3_frame
    p = tmp_path / "song.mp3"
    p.write_bytes(_minimal_mp3_frame() * 30)
    tags = ID3()
    tags.add(TIT2(encoding=3, text="Title"))
    tags.add(TALB(encoding=3, text="Album"))
    tags.add(TPE2(encoding=3, text="AlbumArtistOnly"))
    tags.save(str(p))
    meta = read_tags(p, music_root=tmp_path)
    assert meta.artist == "AlbumArtistOnly"


def test_read_tags_corrupt_raises(tmp_path):
    from app.scanner import TagReadError
    p = make_corrupt_mp3(tmp_path / "bad.mp3")
    with pytest.raises(TagReadError):
        read_tags(p, music_root=tmp_path)


def test_full_scan_indexes_all(music_dir, tmp_path):
    init_db("sqlite:///:memory:")
    s = get_session()
    result = full_scan(s, music_dir, tmp_path / "covers")
    assert result["total"] == 3
    assert result["errors"] == 0
    artists = {a.name for a in s.query(Artist).all()}
    assert artists == {"Pink Floyd", "Beatles"}
    albums = {a.name for a in s.query(Album).all()}
    assert albums == {"The Wall", "Abbey Road"}
    tracks = s.query(Track).all()
    assert len(tracks) == 3
    s.close()


def test_full_scan_skips_corrupt(music_dir, tmp_path):
    make_corrupt_mp3(music_dir / "Pink Floyd" / "The Wall" / "bad.mp3")
    init_db("sqlite:///:memory:")
    s = get_session()
    result = full_scan(s, music_dir, tmp_path / "covers")
    assert result["total"] == 3
    assert result["errors"] == 1
    errors = s.query(ScanError).all()
    assert len(errors) == 1
    assert "bad.mp3" in errors[0].path
    s.close()


def test_full_scan_removes_deleted_tracks(music_dir, tmp_path):
    init_db("sqlite:///:memory:")
    s = get_session()
    full_scan(s, music_dir, tmp_path / "covers")
    assert s.query(Track).count() == 3

    (music_dir / "Beatles" / "Abbey Road" / "01 - Come Together.mp3").unlink()
    full_scan(s, music_dir, tmp_path / "covers")

    remaining = {t.title for t in s.query(Track).all()}
    assert remaining == {"Comfortably Numb", "Hey You"}
    assert s.query(Artist).filter_by(name="Beatles").first() is None
    s.close()


def test_full_scan_lock_prevents_concurrent(music_dir, tmp_path):
    init_db("sqlite:///:memory:")
    s = get_session()
    assert _scan_lock.acquire(blocking=False)
    try:
        with pytest.raises(AlreadyRunning):
            full_scan(s, music_dir, tmp_path / "covers")
    finally:
        _scan_lock.release()
    s.close()
