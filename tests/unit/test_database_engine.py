"""Tests for database engine and session management."""
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.database.engine import get_db, engine, SessionLocal


def test_engine_created():
    """Test that database engine is created."""
    assert engine is not None
    assert engine.url is not None


def test_session_factory_created():
    """Test that SessionLocal factory is created."""
    assert SessionLocal is not None


def test_get_db_returns_session():
    """Test that get_db returns a valid session."""
    with get_db() as db:
        assert isinstance(db, Session)
        assert db.is_active


def test_get_db_commits_on_success():
    """Test that get_db commits when no exception occurs."""
    from src.database.models import Base, Role

    # Create tables for this test
    Base.metadata.create_all(bind=engine)

    with get_db() as db:
        role = Role(name="test_commit", description="Test role")
        db.add(role)
        # Context manager should commit on exit

    # Verify in new session
    with get_db() as db:
        found_role = db.query(Role).filter_by(name="test_commit").first()
        assert found_role is not None
        assert found_role.description == "Test role"
        # Cleanup
        db.delete(found_role)


def test_get_db_rolls_back_on_exception():
    """Test that get_db rolls back when exception occurs."""
    from src.database.models import Base, Role

    Base.metadata.create_all(bind=engine)

    try:
        with get_db() as db:
            role = Role(name="test_rollback", description="Test role")
            db.add(role)
            # Force an exception
            raise ValueError("Test exception")
    except ValueError:
        pass

    # Verify role was not persisted
    with get_db() as db:
        found_role = db.query(Role).filter_by(name="test_rollback").first()
        assert found_role is None


def test_get_db_closes_session():
    """Test that get_db closes the session after use."""
    from src.database.models import Base

    Base.metadata.create_all(bind=engine)

    session_ref = None
    with get_db() as db:
        session_ref = db
        assert db.is_active  # Should be active inside context

    # After context exits, trying to use session should fail or show it's been finalized
    # Check that the session's identity map is cleared (sign of closure)
    assert len(session_ref.identity_map) == 0


def test_engine_pool_pre_ping_enabled():
    """Test that pool_pre_ping is enabled for connection verification."""
    # Check engine configuration
    assert engine.pool._pre_ping is True


def test_session_factory_autocommit_disabled():
    """Test that SessionLocal has autocommit disabled."""
    assert SessionLocal.kw.get("autocommit") is False


def test_session_factory_autoflush_disabled():
    """Test that SessionLocal has autoflush disabled."""
    assert SessionLocal.kw.get("autoflush") is False


def test_get_db_can_execute_queries():
    """Test that sessions from get_db can execute queries."""
    from src.database.models import Base

    Base.metadata.create_all(bind=engine)

    with get_db() as db:
        # Execute a simple query
        result = db.execute(text("SELECT 1 as num"))
        row = result.fetchone()
        assert row[0] == 1


def test_get_db_multiple_uses():
    """Test that get_db can be used multiple times."""
    from src.database.models import Base

    Base.metadata.create_all(bind=engine)

    # First use
    with get_db() as db1:
        result = db1.execute(text("SELECT 1"))
        assert result.fetchone() is not None

    # Second use should work independently
    with get_db() as db2:
        result = db2.execute(text("SELECT 2"))
        assert result.fetchone()[0] == 2


def test_get_db_exception_propagates():
    """Test that exceptions within get_db context are propagated."""
    with pytest.raises(ValueError, match="Test propagation"):
        with get_db() as db:
            raise ValueError("Test propagation")
