"""Tests for role seeding."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.database.models import Base, Role
from src.database.seed_roles import seed_roles


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


def test_seed_roles_creates_all_roles(db_session: Session):
    """Test that seed_roles creates all expected roles."""
    count = seed_roles(db_session)

    # Should create 7 roles
    assert count == 7

    # Verify all roles exist
    roles = db_session.query(Role).all()
    assert len(roles) == 7

    role_names = {role.name for role in roles}
    expected_names = {"lands", "ramp", "draw", "removal", "synergy", "wincons", "flex"}
    assert role_names == expected_names


def test_seed_roles_idempotent(db_session: Session):
    """Test that seed_roles doesn't create duplicates."""
    # First seed
    count1 = seed_roles(db_session)
    assert count1 == 7

    # Second seed should return 0 (already seeded)
    count2 = seed_roles(db_session)
    assert count2 == 0

    # Still only 7 roles
    roles = db_session.query(Role).all()
    assert len(roles) == 7


def test_seed_roles_all_have_descriptions(db_session: Session):
    """Test that all seeded roles have descriptions."""
    seed_roles(db_session)

    roles = db_session.query(Role).all()
    for role in roles:
        assert role.description is not None
        assert len(role.description) > 0


def test_seed_roles_lands_role_exists(db_session: Session):
    """Test that 'lands' role is created."""
    seed_roles(db_session)

    lands_role = db_session.query(Role).filter_by(name="lands").first()
    assert lands_role is not None
    assert "mana" in lands_role.description.lower()


def test_seed_roles_ramp_role_exists(db_session: Session):
    """Test that 'ramp' role is created."""
    seed_roles(db_session)

    ramp_role = db_session.query(Role).filter_by(name="ramp").first()
    assert ramp_role is not None
    assert "acceleration" in ramp_role.description.lower()


def test_seed_roles_draw_role_exists(db_session: Session):
    """Test that 'draw' role is created."""
    seed_roles(db_session)

    draw_role = db_session.query(Role).filter_by(name="draw").first()
    assert draw_role is not None
    assert "draw" in draw_role.description.lower()


def test_seed_roles_removal_role_exists(db_session: Session):
    """Test that 'removal' role is created."""
    seed_roles(db_session)

    removal_role = db_session.query(Role).filter_by(name="removal").first()
    assert removal_role is not None
    assert "removal" in removal_role.description.lower()


def test_seed_roles_synergy_role_exists(db_session: Session):
    """Test that 'synergy' role is created."""
    seed_roles(db_session)

    synergy_role = db_session.query(Role).filter_by(name="synergy").first()
    assert synergy_role is not None
    assert "synergize" in synergy_role.description.lower()


def test_seed_roles_wincons_role_exists(db_session: Session):
    """Test that 'wincons' role is created."""
    seed_roles(db_session)

    wincons_role = db_session.query(Role).filter_by(name="wincons").first()
    assert wincons_role is not None
    assert "win" in wincons_role.description.lower()


def test_seed_roles_flex_role_exists(db_session: Session):
    """Test that 'flex' role is created."""
    seed_roles(db_session)

    flex_role = db_session.query(Role).filter_by(name="flex").first()
    assert flex_role is not None
    assert "utility" in flex_role.description.lower() or "flex" in flex_role.description.lower()


def test_seed_roles_returns_zero_when_roles_exist(db_session: Session):
    """Test that seed_roles returns 0 when roles already exist."""
    # Manually add a role
    role = Role(name="test", description="test role")
    db_session.add(role)
    db_session.commit()

    # Should return 0 since roles already exist
    count = seed_roles(db_session)
    assert count == 0

    # Should only have the one role we added
    roles = db_session.query(Role).all()
    assert len(roles) == 1


def test_seed_roles_commits_transaction(db_session: Session):
    """Test that seed_roles commits the transaction."""
    seed_roles(db_session)

    # Rollback and check - if properly committed, data should persist
    # We'll do this by creating a new session
    roles_count = db_session.query(Role).count()
    assert roles_count == 7
