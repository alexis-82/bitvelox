# Task breakdown — Server MP3 Streaming

Ogni task è chiudibile in modo binario (fatto/non fatto) e ha un criterio di "Done" (DoD) verificabile.

## Fase 1 — Bootstrap

- [x] **Task 1**: Creare struttura progetto e `pyproject.toml` con dipendenze (`fastapi`, `uvicorn[standard]`, `sqlalchemy`, `mutagen`, `pillow`, `passlib[argon2]`, `python-multipart`, `pydantic-settings`, `jinja2`, `pytest`, `httpx`).
  - DoD: `pip install -e .` va a buon fine in un venv pulito; `python -c "import app"` non errora.
- [x] **Task 2**: Implementare `src/app/config.py` con `Settings` (pydantic-settings) che legge `MUSIC_DIR`, `DATA_DIR`, `ADMIN_USER`, `ADMIN_PASSWORD`, `HTTP_PORT`, con default corretti.
  - DoD: test `test_config.py` verifica default e override via env.
- [x] **Task 3**: Implementare `src/app/logging_setup.py` con handler stdout + `RotatingFileHandler` (10 MB × 5) su `{DATA_DIR}/logs/server.log`.
  - DoD: chiamando `setup_logging()` e loggando, il messaggio appare a stdout E nel file; rotazione verificata simulando write oltre 10 MB in test.
- [x] **Task 4**: Creare `src/app/main.py` con app FastAPI vuota, endpoint `/rest/ping.view` che risponde `200` con body Subsonic `ok` (nessuna auth ancora), startup hook che chiama `setup_logging()`.
  - DoD: `uvicorn app.main:app` risponde 200 su `/rest/ping.view?f=json` con `{"subsonic-response": {"status": "ok", "version": "1.13.0"}}`.

## Fase 2 — Modello dati + DB

- [x] **Task 5**: Implementare `src/app/db.py` con engine SQLAlchemy (SQLite in `{DATA_DIR}/library.db`), `SessionLocal`, `Base`, funzione `init_db()`.
  - DoD: chiamando `init_db()` con `DATA_DIR` temp, il file `library.db` viene creato; test in-memory (`sqlite:///:memory:`) crea le tabelle.
- [x] **Task 6**: Definire modelli in `src/app/models.py`: `Artist(id, name, name_lower)`, `Album(id, artist_id, name, year, cover_path)`, `Track(id, album_id, artist_id, path, title, track_no, disc_no, duration_s, bitrate, size_bytes, mime_type)`, `Playlist(id, name, path)`, `PlaylistEntry(id, playlist_id, track_id, position)`, `ScanError(id, path, error, ts)`, `AdminUser(id, username, password_hash)`, `ScanState(id, running, started_at, finished_at, last_scan_ok, error_count, total_tracks)`. Indici su `Artist.name_lower`, `Album.name`, `Track.title`.
  - DoD: `init_db()` crea tutte le tabelle e gli indici; test verifica presenza delle colonne e degli indici via inspector SQLAlchemy.
- [x] **Task 7**: Implementare bootstrap `AdminUser`: se non esiste alcun record, crearlo con `ADMIN_USER` e hash argon2 di `ADMIN_PASSWORD` (o password random se assente, loggata una sola volta con `WARNING`).
  - DoD: test con DB vuoto + env → `AdminUser` presente con hash argon2 valido; con `ADMIN_PASSWORD` assente, log contiene la password generata; secondo bootstrap sullo stesso DB → no override.

## Fase 3 — Scanner

- [x] **Task 8**: Implementare `src/app/scanner.py::iter_mp3_files(root)` che ritorna generatore di path `.mp3` in `root`, ignorando file dot e simlink pericolosi.
  - DoD: test con fixture directory `tests/fixtures/music/` contenente 3 MP3 e file rumore → il generatore ritorna esattamente i 3 mp3.
- [x] **Task 9**: Implementare `read_tags(path)` che usa `mutagen` per estrarre artist/album/title/track_no/disc_no/year/duration/bitrate; ritorna dataclass `TrackMeta` o solleva `TagReadError` con messaggio.
  - DoD: test su MP3 con tag ID3v2 completi, ID3v1 solo, senza tag (fallback su path `Artista/Album/Traccia.mp3`), file corrotto (raises).
