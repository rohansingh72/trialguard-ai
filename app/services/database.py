from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def database_url_from_target(target: str | Path) -> str:
    """Return a SQLAlchemy URL for either a URL string or SQLite file path."""
    if isinstance(target, str) and "://" in target:
        return target

    path = Path(target).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite+pysqlite:///{path}"


def create_database_engine(target: str | Path) -> Engine:
    database_url = database_url_from_target(target)

    kwargs: dict[str, object] = {
        "pool_pre_ping": True,
    }

    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {
            "check_same_thread": False,
        }

    return create_engine(database_url, **kwargs)


def check_database_connection(engine: Engine) -> None:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
