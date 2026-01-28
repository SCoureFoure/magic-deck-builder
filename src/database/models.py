"""Database models using SQLAlchemy ORM."""
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.orm import backref


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


class Card(Base):
    """Card model representing a Magic: The Gathering card."""

    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scryfall_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    type_line: Mapped[str] = mapped_column(String(255), nullable=False)
    oracle_text: Mapped[Optional[str]] = None

    # Colors and identity
    colors: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)
    color_identity: Mapped[list[str]] = mapped_column(JSON, nullable=False)

    # Mana cost
    mana_cost: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    cmc: Mapped[float] = mapped_column(Float, nullable=False, index=True)

    # Legalities (e.g., {"commander": "legal", "vintage": "banned"})
    legalities: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)

    # Pricing (USD)
    price_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Image URIs (e.g., {"small": "url", "normal": "url", "large": "url"})
    image_uris: Mapped[Optional[dict[str, str]]] = mapped_column(JSON, nullable=True)

    # Card faces (for double-faced cards)
    card_faces: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSON, nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<Card(name='{self.name}', cmc={self.cmc})>"


class Commander(Base):
    """Commander model for cards eligible as commanders."""

    __tablename__ = "commanders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    card_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cards.id"), unique=True, nullable=False
    )
    eligibility_reason: Mapped[str] = mapped_column(String(255), nullable=False)
    color_identity: Mapped[list[str]] = mapped_column(JSON, nullable=False)

    # Relationships (one-to-one with Card)
    card: Mapped["Card"] = relationship(
        "Card", backref=backref("commander_info", uselist=False)
    )

    def __repr__(self) -> str:
        return f"<Commander(card_id={self.card_id}, reason='{self.eligibility_reason}')>"


class Role(Base):
    """Role model for card categories (ramp, removal, draw, etc.)."""

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<Role(name='{self.name}')>"


class Archetype(Base):
    """Archetype model for deck themes (tribal, spellslinger, etc.)."""

    __tablename__ = "archetypes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<Archetype(name='{self.name}')>"


class Deck(Base):
    """Deck model representing a Commander deck."""

    __tablename__ = "decks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    commander_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("commanders.id"), nullable=False
    )
    # Constraints (e.g., {"budget": 100, "themes": ["tribal"], "exclusions": ["card_id"]})
    constraints: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    # Relationships
    commander: Mapped["Commander"] = relationship("Commander")
    deck_cards: Mapped[list["DeckCard"]] = relationship(
        "DeckCard", back_populates="deck", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Deck(id={self.id}, commander_id={self.commander_id})>"


class DeckCard(Base):
    """DeckCard join table linking decks to cards with roles."""

    __tablename__ = "deck_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    deck_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("decks.id"), nullable=False, index=True
    )
    card_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cards.id"), nullable=False, index=True
    )
    role_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("roles.id"), nullable=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relationships
    deck: Mapped["Deck"] = relationship("Deck", back_populates="deck_cards")
    card: Mapped["Card"] = relationship("Card")
    role: Mapped[Optional["Role"]] = relationship("Role")

    def __repr__(self) -> str:
        return f"<DeckCard(deck_id={self.deck_id}, card_id={self.card_id}, qty={self.quantity})>"


class DeckArchetype(Base):
    """DeckArchetype join table linking decks to archetypes with weights."""

    __tablename__ = "deck_archetypes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    deck_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("decks.id"), nullable=False, index=True
    )
    archetype_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("archetypes.id"), nullable=False, index=True
    )
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    # Relationships
    deck: Mapped["Deck"] = relationship("Deck")
    archetype: Mapped["Archetype"] = relationship("Archetype")

    def __repr__(self) -> str:
        return f"<DeckArchetype(deck_id={self.deck_id}, archetype_id={self.archetype_id}, weight={self.weight})>"


class LLMRun(Base):
    """LLM run record for card suggestion requests."""

    __tablename__ = "llm_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    deck_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("decks.id"), nullable=False, index=True
    )
    commander_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("commanders.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    # Relationships
    deck: Mapped["Deck"] = relationship("Deck")
    commander: Mapped["Commander"] = relationship("Commander")

    def __repr__(self) -> str:
        return f"<LLMRun(deck_id={self.deck_id}, role={self.role}, success={self.success})>"


class CouncilAgentOpinion(Base):
    """Council agent-level scores/rankings with optional rationale."""

    __tablename__ = "council_agent_opinions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    deck_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("decks.id"), nullable=True, index=True
    )
    training_session_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("training_sessions.id"), nullable=True, index=True
    )
    commander_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("commanders.id"), nullable=False, index=True
    )
    card_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("cards.id"), nullable=True, index=True
    )
    role: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    agent_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    metrics: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ranking: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    deck: Mapped[Optional["Deck"]] = relationship("Deck")
    commander: Mapped["Commander"] = relationship("Commander")
    card: Mapped[Optional["Card"]] = relationship("Card")
    training_session: Mapped[Optional["TrainingSession"]] = relationship("TrainingSession")

    def __repr__(self) -> str:
        return (
            f"<CouncilAgentOpinion(agent_id={self.agent_id}, role={self.role}, "
            f"score={self.score})>"
        )


class CommanderCardSynergy(Base):
    """Commander-card synergy labels (0/1)."""

    __tablename__ = "commander_card_synergy"
    __table_args__ = (UniqueConstraint("commander_id", "card_id", name="uq_commander_card"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    commander_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("commanders.id"), nullable=False, index=True
    )
    card_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cards.id"), nullable=False, index=True
    )
    label: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    commander: Mapped["Commander"] = relationship("Commander")
    card: Mapped["Card"] = relationship("Card")

    def __repr__(self) -> str:
        return (
            f"<CommanderCardSynergy(commander_id={self.commander_id}, "
            f"card_id={self.card_id}, label={self.label})>"
        )


class TrainingSession(Base):
    """Anonymous training session for commander synergy labeling."""

    __tablename__ = "training_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    commander_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("commanders.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    commander: Mapped["Commander"] = relationship("Commander")

    def __repr__(self) -> str:
        return f"<TrainingSession(id={self.id}, commander_id={self.commander_id})>"


class TrainingSessionCard(Base):
    """Card presented within a training session."""

    __tablename__ = "training_session_cards"
    __table_args__ = (
        UniqueConstraint("session_id", "card_id", name="uq_training_session_card"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("training_sessions.id"), nullable=False, index=True
    )
    card_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cards.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    session: Mapped["TrainingSession"] = relationship("TrainingSession")
    card: Mapped["Card"] = relationship("Card")

    def __repr__(self) -> str:
        return f"<TrainingSessionCard(session_id={self.session_id}, card_id={self.card_id})>"


class CommanderCardVote(Base):
    """Vote on commander-card synergy (0/1) tied to a session."""

    __tablename__ = "commander_card_votes"
    __table_args__ = (
        UniqueConstraint("session_id", "card_id", name="uq_session_card_vote"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("training_sessions.id"), nullable=False, index=True
    )
    commander_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("commanders.id"), nullable=False, index=True
    )
    card_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cards.id"), nullable=False, index=True
    )
    vote: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    session: Mapped["TrainingSession"] = relationship("TrainingSession")
    commander: Mapped["Commander"] = relationship("Commander")
    card: Mapped["Card"] = relationship("Card")

    def __repr__(self) -> str:
        return (
            f"<CommanderCardVote(session_id={self.session_id}, card_id={self.card_id}, "
            f"vote={self.vote})>"
        )
