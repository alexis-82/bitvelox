# Specifica: Server MP3 Streaming self-hosted

## Obiettivo

Realizzare un server di streaming musicale self-hosted da installare su una VPS Linux, compatibile con l'API Subsonic, in modo da poter ascoltare la propria libreria MP3 da un cellulare Android tramite il client Substreamer (o qualunque altro client Subsonic).

## Goals (cosa DEVE fare)

- [ ] Goal 1: Esporre l'API Subsonic (versione minima supportata da Substreamer, tipicamente 1.13.0+) su HTTP, con almeno gli endpoint `ping`, `getLicense`, `getMusicFolders`, `getIndexes`, `getMusicDirectory`, `getArtists`, `getAlbumList2`, `getAlbum`, `search3`, `stream`, `download`, `getCoverArt`.
- [ ] Goal 2: Indicizzare automaticamente una cartella locale (`/music`) contenente file `.mp3` organizzati per `Artista/Album/Traccia.mp3`, leggendo i tag ID3v1/ID3v2 (artista, album, titolo, numero traccia, anno, genere) e la cover art embedded o `cover.jpg`/`folder.jpg` nella cartella album.
- [ ] Goal 3: Supportare streaming diretto MP3 con `HTTP Range requests` (seek dal client) senza transcoding — passthrough del file originale.
- [ ] Goal 4: Autenticazione a utente singolo (admin) tramite username + password, compatibile con lo schema Subsonic (`u`, `p`/`t`+`s` con token+salt MD5).
- [ ] Goal 5: Fornire una pagina web di amministrazione per: modificare password admin, triggerare una re-scansione della libreria, vedere stato indice (numero di artisti/album/tracce, ultima scansione, errori di parsing).
- [ ] Goal 6: Scansione della libreria triggerata SOLO all'avvio del server e manualmente dalla pagina admin (pulsante "Scan now"). Ogni scansione è un **full scan**: ri-processa tutti i file MP3 e ricostruisce l'indice. Nessuna scansione periodica, nessun watcher filesystem in background.
- [ ] Goal 7: Distribuire il server come container Docker con `Dockerfile` + `docker-compose.yml` di esempio, che monti la cartella musica e persista il DB dell'indice su volume.
- [ ] Goal 8: Supportare in lettura le playlist definite come file `.m3u`/`.m3u8` presenti dentro `/music` — esposte via `getPlaylists`/`getPlaylist` dell'API Subsonic (solo read-only).
- [ ] Goal 9: Loggare su stdout (per `docker logs`) E su file rotante in `/data/logs/server.log` (rotazione per dimensione, es. 10 MB × 5 file).

## Non-Goals (cosa NON deve fare) — scope hard

- [ ] NON supportare formati audio diversi da MP3 (no FLAC, OGG, AAC, WAV, M4A) — anche se sono facili da aggiungere, restano fuori da questa iterazione.
- [ ] NON transcodificare al volo (no ffmpeg, no bitrate adattivo) — solo passthrough del file originale.
- [ ] NON implementare API Subsonic legate a funzionalità avanzate: podcast, radio internet, chat, jukebox, video, share pubblici, bookmark. Le playlist sono supportate SOLO in lettura da file `.m3u`/`.m3u8` presenti dentro `/music` (no creazione/modifica playlist via client).
- [ ] NON gestire multi-utente né ruoli — un solo account admin. Nessuna registrazione, nessun sistema di inviti.
- [ ] NON scansionare la libreria in background (no scheduler periodico, no watcher filesystem) — solo all'avvio e su comando manuale.
- [ ] NON fornire upload di file MP3 tramite web UI — i file si caricano via SFTP/rsync sulla cartella montata.
- [ ] NON gestire terminazione TLS/HTTPS nel server — si assume reverse proxy davanti (Caddy/Nginx/Traefik) per certificato e dominio.
- [ ] NON scrivere/modificare i tag ID3 dei file esistenti — la libreria è read-only lato server, la si edita fuori.
- [ ] NON implementare un client web di ascolto integrato oltre alla pagina admin — l'ascolto avviene da client Subsonic esterni (Substreamer, DSub, Ultrasonic, ecc.).
- [ ] NON supportare API Subsonic legacy pre-1.13 se non necessarie a Substreamer.

## Utenti / consumatori

