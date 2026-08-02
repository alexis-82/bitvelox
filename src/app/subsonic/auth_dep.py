from __future__ import annotations

from fastapi import Request
from fastapi.responses import Response

from app.auth import verify_subsonic_credentials
from app.config import get_settings
from app.db import get_session
from app.models import AdminUser
from app.subsonic.errors import SubsonicError
from app.subsonic.responses import build_error


class SubsonicAuthResult:
    def __init__(self, fmt: str, error: Response | None, user: AdminUser | None):
        self.fmt = fmt
        self.error = error
        self.user = user


def check_subsonic_auth(request: Request) -> SubsonicAuthResult:
    qp = request.query_params
    fmt = qp.get("f", "xml").lower()
    if fmt not in ("xml", "json"):
        fmt = "xml"

    u = qp.get("u")
    p = qp.get("p")
    t = qp.get("t")
    s = qp.get("s")

    if not u:
        return SubsonicAuthResult(fmt, build_error(SubsonicError.REQUIRED_PARAM_MISSING, fmt), None)
    if not (p or (t and s)):
        return SubsonicAuthResult(fmt, build_error(SubsonicError.REQUIRED_PARAM_MISSING, fmt), None)

    settings = get_settings()
    with get_session() as session:
        user = session.query(AdminUser).filter_by(username=u).first()
        if user is None:
            return SubsonicAuthResult(fmt, build_error(SubsonicError.WRONG_USERNAME_OR_PASSWORD, fmt), None)
        ok = verify_subsonic_credentials(user.plain_password, p=p, t=t, s=s)
        if not ok:
            return SubsonicAuthResult(fmt, build_error(SubsonicError.WRONG_USERNAME_OR_PASSWORD, fmt), None)
        # Detach user from session so caller can use it after with-block
        session.expunge(user)
    return SubsonicAuthResult(fmt, None, user)
