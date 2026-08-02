# Piano tecnico — Server MP3 Streaming (Subsonic-compatible)

## Approccio

Applicazione monolitica Python 3.12 + FastAPI, servita da `uvicorn`. Un modulo per il **library scanner** (mutagen → SQLite), un modulo per l'**API Subsonic** (routing `/rest/*` con risposte XML/JSON e schema di errore Subsonic), un modulo per l'**admin UI** (Jinja2 templates + form login/rescan/password). Persistenza in SQLite dentro `/data`. Cover art servita da file embedded (estratti a `/data/covers/`) o `cover.jpg` accanto ai file. Il container gira come utente non-root con volumi montati per `/music` (read-only) e `/data` (read-write). Sviluppo incrementale bottom-up: prima l'indice, poi lo streaming, poi il resto dell'API, poi l'admin, poi Docker.

## File / moduli coinvolti

Layout `src/app/`:

- [ ] `pyproject.toml` — dipendenze, entry point, config pytest.
- [ ] `README.md` — istruzioni run locale + Docker.
- [ ] `.env.example` — template variabili d'ambiente.
- [ ] `src/app/__init__.py` — package marker.
- [ ] `src/app/main.py` — bootstrap FastAPI, mount router, startup hook (init DB + first scan), config logging.
- [ ] `src/app/config.py` — lettura env vars in oggetto `Settings` (pydantic-settings).
- [ ] `src/app/logging_setup.py` — logger su stdout + `RotatingFileHandler` (10 MB × 5) su `/data/logs/server.log`.
- [ ] `src/app/db.py` — engine SQLAlchemy, `SessionLocal`, `init_db()` con `create_all`.
- [ ] `src/app/models.py` — modelli ORM: `Artist`, `Album`, `Track`, `Playlist`, `PlaylistEntry`, `ScanError`, `AdminUser`, `ScanState`.
- [ ] `src/app/scanner.py` — full scan della cartella `MUSIC_DIR`: enumera `.mp3`, legge tag con mutagen, upsert nel DB, estrae cover art embedded, parse `.m3u`/`.m3u8`, aggiorna `ScanError` table. Lock singolo tramite `threading.Lock` + flag stato in `ScanState`.
- [ ] `src/app/covers.py` — estrazione cover embedded → `/data/covers/<hash>.jpg`, fallback a `cover.jpg`/`folder.jpg` nella cartella album, resize on-demand con Pillow.
- [ ] `src/app/auth.py` — hash password argon2 (passlib), verifica token Subsonic (`t = md5(password + salt)`), dipendenza FastAPI per l'API.
- [ ] `src/app/subsonic/__init__.py` — router `/rest`.
- [ ] `src/app/subsonic/responses.py` — costruttori per risposta XML e JSON con lo schema Subsonic (root `<subsonic-response>` / `subsonic-response`), gestione codici errore.
- [ ] `src/app/subsonic/errors.py` — enum codici errore Subsonic (0, 10, 20, 30, 40, 41, 50, 60, 70).
- [ ] `src/app/subsonic/endpoints.py` — implementazione endpoint: `ping`, `getLicense`, `getMusicFolders`, `getIndexes`, `getMusicDirectory`, `getArtists`, `getArtist`, `getAlbumList2`, `getAlbum`, `search3`, `getSong`, `stream`, `download`, `getCoverArt`, `getPlaylists`, `getPlaylist`.
- [ ] `src/app/subsonic/streaming.py` — helper streaming MP3 con supporto `Range` (parse header, `StreamingResponse` con offset+length, header `Accept-Ranges: bytes`, `Content-Range`).
- [ ] `src/app/admin/__init__.py` — router `/` e `/admin/*`.
- [ ] `src/app/admin/routes.py` — GET `/` (login o dashboard), POST `/login`, POST `/admin/rescan`, POST `/admin/password`, GET `/logout`. Session cookie firmato.
- [ ] `src/app/admin/templates/base.html` — layout base.
- [ ] `src/app/admin/templates/login.html` — form login.
- [ ] `src/app/admin/templates/dashboard.html` — stato indice (conteggi, ultima scansione, "scan in corso"), pulsante rescan, form cambio password, tabella errori scansione.
- [ ] `src/app/admin/static/style.css` — CSS minimale.
- [ ] `tests/conftest.py` — fixture: temp dir con MP3 di prova (usa `mutagen` per generarli), client FastAPI, DB in-memory.
- [ ] `tests/test_scanner.py` — scan struttura Artista/Album, tag validi/mancanti, cover embedded e da file, file corrotti finiscono in `ScanError`.
- [ ] `tests/test_auth.py` — verifica schema token MD5, password errata → error 40.
- [ ] `tests/test_subsonic_navigation.py` — `ping`, `getArtists`, `getAlbumList2`, `getAlbum`, `search3` in XML e JSON.
- [ ] `tests/test_streaming.py` — `stream` senza Range = 200 + full body, con `Range: bytes=100-` = 206 + `Content-Range` corretto.
- [ ] `tests/test_playlists.py` — parse `.m3u` con path relativi/assoluti, `getPlaylists`/`getPlaylist`.
- [ ] `tests/test_admin.py` — login, rescan lock (secondo POST = "in corso"), cambio password.
- [ ] `Dockerfile` — multi-stage: builder con `python:3.12-slim` per installare deps in venv, runtime slim che copia venv + app, utente non-root `app`, expose `4040`, entrypoint `uvicorn app.main:app --host 0.0.0.0 --port ${HTTP_PORT}`.
- [ ] `docker-compose.yml` — servizio `mp3-server` con env vars, volumi `./music:/music:ro` e `mp3-data:/data`, porta.
- [ ] `.dockerignore` — esclude `tests/`, `.venv`, cache.