- **Utente umano (io)** — accede alla pagina admin da browser per configurare il server e triggerare scansioni.
- **Client Subsonic su Android (Substreamer)** — consuma l'API Subsonic per navigare libreria, streammare, scaricare per offline.
- **Altri client Subsonic** (DSub, Ultrasonic, Sonixd desktop, ecc.) — devono funzionare come effetto collaterale della compatibilità Subsonic, ma il target primario di test è Substreamer.

## Interfaccia

### API Subsonic (per i client)

- Base URL: `http://<host>:<porta>/rest/`
- Formato risposta: `f=xml` (default) e `f=json` — entrambi obbligatori per compatibilità
- Autenticazione: query parameters `u=<user>&t=<token>&s=<salt>&v=<api-version>&c=<client-name>` (schema token MD5 Subsonic)
- Endpoint minimi elencati nel Goal 1
- Streaming: `GET /rest/stream?id=<trackId>` risponde con `Content-Type: audio/mpeg`, supporta header `Range`

### Web UI admin

- `GET /` → pagina admin con: stato libreria, form cambio password, pulsante "Scan now", tabella errori scansione
- `POST /admin/rescan` → trigger scansione manuale
- `POST /admin/password` → cambio password admin
- Login separato (form HTML basic) prima di accedere a `/admin/*`

### Configurazione

Via variabili d'ambiente (compatibili con Docker):
- `MUSIC_DIR` (default `/music`)
- `DATA_DIR` (default `/data`, per DB SQLite indice)
- `ADMIN_USER` (default `admin`)
- `ADMIN_PASSWORD` (obbligatorio al primo avvio; se assente, genera password random e la stampa nei log)
- `HTTP_PORT` (default `4040`)

## Criteri di accettazione

- [ ] Dato un `docker-compose.yml` con volume `./music:/music` e password admin, il container parte, indicizza la libreria e risponde `200` su `GET /rest/ping?u=...&t=...&s=...&v=1.13.0&c=test&f=json`.
- [ ] Aggiungendo l'account con URL server + credenziali in Substreamer su Android, la libreria appare navigabile per artista/album e ogni traccia MP3 è ascoltabile con seek funzionante.
- [ ] Aggiungendo un nuovo album nella cartella `/music` e cliccando "Scan now" nella pagina admin, l'album appare nel client entro 5 secondi dal termine della scansione.
- [ ] Un secondo click su "Scan now" mentre una scansione è già in corso non ne avvia una parallela — mostra "Scan già in corso".
- [ ] Rimuovendo un file MP3 dal disco e triggerando una scansione, il file scompare dall'indice a fine scansione.
- [ ] La cover art embedded nell'MP3 (o `cover.jpg` nella cartella) viene restituita da `getCoverArt` e visualizzata in Substreamer.
- [ ] Riavviando il container, l'indice preesistente su volume `/data` viene rimpiazzato dal risultato del full scan all'avvio (il file DB persiste, il contenuto viene ricostruito).
- [ ] Con `ADMIN_PASSWORD` errata dal client, `GET /rest/ping` risponde con errore Subsonic code `40` (Wrong username or password).

## Vincoli tecnici

