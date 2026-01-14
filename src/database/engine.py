"""Database engine and session management."""
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import settings

# Create engine
engine = create_engine(
    settings.database_url,
    echo=False,  # Set to True for SQL logging
    pool_pre_ping=True,  # Verify connections before using
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Get database session context manager.

    Usage:
        with get_db() as db:
            db.query(Card).all()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """Initialize database by creating all tables.

    Note: This is for quick setup. Use Alembic for production migrations.
    """
    from src.database.models import Base

    Base.metadata.create_all(bind=engine)
