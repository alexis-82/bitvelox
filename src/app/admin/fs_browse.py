from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath


class InvalidPath(Exception):
    """Raised when the requested relative path escapes MUSIC_DIR or is malformed."""


@dataclass
class FileEntry:
    name: str
    rel_path: str
    size_bytes: int


@dataclass
class FolderEntry:
    name: str
    rel_path: str


@dataclass
class Crumb:
    name: str
    rel_path: str


@dataclass
class BrowseResult:
    folders: list[FolderEntry] = field(default_factory=list)
    files: list[FileEntry] = field(default_factory=list)
    breadcrumb: list[Crumb] = field(default_factory=list)
    rel_path: str = ""
    abs_path: Path | None = None


def _sanitize(music_root: Path, rel_path: str) -> tuple[Path, str]:
    """Resolve MUSIC_DIR + rel_path and reject any escape from MUSIC_DIR.

    Returns (absolute resolved path, normalized rel_path with forward slashes).
    """
    rel = (rel_path or "").strip().replace("\\", "/").lstrip("/")
    if rel:
        parts = PurePosixPath(rel).parts
        for p in parts:
            if p in ("", ".", ".."):
                raise InvalidPath(f"invalid path segment: {p!r}")

    music_root_resolved = music_root.resolve()
    candidate = (music_root_resolved / rel).resolve()
    try:
        candidate.relative_to(music_root_resolved)
    except ValueError as e:
        raise InvalidPath("path escapes music root") from e
    return candidate, rel


def _breadcrumb(rel: str) -> list[Crumb]:
    crumbs = [Crumb(name="Library", rel_path="")]
    if not rel:
        return crumbs
    acc: list[str] = []
    for segment in PurePosixPath(rel).parts:
        acc.append(segment)
        crumbs.append(Crumb(name=segment, rel_path="/".join(acc)))
    return crumbs


def list_directory(music_root: Path, rel_path: str) -> BrowseResult:
    abs_path, normalized = _sanitize(music_root, rel_path)

    if not abs_path.exists() or not abs_path.is_dir():
        raise InvalidPath(f"not a directory: {normalized!r}")

    folders: list[FolderEntry] = []
    files: list[FileEntry] = []

    for entry in sorted(abs_path.iterdir(), key=lambda p: p.name.lower()):
        if entry.name.startswith("."):
            continue
        entry_rel = f"{normalized}/{entry.name}" if normalized else entry.name
        if entry.is_dir():
            folders.append(FolderEntry(name=entry.name, rel_path=entry_rel))
        elif entry.is_file() and entry.suffix.lower() == ".mp3":
            try:
                size = entry.stat().st_size
            except OSError:
                size = 0
            files.append(FileEntry(name=entry.name, rel_path=entry_rel, size_bytes=size))

    return BrowseResult(
        folders=folders,
        files=files,
        breadcrumb=_breadcrumb(normalized),
        rel_path=normalized,
        abs_path=abs_path,
    )