- [x] **Task 10**: Implementare `full_scan(session, music_dir)` che: itera MP3, upsert Artist/Album/Track, gestisce `TagReadError` scrivendo in `ScanError`, a fine scansione cancella dall'indice le tracce non incontrate. Aggiorna `ScanState` (start/finish, counts). Lock singolo con `threading.Lock` a livello modulo — secondo call ritorna `AlreadyRunning`.
  - DoD: test scansiona fixture, verifica righe Artist/Album/Track; secondo call in thread concorrente durante il primo → `AlreadyRunning`; rimozione file + re-scan → traccia rimossa; file corrotto → in `ScanError` senza abortire.

## Fase 4 — Cover art

- [x] **Task 11**: Implementare `src/app/covers.py::extract_cover(mp3_path, out_dir)` che estrae immagine embedded (APIC), la salva come `{sha1(album_key)}.jpg` in `out_dir`, ritorna path. Se assente, cerca `cover.jpg`/`folder.jpg`/`front.jpg` nella cartella dell'MP3 e ritorna quel path. Se nulla trovato, ritorna `None`.
  - DoD: test MP3 con APIC → file creato; MP3 senza APIC + `cover.jpg` accanto → ritorna path del file; nulla → `None`.
- [x] **Task 12**: Implementare `get_cover_resized(path, size)` con Pillow che restituisce bytes JPEG ridimensionati quadrati (cache in RAM opzionale — LRU semplice).
  - DoD: test su cover 1000×1000 con `size=300` → output ≤ 300×300, JPEG valido.

## Fase 5 — Auth Subsonic

- [x] **Task 13**: Implementare `src/app/auth.py::verify_subsonic_token(username, token, salt, stored_hash)` che verifica `t == md5(password + salt)` (Subsonic legacy) e anche `p=<password>` in chiaro / `p=enc:<hex>` (per compatibilità).
  - DoD: test con vector noto Subsonic (password, salt, token md5 atteso) → verify vero; token errato → falso; supporto `p=` diretto → vero.
- [x] **Task 14**: Creare dipendenza FastAPI `subsonic_auth` che estrae `u`, `t`, `s`, `p`, `v`, `c`, `f` dai query params, carica `AdminUser`, verifica; su fallimento ritorna risposta Subsonic error code 40 nel formato richiesto (`f=json` o XML).
  - DoD: test su endpoint dummy protetto: senza params → error 10, credenziali errate → error 40, ok → passa.

## Fase 6 — API Subsonic (navigazione)

- [x] **Task 15**: Implementare `src/app/subsonic/responses.py::build_response(payload, fmt)` che serializza in XML (`<subsonic-response status="ok" version="1.13.0">…</subsonic-response>`) o JSON (`{"subsonic-response": {...}}`), e `build_error(code, message, fmt)`.
  - DoD: test snapshot XML e JSON per payload noto.
- [x] **Task 16**: Endpoint `ping`, `getLicense`, `getMusicFolders` (ritorna una sola cartella con id=1).
  - DoD: `GET /rest/ping.view?f=json&...` → `status: ok`; `getMusicFolders` → un `musicFolder` con id 1, name "Music".
- [x] **Task 17**: Endpoint `getIndexes` e `getArtists` che ritornano artisti raggruppati per lettera iniziale (Subsonic `<index name="A">`).
  - DoD: fixture con 3 artisti (Alfa, Beta, Charlie) → response con 3 gruppi lettera; test XML e JSON.
- [x] **Task 18**: Endpoint `getMusicDirectory`, `getArtist`, `getAlbum`, `getAlbumList2` (type=alphabeticalByName con paginazione `size`/`offset`), `getSong`.
  - DoD: test copre gerarchia navigazione: artist → album → track con id numerici stabili tra request.
- [x] **Task 19**: Endpoint `search3` con prefix match case-insensitive su `artist.name_lower`, `album.name`, `track.title`, con parametri `artistCount`, `albumCount`, `songCount` (default 20).
  - DoD: fixture con "Pink Floyd", "Pink" isolato, "Blue" → `search3?query=pin` ritorna entrambi Pink*.

## Fase 7 — Streaming

- [x] **Task 20**: Implementare `src/app/subsonic/streaming.py::range_response(path, range_header)` che: parse `Range: bytes=<start>-<end>`, apre file, ritorna `StreamingResponse` con `Content-Type: audio/mpeg`, `Accept-Ranges: bytes`, `Content-Length`, `Content-Range` (solo se range), status 206 o 200.
  - DoD: unit test con file 1000 bytes: no Range → 200 + 1000 bytes; `Range: bytes=100-199` → 206 + 100 bytes + `Content-Range: bytes 100-199/1000`; `Range: bytes=900-` → 206 fino a fine; range malformato → 416.
