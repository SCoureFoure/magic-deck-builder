"""Local TF-IDF vectorization for commander-conditioned similarity."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import Session

from src.database.models import Card


@dataclass
class VectorIndex:
    vectorizer: TfidfVectorizer
    card_ids: list[int]
    matrix: np.ndarray


_INDEX: VectorIndex | None = None


def _card_text(card: Card) -> str:
    parts = [
        card.name or "",
        card.type_line or "",
        card.oracle_text or "",
    ]
    return " ".join(part for part in parts if part).lower()


def build_index(session: Session) -> VectorIndex:
    """Build or rebuild the TF-IDF index for commander-legal cards."""
    cards = (
        session.query(Card)
        .filter(Card.legalities["commander"].as_string() == "legal")
        .all()
    )
    texts = [_card_text(card) for card in cards]
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1, max_features=50000)
    matrix = vectorizer.fit_transform(texts)
    card_ids = [card.id for card in cards]
    return VectorIndex(vectorizer=vectorizer, card_ids=card_ids, matrix=matrix)


def get_index(session: Session) -> VectorIndex:
    """Return a cached TF-IDF index, building it if needed."""
    global _INDEX
    if _INDEX is None:
        _INDEX = build_index(session)
    return _INDEX


def compute_similarity(
    session: Session, commander: Card, candidates: Iterable[Card]
) -> dict[int, float]:
    """Compute cosine similarity between commander text and candidate cards."""
    index = get_index(session)
    commander_vec = index.vectorizer.transform([_card_text(commander)])
    candidate_ids = [card.id for card in candidates]
    if not candidate_ids:
        return {}

    id_to_row = {card_id: i for i, card_id in enumerate(index.card_ids)}
    rows = [id_to_row[card_id] for card_id in candidate_ids if card_id in id_to_row]
    if not rows:
        return {}

    candidate_matrix = index.matrix[rows]
    sims = cosine_similarity(commander_vec, candidate_matrix).flatten()
    return {card_id: float(score) for card_id, score in zip(candidate_ids, sims)}