## Ordine di implementazione

Ogni tappa lascia il codice funzionante e testabile in isolamento.

1. **Bootstrap progetto** — `pyproject.toml`, layout, logging, config env. Lanciabile con `uvicorn` che risponde 200 su `/rest/ping.view` con `Failed to authenticate` (senza auth ancora, solo scheletro).
2. **Modello dati + DB** — SQLAlchemy models + `init_db()` + test che li crea in-memory.
3. **Scanner** — enumerazione `.mp3`, mutagen, upsert artist/album/track, gestione errori parsing, lock singolo. Test con fixture di 3-4 MP3 sintetici.
4. **Cover art** — estrazione embedded + fallback file, resize on-demand. Test.
5. **Auth Subsonic** — verifica token MD5, schema errori. Test.
6. **Endpoints navigazione** — `ping`, `getMusicFolders`, `getIndexes`, `getArtists`, `getArtist`, `getAlbumList2`, `getAlbum`, `getSong`, `search3` (XML + JSON). Test.
7. **Streaming Range** — `stream`, `download`, `getCoverArt`. Test con Range parziale.
8. **Playlist `.m3u`** — parser durante scan, `getPlaylists`, `getPlaylist`. Test.
9. **Admin UI** — login/dashboard/rescan/password. Test.
10. **Dockerfile + compose** — build immagine, verifica dimensione < 250 MB, smoke test locale.
11. **Test end-to-end manuale con Substreamer** su dispositivo Android reale — checklist di verifica dei criteri di accettazione.
12. **README + `.env.example`** — istruzioni di deploy VPS con Caddy/Nginx davanti.

## Rischi e dipendenze