- [x] **Task 21**: Endpoint `/rest/stream.view?id=` e `/rest/download.view?id=` che usano `range_response` (download ignora Range e forza `Content-Disposition: attachment`).
  - DoD: test integrato via `httpx` con MP3 fixture; ID sconosciuto → error 70 (not found).
- [x] **Task 22**: Endpoint `/rest/getCoverArt.view?id=&size=` che risolve id → cover path e ritorna JPEG ridimensionato (se `size` presente) o originale.
  - DoD: test con album con cover embedded → 200 + JPEG; senza cover → 404 (o placeholder). ID sconosciuto → error 70.

## Fase 8 — Playlist M3U

- [x] **Task 23**: Estendere `full_scan` per rilevare `.m3u`/`.m3u8` in `MUSIC_DIR`, parsare (skip righe `#`, path relativi risolti rispetto al file M3U), risolvere in `track_id` esistenti, popolare `Playlist` + `PlaylistEntry`. Voci non risolvibili → log `WARNING` (non `ScanError`).
  - DoD: fixture con `mix.m3u` che referenzia 2 tracce esistenti + 1 mancante → `Playlist` "mix" con 2 entries in ordine.
- [x] **Task 24**: Endpoint `getPlaylists` (lista) e `getPlaylist?id=` (dettaglio con entries).
  - DoD: test verifica JSON + XML.

## Fase 9 — Admin UI

- [x] **Task 25**: Implementare middleware session cookie firmato (con `itsdangerous` o `starlette.middleware.sessions`) usando `SECRET_KEY` letta da env (auto-generata al primo avvio e persistita in `{DATA_DIR}/secret.key`).
  - DoD: test: dopo POST `/login` corretto, cookie `session` presente e valido su richiesta successiva.
- [x] **Task 26**: Template `login.html`, route `GET /` (redirect a `/login` se non loggato, altrimenti `dashboard.html`), `POST /login` con rate limit (max 5 tentativi errati / 5 min per IP — semplice contatore in memoria).
  - DoD: test login corretto → 302 verso `/`; login errato 6 volte → 429.
- [x] **Task 27**: Route `POST /admin/rescan` che chiama `full_scan` in background thread; se lock già preso, ritorna dashboard con messaggio "Scan già in corso" (no doppio thread).
  - DoD: test: primo POST → 202 + thread partito; secondo POST mentre in corso → 202 + messaggio "in corso"; verifica non partano due thread.
- [x] **Task 28**: Route `POST /admin/password` che verifica password attuale, aggiorna hash argon2, invalida sessioni esistenti (rigenerando `SECRET_KEY`? no, troppo aggressivo — semplicemente forza re-login).
  - DoD: test cambio password valido → 302 + nuovo hash in DB; password attuale errata → messaggio errore + no update.
- [x] **Task 29**: Template `dashboard.html` con: stato indice (counts artisti/album/tracce), ultima scansione (timestamp + esito), badge "Scan in corso" se attivo, form password, pulsante Scan now, tabella `ScanError` (path + errore).
  - DoD: rendering non solleva eccezioni con DB popolato di fixture; presenti tutti gli elementi verificabili con selettori.

## Fase 10 — Docker

- [x] **Task 30**: Scrivere `Dockerfile` multi-stage (`builder` per `pip install` in venv, `runtime` che copia venv + app, utente `app` non-root uid 1000, expose 4040, entrypoint `uvicorn`).
  - DoD: `docker build -t mp3-server .` produce immagine < 250 MB (`docker images`); `docker run --rm mp3-server /bin/sh -c 'id'` mostra uid 1000.
- [x] **Task 31**: Scrivere `docker-compose.yml` con servizio, env vars da `.env`, volume `./music:/music:ro` e volume named `mp3-data:/data`, `restart: unless-stopped`, port `4040:4040`.
  - DoD: `docker compose up -d` avvia il container, `curl localhost:4040/rest/ping.view?u=admin&p=<pwd>&v=1.13.0&c=test&f=json` → status ok.
- [x] **Task 32**: `.dockerignore` esclude `tests/`, `.venv`, `__pycache__`, `.git`, `music/`, `data/`.
  - DoD: `docker build` non copia queste dir (verifica con `docker history` o `--progress=plain`).

## Fase 11 — Verifica end-to-end

