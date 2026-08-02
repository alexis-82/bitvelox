from pathlib import Path

from PIL import Image

from app.covers import extract_cover, get_cover_resized
from tests.fixtures import make_cover_file, make_mp3


def test_extract_from_embedded(tmp_path):
    mp3 = make_mp3(tmp_path / "song.mp3", "T", "A", "Al", with_cover=True)
    out = tmp_path / "covers"
    cover = extract_cover(mp3, out)
    assert cover is not None
    assert cover.exists()
    assert cover.suffix == ".jpg"
    with Image.open(cover) as img:
        assert img.format == "JPEG"


def test_extract_falls_back_to_folder_file(tmp_path):
    album_dir = tmp_path / "album"
    mp3 = make_mp3(album_dir / "song.mp3", "T", "A", "Al", with_cover=False)
    cover_file = make_cover_file(album_dir, "cover.jpg")
    out = tmp_path / "covers"
    result = extract_cover(mp3, out)
    assert result == cover_file


def test_extract_returns_none_when_missing(tmp_path):
    mp3 = make_mp3(tmp_path / "song.mp3", "T", "A", "Al", with_cover=False)
    out = tmp_path / "covers"
    assert extract_cover(mp3, out) is None


def test_get_cover_resized(tmp_path):
    src = tmp_path / "big.jpg"
    Image.new("RGB", (1000, 800), (10, 10, 200)).save(src, "JPEG")
    data = get_cover_resized(src, 300)
    assert data[:3] == b"\xff\xd8\xff"  # JPEG magic
    from io import BytesIO
    with Image.open(BytesIO(data)) as img:
        assert max(img.size) <= 300
