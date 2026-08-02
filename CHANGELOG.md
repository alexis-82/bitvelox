# Changelog

All notable changes to BitVelox are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- In-app **Changelog** page reachable from the sidebar (bottom, above the version tag). Renders `CHANGELOG.md` from the repo root.

## [0.3.0]

### Added
- **Rebrand to BitVelox** across HTML pages, sidebar, README, `pyproject.toml` package name, Docker service/image/container.
- **Filesystem-based Library browser** at `/library`: shows the actual contents of `/music` — folders and `.mp3` files as they are on disk, with breadcrumb navigation. No metadata-based artificial grouping.
- Path-traversal protection in the filesystem browser (`..`, absolute paths, symlinks escaping `MUSIC_DIR` → 404).
- Track title enrichment in the browser only when the ID3 tag differs from the filename stem (avoids "song.mp3 · song" duplication).
- Software **version number** shown in the sidebar footer.

### Changed
- Scanner fallback: files without ID3 tags no longer produce literal `Unknown Artist` / `Unknown Album` placeholders in the DB. Loose files get empty artist/album; files in a single subfolder use the folder name as the album.
- `TPE2` (AlbumArtist) used as fallback for artist when `TPE1` is missing.

### Removed
- Metadata-based Library views (`/library/artist/{id}`, `/library/album/{id}`, `/library/tracks`, `/admin/cover/{id}`) and their templates. Replaced by the filesystem browser.
- Literal `Unknown Artist` / `Unknown Album` strings from the scanner output.

## [0.2.0]

### Added
- Redesigned admin UI with a persistent sidebar, card system, light/dark palette that follows `prefers-color-scheme`.
- **Live scan status**: dashboard polls `/admin/scan/status` every 2 s while a scan is running and updates the badge without page reloads.
- Auto-dismissing toast notifications (4 s fade-out) for admin actions.
- Static assets served from `/static/admin/` (`admin.js`, `style.css`).

### Fixed
- "Scan in progress" badge and "Scan started" flash no longer stuck on the dashboard after a scan completes.

## [0.1.0]

### Added
- Initial release.
- Subsonic API v1.13.0 subset: `ping`, `getLicense`, `getMusicFolders`, `getIndexes`, `getArtists`, `getArtist`, `getMusicDirectory`, `getAlbum`, `getAlbumList2`, `getSong`, `search3`, `stream`, `download`, `getCoverArt`, `getPlaylists`, `getPlaylist`.
- MP3 streaming with HTTP `Range` requests (seek support).
- Read-only M3U/M3U8 playlist parsing.
- Cover art extraction from embedded APIC frames or `cover.jpg` / `folder.jpg` / `front.jpg` beside the album files.
- Full library scan at container startup and on demand via the admin panel (no periodic scheduler, no filesystem watcher).
- Single-admin authentication: argon2 hash for the admin panel + plaintext storage for Subsonic token auth (as required by the protocol).
- Admin dashboard with library stats, scan trigger, scan errors table, password change.
- Rotating log file (`{DATA_DIR}/logs/server.log`, 10 MB × 5) in addition to stdout.
- Docker deployment with multi-stage build, non-root user, `docker-compose.yml` example.
