from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.covers import get_cover_resized
from app.db import get_session
from app.models import Album, Artist, Playlist, PlaylistEntry, Track
from app.subsonic.auth_dep import check_subsonic_auth
from app.subsonic.errors import SubsonicError
from app.subsonic.responses import build_error, build_response
from app.subsonic.streaming import range_response

router = APIRouter(prefix="/rest")

MUSIC_FOLDER_ID = 1
MUSIC_FOLDER_NAME = "Music"


def _artist_prefix(name: str) -> str:
    for prefix in ("The ", "A ", "An "):
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    ch = name[:1].upper()
    return ch if ch.isalpha() else "#"


def _artist_dict(a: Artist, album_count: int) -> dict:
    return {"id": f"ar-{a.id}", "name": a.name, "albumCount": album_count}


def _album_dict(al: Album, artist_name: str, song_count: int, duration: int) -> dict:
    d = {
        "id": f"al-{al.id}",
        "parent": f"ar-{al.artist_id}",
        "name": al.name,
        "title": al.name,
        "album": al.name,
        "artist": artist_name,
        "artistId": f"ar-{al.artist_id}",
        "songCount": song_count,
        "duration": duration,
        "isDir": True,
    }
    if al.year:
        d["year"] = al.year
    if al.cover_path:
        d["coverArt"] = f"al-{al.id}"
    return d


def _track_dict(t: Track, album_name: str, artist_name: str, cover_ok: bool) -> dict:
    d = {
        "id": f"tr-{t.id}",
        "parent": f"al-{t.album_id}",
        "title": t.title,
        "album": album_name,
        "artist": artist_name,
        "albumId": f"al-{t.album_id}",
        "artistId": f"ar-{t.artist_id}",
        "isDir": False,
        "isVideo": False,
        "type": "music",
        "duration": t.duration_s or 0,
        "bitRate": t.bitrate or 0,
        "size": t.size_bytes,
        "suffix": "mp3",
        "contentType": t.mime_type,
        "path": f"{artist_name}/{album_name}/{t.title}.mp3",
    }
    if t.track_no:
        d["track"] = t.track_no
    if t.disc_no:
        d["discNumber"] = t.disc_no
    if cover_ok:
        d["coverArt"] = f"al-{t.album_id}"
    return d


def _parse_id(prefix: str, raw: str | None) -> int | None:
    if raw is None:
        return None
    if raw.startswith(prefix):
        raw = raw[len(prefix):]
    try:
        return int(raw)
    except ValueError:
        return None


@router.get("/ping.view")
@router.get("/ping")
async def ping(request: Request) -> Response:
    auth = check_subsonic_auth(request)
    if auth.error:
        return auth.error
    return build_response({}, auth.fmt)


@router.get("/getLicense.view")
@router.get("/getLicense")
async def get_license(request: Request) -> Response:
    auth = check_subsonic_auth(request)
    if auth.error:
        return auth.error
    return build_response(
        {"license": {"valid": True, "email": "self-hosted@localhost"}},
        auth.fmt,
    )


@router.get("/getMusicFolders.view")
@router.get("/getMusicFolders")
async def get_music_folders(request: Request) -> Response:
    auth = check_subsonic_auth(request)
    if auth.error:
        return auth.error
    return build_response(
        {"musicFolders": {"musicFolder": [{"id": MUSIC_FOLDER_ID, "name": MUSIC_FOLDER_NAME}]}},
        auth.fmt,
    )


def _grouped_artists(session) -> tuple[list[dict], int]:
    artists = session.query(Artist).order_by(Artist.name_lower).all()
    counts = {a.id: session.query(Album).filter_by(artist_id=a.id).count() for a in artists}
    groups: dict[str, list[dict]] = {}
    for a in artists:
        prefix = _artist_prefix(a.name)
        groups.setdefault(prefix, []).append(_artist_dict(a, counts[a.id]))
    index_list = [{"name": k, "artist": v} for k, v in sorted(groups.items())]
    return index_list, len(artists)


@router.get("/getIndexes.view")
@router.get("/getIndexes")
async def get_indexes(request: Request) -> Response:
    auth = check_subsonic_auth(request)
    if auth.error:
        return auth.error
    with get_session() as session:
        index_list, _ = _grouped_artists(session)
    return build_response(
        {"indexes": {"lastModified": 0, "ignoredArticles": "The A An", "index": index_list}},
        auth.fmt,
    )