- [ ] **Rischio: incompatibilità sottile con Substreamer** su un endpoint (`getIndexes` vs `getArtists`, formato ID come stringa vs numero, escape XML). Mitigazione: testare early con dispositivo reale al passo 6-7, non lasciare al passo 11.
- [ ] **Rischio: performance full scan sopra 10k tracce** — se supera i 2 min su VPS 1 vCPU, valutare parallelizzazione con `ThreadPoolExecutor` (I/O bound). Non pianificato di default per non introdurre bug di concorrenza; misurare prima.
- [ ] **Rischio: Range requests malformati o edge case (Range aperto `bytes=0-`, unità non-bytes)** — implementare parser stretto con test di regressione, non fidarsi del client.
- [ ] **Rischio: `.m3u` con encoding esotici o path Windows** — decodificare come UTF-8 con fallback latin-1, normalizzare separatori path, saltare voci non risolvibili con log in `ScanError`.
- [ ] **Rischio: dimensione immagine Docker sopra 250 MB** — usare `python:3.12-slim`, no `build-essential` in runtime stage, `--no-cache-dir` su pip.
- [ ] **Rischio: prima esecuzione senza `ADMIN_PASSWORD`** — generare random, stampare in log **una sola volta all'init del DB**, non a ogni startup (altrimenti sovrascrive ogni riavvio).
- [ ] **Dipendenza esterna**: mutagen (BSD-2, attivo), Pillow (attivo), FastAPI+uvicorn, SQLAlchemy 2.x, passlib[argon2] + argon2-cffi. Nessuna dipendenza binaria oltre `libffi` (già in slim).

## Verifica di allineamento con la spec

- [x] Goal 1 → task 5, 6, 7, 8 (endpoint API Subsonic).
- [x] Goal 2 → task 3, 4 (scanner + cover).
- [x] Goal 3 → task 7 (streaming Range).
- [x] Goal 4 → task 5 (auth Subsonic).
- [x] Goal 5 → task 9 (admin UI).
- [x] Goal 6 → task 3, 9 (scan startup + trigger manuale, no scheduler).
- [x] Goal 7 → task 10 (Docker + compose).
- [x] Goal 8 → task 8 (playlist M3U).
- [x] Goal 9 → task 1 (logging setup con RotatingFileHandler).
- [x] Nessun task viola i Non-Goals: assente ffmpeg/transcoding, assente watchdog/scheduler, assente upload web, assente TLS, assente multi-utente.

---

## Iterazione v1.1 — Piano miglioramenti admin

### Approccio

Estensione dell'admin router esistente (`src/app/admin/routes.py`) con nuove route di browsing (`/library`, `/library/artist/{id}`, `/library/album/{id}`) e un endpoint JSON per lo stato scan (`/admin/scan/status`). Redesign templates: sidebar di navigazione permanente, sistema di card unificato, palette con supporto tema chiaro/scuro via `prefers-color-scheme`. Live update via un piccolo file JS (`static/admin.js`) che fa polling di `/admin/scan/status`, aggiorna un div `#scan-status`, ferma il polling quando `running=false` e mostra "Scan completed". Toast flash auto-dismiss in 4s tramite CSS animation + JS `setTimeout`.

### File da toccare / creare

