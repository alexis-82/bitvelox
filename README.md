# BitVelox

Self-hosted, Subsonic-compatible MP3 streaming server. Point Substreamer (or any
other Subsonic client) at it and stream your MP3 library from anywhere.

- **Backend**: Python 3.12 + FastAPI + SQLite
- **Library**: mounted folder, scanned at startup and on demand from the admin UI
- **API**: Subsonic v1.13.0 subset (navigation, streaming with `Range`, cover art, M3U playlists)
- **Auth**: single admin user (Subsonic token auth for the API, session cookie for the admin UI)
- **Deploy**: single Docker container with two volumes (music + persistent data)

## Quick start with Docker

```bash
git clone <this-repo> bitvelox && cd bitvelox
./install.sh
```

The script checks Docker is installed, creates `.env` from the template
(prompting for `ADMIN_PASSWORD`), creates `./music`, builds the image and
starts the container in the background. Skip it if you prefer manual setup:

```bash
cp .env.example .env
# Edit .env and set a real ADMIN_PASSWORD
mkdir music
# Copy MP3s into ./music, ideally organised as Artist/Album/Track.mp3
docker compose up -d --build
```

The server is now listening on `http://<host>:4040`. Point Substreamer at that
URL with the credentials from `.env`. Uploading new music: SFTP/rsync into the
`./music` folder on the host, then click **Scan now** in the admin panel at
`http://<host>:4040/`.

## Local run (without Docker)

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

export MUSIC_DIR=/path/to/music
export DATA_DIR=./data
export ADMIN_PASSWORD=change-me

uvicorn app.main:app --host 0.0.0.0 --port 4040
```

## Configuration

All configuration is done via environment variables (see `.env.example`).

| Variable | Default | Purpose |
|---|---|---|
| `ADMIN_PASSWORD` | *(required)* | Admin password. If missing on first startup, a random one is generated and logged with `WARNING`. |
| `ADMIN_USER` | `admin` | Admin username. |
| `MUSIC_DIR` | `/music` | Directory with MP3 files. Read-only in Docker. |
| `DATA_DIR` | `/data` | Persistent state: SQLite index, extracted covers, session secret, logs. |
| `HTTP_PORT` | `4040` | Port the server binds to inside the container. |
| `CHANGELOG_PATH` | *(auto-detect)* | Explicit path to `CHANGELOG.md` for the in-app Changelog page. Auto-detection tries the repo root (dev/editable install) then `/app/CHANGELOG.md` (Docker) then the current working directory. |

## Library layout

The scanner walks `MUSIC_DIR` recursively for `*.mp3` files. Preferred layout:

```
music/
├── Pink Floyd/
│   └── The Wall/
│       ├── 01 - Comfortably Numb.mp3
│       ├── 02 - Hey You.mp3
│       └── cover.jpg           # optional; APIC embedded cover is used first
├── The Beatles/
│   └── Abbey Road/
│       └── ...
└── mixes/
    └── road-trip.m3u           # optional, relative paths supported
```

Tags are read via `mutagen`. If a file has no ID3 tag, artist/album/title are
derived from the path (`Artist/Album/Title.mp3`).

## Scanning

The library is scanned:

1. **At container startup** — automatic full scan of `MUSIC_DIR`.
2. **On demand** — click "Scan now" in the admin panel.

Each scan is a full scan (re-reads every file). There is no background watcher
and no periodic timer. Tracks whose files have been removed from disk are
purged from the index at the end of each scan.

## HTTPS

The server ships **without** TLS. Put a reverse proxy in front of it — for
example Caddy:

```caddyfile
music.example.com {
    reverse_proxy localhost:4040
}
```

or nginx / Traefik. Caddy is the least-effort option because it handles Let's
Encrypt automatically.

## Substreamer configuration

In Substreamer, add a server with:

- **URL**: `https://music.example.com` (or `http://<host>:4040` if you skip TLS)
- **Username**: value of `ADMIN_USER`
- **Password**: value of `ADMIN_PASSWORD`

## Running the tests

```bash
pip install -e ".[dev]"
pytest
```

## Troubleshooting

**`/changelog` returns 404 "CHANGELOG.md not found".**
The app tries several paths (repo root, `/app/CHANGELOG.md`, cwd). Check the
container logs — a `WARNING` line lists exactly which paths were tried, e.g.
`docker logs bitvelox 2>&1 | grep -i changelog`. If none of them match your
deployment, set `CHANGELOG_PATH=/absolute/path/to/CHANGELOG.md` in your `.env`
and restart. If you're on Docker and just added the file, make sure you rebuilt
the image: `docker compose build --no-cache && docker compose up -d`.

## What is NOT supported (by design)

- Formats other than MP3 (no FLAC/OGG/AAC/M4A)
- Transcoding
- Multi-user, ACLs, user registration
- Podcasts, jukebox, share links, chat
- Uploads via web UI (use SFTP/rsync)
- Writing back tags to source files
- Editing playlists from the client (`.m3u` files are read-only)
- HTTPS termination (delegated to a reverse proxy)

See `spec.md` for the full non-goals list.
