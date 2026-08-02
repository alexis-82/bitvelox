from __future__ import annotations

from xml.sax.saxutils import escape, quoteattr

from fastapi.responses import JSONResponse, Response

from app.subsonic.errors import ERROR_MESSAGES, SubsonicError

SUBSONIC_API_VERSION = "1.13.0"


def _dict_to_xml(name: str, obj) -> str:
    if isinstance(obj, dict):
        attrs = []
        children = []
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                children.append((k, v))
            elif v is not None:
                attrs.append(f"{k}={quoteattr(str(v))}")
        attr_str = (" " + " ".join(attrs)) if attrs else ""
        if not children:
            return f"<{name}{attr_str}/>"
        inner = "".join(_dict_to_xml(k, v) for k, v in children)
        return f"<{name}{attr_str}>{inner}</{name}>"
    if isinstance(obj, list):
        return "".join(_dict_to_xml(name, item) for item in obj)
    return f"<{name}>{escape(str(obj))}</{name}>"


def build_response(payload: dict, fmt: str) -> Response:
    root = {"status": "ok", "version": SUBSONIC_API_VERSION, **payload}
    if fmt == "json":
        return JSONResponse({"subsonic-response": root})
    xml = f'<?xml version="1.0" encoding="UTF-8"?>{_dict_to_xml("subsonic-response", root)}'
    return Response(content=xml, media_type="application/xml")


def build_error(code: SubsonicError, fmt: str, message: str | None = None) -> Response:
    msg = message or ERROR_MESSAGES[code]
    body = {
        "status": "failed",
        "version": SUBSONIC_API_VERSION,
        "error": {"code": int(code), "message": msg},
    }
    if fmt == "json":
        return JSONResponse({"subsonic-response": body})
    xml = f'<?xml version="1.0" encoding="UTF-8"?>{_dict_to_xml("subsonic-response", body)}'
    return Response(content=xml, media_type="application/xml")