@router.get("/getArtists.view")
@router.get("/getArtists")
async def get_artists(request: Request) -> Response:
    auth = check_subsonic_auth(request)
    if auth.error:
        return auth.error
    with get_session() as session:
        index_list, _ = _grouped_artists(session)
    return build_response(
        {"artists": {"ignoredArticles": "The A An", "index": index_list}},
        auth.fmt,
    )


@router.get("/getArtist.view")
@router.get("/getArtist")
async def get_artist(request: Request) -> Response:
    auth = check_subsonic_auth(request)
    if auth.error:
        return auth.error
    aid = _parse_id("ar-", request.query_params.get("id"))
    if aid is None:
        return build_error(SubsonicError.REQUIRED_PARAM_MISSING, auth.fmt)
    with get_session() as session:
        artist = session.get(Artist, aid)
        if artist is None:
            return build_error(SubsonicError.NOT_FOUND, auth.fmt)
        albums = session.query(Album).filter_by(artist_id=aid).order_by(Album.name_lower).all()
        album_list = []
        for al in albums:
            song_count = session.query(Track).filter_by(album_id=al.id).count()
            duration = sum(t.duration_s or 0 for t in session.query(Track).filter_by(album_id=al.id))
            album_list.append(_album_dict(al, artist.name, song_count, duration))
        payload = {
            "artist": {
                "id": f"ar-{artist.id}",
                "name": artist.name,
                "albumCount": len(albums),
                "album": album_list,
            }
        }
    return build_response(payload, auth.fmt)


@router.get("/getMusicDirectory.view")
@router.get("/getMusicDirectory")
async def get_music_directory(request: Request) -> Response:
    auth = check_subsonic_auth(request)
    if auth.error:
        return auth.error
    raw_id = request.query_params.get("id", "")
    with get_session() as session:
        if raw_id.startswith("ar-"):
            aid = _parse_id("ar-", raw_id)
            artist = session.get(Artist, aid) if aid else None
            if artist is None:
                return build_error(SubsonicError.NOT_FOUND, auth.fmt)
            albums = session.query(Album).filter_by(artist_id=aid).order_by(Album.name_lower).all()
            children = []
            for al in albums:
                song_count = session.query(Track).filter_by(album_id=al.id).count()
                duration = sum(t.duration_s or 0 for t in session.query(Track).filter_by(album_id=al.id))
                children.append(_album_dict(al, artist.name, song_count, duration))
            payload = {
                "directory": {
                    "id": f"ar-{artist.id}",
                    "name": artist.name,
                    "child": children,
                }
            }
            return build_response(payload, auth.fmt)
        if raw_id.startswith("al-"):
            alid = _parse_id("al-", raw_id)
            album = session.get(Album, alid) if alid else None
            if album is None:
                return build_error(SubsonicError.NOT_FOUND, auth.fmt)
            artist = session.get(Artist, album.artist_id)
            tracks = (
                session.query(Track)
                .filter_by(album_id=alid)
                .order_by(Track.disc_no.nulls_first(), Track.track_no.nulls_first(), Track.title_lower)
                .all()
            )
            children = [_track_dict(t, album.name, artist.name, bool(album.cover_path)) for t in tracks]
            payload = {
                "directory": {
                    "id": f"al-{album.id}",
                    "parent": f"ar-{artist.id}",
                    "name": album.name,
                    "child": children,
                }
            }
            return build_response(payload, auth.fmt)
    return build_error(SubsonicError.NOT_FOUND, auth.fmt)


@router.get("/getAlbum.view")
@router.get("/getAlbum")
async def get_album(request: Request) -> Response:
    auth = check_subsonic_auth(request)
    if auth.error:
        return auth.error
    alid = _parse_id("al-", request.query_params.get("id"))
    if alid is None:
        return build_error(SubsonicError.REQUIRED_PARAM_MISSING, auth.fmt)
    with get_session() as session:
        album = session.get(Album, alid)
        if album is None:
            return build_error(SubsonicError.NOT_FOUND, auth.fmt)
        artist = session.get(Artist, album.artist_id)
        tracks = (
            session.query(Track)
            .filter_by(album_id=alid)
            .order_by(Track.disc_no.nulls_first(), Track.track_no.nulls_first(), Track.title_lower)
            .all()
        )
        duration = sum(t.duration_s or 0 for t in tracks)
        payload = {
            "album": {
                **_album_dict(album, artist.name, len(tracks), duration),
                "song": [_track_dict(t, album.name, artist.name, bool(album.cover_path)) for t in tracks],
            }
        }
    return build_response(payload, auth.fmt)


