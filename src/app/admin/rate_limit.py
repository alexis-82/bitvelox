from __future__ import annotations

import time
from collections import defaultdict, deque

_MAX_ATTEMPTS = 5
_WINDOW_SECONDS = 5 * 60
_attempts: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=_MAX_ATTEMPTS))


def check_and_record(ip: str) -> bool:
    """Return True if the request is allowed, False if rate-limited."""
    now = time.time()
    dq = _attempts[ip]
    while dq and now - dq[0] > _WINDOW_SECONDS:
        dq.popleft()
    if len(dq) >= _MAX_ATTEMPTS:
        return False
    dq.append(now)
    return True


def reset(ip: str) -> None:
    _attempts.pop(ip, None)


def clear_all() -> None:
    _attempts.clear()
