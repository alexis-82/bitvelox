"""Helpers to generate synthetic MP3 files for tests without pulling ffmpeg."""
from __future__ import annotations

import io
import struct
import zlib
from pathlib import Path

from mutagen.id3 import APIC, ID3, TALB, TDRC, TIT2, TPE1, TRCK
from mutagen.mp3 import MP3
from PIL import Image


def _minimal_mp3_frame() -> bytes:
    """A single minimal MPEG-1 Layer III frame (silence).

    Header: 0xFF 0xFB 0x90 0x00
    - byte 0: 0xFF sync
    - byte 1: 0xFB = MPEG-1, Layer III, no CRC
    - byte 2: 0x90 = bitrate index 9 (128kbps), sample rate 44.1kHz, no padding
    - byte 3: 0x00 = stereo, no mode ext, no emphasis
    Frame size = 144 * 128000 / 44100 = 417 bytes (no padding).
    """
    FRAME_SIZE = 417
    header = bytes([0xFF, 0xFB, 0x90, 0x00])
    padding = bytes(FRAME_SIZE - len(header))
    return header + padding


def make_mp3(
    path: Path,
    title: str,
    artist: str,
    album: str,
    track_no: int | None = None,
    year: int | None = None,
    with_cover: bool = False,
    n_frames: int = 30,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = _minimal_mp3_frame()
    path.write_bytes(frame * n_frames)

    tags = ID3()
    tags.add(TIT2(encoding=3, text=title))
    tags.add(TPE1(encoding=3, text=artist))
    tags.add(TALB(encoding=3, text=album))
    if track_no is not None:
        tags.add(TRCK(encoding=3, text=str(track_no)))
    if year is not None:
        tags.add(TDRC(encoding=3, text=str(year)))
    if with_cover:
        img = Image.new("RGB", (100, 100), color=(200, 50, 50))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        tags.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=buf.getvalue()))
    tags.save(str(path))
    return path


def make_cover_file(dir_path: Path, name: str = "cover.jpg") -> Path:
    dir_path.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (100, 100), color=(50, 200, 50))
    p = dir_path / name
    img.save(p, format="JPEG")
    return p


def make_corrupt_mp3(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"this is not an mp3 file at all, just garbage")
    return path
