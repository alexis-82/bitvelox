from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator

from mutagen import File as MutagenFile
from mutagen.id3 import ID3NoHeaderError
from mutagen.mp3 import MP3
from sqlalchemy.orm import Session

from app.covers import extract_cover
from app.models import Album, Artist, ScanError, ScanState, Track
from app.playlists import scan_playlists

logger = logging.getLogger(__name__)

_scan_lock = threading.Lock()


class TagReadError(Exception):
    pass


class AlreadyRunning(Exception):
    pass


@dataclass
class TrackMeta:
    title: str
    artist: str
    album: str
    track_no: int | None
    disc_no: int | None
    year: int | None
    duration_s: int | None
    bitrate: int | None


def iter_mp3_files(root: Path) -> Iterator[Path]:
    if not root.exists():
        return
    for p in root.rglob("*.mp3"):
        if p.name.startswith("."):
            continue
        if p.is_symlink():
            try:
                real = p.resolve(strict=True)
            except OSError:
                continue
            if not str(real).startswith(str(root.resolve())):
                continue
        if p.is_file():
            yield p


def _first_int(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, list) and value:
        value = value[0]
    s = str(value).split("/")[0].strip()
    try:
        return int(s)
    except (ValueError, TypeError):
        return None


def _first_str(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, list) and value:
        value = value[0]
    s = str(value).strip()
    return s or None


def _fallback_from_path(path: Path, music_root: Path) -> tuple[str, str, str]:
    try:
        rel = path.relative_to(music_root)
    except ValueError:
        rel = Path(path.name)
    parts = rel.parts
    if len(parts) >= 3:
        artist = parts[-3]
        album = parts[-2]
    elif len(parts) == 2:
        # Single parent folder is the album; artist is not derivable.
        artist = ""
        album = parts[0]
    else:
        # Loose file directly in MUSIC_DIR.
        artist = ""
        album = ""
    title = path.stem
    return artist, album, title


def read_tags(path: Path, music_root: Path | None = None) -> TrackMeta:
    try:
        audio = MP3(str(path))
    except ID3NoHeaderError:
        audio = None
    except Exception as e:
        try:
            audio = MutagenFile(str(path))
            if audio is None:
                raise TagReadError(f"unreadable MP3: {e}")
        except Exception as e2:
            raise TagReadError(f"unreadable MP3: {e2}") from e2

    tags = audio.tags if audio is not None and audio.tags is not None else {}

    def _tag(*keys):
        for k in keys:
            if k in tags:
                v = tags[k]
                text = getattr(v, "text", v)
                return _first_str(text)
        return None

    artist = _tag("TPE1", "TPE2", "artist")
    album = _tag("TALB", "album")
    title = _tag("TIT2", "title")

    if not (artist and album and title):
        fb_a, fb_al, fb_t = _fallback_from_path(path, music_root or path.parent)
        artist = artist or fb_a
        album = album or fb_al
        title = title or fb_t

    track_no = _first_int(_tag("TRCK", "tracknumber"))
    disc_no = _first_int(_tag("TPOS", "discnumber"))
    year_raw = _tag("TDRC", "TYER", "date")
    year: int | None = None
    if year_raw:
        try:
            year = int(str(year_raw)[:4])
        except ValueError:
            year = None

    duration_s = None
    bitrate = None
    if audio is not None and audio.info is not None:
        duration_s = int(getattr(audio.info, "length", 0) or 0) or None
        bitrate_bps = getattr(audio.info, "bitrate", None)
        if bitrate_bps:
            bitrate = int(bitrate_bps / 1000)

    return TrackMeta(
        title=title,
        artist=artist,
        album=album,
        track_no=track_no,
        disc_no=disc_no,
        year=year,
        duration_s=duration_s,
        bitrate=bitrate,
    )


def _get_or_create_artist(session: Session, cache: dict, name: str) -> Artist:
    key = name.lower()
    if key in cache:
        return cache[key]
    artist = session.query(Artist).filter_by(name_lower=key).first()
    if artist is None:
        artist = Artist(name=name, name_lower=key)
        session.add(artist)
        session.flush()
    cache[key] = artist
    return artist


