from __future__ import annotations

import re
from pathlib import Path

from fastapi.responses import Response, StreamingResponse

RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")
CHUNK_SIZE = 64 * 1024


def _read_range(path: Path, start: int, length: int):
    with path.open("rb") as f:
        f.seek(start)
        remaining = length
        while remaining > 0:
            chunk = f.read(min(CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def range_response(
    path: Path,
    range_header: str | None,
    media_type: str = "audio/mpeg",
    filename: str | None = None,
    force_download: bool = False,
) -> Response:
    if not path.exists() or not path.is_file():
        return Response(status_code=404)

    size = path.stat().st_size
    headers: dict[str, str] = {"Accept-Ranges": "bytes"}
    if force_download and filename:
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'

    if range_header:
        m = RANGE_RE.match(range_header.strip())
        if not m:
            return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})
        s_raw, e_raw = m.group(1), m.group(2)
        if s_raw == "" and e_raw == "":
            return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})
        if s_raw == "":
            suffix = int(e_raw)
            if suffix == 0:
                return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})
            start = max(0, size - suffix)
            end = size - 1
        else:
            start = int(s_raw)
            end = int(e_raw) if e_raw else size - 1
        if start >= size or start > end:
            return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})
        end = min(end, size - 1)
        length = end - start + 1
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
        headers["Content-Length"] = str(length)
        return StreamingResponse(
            _read_range(path, start, length),
            status_code=206,
            media_type=media_type,
            headers=headers,
        )

    headers["Content-Length"] = str(size)
    return StreamingResponse(
        _read_range(path, 0, size),
        status_code=200,
        media_type=media_type,
        headers=headers,
    )