- **Stack / linguaggio**: [?] da decidere in fase di plan (candidati sensati: Python+FastAPI, Go, Node.js). Priorità: footprint basso, singolo binario o singola immagine Docker piccola, avvio rapido.
- **Storage indice**: SQLite in `/data/library.db` — nessun DB esterno.
- **Compatibilità API**: Subsonic API v1.13.0+ come baseline, sufficiente per Substreamer corrente.
- **Compatibilità client**: Substreamer (Android) è il target primario di test manuale. Test opportunistico con almeno un altro client (es. DSub o Sonixd).
- **Performance**: libreria di riferimento fino a ~10.000 tracce; la scansione completa deve stare sotto 2 minuti su VPS entry-level (1 vCPU, 1 GB RAM); risposta a `getAlbumList2` sotto 200 ms.
- **Sicurezza**: nessun TLS nel server (delegato a reverse proxy); password admin hashata a riposo (bcrypt/argon2); rate limit base sui tentativi di login admin (non sull'API Subsonic, per non rompere i client).
- **Ambiente di esecuzione**: Linux x86_64, container Docker basato su immagine slim/alpine, non richiede privilegi root (utente non-root nel container).
- **Filesystem sorgente**: struttura attesa `Artista/Album/NN - Titolo.mp3`; deve reggere anche cartelle piatte (senza sottocartelle album) usando i tag ID3.

## Decisioni prese (fase clarify)

- **Non-Goals**: confermati integralmente dall'utente.
- **Playlist**: supporto read-only per file `.m3u`/`.m3u8` dentro `/music`. Alternative scartate: (a) nessuna playlist — perdita di feature comoda a costo basso; (b) playlist editabili lato server — fuori scope, richiede storage stato utente.
- **Logging**: stdout + file rotante in `/data/logs/server.log`. Alternativa scartata: solo stdout — l'utente vuole persistenza log oltre la vita del container.
- **Backup indice**: nessun endpoint di backup. Motivazione: l'indice è ricostruibile dai file MP3 con una scansione, quindi non ha valore proprio da salvaguardare.
- **Gestione file corrotti / tag illeggibili**: skip silenzioso + riga visibile nella tabella "errori scansione" della pagina admin (nessun hard-fail sulla scansione).
- **Ricerca `search3`**: prefix match case-insensitive su artista/album/titolo (comportamento standard Subsonic, sufficiente per Substreamer).
- **Stack**: **Python 3.12 + FastAPI**. Librerie chiave: `mutagen` (tag ID3 + cover art embedded), `SQLAlchemy` + `SQLite` (indice), `Pillow` (resize cover art), `uvicorn` (ASGI runner), `passlib[argon2]` (hash password), `python-multipart` per il form admin, `pytest` per i test. Alternative valutate: Go+chi (footprint migliore ~20 MB image ma ~2x LoC, `dhowden/tag` con qualche edge case sui tag esotici) e Node+Fastify+music-metadata (miglior parser ID3 ma stack meno omogeneo con il resto). Motivo scelta: velocità di sviluppo e maturità di `mutagen` prevalgono sul footprint per un uso personale su VPS 1 GB.
- **Strategia scansione libreria**: **solo all'avvio del server + trigger manuale** dalla pagina admin, sempre in modalità **full scan** (ri-processa tutti i file, ricostruisce l'indice). Nessuno scheduler periodico, nessun watcher inotify. Alternative valutate: (a) periodica ogni 15 min + manuale — scartata, complicava il runtime e non serve per uso personale con upload SFTP occasionali; (b) periodica + watchdog inotify — scartata per problemi di affidabilità su mount NFS/SMB e complessità aggiunta; (c) incrementale con mtime+size — scartata per semplicità: il full scan su ~10k tracce resta accettabile e garantisce coerenza assoluta dell'indice. Motivazione: l'utente controlla esplicitamente quando l'indice si aggiorna, minor superficie di bug in background.
- **Concorrenza scansione**: lock singolo — una sola scansione attiva alla volta. Un secondo trigger mentre una scansione è in corso è un no-op (log warning + messaggio in admin "Scan già in corso"). File spariti dal disco durante il full scan → hard delete dall'indice a fine scansione.

## Vincoli tecnici (aggiornati post-clarify)

Sostituisce la riga stack in "Vincoli tecnici":
- **Stack**: Python 3.12, FastAPI, uvicorn, mutagen, SQLAlchemy + SQLite, Pillow, passlib[argon2].
- **Immagine base Docker**: `python:3.12-slim`, multi-stage build, utente non-root, target immagine finale sotto 250 MB.

## Iterazione v1.1 — Miglioramenti admin UI

Aggiunta di Goals dopo la prima release funzionante. Feedback utente: server funziona ma la UI admin è troppo scarna, manca il browsing libreria, e lo stato scansione non si aggiorna da solo.

### Goals v1.1

- [ ] Goal 10: Aggiungere una **sezione "Library" nell'admin** che permetta di navigare la libreria in sola lettura: pagina indice con lista artisti, drill-down su artista → lista album, drill-down su album → lista tracce. La navigazione mostra copertine (miniatura), conteggi, durata totale.
- [ ] Goal 11: Redesign UI admin — CSS più moderno (font-stack sistema mantenuto, palette coerente light/dark automatica via `prefers-color-scheme`, layout a due colonne con sidebar di navigazione, card più aeree, tipografia leggibile). Nessuna dipendenza CSS esterna (spec Non-Goal esistente: no upload web, no CDN).
- [ ] Goal 12: **Live status della scansione**: la dashboard aggiorna automaticamente lo stato "Scan in progress / done" senza bisogno di ricaricare. Meccanismo: piccolo endpoint JSON `/admin/scan/status` + JS polling ogni 2 secondi finché lo scan è attivo, poi alla fine mostra "Scan completed at HH:MM:SS" e ferma il polling.
- [ ] Goal 13: **Toast/flash effimeri**: i messaggi tipo "Scan started" spariscono automaticamente dopo N secondi (o al successivo click), non restano visibili come banner permanente.

