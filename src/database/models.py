"""Database models using SQLAlchemy ORM."""
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
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
    oracle_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Colors and identity
    colors: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)
    color_identity: Mapped[list[str]] = mapped_column(JSON, nullable=False, index=True)

    # Mana cost
    mana_cost: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    cmc: Mapped[float] = mapped_column(Float, nullable=False, index=True)

    # Legalities (e.g., {"commander": "legal", "vintage": "banned"})
    legalities: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)

    # Pricing (USD)
    price_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Image URIs (e.g., {"small": "url", "normal": "url", "large": "url"})
    image_uris: Mapped[Optional[dict[str, str]]] = mapped_column(JSON, nullable=True)

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
    color_identity: Mapped[list[str]] = mapped_column(JSON, nullable=False, index=True)

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
