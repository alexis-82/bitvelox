from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator

from sqlalchemy.orm import Session

from app.models import Playlist, PlaylistEntry, Track

logger = logging.getLogger(__name__)


def _iter_m3u_files(root: Path) -> Iterator[Path]:
    if not root.exists():
        return
    for pattern in ("*.m3u", "*.m3u8"):
        for p in root.rglob(pattern):
            if p.name.startswith("."):
                continue
            if p.is_file():
                yield p


def _parse_m3u(m3u_path: Path) -> list[Path]:
    """Parse an M3U/M3U8 file, returning resolved absolute track paths."""
    try:
        raw = m3u_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raw = m3u_path.read_text(encoding="latin-1", errors="replace")

    tracks: list[Path] = []
    base = m3u_path.parent
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line = line.replace("\\", "/")
        candidate = Path(line)
        if not candidate.is_absolute():
            candidate = (base / candidate).resolve()
        tracks.append(candidate)
    return tracks


def scan_playlists(session: Session, music_dir: Path) -> int:
    session.query(PlaylistEntry).delete()
    session.query(Playlist).delete()
    session.commit()

    total = 0
    for m3u in _iter_m3u_files(music_dir):
        name = m3u.stem
        pl = Playlist(name=name, path=str(m3u))
        session.add(pl)
        session.flush()

        entries = _parse_m3u(m3u)
        position = 0
        for track_path in entries:
            track = session.query(Track).filter_by(path=str(track_path)).first()
            if track is None:
                logger.warning("playlist %s: unresolved track %s", m3u, track_path)
                continue
            session.add(PlaylistEntry(playlist_id=pl.id, track_id=track.id, position=position))
            position += 1
        total += 1
    session.commit()
    return total