- [ ] `src/app/admin/routes.py` — aggiungere: `library_index`, `library_artist`, `library_album`, `scan_status_json`. Rendere `_flash` esposto per riuso; niente breaking sulle route esistenti.
- [ ] `src/app/admin/templates/base.html` — riscrittura del CSS: sidebar sinistra fissa (nav: Dashboard, Library, Logout), colonna destra col contenuto, palette con variabili CSS `--bg`, `--card`, `--text`, `--accent`, `--muted` sia per light che per dark. Toast container `#toasts` fixed bottom-right.
- [ ] `src/app/admin/templates/dashboard.html` — spostare Library-counts in card compatte, aggiungere div `#scan-status` con markup dinamico (aggiornato da JS), rimuovere logica flash inline (delegata al toast globale).
- [ ] `src/app/admin/templates/library_index.html` — nuovo. Grid di card artista (nome + numero album).
- [ ] `src/app/admin/templates/library_artist.html` — nuovo. Header artista + grid di card album (cover + nome + anno + numero tracce).
- [ ] `src/app/admin/templates/library_album.html` — nuovo. Header album (cover grande + artista + anno + durata totale) + tabella tracce (# / titolo / durata / bitrate).
- [ ] `src/app/admin/templates/login.html` — piccolo restyle coerente (card centrata, logo testuale).
- [ ] `src/app/admin/static/admin.js` — nuovo. Polling `/admin/scan/status` ogni 2 s se `running`, aggiornamento DOM, auto-dismiss toast dopo 4 s.
- [ ] `src/app/admin/static/style.css` — nuovo file (attualmente il CSS è inline in base.html; estrarlo per pulizia). Servito come StaticFiles.
- [ ] `src/app/main.py` — montare `StaticFiles` per `/static/admin/` puntando a `src/app/admin/static/`.
- [ ] `tests/test_admin_library.py` — nuovo. Test route browsing e status JSON.

### Ordine di implementazione

1. **Endpoint JSON scan status** — semplice, sblocca il fix bug 3/4 anche senza redesign.
2. **JS polling + toast auto-dismiss** — usa l'endpoint del passo 1.
3. **Nuove route library** (index, artist, album) + query di aggregazione.
4. **Template library_index/artist/album** minimi (contenuto prima di stile).
5. **Redesign base.html + style.css** — palette, sidebar, dark mode.
6. **StaticFiles mount** in main.
7. **Rifinitura login + dashboard** con nuovo stile.
8. **Test** per route library + status JSON.

### Rischi

- [ ] **Rischio**: il polling JS in tab dimenticato consuma CPU inutile. Mitigazione: fermare quando `running=false`, riprendere solo dopo click "Scan now" o refresh.
- [ ] **Rischio**: le query aggregate (numero album per artista, durata album) su libreria da 10k tracce potrebbero risultare lente se fatte in N+1. Mitigazione: usare `func.count`/`func.sum` con `group_by` in un'unica query per pagina.
- [ ] **Rischio**: `StaticFiles` mount in `src/app/admin/static` non trova i file quando pacchettizzato con hatchling se questi non sono inclusi. Mitigazione: verificare wheel includa `.js`/`.css` (hatchling include di default tutti i file sotto `packages`).
- [ ] **Rischio scope**: la voce "migliorare l'UI" è aperta. Non aggiungere motion library, icon set esterni, framework CSS — solo palette + spacing + tipografia + supporto dark.
- [ ] **Rischio**: modificare `base.html` può rompere test admin esistenti (`test_admin.py::test_login_success_and_dashboard` che cerca stringa "Library"). Mitigazione: mantenere le stringhe di ancoraggio testuale usate dai test.

### Verifica di allineamento

- [x] Goal 10 (browsing) → task 39-42.
- [x] Goal 11 (redesign UI) → task 43-44.
- [x] Goal 12 (live status scan) → task 36-38.
- [x] Goal 13 (toast effimeri) → task 37.
- [x] Nessun Non-Goal v1.1 violato: solo HTML/CSS/JS vanilla, niente framework, niente WebSocket, niente streaming dal browser, API Subsonic invariata.

---

## Iterazione v1.2 — Fallback pulito senza "Unknown"

### Approccio

Cambio chirurgico su tre punti: (1) `scanner.py::_fallback_from_path` corretto per usare la cartella parent come **album** quando c'è una sola sottocartella (bug), e per non produrre mai stringhe letterali "Unknown"; (2) `read_tags` che accetta `TPE2` come fallback di `TPE1` per artist; (3) Library UI ristrutturata in due tab (**Artists** / **Tracks**) usando un sistema minimale a link con parametro `?tab=tracks`, così senza JS extra. Filtro dei record `name==""` dalla griglia artisti admin. L'API Subsonic continua a esporre tutti i record — ma senza il testo "Unknown", per Substreamer i loose appariranno raggruppati sotto un artista con nome vuoto (che i client tipicamente rendono come "Various" o ordinano in fondo).

### File da toccare

- [ ] `src/app/scanner.py` — `_fallback_from_path` fix: `parts==1` → title solo, artist/album `""`; `parts==2` → album = `parts[0]`, artist `""`; `parts>=3` invariato. `read_tags`: aggiungere `TPE2` come fallback per artist se `TPE1` mancante.
- [ ] `src/app/admin/routes.py` — `library_index` filtra `Artist.name != ""` per la griglia artisti; nuova route `library_tracks` con paginazione (default 100 righe, param `?page=`). `library_index` accetta `?tab=artists|tracks` e ridirige/rende il template giusto.
- [ ] `src/app/admin/templates/library_index.html` — aggiungere tab bar "Artists / Tracks".
- [ ] `src/app/admin/templates/library_tracks.html` — nuovo template. Tabella #/Title/Artist/Album/Duration, paginazione semplice (prev/next link).
- [ ] `src/app/admin/static/style.css` — piccola sezione per `.tabs` link bar (uso variabili esistenti).
- [ ] `tests/test_scanner.py` — nuovi test per il fallback corretto.
- [ ] `tests/test_admin_library.py` — nuovi test per la tab Tracks, filtro artisti vuoti.

### Ordine di implementazione

1. **Bug fix `_fallback_from_path`** + test — la modifica più critica, sblocca tutto il resto.
2. **Fallback tag `TPE2`** in `read_tags` + test.
3. **Filtro artisti vuoti** in `library_index` + test.
4. **Route `library_tracks` + template + tab bar** + test.
5. **CSS per `.tabs`**.
6. **Smoke manuale**.

### Rischi

- [ ] **Rischio**: cambiare `_fallback_from_path` rompe test esistenti in `test_scanner.py` che aspettano il vecchio comportamento. Mitigazione: aggiornare i test contestualmente al fix (documenta il cambio di comportamento).
- [ ] **Rischio**: un DB esistente da v1.1 contiene già artisti/album "Unknown ...". Il full scan al riavvio li riscrive, ma restano orfani finché lo scan non li cancella. Mitigazione: nel finale dello scan, il codice attuale già cancella artisti/album senza tracce — quindi al primo scan v1.2 spariranno.
- [ ] **Rischio scope**: la Library UI potrebbe suggerire di aggiungere sorting/filter avanzati sulla tab Tracks. Restare al minimo: solo paginazione prev/next, ordinamento fisso alfabetico per titolo.
- [ ] **Rischio Subsonic**: alcuni client Subsonic potrebbero comportarsi male con `artist.name = ""`. Non testabile senza il device reale — se emerge, aggiungeremo una route Subsonic che mappa `""` → `"Various"` solo in output.

### Verifica di allineamento

- [ ] Goal 14 → task 47 (fix `_fallback_from_path`).
- [ ] Goal 15 → task 47, 48 (niente "Unknown", solo stringhe vuote o derivate).
- [ ] Goal 16 → task 48 (fallback `TPE2`).
- [ ] Goal 17 → task 49-51 (Tracks tab).
- [ ] Goal 18 → task 50 (filtro artisti vuoti).
- [ ] Goal 19 → nessuna modifica Subsonic in questa fase (le tracce restano indicizzate e streamabili con artist name `""`; se serve mapping "Various" si apre un follow-up).
- [ ] Goal 20 → task 53 (versione in dashboard).
- [ ] Nessun Non-Goal v1.2 violato: nessuna migrazione, nessuna nuova colonna, nessun inference smart, nessuna modifica ai file MP3, nessun blocco streaming.

### Nota versioning

Con l'aggiunta di questa iterazione bumperemo `__version__` in `src/app/__init__.py` (e la coppia in `pyproject.toml`) da `0.1.0` → `0.3.0` (0.2.0 corrisponde a v1.1 admin UI, 0.3.0 a v1.2 unknown fix + versione visibile). Nessun impatto su semver perché resta pre-1.0 (breaking allowed).

---

## Iterazione v1.3 — Library = filesystem browser puro

### Approccio

Sostituire completamente il modello Library dell'admin: da metadata-based (Artists / Albums / Tracks) a **filesystem browser** che riflette 1:1 il contenuto di `MUSIC_DIR`. Il DB e l'API Subsonic restano invariati (obbligatori per Substreamer). Ci sarà **una sola route Library**: `GET /library` che accetta `?path=<subpath>` e enumera il filesystem in quel punto. Sanitizzazione stretta contro path traversal. Rimozione fisica delle route e template metadata-based aggiunti in v1.1/v1.2.

### File da toccare

- [ ] `src/app/admin/routes.py` — nuova funzione `library` (accetta `?path=`). Rimuovere `library_index`, `library_artist`, `library_album`, `library_tracks`, `admin_cover`. Sanificare path: `resolve()`, verificare `str(resolved).startswith(str(music_root.resolve()))`.
- [ ] `src/app/admin/fs_browse.py` — nuovo helper: `list_directory(abs_path, music_root) -> {folders: [...], files: [...], breadcrumb: [...]}`. Enumera solo `.mp3` per i file, sottodirectory reali per folders, ignora dotfiles. Ogni file `.mp3` opzionalmente arricchito con metadata dal DB via lookup su `Track.path`.
- [ ] `src/app/admin/templates/library.html` — nuovo template con breadcrumb, lista folders + lista files (icona 📁 vs 🎵, dimensione, durata, titolo tag).
- [ ] Rimuovere `src/app/admin/templates/library_index.html`, `library_artist.html`, `library_album.html`, `library_tracks.html`.
- [ ] Rimuovere `tests/test_admin_library.py` completamente e riscriverlo con test focalizzati su filesystem browser.
- [ ] `src/app/admin/static/style.css` — piccole aggiunte per `.fs-list`, `.fs-row`, icona, breadcrumb (o riuso esistente `.breadcrumbs`).

### Ordine di implementazione

1. **Nuovo helper `fs_browse.list_directory`** con sanitizzazione + test unit.
2. **Route `GET /library`** che usa l'helper e renderizza template.
3. **Template `library.html`** minimale (funziona prima dello stile).
4. **Rimozione** delle vecchie route e template metadata-based.
5. **Riscrittura test** `test_admin_library.py` — focalizzati solo sul browser filesystem.
6. **Rifinitura CSS** per icone e riga file/folder.
7. **Regression run**: full test suite ancora verde, nessun 404 stray da template deletati.

### Rischi

- [ ] **Rischio path traversal**: input `?path=..` deve essere sanitizzato. Mitigazione: usare `Path(music_root, relative).resolve()` e verificare `startswith(music_root.resolve())`. Test dedicato con `?path=../../../etc`.
- [ ] **Rischio Windows path**: `MUSIC_DIR` su Windows in dev usa `\\`, in Docker su Linux `/`. Uso `Path` in entrambi i casi, decodifica URL degli slash forward.
- [ ] **Rischio simlink out-of-tree**: symlink dentro `/music` che punta fuori (es. `/etc`) potrebbe essere seguito. Mitigazione: `resolve(strict=False)` e re-check `startswith`.
- [ ] **Rischio scope creep**: la tentazione di aggiungere player/download/upload/search sarebbe naturale ora che c'è la vista file, ma la spec v1.3 dice esplicitamente no. Resistere.
- [ ] **Rischio arricchimento DB**: per mostrare titolo/durata di ogni file serve un lookup su `Track.path`. Con 500 file in una cartella sarebbe pesante come N+1. Mitigazione: `SELECT ... WHERE path IN (:list)` in un'unica query per pagina.

### Verifica di allineamento

- [ ] Goal 21 → task 54, 55 (route + template).
- [ ] Goal 22 → task 55 (breadcrumb + link cartelle).
- [ ] Goal 23 → task 56 (metadata arricchimento).
- [ ] Goal 24 → task 57 (rimozione code path metadata).
- [ ] Goal 25 → task 54 (sanitizzazione path traversal, test dedicato).
- [ ] Nessun Non-Goal v1.3 violato: nessun cambio Subsonic/DB, nessun player, no upload/delete, no search, no viste metadata residue.