### Non-Goals v1.1

- [ ] NON introdurre un frontend framework (React/Vue/HTMX) — solo HTML + CSS + JS vanilla minimo.
- [ ] NON riscrivere il backend/API — solo aggiungere route admin di sola lettura per Library e status.
- [ ] NON aggiungere play/streaming dal browser — la pagina Library è navigazione read-only, si ascolta sempre da Substreamer.
- [ ] NON aggiungere WebSocket/SSE — polling AJAX semplice è sufficiente per lo stato scan (scan dura tipicamente < 2 min).
- [ ] NON toccare l'API Subsonic esistente né i test già verdi.

## Iterazione v1.2 — Fallback pulito per MP3 senza tag / senza gerarchia

Feedback utente: con file MP3 senza tag chiari o senza struttura `Artista/Album/*.mp3`, il server crea placeholder "Unknown Artist" / "Unknown Album" e forza a navigare sotto di essi. Con 2 file loose in `/music` l'utente vuole vedere 2 file, non finti sotto-alberi.

### Diagnosi

1. **Bug in `_fallback_from_path` (`src/app/scanner.py`)**: se un file è a `/music/album/song.mp3` (una sola cartella parent), il codice usa `parts[0]` come **artist** e imposta album a `"Unknown Album"`. È esattamente il contrario di quello che ci si aspetta: la cartella parent è chiaramente l'album, non l'artista.
2. **Stringhe placeholder letterali**: `"Unknown Artist"` e `"Unknown Album"` vengono scritte nel DB, sporcando la libreria in modo permanente.
3. **Library UI monotematica**: la pagina `/library` mostra solo la griglia degli artisti. Se un file non ha un artista sensato, l'utente non lo vede senza cliccare su un finto artista.

### Goals v1.2