@router.get("/getAlbumList2.view")
@router.get("/getAlbumList2")
async def get_album_list2(request: Request) -> Response:
    auth = check_subsonic_auth(request)
    if auth.error:
        return auth.error
    qp = request.query_params
    typ = qp.get("type", "alphabeticalByName")
    try:
        size = min(int(qp.get("size", "10")), 500)
        offset = int(qp.get("offset", "0"))
    except ValueError:
        return build_error(SubsonicError.REQUIRED_PARAM_MISSING, auth.fmt)

    with get_session() as session:
        q = session.query(Album, Artist).join(Artist, Album.artist_id == Artist.id)
        if typ == "alphabeticalByArtist":
            q = q.order_by(Artist.name_lower, Album.name_lower)
        elif typ == "newest":
            q = q.order_by(Album.id.desc())
        else:
            q = q.order_by(Album.name_lower)
        rows = q.offset(offset).limit(size).all()
        albums = []
        for al, ar in rows:
            song_count = session.query(Track).filter_by(album_id=al.id).count()
            duration = sum(t.duration_s or 0 for t in session.query(Track).filter_by(album_id=al.id))
            albums.append(_album_dict(al, ar.name, song_count, duration))
    return build_response({"albumList2": {"album": albums}}, auth.fmt)


@router.get("/getSong.view")
@router.get("/getSong")
async def get_song(request: Request) -> Response:
    auth = check_subsonic_auth(request)
    if auth.error:
        return auth.error
    tid = _parse_id("tr-", request.query_params.get("id"))
    if tid is None:
        return build_error(SubsonicError.REQUIRED_PARAM_MISSING, auth.fmt)
    with get_session() as session:
        track = session.get(Track, tid)
        if track is None:
            return build_error(SubsonicError.NOT_FOUND, auth.fmt)
        album = session.get(Album, track.album_id)
        artist = session.get(Artist, track.artist_id)
        payload = {"song": _track_dict(track, album.name, artist.name, bool(album.cover_path))}
    return build_response(payload, auth.fmt)


@router.get("/search3.view")
@router.get("/search3")
async def search3(request: Request) -> Response:
    auth = check_subsonic_auth(request)
    if auth.error:
        return auth.error
    qp = request.query_params
    query = (qp.get("query") or "").strip().lower()
    try:
        artist_count = int(qp.get("artistCount", "20"))
        album_count = int(qp.get("albumCount", "20"))
        song_count = int(qp.get("songCount", "20"))
    except ValueError:
        return build_error(SubsonicError.REQUIRED_PARAM_MISSING, auth.fmt)

    result: dict = {"searchResult3": {}}
    if not query:
        return build_response(result, auth.fmt)

    like = f"{query}%"
    contains = f"%{query}%"
    with get_session() as session:
        artists = (
            session.query(Artist)
            .filter(Artist.name_lower.like(like) | Artist.name_lower.like(contains))
            .order_by(Artist.name_lower)
            .limit(artist_count)
            .all()
        )
        if artists:
            result["searchResult3"]["artist"] = [
                {"id": f"ar-{a.id}", "name": a.name} for a in artists
            ]
        albums = (
            session.query(Album, Artist)
            .join(Artist, Album.artist_id == Artist.id)
            .filter(Album.name_lower.like(like) | Album.name_lower.like(contains))
            .order_by(Album.name_lower)
            .limit(album_count)
            .all()
        )
        if albums:
            out_al = []
            for al, ar in albums:
                sc = session.query(Track).filter_by(album_id=al.id).count()
                dur = sum(t.duration_s or 0 for t in session.query(Track).filter_by(album_id=al.id))
                out_al.append(_album_dict(al, ar.name, sc, dur))
            result["searchResult3"]["album"] = out_al
        tracks = (
            session.query(Track, Album, Artist)
            .join(Album, Track.album_id == Album.id)
            .join(Artist, Track.artist_id == Artist.id)
            .filter(Track.title_lower.like(like) | Track.title_lower.like(contains))
            .order_by(Track.title_lower)
            .limit(song_count)
            .all()
        )
        if tracks:
            result["searchResult3"]["song"] = [
                _track_dict(t, al.name, ar.name, bool(al.cover_path))
                for t, al, ar in tracks
            ]
    return build_response(result, auth.fmt)


