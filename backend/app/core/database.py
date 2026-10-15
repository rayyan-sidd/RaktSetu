import os
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# Default SQLite database path in project repository
DEFAULT_DB_PATH = Path("data") / "raktsetu.db"
DEFAULT_DATABASE_URL = f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"

DATABASE_URL = os.getenv("RAKTSETU_DATABASE_URL", DEFAULT_DATABASE_URL)

# Ensure parent directory exists for SQLite database files
if DATABASE_URL.startswith("sqlite:///"):
    sqlite_rel_or_abs = DATABASE_URL.replace("sqlite:///", "")
    if sqlite_rel_or_abs and sqlite_rel_or_abs != ":memory:":
        db_file = Path(sqlite_rel_or_abs)
        db_file.parent.mkdir(parents=True, exist_ok=True)

# Connection configuration appropriate for SQLite and FastAPI concurrent workers
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class Base(DeclarativeBase):
    """Declarative Base class for all RaktSetu SQLAlchemy ORM models."""

    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a SQLAlchemy session and ensuring it closes after request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all registered database tables if they do not already exist."""
    Base.metadata.create_all(bind=engine)