- [ ] Goal 14: Bug fix `_fallback_from_path` — per `parts == 2` (una cartella parent + file), la cartella parent è **album**, artist resta vuoto (o dal tag `TPE1`/`TPE2` se presente).
- [ ] Goal 15: **Nessuna stringa letterale "Unknown ..."** mai scritta nel DB. Le colonne `Artist.name` e `Album.name` possono contenere stringa vuota `""` per tracce senza artista/album derivabile.
- [ ] Goal 16: Lettura tag più tollerante — usare `TPE2` (AlbumArtist) come fallback per artista, `TIT2` per titolo, fallback finale al filename per il titolo (già presente). Non forzare mai stringhe "Unknown".
- [ ] Goal 17: Vista **All tracks** in `/library` — la pagina Library diventa un tab: **Artists** (griglia attuale, ma senza artisti vuoti) e **Tracks** (tabella piatta di tutte le tracce con colonne #/Title/Artist/Album/Duration ordinabili per default alfabeticamente per titolo). I file loose sono visibili qui senza navigare sotto artisti.
- [ ] Goal 18: Nascondere artisti/album vuoti (`name == ""`) dalla griglia artisti admin. Restano nel DB (necessari per lo streaming) ma non si vedono come cluster fittizio.
- [ ] Goal 19: L'API Subsonic continua a esporre le tracce loose sotto un artista/album virtuale (nome "" o "Various") in modo che Substreamer possa comunque raggiungerle — ma senza il testo "Unknown".
- [ ] Goal 20: La dashboard admin mostra il numero di versione del software (letto da `app.__version__`), in modo che l'utente sappia quale build sta girando in produzione (utile dopo update / debug).

## Iterazione v1.3 — Library = filesystem browser puro

Feedback utente: le viste basate su metadata (Artists / Albums / Tracks) creano gerarchie artificiali che confondono. Preferisce vedere **il filesystem reale** di `/music`.

### Diagnosi

Il modello attuale mappa i metadata (tag ID3 / fallback) in Artists/Albums/Tracks, mostrando griglia artisti come landing di `/library`. Questo produce nel migliore dei casi una gerarchia coerente ma inventata quando i tag non sono presenti, nel peggiore genera cluster fittizi (già mitigati in v1.2 ma il modello resta metadata-based, non filesystem-based).

### Goals v1.3

- [ ] Goal 21: `/library` mostra il contenuto **diretto** di `MUSIC_DIR` — lista delle cartelle presenti nella radice (cliccabili) e lista dei file `.mp3` presenti nella radice. Nulla di più.
- [ ] Goal 22: Cliccando su una cartella si entra dentro (`/library/browse?path=<subpath>`), mostrando il contenuto di quella cartella (altre sottocartelle + `.mp3`). Ricorsivo a qualunque profondità. Breadcrumb per tornare indietro.
- [ ] Goal 23: Ogni file `.mp3` mostrato riporta: nome file, titolo (dal tag ID3 se disponibile, altrimenti stringa vuota o filename), durata `mm:ss`, dimensione in MB. **Non azionabile** dal browser admin — nessun play/download/stream. Si ascolta sempre e solo da Substreamer.
- [ ] Goal 24: **Rimuovere dall'admin UI** le viste basate su metadata: Artists index, Artist detail, Album detail, Tracks flat list. Rimuovere le route corrispondenti (`/library/artist/{id}`, `/library/album/{id}`, `/library/tracks`) e i template. Anche l'endpoint `/admin/cover/{album_id}` va rimosso perché usato solo da quelle viste (le cover in browser saranno lette direttamente dal filesystem come `cover.jpg`/`folder.jpg` accanto agli mp3, se serve).
- [ ] Goal 25: **Sicurezza filesystem**: la route `browse` deve rigettare path traversal (`..`, path assoluti, symlink che escono da `MUSIC_DIR`). Solo `.mp3` visibili, file dot ignorati.
- [ ] Goal 26: **No duplicazione filename/title** — nella lista file mostrare il titolo dal tag ID3 solo se differisce (case-insensitive) dal filename senza estensione. Se il DB ha `title == stem(filename)` (caso tipico del fallback scanner senza tag), non mostrare il titolo separatamente.
- [ ] Goal 27: **Rebrand del software da "mp3-server" a "BitVelox"** in tutti i punti user-facing (titolo pagine HTML, sidebar, README, nome pacchetto pyproject, container Docker). Il package Python interno `app/` resta invariato per evitare massive import churn.
- [ ] Goal 28: **CHANGELOG.md** al root del repository, formato Keep a Changelog, con sezione `[Unreleased]` in cima e lo storico versioni (0.1.0 → 0.3.0) popolato dai task già fatti.
- [ ] Goal 29: **Voce "Changelog" nella sidebar admin**, cliccabile, posizionata subito sopra il testo `v{{ app_version }}`. Al click apre `/changelog` che mostra il contenuto di `CHANGELOG.md` renderizzato da markdown a HTML.
- [ ] Goal 30: **Risoluzione robusta del path `CHANGELOG.md`** — il file va trovato indipendentemente da dove il server viene avviato (uvicorn locale, editable install, Docker container, VPS con cwd variabile). Fallback logico: env var `CHANGELOG_PATH` → path relativo al modulo → `/app/CHANGELOG.md` → `cwd/CHANGELOG.md`. Su 404 loggare a WARNING quali path sono stati tentati.

### Non-Goals v1.3

- [ ] NON alterare l'API Subsonic né lo schema DB — il DB con Artist/Album/Track resta identico perché serve a Substreamer (che è metadata-based per protocollo).
- [ ] NON aggiungere player/streaming/download dall'admin browser — solo lista visiva.
- [ ] NON permettere upload/delete/rename di file — la vista è read-only, i file si gestiscono via SFTP/rsync (Non-Goal storico invariato).
- [ ] NON aggiungere ricerca/filtro/sorting nella tab browse (per ora). Il sorting è alfabetico fisso: cartelle prima, poi file.
- [ ] NON mantenere le vecchie viste Artists/Tracks come "alternative view" — vanno rimosse per pulizia, l'utente le ha esplicitamente respinte.
- [ ] NON aggiungere una vista basata sul contenuto del DB per ora (per esempio "solo tracce indicizzate" filtrando quelle cui il file è sparito) — filesystem è la verità.

### Non-Goals v1.2

- [ ] NON introdurre migrazioni schema con Alembic — il DB è personale, `docker compose down -v` per resettarlo se serve.
- [ ] NON tentare tag inference "smart" (lookup MusicBrainz, guess artist dalla struttura del testo del titolo, ecc.). Solo tag ID3 + filename + folder name.
- [ ] NON rendere le tracce loose non-streamabili — devono restare accessibili via API Subsonic anche se raggruppate diversamente.
- [ ] NON modificare i file MP3 sorgente — la libreria resta read-only lato server.
- [ ] NON introdurre nuove tabelle o colonne — solo cambi comportamento sul contenuto delle colonne esistenti.