@router.get("/stream.view")
@router.get("/stream")
async def stream(request: Request) -> Response:
    auth = check_subsonic_auth(request)
    if auth.error:
        return auth.error
    tid = _parse_id("tr-", request.query_params.get("id"))
    if tid is None:
        return build_error(SubsonicError.REQUIRED_PARAM_MISSING, auth.fmt)
    with get_session() as session:
        track = session.get(Track, tid)
        if track is None:
            return build_error(SubsonicError.NOT_FOUND, auth.fmt)
        path = Path(track.path)
    return range_response(path, request.headers.get("range"))


@router.get("/download.view")
@router.get("/download")
async def download(request: Request) -> Response:
    auth = check_subsonic_auth(request)
    if auth.error:
        return auth.error
    tid = _parse_id("tr-", request.query_params.get("id"))
    if tid is None:
        return build_error(SubsonicError.REQUIRED_PARAM_MISSING, auth.fmt)
    with get_session() as session:
        track = session.get(Track, tid)
        if track is None:
            return build_error(SubsonicError.NOT_FOUND, auth.fmt)
        path = Path(track.path)
    return range_response(path, None, force_download=True, filename=path.name)


@router.get("/getCoverArt.view")
@router.get("/getCoverArt")
async def get_cover_art(request: Request) -> Response:
    auth = check_subsonic_auth(request)
    if auth.error:
        return auth.error
    raw = request.query_params.get("id", "")
    size_raw = request.query_params.get("size")
    with get_session() as session:
        album = None
        if raw.startswith("al-"):
            alid = _parse_id("al-", raw)
            album = session.get(Album, alid) if alid else None
        elif raw.startswith("tr-"):
            tid = _parse_id("tr-", raw)
            track = session.get(Track, tid) if tid else None
            if track is not None:
                album = session.get(Album, track.album_id)
        if album is None or not album.cover_path:
            return build_error(SubsonicError.NOT_FOUND, auth.fmt)
        cover_path = Path(album.cover_path)
    if not cover_path.exists():
        return build_error(SubsonicError.NOT_FOUND, auth.fmt)
    if size_raw:
        try:
            size = int(size_raw)
        except ValueError:
            size = None
        if size and size > 0:
            data = get_cover_resized(cover_path, size)
            return Response(content=data, media_type="image/jpeg")
    return Response(content=cover_path.read_bytes(), media_type="image/jpeg")


@router.get("/getPlaylists.view")
@router.get("/getPlaylists")
async def get_playlists(request: Request) -> Response:
    auth = check_subsonic_auth(request)
    if auth.error:
        return auth.error
    with get_session() as session:
        pls = session.query(Playlist).order_by(Playlist.name).all()
        out = []
        for pl in pls:
            n = session.query(PlaylistEntry).filter_by(playlist_id=pl.id).count()
            out.append({
                "id": f"pl-{pl.id}",
                "name": pl.name,
                "songCount": n,
                "owner": "admin",
                "public": False,
            })
    return build_response({"playlists": {"playlist": out}}, auth.fmt)


@router.get("/getPlaylist.view")
@router.get("/getPlaylist")
async def get_playlist(request: Request) -> Response:
    auth = check_subsonic_auth(request)
    if auth.error:
        return auth.error
    pid = _parse_id("pl-", request.query_params.get("id"))
    if pid is None:
        return build_error(SubsonicError.REQUIRED_PARAM_MISSING, auth.fmt)
    with get_session() as session:
        pl = session.get(Playlist, pid)
        if pl is None:
            return build_error(SubsonicError.NOT_FOUND, auth.fmt)
        entries = (
            session.query(PlaylistEntry, Track, Album, Artist)
            .join(Track, PlaylistEntry.track_id == Track.id)
            .join(Album, Track.album_id == Album.id)
            .join(Artist, Track.artist_id == Artist.id)
            .filter(PlaylistEntry.playlist_id == pid)
            .order_by(PlaylistEntry.position)
            .all()
        )
        songs = [_track_dict(t, al.name, ar.name, bool(al.cover_path)) for _, t, al, ar in entries]
        payload = {
            "playlist": {
                "id": f"pl-{pl.id}",
                "name": pl.name,
                "songCount": len(songs),
                "owner": "admin",
                "public": False,
                "entry": songs,
            }
        }
    return build_response(payload, auth.fmt)
