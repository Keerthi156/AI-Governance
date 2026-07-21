"""
Database engine and session factory.

Why this file exists:
- Single place to create the SQLAlchemy engine and sessions.
- Keeps connection concerns out of route handlers.
- Supports readiness checks without crashing app startup if DB is briefly down.
"""

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.models.base import Base

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    class_=Session,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session and closes it afterward."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> tuple[bool, str]:
    """
    Probe the database with a lightweight SELECT 1.

    Returns (ok, detail) for readiness endpoints.
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True, "connected"
    except Exception as exc:  # noqa: BLE001 - surface any driver/network failure
        return False, str(exc)


# Re-export Base for convenience in scripts / Alembic.
__all__ = [
    "Base",
    "SessionLocal",
    "check_database_connection",
    "engine",
    "get_db",
]
