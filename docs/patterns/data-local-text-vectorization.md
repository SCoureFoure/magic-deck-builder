# Data: Local Text Vectorization

## Context
Use when we want similarity signals without paid APIs. This provides commander-conditioned text similarity using local TF-IDF vectors over card text.

## Implementation
- Build a TF-IDF index from card name, type line, and oracle text.
- Cache the index in-process for reuse.
- Compute cosine similarity between commander text and candidate cards.
- Use similarity as a feature for ranking or selection, not as a hard rule.

## Trade-offs
- Optimizes for zero-cost and fast iteration.
- Sacrifices semantic depth compared to neural embeddings.
- Requires local dependencies (scikit-learn, numpy, scipy).

## Examples
- `src/engine/text_vectorizer.py`
- `src/engine/llm_agent.py`

## Updated
2025-02-14: Added local TF-IDF similarity for commander-conditioned ranking.