def _get_or_create_album(
    session: Session,
    cache: dict,
    artist: Artist,
    name: str,
    year: int | None,
    cover_path: str | None,
) -> Album:
    key = (artist.id, name.lower())
    if key in cache:
        return cache[key]
    album = (
        session.query(Album)
        .filter_by(artist_id=artist.id, name_lower=name.lower())
        .first()
    )
    if album is None:
        album = Album(
            artist_id=artist.id,
            name=name,
            name_lower=name.lower(),
            year=year,
            cover_path=cover_path,
        )
        session.add(album)
        session.flush()
    else:
        if cover_path and not album.cover_path:
            album.cover_path = cover_path
        if year and not album.year:
            album.year = year
    cache[key] = album
    return album


def full_scan(session: Session, music_dir: Path, covers_dir: Path) -> dict:
    acquired = _scan_lock.acquire(blocking=False)
    if not acquired:
        raise AlreadyRunning("scan already in progress")

    state = session.query(ScanState).first()
    if state is None:
        state = ScanState()
        session.add(state)
    state.running = True
    state.started_at = datetime.utcnow()
    state.finished_at = None
    session.commit()

    covers_dir.mkdir(parents=True, exist_ok=True)

    seen_paths: set[str] = set()
    artist_cache: dict = {}
    album_cache: dict = {}
    error_count = 0
    ok_count = 0

    session.query(ScanError).delete()
    session.commit()

    try:
        for mp3 in iter_mp3_files(music_dir):
            path_str = str(mp3)
            try:
                meta = read_tags(mp3, music_root=music_dir)
                size = mp3.stat().st_size
                cover = extract_cover(mp3, covers_dir)

                artist = _get_or_create_artist(session, artist_cache, meta.artist)
                album = _get_or_create_album(
                    session, album_cache, artist, meta.album, meta.year,
                    str(cover) if cover else None,
                )

                track = session.query(Track).filter_by(path=path_str).first()
                title_lower = meta.title.lower()
                if track is None:
                    track = Track(
                        album_id=album.id,
                        artist_id=artist.id,
                        path=path_str,
                        title=meta.title,
                        title_lower=title_lower,
                        track_no=meta.track_no,
                        disc_no=meta.disc_no,
                        duration_s=meta.duration_s,
                        bitrate=meta.bitrate,
                        size_bytes=size,
                        mime_type="audio/mpeg",
                    )
                    session.add(track)
                else:
                    track.album_id = album.id
                    track.artist_id = artist.id
                    track.title = meta.title
                    track.title_lower = title_lower
                    track.track_no = meta.track_no
                    track.disc_no = meta.disc_no
                    track.duration_s = meta.duration_s
                    track.bitrate = meta.bitrate
                    track.size_bytes = size

                seen_paths.add(path_str)
                ok_count += 1
            except TagReadError as e:
                error_count += 1
                session.add(ScanError(path=path_str, error=str(e)))
                logger.warning("scan error on %s: %s", path_str, e)
            except Exception as e:
                error_count += 1
                session.add(ScanError(path=path_str, error=f"unexpected: {e}"))
                logger.exception("unexpected error on %s", path_str)

            if ok_count % 100 == 0:
                session.commit()

        # Delete tracks no longer present on disk
        existing = session.query(Track.id, Track.path).all()
        for tid, tpath in existing:
            if tpath not in seen_paths:
                session.query(Track).filter_by(id=tid).delete()

        # Delete empty albums and artists
        session.commit()
        empty_albums = (
            session.query(Album).outerjoin(Track).filter(Track.id.is_(None)).all()
        )
        for a in empty_albums:
            session.delete(a)
        session.commit()
        empty_artists = (
            session.query(Artist).outerjoin(Album).filter(Album.id.is_(None)).all()
        )
        for a in empty_artists:
            session.delete(a)
        session.commit()

        scan_playlists(session, music_dir)

        state.finished_at = datetime.utcnow()
        state.running = False
        state.last_scan_ok = True
        state.error_count = error_count
        state.total_tracks = ok_count
        session.commit()

        return {"total": ok_count, "errors": error_count}
    except Exception:
        state.finished_at = datetime.utcnow()
        state.running = False
        state.last_scan_ok = False
        session.commit()
        raise
    finally:
        _scan_lock.release()


def is_scan_running() -> bool:
    return _scan_lock.locked()
