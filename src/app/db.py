from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


_engine = None
_SessionLocal: sessionmaker[Session] | None = None


def _make_engine(db_path: Path | str):
    if isinstance(db_path, Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{db_path}"
    else:
        url = db_path  # already a URL, e.g. sqlite:///:memory:
    return create_engine(url, echo=False, future=True)


def init_db(db_path: Path | str) -> None:
    global _engine, _SessionLocal
    # Import models so their tables are registered on Base.metadata.
    from app import models  # noqa: F401

    _engine = _make_engine(db_path)
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(_engine)


def get_session() -> Session:
    if _SessionLocal is None:
        raise RuntimeError("init_db() must be called before get_session()")
    return _SessionLocal()


def get_engine():
    if _engine is None:
        raise RuntimeError("init_db() must be called before get_engine()")
    return _engine
