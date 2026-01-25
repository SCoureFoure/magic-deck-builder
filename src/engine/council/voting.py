"""Voting and aggregation helpers for council selection."""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable


def _normalize_rankings(rankings: dict[str, list[str]]) -> dict[str, list[str]]:
    return {
        agent_id: [name for name in ranked if name]
        for agent_id, ranked in rankings.items()
        if ranked
    }


def borda_count(
    rankings: dict[str, list[str]],
    agent_weights: dict[str, float],
    top_k: int,
) -> list[str]:
    rankings = _normalize_rankings(rankings)
    scores: dict[str, float] = defaultdict(float)

    for agent_id, ranked in rankings.items():
        weight = agent_weights.get(agent_id, 1.0)
        total = len(ranked)
        for idx, name in enumerate(ranked[:top_k]):
            score = (total - idx) * weight
            scores[name] += score

    return [
        name
        for name, _ in sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    ]


def majority_vote(
    rankings: dict[str, list[str]],
    agent_weights: dict[str, float],
    top_k: int,
) -> list[str]:
    rankings = _normalize_rankings(rankings)
    scores: dict[str, float] = defaultdict(float)

    for agent_id, ranked in rankings.items():
        weight = agent_weights.get(agent_id, 1.0)
        for name in ranked[:top_k]:
            scores[name] += weight

    return [
        name
        for name, _ in sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    ]


def aggregate_rankings(
    rankings: dict[str, list[str]],
    agent_weights: dict[str, float],
    strategy: str,
    top_k: int,
) -> list[str]:
    if strategy == "majority":
        return majority_vote(rankings, agent_weights, top_k)
    return borda_count(rankings, agent_weights, top_k)