- [ ] **Task 33**: Test manuale con Substreamer su Android reale — checklist criteri di accettazione della spec.
  - DoD: tutti i criteri di accettazione della spec passano; screenshot o note in `docs/manual-test.md`.
- [x] **Task 34**: Scrivere `README.md` con: overview, run locale con `uvicorn`, run con Docker Compose, esempio Caddyfile davanti, configurazione Substreamer.
  - DoD: seguendo il README da zero su una VPS pulita, il server è raggiungibile via HTTPS con Substreamer che vede la libreria.
- [x] **Task 35**: Creare `.env.example` con tutte le env var documentate e valori d'esempio (non segreti reali).
  - DoD: `cp .env.example .env` + edit + `docker compose up` funziona.

---

## Iterazione v1.1 — Miglioramenti admin UI

### Fase 12 — Scan status live (fix bug 3 e 4)

- [x] **Task 36**: Aggiungere endpoint `GET /admin/scan/status` che ritorna JSON `{running: bool, started_at: ISO|null, finished_at: ISO|null, last_scan_ok: bool|null, total_tracks: int, error_count: int}`. Richiede sessione admin, altrimenti 401 JSON.
  - DoD: test `test_admin_library.py::test_scan_status_endpoint`: chiamata da sessione autenticata durante scan → `running: true`; a scan finito → `running: false` + `finished_at` valorizzato; senza login → 401.
- [x] **Task 37**: Creare `src/app/admin/static/admin.js` con: polling `/admin/scan/status` ogni 2 s solo quando `#scan-status[data-running="true"]`; aggiornamento DOM del blocco status; stop polling appena `running=false` e mostra "Scan completed at HH:MM:SS"; auto-dismiss dei `.toast` dopo 4 s con fade-out CSS.
  - DoD: smoke test manuale: click "Scan now", il badge "Scan in progress" appare, l'orario "started at" si aggiorna, alla fine appare "Scan completed", tutto senza refresh. Toast "Scan started" scompare in 4 s.
- [x] **Task 38**: Montare `StaticFiles(directory="src/app/admin/static")` su `/static/admin` in `create_app()` di `src/app/main.py`. Aggiornare `base.html` per referenziare `/static/admin/admin.js` e `/static/admin/style.css`.
  - DoD: `GET /static/admin/admin.js` risponde 200 con `application/javascript`; il file HTML lo include con `<script defer>`.

### Fase 13 — Library browser (Goal 10)

- [x] **Task 39**: Route `GET /library` che ritorna una pagina con lista artisti (nome + numero album) ordinati alfabeticamente, usando un'unica query con `func.count(Album.id)` + `group_by(Artist.id)`.
  - DoD: test: pagina risponde 200 se loggato, 302 verso `/login` se no; con fixture di 2 artisti, contiene entrambi i nomi.
- [x] **Task 40**: Route `GET /library/artist/{id}` con lista album dell'artista (cover thumbnail via `/rest/getCoverArt.view` — richiede token session per l'admin, o servita direttamente da endpoint admin dedicato per evitare auth Subsonic da pagina admin).
  - DoD: test: pagina mostra nome artista + tutti i suoi album con anno e numero tracce; 404 su id inesistente.
