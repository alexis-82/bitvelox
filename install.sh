#!/usr/bin/env bash
# BitVelox — one-shot installer / updater.
# Usage: ./install.sh
# What it does:
#   1. Checks docker + docker compose are available.
#   2. Creates .env from .env.example if missing (prompts for ADMIN_PASSWORD).
#   3. Creates ./music if missing.
#   4. Builds and starts the container in the background.
#   5. Prints the URL you can reach it on.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

log()  { printf "\033[1;34m==>\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m!!\033[0m %s\n" "$*" >&2; }
die()  { printf "\033[1;31m✗\033[0m %s\n" "$*" >&2; exit 1; }

# ------------------------------------------------------------------
# 1. Prerequisites
# ------------------------------------------------------------------
command -v docker >/dev/null 2>&1 \
    || die "docker not found. Install Docker Engine: https://docs.docker.com/engine/install/"

if docker compose version >/dev/null 2>&1; then
    COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE="docker-compose"
else
    die "docker compose not found. Install the Compose plugin: https://docs.docker.com/compose/install/"
fi
log "Using: $COMPOSE"

# ------------------------------------------------------------------
# 2. .env
# ------------------------------------------------------------------
if [[ ! -f .env ]]; then
    if [[ ! -f .env.example ]]; then
        die ".env.example is missing. Are you in the project root?"
    fi
    log "Creating .env from .env.example"
    cp .env.example .env

    printf "Enter an admin password for BitVelox (leave blank to keep the placeholder): "
    read -r -s admin_pwd
    printf "\n"
    if [[ -n "$admin_pwd" ]]; then
        # Portable sed in-place: uses a tmp file, works on both GNU and BSD sed.
        awk -v pw="$admin_pwd" \
            'BEGIN{FS=OFS="="} /^ADMIN_PASSWORD=/{$2=pw} 1' .env > .env.tmp \
            && mv .env.tmp .env
        log "ADMIN_PASSWORD written to .env"
    else
        warn "Kept the placeholder ADMIN_PASSWORD from .env.example — edit .env before exposing the server."
    fi
else
    log ".env already exists, leaving it as is"
fi

# ------------------------------------------------------------------
# 3. Music folder
# ------------------------------------------------------------------
if [[ ! -d music ]]; then
    log "Creating ./music (put your MP3 files here)"
    mkdir -p music
else
    log "./music already exists"
fi

# ------------------------------------------------------------------
# 4. Build + start
# ------------------------------------------------------------------
log "Building the image (this can take a few minutes on first run)"
$COMPOSE build

log "Starting the container in the background"
$COMPOSE up -d

# ------------------------------------------------------------------
# 5. Report
# ------------------------------------------------------------------
port="$(grep -E '^HTTP_PORT=' .env 2>/dev/null | tail -n1 | cut -d= -f2 || true)"
port="${port:-4040}"

log "BitVelox is running."
cat <<EOF

  Admin panel : http://localhost:${port}/
  Subsonic API: http://localhost:${port}/rest/ping.view?u=admin&p=<password>&v=1.13.0&c=test&f=json
  Logs        : $COMPOSE logs -f bitvelox
  Stop        : $COMPOSE down
  Rebuild     : $COMPOSE build --no-cache && $COMPOSE up -d

Put MP3 files into ./music, then open the admin panel and click "Scan now".
EOF
