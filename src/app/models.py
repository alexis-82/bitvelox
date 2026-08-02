from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String, Text, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Artist(Base):
    __tablename__ = "artist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    name_lower: Mapped[str] = mapped_column(String(500), nullable=False)

    albums: Mapped[list["Album"]] = relationship(
        back_populates="artist", cascade="all, delete-orphan"
    )
    tracks: Mapped[list["Track"]] = relationship(back_populates="artist")

    __table_args__ = (Index("ix_artist_name_lower", "name_lower"),)


class Album(Base):
    __tablename__ = "album"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    artist_id: Mapped[int] = mapped_column(
        ForeignKey("artist.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    name_lower: Mapped[str] = mapped_column(String(500), nullable=False)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cover_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    artist: Mapped[Artist] = relationship(back_populates="albums")
    tracks: Mapped[list["Track"]] = relationship(
        back_populates="album", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_album_name_lower", "name_lower"),
        Index("ix_album_artist_id", "artist_id"),
    )


class Track(Base):
    __tablename__ = "track"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    album_id: Mapped[int] = mapped_column(
        ForeignKey("album.id", ondelete="CASCADE"), nullable=False
    )
    artist_id: Mapped[int] = mapped_column(
        ForeignKey("artist.id"), nullable=False
    )
    path: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    title_lower: Mapped[str] = mapped_column(String(500), nullable=False)
    track_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    disc_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_s: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bitrate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mime_type: Mapped[str] = mapped_column(String(50), nullable=False, default="audio/mpeg")

    album: Mapped[Album] = relationship(back_populates="tracks")
    artist: Mapped[Artist] = relationship(back_populates="tracks")

    __table_args__ = (
        Index("ix_track_title_lower", "title_lower"),
        Index("ix_track_album_id", "album_id"),
        Index("ix_track_path", "path"),
    )


class Playlist(Base):
    __tablename__ = "playlist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    entries: Mapped[list["PlaylistEntry"]] = relationship(
        back_populates="playlist",
        cascade="all, delete-orphan",
        order_by="PlaylistEntry.position",
    )


class PlaylistEntry(Base):
    __tablename__ = "playlist_entry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    playlist_id: Mapped[int] = mapped_column(
        ForeignKey("playlist.id", ondelete="CASCADE"), nullable=False
    )
    track_id: Mapped[int] = mapped_column(ForeignKey("track.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    playlist: Mapped[Playlist] = relationship(back_populates="entries")

    __table_args__ = (Index("ix_playlist_entry_playlist_id", "playlist_id"),)


class ScanError(Base):
    __tablename__ = "scan_error"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    error: Mapped[str] = mapped_column(Text, nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class AdminUser(Base):
    __tablename__ = "admin_user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    # Plaintext required by Subsonic token auth (t = md5(password + salt)).
    # Same trade-off Airsonic/Navidrome make. DB file lives in /data on VPS.
    plain_password: Mapped[str] = mapped_column(Text, nullable=False)


class ScanState(Base):
    __tablename__ = "scan_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    running: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_scan_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tracks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
