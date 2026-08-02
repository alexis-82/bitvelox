from __future__ import annotations

import hashlib
import io
import logging
from functools import lru_cache
from pathlib import Path

from mutagen.id3 import ID3, ID3NoHeaderError
from mutagen.mp3 import MP3
from PIL import Image

logger = logging.getLogger(__name__)

COVER_FILENAMES = ("cover.jpg", "cover.jpeg", "cover.png",
                   "folder.jpg", "folder.jpeg", "folder.png",
                   "front.jpg", "front.jpeg", "front.png")


def _album_key(mp3_path: Path) -> str:
    parent = str(mp3_path.parent.resolve())
    return hashlib.sha1(parent.encode("utf-8")).hexdigest()


def extract_cover(mp3_path: Path, out_dir: Path) -> Path | None:
    """Return path to a cover image for the album of mp3_path.

    Priority:
    1. Cached extraction from a previous call in this scan (same album dir).
    2. APIC embedded picture in the MP3 → written to out_dir/<album_key>.jpg.
    3. cover.jpg / folder.jpg / front.jpg alongside the file → returned as-is.
    4. None.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    key = _album_key(mp3_path)
    cached = out_dir / f"{key}.jpg"
    if cached.exists():
        return cached

    try:
        audio = MP3(str(mp3_path), ID3=ID3)
        if audio.tags is not None:
            apic = audio.tags.getall("APIC")
            if apic:
                data = apic[0].data
                try:
                    img = Image.open(io.BytesIO(data))
                    img.convert("RGB").save(cached, format="JPEG", quality=88)
                    return cached
                except Exception as e:
                    logger.warning("APIC decode failed for %s: %s", mp3_path, e)
    except ID3NoHeaderError:
        pass
    except Exception as e:
        logger.warning("cover read failed for %s: %s", mp3_path, e)

    for name in COVER_FILENAMES:
        candidate = mp3_path.parent / name
        if candidate.exists() and candidate.is_file():
            return candidate

    return None


@lru_cache(maxsize=128)
def _resize_cached(path_str: str, size: int, mtime: float) -> bytes:
    with Image.open(path_str) as img:
        img = img.convert("RGB")
        img.thumbnail((size, size))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue()


def get_cover_resized(path: Path, size: int) -> bytes:
    mtime = path.stat().st_mtime
    return _resize_cached(str(path), size, mtime)


def read_cover_bytes(path: Path) -> bytes:
    return path.read_bytes()