- [x] **Task 41**: Route `GET /library/album/{id}` con header album (cover + artista + anno + durata totale) e tabella tracce (# / titolo / durata mm:ss / bitrate kbps).
  - DoD: test: pagina mostra le tracce ordinate per `disc_no, track_no, title_lower`; 404 su id inesistente.
- [x] **Task 42**: Endpoint admin `GET /admin/cover/{album_id}` che serve l'immagine album (bypassa auth Subsonic, richiede solo sessione admin) — usato dai template library per le miniature. 200 con `image/jpeg` (o `image/png`), 404 se assente, 302 al login se non autenticato.
  - DoD: test: cover di album con `cover_path` valido → 200 + JPEG; album senza cover → 404; senza login → 302.

### Fase 14 — Redesign UI (Goal 11)

- [x] **Task 43**: Creare `src/app/admin/static/style.css` con: variabili CSS `--bg`, `--card`, `--text`, `--muted`, `--accent`, `--danger`, `--ok` sia per light che dark tramite `@media (prefers-color-scheme: dark)`. Font-stack sistema. Layout a due colonne: sidebar 220px fixed + main. Sistema di card con spacing 1.25rem, bordi arrotondati 8px, ombra soft. Bottoni con hover state. Tabelle con zebra light. Toast fissi bottom-right con animazione fade-in / fade-out.
  - DoD: pagine renderizzano coerenti in light e dark (verificabile a mano); nessun horizontal scroll sotto 900px.
- [x] **Task 44**: Riscrivere `base.html` per usare `style.css` esterno + sidebar di navigazione (`Dashboard`, `Library`, `Logout`) con evidenziazione voce attiva; container `#toasts` fixed bottom-right. Rimuovere lo stile inline attuale. Adattare `dashboard.html`, `login.html` alla nuova struttura senza rompere le stringhe usate dai test (`"Library"`, `"Wrong username or password"`, `"Current password is wrong"`).
  - DoD: `pytest tests/test_admin.py` resta 6/6 verde; ispezione visiva mostra sidebar + card, dark mode funziona su OS con tema scuro.

### Fase 15 — Test end-to-end v1.1

- [x] **Task 45**: Aggiornare `tests/test_admin.py` per coprire i nuovi endpoint (`/library`, `/library/artist/{id}`, `/library/album/{id}`, `/admin/scan/status`, `/admin/cover/{id}`) con sessione autenticata, e verificare che le route esistenti non regressino.
  - DoD: `pytest tests/test_admin.py tests/test_admin_library.py -q` verde con almeno 5 nuovi test.
- [ ] **Task 46**: Smoke test manuale: `uvicorn app.main:app`, login, click Library → naviga fino a un album → torna a Dashboard → click Scan now → osserva aggiornamento live senza refresh.
  - DoD: nessun step richiede refresh manuale per vedere aggiornamenti.

---

## Iterazione v1.2 — Rimozione "Unknown" + Tracks tab

### Fase 16 — Fallback pulito nello scanner

- [x] **Task 47**: Correggere `src/app/scanner.py::_fallback_from_path`. Nuovo comportamento: se `parts == 1` (file loose in `/music`) → `artist = ""`, `album = ""`, `title = filename senza estensione`; se `parts == 2` (`/music/<folder>/<file>`) → `artist = ""`, `album = parts[0]`, `title = filename`; se `parts >= 3` → `artist = parts[-3]`, `album = parts[-2]`, `title = filename` (invariato). **Nessuna stringa "Unknown Artist" o "Unknown Album" più prodotta.**
  - DoD: aggiornare `tests/test_scanner.py::test_read_tags_fallback_from_path` per verificare il nuovo comportamento su 3 casi (loose, 1 folder, 2 folders); aggiungere test che verifica assenza della stringa "Unknown" in artist/album prodotti.
- [x] **Task 48**: In `src/app/scanner.py::read_tags`, quando `TPE1` è assente, provare `TPE2` (AlbumArtist) come fallback per il campo `artist` prima di ricadere sul path.
  - DoD: nuovo test in `tests/test_scanner.py`: MP3 con solo `TPE2` valorizzato → `meta.artist` = valore di `TPE2`.

### Fase 17 — Library UI: tab Artists / Tracks

- [x] **Task 49**: Nuova route `GET /library/tracks` in `src/app/admin/routes.py`, paginata (default 100 per pagina, param `?page=N`), che ritorna tutte le tracce ordinate per `title_lower` con `artist.name` e `album.name` in join. Richiede login (302 se no).
  - DoD: nuovo test `tests/test_admin_library.py::test_tracks_tab_shows_all_including_loose`: crea 3 tracce (2 con artist tag, 1 loose senza artist) → la pagina contiene tutti e 3 i titoli.
- [x] **Task 50**: Modificare `library_index` in `src/app/admin/routes.py` per filtrare `Artist.name != ""` (nasconde il cluster fittizio degli artisti loose dalla griglia).
  - DoD: aggiornare/nuovo test che verifica: 1 artista con nome + 1 traccia loose (artist name "") → la pagina `/library` mostra solo l'artista con nome; il conteggio "N artists" riflette quello reale.
- [x] **Task 51**: Creare `src/app/admin/templates/library_tracks.html` con: tabella #/Title/Artist/Album/Duration, righe cliccabili verso `/library/album/<id>` (se `album_id`), link paginazione prev/next in fondo. Aggiornare `library_index.html` con una tab-bar in cima (`Artists` attivo di default | `Tracks`) — link `/library` e `/library/tracks`. Aggiungere CSS `.tabs` in `style.css`.
  - DoD: `pytest tests/test_admin_library.py` verde inclusi i test nuovi; ispezione visiva: la tab bar si vede sulla pagina, cliccando "Tracks" si vede la tabella con tutti i file.

### Fase 18 — Verifica finale

- [x] **Task 52**: Test di regressione: `pytest` su tutta la suite verde. Verifica che il full-scan su un music dir con 2 loose + 1 file in cartella produca (a) 0 record con name "Unknown ...", (b) 3 tracce visibili in `/library/tracks`, (c) 1 artista visibile nella griglia se il file in cartella ha tag artist, altrimenti 0.
  - DoD: nuovo test integrato che asserisce le tre condizioni.
- [x] **Task 53**: Aggiungere il numero di versione alla dashboard admin. Bump `__version__` in `src/app/__init__.py` e `version` in `pyproject.toml` a `0.3.0`. Passare `app_version` al context di `library_index`, `library_artist`, `library_album`, `index` (dashboard) — o meglio: iniettarlo direttamente in `base.html` tramite un context processor / template global. Mostrare `v{{ app_version }}` in fondo alla sidebar (subtle style).
  - DoD: `GET /` autenticato contiene la stringa `v0.3.0` nel body; test `tests/test_admin.py` verifica la presenza; visivamente si vede `v0.3.0` nella sidebar.

---

## Iterazione v1.3 — Library = filesystem browser

### Fase 19 — Filesystem browser core

- [x] **Task 54**: Creare `src/app/admin/fs_browse.py` con `list_directory(music_root: Path, rel_path: str) -> BrowseResult` che: (a) rigetta path traversal risolvendo `music_root / rel_path` e verificando `startswith(music_root.resolve())`; (b) ritorna `folders` (list di `{name, rel_path}`) e `files` (list di `{name, rel_path, size_bytes}`) ordinate alfabeticamente; (c) skippa dotfiles e non-`.mp3` per i file; (d) ritorna anche `breadcrumb` come list di `{name, rel_path}` risalendo i segmenti.
  - DoD: nuovo file di test `tests/test_fs_browse.py` con: enumerazione base, rigetto `..`, rigetto path assoluto, breadcrumb corretto a 3 livelli di profondità.
- [x] **Task 55**: Nuova route `GET /library` in `src/app/admin/routes.py` che accetta query param `?path=<rel>` (default `""` = root), chiama `list_directory`, arricchisce ogni file con `title`, `duration_s` da `Track` (una sola query `WHERE path IN (:list)`), renderizza `library.html`. Se il path è invalido (traversal / non esiste / non è dir) → 404. Redirect a `/login` se non autenticato.
  - DoD: test in nuovo `tests/test_admin_library.py`: (a) `/library` senza login → 302 al login; (b) con MUSIC_DIR = fixture 2 file loose + 1 cartella con 1 file, la root mostra 2 file + 1 folder; (c) `/library?path=<folder>` mostra il file dentro; (d) `/library?path=../etc` → 404.
- [x] **Task 56**: Creare template `src/app/admin/templates/library.html`. Contiene: breadcrumb (Library / segment1 / segment2 / …), tabella con due sezioni — folders in cima (icona 📁 nome cliccabile) e files (icona 🎵 nome + titolo tag + durata `mm:ss` + dimensione `X.X MB`). Nessuna azione cliccabile sui file. Se cartella vuota, messaggio "Empty folder".
  - DoD: rendering non solleva eccezioni, test verifica presenza breadcrumb, nomi cartelle e file, e assenza di link/pulsanti azione sui file.

### Fase 20 — Rimozione codice metadata-based

- [x] **Task 57**: Rimuovere completamente da `src/app/admin/routes.py` le funzioni `library_index`, `library_artist`, `library_album`, `library_tracks`, `admin_cover` e tutte le loro dipendenze non usate altrove (`func`, se non serve altrove). Rimuovere i template `library_index.html`, `library_artist.html`, `library_album.html`, `library_tracks.html`. Cancellare i vecchi test in `tests/test_admin_library.py` che li verificavano.
  - DoD: `pytest` verde su tutta la suite; `grep -r "library_index\|library_artist\|library_album\|library_tracks\|admin_cover"` restituisce zero match nel codebase eccetto in questo `tasks.md` e `plan.md` (documentazione storica).
- [x] **Task 58**: Piccole aggiunte a `src/app/admin/static/style.css`: classe `.fs-row` (padding, hover), `.fs-icon` (dimensione fissa, allineamento verticale), riuso `.breadcrumbs` esistente. Nessun refactor di CSS preesistente.
  - DoD: ispezione visiva: righe con altezza consistente, icona allineata, cursor pointer solo su folder.

### Fase 21 — Verifica

- [x] **Task 59**: Suite completa verde dopo rimozione + smoke manuale: aprire `/library` con MUSIC_DIR reale, cliccare cartella, verificare navigazione e breadcrumb.
  - DoD: `pytest -q` verde, nessun test residuo che referenzia le vecchie route metadata; smoke ok.

### Fase 22 — Fix visualizzazione file (feedback utente)

- [x] **Task 60**: In `src/app/admin/routes.py` route `library`, quando si arricchisce `files_view` con `title` dal DB, includere il titolo **solo se differisce** dal filename senza estensione (confronto case-insensitive). Se combaciano, mettere `title = None`. Il template `library.html` già gestisce `{% if f.title %}`, non serve modificarlo.
  - DoD: aggiungere 2 test in `tests/test_admin_library.py`: (a) file `song.mp3` senza tag reale → il DB avrà `title == "song"` (fallback stem) → la riga file nella HTML contiene "song.mp3" **una sola volta**, non "song.mp3 · song"; (b) file con `title` tag = "Real Title" diverso dal filename → risposta contiene sia "song.mp3" che "Real Title".

### Fase 23 — Rebrand → BitVelox

- [x] **Task 61**: Rebrand strings user-facing HTML. In `src/app/admin/templates/base.html`: `<title>` block e `.sidebar-brand` → `BitVelox`. In `login.html`: block title `Login — BitVelox` + `<h2>BitVelox</h2>`. In `library.html` e `dashboard.html`: suffisso block title `— BitVelox`. In `src/app/main.py`: `FastAPI(title="BitVelox", …)`.
  - DoD: `grep -r "mp3-server" src/` restituisce zero risultati (case-sensitive). Test `test_admin.py::test_dashboard_shows_version` continua verde. Nuovo test verifica presenza stringa `BitVelox` nell'HTML della dashboard.
- [x] **Task 62**: Rinominare package + entry point in `pyproject.toml`. `name = "bitvelox"` (lowercase). `[project.scripts]` → `bitvelox = "app.main:run"`. Il package Python interno `src/app/` resta invariato.
  - DoD: `pip install -e .` va a buon fine; `pip show bitvelox` mostra il nuovo nome; `bitvelox --help` (o solo `bitvelox` che avvia uvicorn) funziona nel venv.
- [x] **Task 63**: Rinominare in `docker-compose.yml` il service key, `container_name` e `image` da `mp3-server` a `bitvelox`. Aggiornare `Dockerfile` se contiene stringhe brand (spot check).
  - DoD: `docker compose config` valida senza errori; nessun match `mp3-server` nel file. `docker compose up -d` (se docker disponibile sul target) parte con `bitvelox`.
- [x] **Task 64**: Aggiornare `README.md`: heading `# BitVelox`, descrizione, esempio git clone `<repo> bitvelox && cd bitvelox`. Un paragrafo iniziale di descrizione breve del brand va bene ma minimale (no marketing, no logo).
  - DoD: `grep -c "mp3-server" README.md` = 0; il file resta coerente e leggibile.
- [x] **Task 65**: Cosmetico: aggiornare `tests/conftest.py` prefissi tempfile (`mp3-server-test-` → `bitvelox-test-`) e i path di esempio in `tests/test_config.py` (`/var/lib/mp3-server` → `/var/lib/bitvelox`). Solo consistenza — non impatta il comportamento.
  - DoD: `pytest tests/test_config.py` verde; `grep "mp3-server" tests/` restituisce zero.

### Fase 24 — Changelog

- [x] **Task 66**: Creare `CHANGELOG.md` al root del repository seguendo Keep a Changelog (https://keepachangelog.com). Sezioni: `[Unreleased]` (voce "Changelog page + CHANGELOG.md" di questa iterazione), `[0.3.0]` (rebrand BitVelox + fix duplicato filename/title + filesystem browser + fix "Unknown" scanner + versione in dashboard + live scan status + redesign UI), `[0.2.0]` (redesign admin UI + Library metadata browser + live scan status), `[0.1.0]` (initial: Subsonic API, streaming Range, admin panel, Docker).
  - DoD: file esiste con almeno 4 sezioni; markdown ben formato; una intestazione `# Changelog` in cima.
- [x] **Task 67**: Aggiungere `markdown>=3.5` a `[project.dependencies]` in `pyproject.toml`. Reinstall con `pip install -e .` per averla disponibile.
  - DoD: `python -c "import markdown; print(markdown.__version__)"` risponde senza errori.
- [x] **Task 68**: Nuova route `GET /changelog` in `src/app/admin/routes.py`. Se non autenticato → 302 al login. Se autenticato, legge `CHANGELOG.md` risolvendo dal path del modulo (`Path(__file__).parents[3] / "CHANGELOG.md"`); se il file manca → 404. Converte markdown → HTML con `markdown.markdown(text, extensions=["fenced_code", "tables"])`. Rende `changelog.html` con contesto `{"changelog_html": html, "nav_active": "changelog"}`.
  - DoD: nuovo test in `tests/test_admin.py`: (a) `GET /changelog` senza login → 302; (b) con login → 200 e contiene tag HTML derivato da markdown; (c) contiene la stringa "Unreleased" o "0.3.0".
- [x] **Task 69**: Creare `src/app/admin/templates/changelog.html` che estende `base.html`, header `<h1>Changelog</h1>`, poi `{{ changelog_html|safe }}` in una `.card`. Nessuna dipendenza da nav highlight.
  - DoD: rendering ok, nessun XSS (usare solo `fenced_code` e `tables`, non estensione `html` che consentirebbe HTML raw).
- [x] **Task 70**: In `src/app/admin/templates/base.html` aggiungere link "Changelog" **subito sopra** `<div class="sidebar-version">`. Nuovo container `<div class="sidebar-footer">` che avvolge Changelog + version, con la voce Changelog come `<a href="/changelog" class="sidebar-footer-link">`. In `src/app/admin/static/style.css` aggiungere `.sidebar-footer` (`margin-top: auto`, allineato in fondo) e `.sidebar-footer-link` (colore muted, hover accent, padding coerente).
  - DoD: ispezione visiva: link Changelog cliccabile subito sopra `v0.3.0`, entrambi in fondo alla sidebar; test HTML: presenza `href="/changelog"` nella dashboard.
- [x] **Task 71**: Aggiornare `Dockerfile` runtime stage per copiare `CHANGELOG.md` in `/app/CHANGELOG.md` (aggiungere `COPY CHANGELOG.md ./` dopo il `COPY --from=builder` del src). Verificare che `.dockerignore` non lo escluda.
  - DoD: `grep CHANGELOG .dockerignore` = 0; ispezione Dockerfile mostra la nuova COPY.

### Fase 25 — Fix path resolution CHANGELOG.md

- [x] **Task 72**: Refactor risoluzione `_CHANGELOG_PATH` in `src/app/admin/routes.py`. Introdurre helper `_resolve_changelog_path() -> Path | None` che prova in ordine: (a) env var `CHANGELOG_PATH` se settata e file esiste; (b) `Path(__file__).resolve().parents[3] / "CHANGELOG.md"` (editable install / dev); (c) `Path("/app/CHANGELOG.md")` (Docker); (d) `Path.cwd() / "CHANGELOG.md"` (fallback cwd). Ritorna il primo path esistente o `None`. La chiamata avviene **a ogni request**, non a module-load, così un file aggiunto dopo l'avvio del server è visibile.
  - DoD: 2 nuovi test in `tests/test_admin.py`: (a) con `CHANGELOG_PATH` env var puntante a un file temp con contenuto noto → route ritorna 200 e contiene quel contenuto; (b) con env var non settata e file esistente al path del modulo → funziona (test esistente `test_changelog_renders_markdown_to_html` copre già).
- [x] **Task 73**: Nella route `/changelog`, quando la risoluzione ritorna `None`, loggare a WARNING con la lista dei path tentati (formato: `changelog: file not found, tried: [path1, path2, ...]`). La response 404 include un breve testo di aiuto: "CHANGELOG.md not found — set CHANGELOG_PATH env var or check server logs."
  - DoD: test con `caplog.at_level(logging.WARNING)` che asserisce presenza della stringa "tried" nel log dopo una request 404 (creata puntando `CHANGELOG_PATH` a un path fake e temporaneamente rinominando il vero file — o usando monkeypatch sul helper).
- [x] **Task 74**: Aggiungere alla tabella env vars del `README.md` la voce `CHANGELOG_PATH` (optional, default: auto-detect). E una piccola sezione "Troubleshooting" con: "Se `/changelog` risponde 404, controlla i log del container per vedere quali path sono stati tentati, oppure imposta `CHANGELOG_PATH` esplicitamente."
  - DoD: `README.md` contiene la nuova env var e la sezione troubleshooting; `grep -c "CHANGELOG_PATH" README.md` >= 2.
