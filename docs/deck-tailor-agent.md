# Deck Tailor Agent

## Overview

The Deck Tailor Agent is an AI-assisted deck building system that creates coherent, synergistic Commander decks by understanding and evolving deck identity as cards are selected. Unlike simple heuristic-based builders, the agent treats deck construction as an emergent process where each card addition influences subsequent selections.

## Core Concept: Emergent Deck Identity

Traditional deck builders fill slots independently: "pick 10 ramp cards, pick 10 draw cards." The Deck Tailor instead builds a **deck identity** that evolves:

1. **Commander + Seeds establish initial identity** → voltron, spellslinger, aristocrats, etc.
2. **Each card selection shifts the identity** → adding equipment cards strengthens "voltron" weight
3. **Identity influences future selections** → system prefers cards that reinforce emerging themes
4. **Result: coherent decks with stacking synergies** → cards work together, not just individually

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        DECK BRIEF (Input)                        │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ Commander: Zurgo Helmsmasher                              │  │
│  │ Seeds: [Assault Suit, Worldslayer]                        │  │
│  │ Objectives: {power: 0.7, theme: 0.8, budget: 0.3}         │  │
│  │ Constraints: {max_price: 500, ban: ["Dockside"]}          │  │
│  └───────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  LAYER 1: SOFT ROLE GATE                                        │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Ensures baseline deckbuilding fundamentals              │    │
│  │ Minimums come from DeckBrief/config (no enforced defaults)│    │
│  │ After minimum: soft penalty, not hard exclusion         │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  LAYER 2: IDENTITY EXTRACTION                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Deterministic baseline: keyword/type → archetype tags   │    │
│  │ Optional LLM enhancement: clamped to ±0.2 delta         │    │
│  │ Output: weighted archetype vector                       │    │
│  │ Example: {"voltron": 0.7, "equipment": 0.5, ...}        │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  LAYER 3: CARD SCORING                                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Combines: embeddings, archetype match, keywords,        │    │
│  │          learned synergy, objectives, role penalties    │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  LAYER 4: FEEDBACK & LEARNING                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Pairwise preferences: "A vs B for this deck?"           │    │
│  │ Contextual logging: learns synergy per deck state       │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

## Deck Brief Specification

The Deck Brief is the input contract that steers deck generation.

### Schema

```python
@dataclass
class DeckBrief:
    commander: str                    # Required: commander card name
    seeds: list[str] = field(default_factory=list)  # Optional: 0-10 cards to build around
    objectives: ObjectiveWeights = field(default_factory=ObjectiveWeights)
    constraints: DeckConstraints = field(default_factory=DeckConstraints)

@dataclass
class ObjectiveWeights:
    """Weights from 0.0 to 1.0. Higher = more important."""
    power: float = 0.5       # Prefer powerful/efficient cards
    theme: float = 0.5       # Prefer on-theme synergistic cards (exploratory)
    budget: float = 0.5      # Prefer cheaper cards
    consistency: float = 0.5 # Prefer redundant effects
    novelty: float = 0.0     # Prefer unusual/underplayed cards

@dataclass
class DeckConstraints:
    max_price_usd: float | None = None    # Total deck budget cap
    card_price_cap: float | None = None   # Per-card price limit
    must_include: list[str] = field(default_factory=list)  # Force these cards
    must_exclude: list[str] = field(default_factory=list)  # Ban these cards

    # Role overrides (None = no enforced minimums)
    min_lands: int | None = None
    min_ramp: int | None = None
    min_draw: int | None = None
    min_removal: int | None = None
```

### Example Deck Briefs

**Competitive Voltron:**
```python
DeckBrief(
    commander="Zurgo Helmsmasher",
    seeds=["Worldslayer", "Assault Suit", "Sunforger"],
    objectives=ObjectiveWeights(power=0.9, theme=0.7, budget=0.1),
    constraints=DeckConstraints(max_price_usd=800)
)
```

**Budget Spellslinger:**
```python
DeckBrief(
    commander="Kess, Dissident Mage",
    seeds=["Thousand-Year Storm"],
    objectives=ObjectiveWeights(power=0.4, theme=0.9, budget=0.9),
    constraints=DeckConstraints(max_price_usd=100, card_price_cap=5)
)
```

**Theme-First Tribal:**
```python
DeckBrief(
    commander="Edgar Markov",
    seeds=[],  # Let agent discover vampire synergies
    objectives=ObjectiveWeights(power=0.5, theme=1.0, budget=0.5),
    constraints=DeckConstraints()
)
```

## Scoring System

### Master Formula

```python
def score_card(card, deck_state, deck_brief):
    # === BASE SIGNALS (0-1 normalized) ===
    emb_sim = cosine_similarity(card.embedding, deck_state.centroid)
    arch_match = compute_archetype_match(card, deck_state.identity)
    kw_overlap = compute_keyword_overlap(card, deck_state.keywords)
    learned = synergy_model.predict(deck_state.identity_vector, card.embedding)

    raw_score = (
        emb_sim    * 0.25 +
        arch_match * 0.35 +
        kw_overlap * 0.20 +
        learned    * 0.20
    )

    # === OBJECTIVE FIT (weighted blend, floor at 0.5) ===
    obj_fit = compute_objective_fit(card, deck_brief, deck_state)
    score = raw_score * (0.5 + 0.5 * obj_fit)

    # === SOFT ROLE PENALTY ===
    role_penalty = compute_role_penalty(card, deck_state)
    score *= role_penalty

    return score
```

### Signal Components

#### 1. Embedding Similarity (25%)

Measures semantic similarity between the candidate card and the current deck's "centroid" (average embedding of all selected cards).

```python
def compute_embedding_similarity(card, deck_state):
    if deck_state.centroid is None:
        return 0.5  # Neutral for first card
    return cosine_similarity(card.embedding, deck_state.centroid)
```

**What it captures:**
- Cards with similar text/mechanics to existing selections
- Thematic coherence at the text level

**Limitations:**
- May miss mechanical synergies with opposite-sounding text
- "Sacrifice a creature" and "When a creature dies" are synergistic but may not be similar

#### 2. Archetype Match (35%)

Measures how well a card fits the deck's current archetype weights.

```python
def compute_archetype_match(card, identity):
    """
    card.archetype_tags: {"voltron": 0.8, "equipment": 0.6, ...}
    identity: {"voltron": 0.7, "spellslinger": 0.1, ...}
    """
    if not identity:
        return 0.5

    total = 0.0
    weight_sum = sum(identity.values())
    if weight_sum <= 0:
        return 0.5
    for archetype, deck_weight in identity.items():
        card_weight = card.archetype_tags.get(archetype, 0.0)
        total += card_weight * deck_weight

    return total / weight_sum
```

#### 3. Keyword Overlap (20%)

Measures shared keywords/mechanics between candidate and deck.

```python
def compute_keyword_overlap(card, deck_keywords):
    if not card.keywords or not deck_keywords:
        return 0.0
    overlap = len(card.keywords & deck_keywords)
    union = len(card.keywords | deck_keywords)
    return overlap / max(union, 1)
```

**Example keywords:** haste, flying, trample, lifelink, deathtouch, flash, vigilance

#### 4. Learned Synergy (20%)

Model-predicted synergy based on pairwise feedback data.

```python
def predict_synergy(identity_vector, card_embedding):
    """
    Trained on: (deck_identity, card_a, card_b, user_preference)
    Predicts: how well this card fits this deck identity
    """
    # Initially returns 0.5 (neutral) until sufficient training data
    return synergy_model.predict(identity_vector, card_embedding)
```

### Objective Fit Calculation

Objectives are combined as a weighted average, not chained multiplication:

```python
def compute_objective_fit(card, deck_brief, deck_state):
    fits = []
    weights = []
    obj = deck_brief.objectives

    if obj.power > 0:
        fits.append(power_rating(card))
        weights.append(obj.power)

    if obj.budget > 0:
        budget_fit = compute_budget_fit(card, deck_brief.constraints)
        fits.append(budget_fit)
        weights.append(obj.budget)

    if obj.theme > 0:
        # Theme remains exploratory; use current identity if available.
        fits.append(theme_purity(card, deck_state.identity))
        weights.append(obj.theme)

    if obj.consistency > 0:
        fits.append(redundancy_score(card, deck_state))
        weights.append(obj.consistency)

    if obj.novelty > 0:
        fits.append(novelty_score(card))
        weights.append(obj.novelty)

    if not weights:
        return 1.0

    return sum(f * w for f, w in zip(fits, weights)) / sum(weights)

def compute_budget_fit(card, constraints):
    if not constraints.max_price_usd:
        return 1.0
    if card.price_usd is None:
        return 0.5  # Unknown price, neutral

    # Per-card cap check
    if constraints.card_price_cap and card.price_usd > constraints.card_price_cap:
        return 0.0

    # Gradual penalty as price approaches cap
    return 1.0 - min(card.price_usd / constraints.max_price_usd, 1.0)
```

**Key design:** `score = raw * (0.5 + 0.5 * obj_fit)` ensures:
- Minimum 50% of raw score preserved (good cards aren't crushed)
- Maximum 100% of raw score (perfect objective fit)
- No compounding penalties from multiple objectives

### Soft Role Gate

Role minimums are enforced when configured, but exceeding them incurs gradual penalty:

```python
ROLE_MINIMUMS = {
    # Intentionally no enforced defaults; set via DeckBrief or config.
    # Use None to disable minimums for a role.
    'lands': None,
    'ramp': None,
    'draw': None,
    'removal': None,
    'wincon': None,
    'synergy': None,
    'flex': None,
}

def compute_role_penalty(card, deck_state):
    card_role = classify_card_role(card)
    current = deck_state.role_counts.get(card_role, 0)
    minimum = ROLE_MINIMUMS.get(card_role)

    if minimum is None:
        return 1.0

    if current < minimum:
        return 1.0  # No penalty, still need this role

    # Each card over minimum: -0.1 multiplier, floor at 0.5
    excess = current - minimum
    return max(0.5, 1.0 - (excess * 0.1))
```

**Behavior examples:**

| Situation | Penalty |
|-----------|---------|
| 8th ramp card (min 10) | 1.0 (no penalty) |
| 11th ramp card | 0.9 |
| 15th ramp card | 0.5 (floor) |

This allows archetypes that naturally want more of a role (spellslinger wanting 12+ draw) while maintaining fundamentals.

## Identity System

### Archetype Taxonomy

Core archetypes the system recognizes:

| Archetype | Description | Key Indicators |
|-----------|-------------|----------------|
| `voltron` | Win via commander damage | Equipment, auras, protection, evasion |
| `spellslinger` | Spell-focused value | Instants/sorceries matter, copy, storm |
| `aristocrats` | Sacrifice synergies | Death triggers, sacrifice outlets, recursion |
| `tribal` | Creature type synergies | Lords, type-specific effects |
| `tokens` | Go-wide strategies | Token generators, anthems, populate |
| `control` | Answer-heavy reactive | Counters, removal, card draw |
| `combo` | Specific card interactions | Tutors, infinite enablers |
| `reanimator` | Graveyard recursion | Discard, reanimate, mill self |
| `stax` | Resource denial | Tax effects, sacrifice symmetrical |
| `landfall` | Land-based triggers | Extra land drops, land recursion |
| `+1/+1_counters` | Counter synergies | Counter placement, doubling, moving |
| `equipment` | Equipment-focused | Equip cost reduction, equipment tutors |
| `enchantress` | Enchantment synergies | Enchantment draw, constellation |
| `wheels` | Hand cycling | Wheel effects, no max hand size |
| `goodstuff` | Generic value | Staples, efficient cards |

### Identity Extraction

#### Deterministic Baseline

```python
def extract_identity_deterministic(commander, seeds):
    """
    Analyze commander + seeds to establish initial archetype weights.
    Returns dict of archetype -> weight (0.0 to 1.0)
    """
    identity = defaultdict(float)

    cards = [commander] + seeds
    for card in cards:
        tags = extract_archetype_tags(card)
        for arch, weight in tags.items():
            identity[arch] = max(identity[arch], weight)

    # Normalize so max weight is 1.0
    if identity:
        max_weight = max(identity.values())
        identity = {k: v / max_weight for k, v in identity.items()}

    return dict(identity)

def extract_archetype_tags(card):
    """
    Pattern-match card text/types to archetype indicators.
    """
    tags = {}
    text = (card.oracle_text or "").lower()
    type_line = (card.type_line or "").lower()

    # Voltron indicators
    if any(kw in text for kw in ["equipped creature", "attach", "equipment"]):
        tags["voltron"] = 0.6
        tags["equipment"] = 0.8
    if any(kw in text for kw in ["aura", "enchanted creature gets"]):
        tags["voltron"] = 0.5
    if "commander damage" in text or "double strike" in text:
        tags["voltron"] = 0.7

    # Spellslinger indicators
    if "instant" in type_line or "sorcery" in type_line:
        tags["spellslinger"] = 0.4
    if any(kw in text for kw in ["copy target", "when you cast", "magecraft"]):
        tags["spellslinger"] = 0.7
    if "storm" in text:
        tags["spellslinger"] = 0.9

    # Aristocrats indicators
    if any(kw in text for kw in ["sacrifice a creature", "when a creature dies"]):
        tags["aristocrats"] = 0.7
    if "blood artist" in card.name.lower() or "zulaport" in card.name.lower():
        tags["aristocrats"] = 0.9

    # ... additional patterns for other archetypes

    return tags
```

#### LLM Enhancement (Optional)

When enabled, LLM refines the deterministic baseline:

```python
def enhance_identity_with_llm(deterministic_identity, commander, seeds, deck_cards):
    """
    Use LLM to refine identity, clamped to ±0.2 delta from baseline.
    """
    prompt = f"""
    Analyze this Commander deck's emerging identity.

    Commander: {commander.name}
    Commander text: {commander.oracle_text}
    Seed cards: {[s.name for s in seeds]}
    Current deck ({len(deck_cards)} cards): {[c.name for c in deck_cards[:20]]}...

    Current identity weights: {deterministic_identity}

    Return adjusted weights as JSON. You may adjust each weight by at most ±0.2.
    Consider: What strategies are emerging? What should we lean into?

    Response format:
    {{"voltron": 0.X, "spellslinger": 0.X, ...}}
    """

    response = llm_client.complete(prompt, response_format="json")
    llm_identity = json.loads(response)

    # Clamp deltas to ±0.2 (including new archetypes if suggested)
    clamped = {}
    all_arches = set(deterministic_identity.keys()) | set(llm_identity.keys())
    for arch in all_arches:
        baseline_weight = deterministic_identity.get(arch, 0.0)
        llm_weight = llm_identity.get(arch, baseline_weight)
        delta = llm_weight - baseline_weight
        clamped_delta = max(-0.2, min(0.2, delta))
        clamped[arch] = baseline_weight + clamped_delta

    return clamped
```

### Identity Evolution

Identity updates as cards are added:

```python
def update_identity(deck_state, new_card):
    """
    Blend new card's archetype tags into deck identity.
    Uses exponential moving average for stability.
    """
    alpha = 0.1  # Learning rate - small for stability

    new_tags = extract_archetype_tags(new_card)

    for arch in set(deck_state.identity.keys()) | set(new_tags.keys()):
        current = deck_state.identity.get(arch, 0.0)
        new = new_tags.get(arch, 0.0)
        deck_state.identity[arch] = current * (1 - alpha) + new * alpha
```

## Feedback System

### Pairwise Preference Collection

Users provide feedback by choosing between card pairs:

```
┌─────────────────────────────────────────────────────────────┐
│  For this Zurgo deck (identity: voltron 0.7, equipment 0.5) │
│                                                              │
│  Which card fits better?                                     │
│                                                              │
│  [A] Sword of Feast and Famine                              │
│  [B] Phyrexian Arena                                        │
│                                                              │
│  [ ] A is much better                                        │
│  [X] A is slightly better                                    │
│  [ ] About equal                                             │
│  [ ] B is slightly better                                    │
│  [ ] B is much better                                        │
└─────────────────────────────────────────────────────────────┘
```

### Feedback Data Model

```python
@dataclass
class PairwisePreference:
    id: int
    deck_identity_vector: list[float]  # Current identity as vector
    card_a_id: int
    card_b_id: int
    preference: int  # -2 (B much better) to +2 (A much better)
    context: dict    # Additional deck state info
    created_at: datetime
```

### Learning from Feedback

```python
class SynergyModel:
    """
    Learns to predict card fit from pairwise preferences.
    Starts with logistic regression, can upgrade to neural net.
    """

    def __init__(self):
        self.model = LogisticRegression()
        self.trained = False

    def train(self, preferences: list[PairwisePreference], embeddings: dict):
        if len(preferences) < 50:
            return  # Not enough data yet

        X, y = [], []
        for pref in preferences:
            # Feature: concat(identity, card_a_emb - card_b_emb)
            identity = np.array(pref.deck_identity_vector)
            card_a_emb = embeddings[pref.card_a_id]
            card_b_emb = embeddings[pref.card_b_id]
            diff = card_a_emb - card_b_emb

            X.append(np.concatenate([identity, diff]))
            # Preserve ordinal signal; tie handling can be filtered or modeled.
            y.append(pref.preference)

        self.model.fit(X, y)
        self.trained = True

    def predict(self, identity_vector, card_embedding):
        if not self.trained:
            return 0.5  # Neutral until trained

        # Predict fit score for this card given identity
        # Implementation depends on model architecture
        ...
```

## Implementation Phases

### Phase 0: Deterministic Baseline

**Goal:** Establish measurable baseline before adding AI complexity.

**Deliverables:**
- Archetype taxonomy (15 core archetypes)
- Pattern-based archetype tagger
- Deck Brief data model
- Modified card selection using identity weights
- Baseline coherence metrics

**Success criteria:**
- Generated decks have measurably higher card synergy than random selection
- Deterministic and reproducible builds

### Phase 1: Embeddings + Centroid

**Goal:** Add semantic similarity as scoring signal.

**Deliverables:**
- sentence-transformers integration
- Embedding generation for all commander-legal cards
- Numpy-based storage (simple, no vector DB)
- Centroid calculation and similarity scoring
- A/B comparison vs Phase 0

**Success criteria:**
- Embedding similarity improves deck coherence metrics
- <2s overhead for embedding lookups

### Phase 2: LLM Identity Enhancement

**Goal:** Optional LLM layer for refined identity extraction.

**Deliverables:**
- OpenAI API integration
- Structured output prompts for identity analysis
- Delta clamping (±0.2) for stability
- Toggle to disable for reproducibility
- Cost tracking and limits

**Success criteria:**
- LLM suggestions improve theme coherence
- No regressions when LLM disabled
- <$0.05 per deck generation

### Phase 3: Pairwise Feedback System

**Goal:** Learn user preferences over time.

**Deliverables:**
- Preference collection UI (CLI first, then web)
- Contextual logging (identity + deck state)
- Simple preference model (logistic regression)
- Model persistence and versioning

**Success criteria:**
- Model accuracy >60% on held-out preferences after 100 ratings
- Measurable improvement in user satisfaction

### Phase 4: Local Model Migration

**Goal:** Reduce costs and latency with local models.

**Deliverables:**
- Test Llama/Mistral for identity extraction
- Quality comparison vs OpenAI
- Configurable model selection
- Fallback chain (local → API → deterministic)

**Success criteria:**
- <10% quality degradation vs OpenAI
- <5s total generation time

## Database Schema Additions

```sql
-- Archetype reference table
CREATE TABLE archetype (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    keywords TEXT[]  -- Associated keywords for pattern matching
);

-- Card archetype associations (precomputed)
CREATE TABLE card_archetype (
    card_id INTEGER REFERENCES card(id),
    archetype_id INTEGER REFERENCES archetype(id),
    weight FLOAT NOT NULL CHECK (weight >= 0 AND weight <= 1),
    PRIMARY KEY (card_id, archetype_id)
);

-- Card embeddings
CREATE TABLE card_embedding (
    card_id INTEGER PRIMARY KEY REFERENCES card(id),
    embedding FLOAT[] NOT NULL,  -- Or use pgvector if available
    model_version VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Deck briefs
CREATE TABLE deck_brief (
    id SERIAL PRIMARY KEY,
    deck_id INTEGER REFERENCES deck(id),
    commander_id INTEGER REFERENCES card(id),
    seeds INTEGER[],  -- Array of card IDs
    objectives JSONB NOT NULL DEFAULT '{}',
    constraints JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Pairwise preferences for learning
CREATE TABLE pairwise_preference (
    id SERIAL PRIMARY KEY,
    deck_identity FLOAT[] NOT NULL,
    card_a_id INTEGER REFERENCES card(id),
    card_b_id INTEGER REFERENCES card(id),
    preference INTEGER NOT NULL CHECK (preference >= -2 AND preference <= 2),
    context JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_card_archetype_card ON card_archetype(card_id);
CREATE INDEX idx_card_archetype_archetype ON card_archetype(archetype_id);
CREATE INDEX idx_deck_brief_commander ON deck_brief(commander_id);
```

## API Additions

```python
# POST /api/decks/generate - Enhanced
@app.post("/api/decks/generate")
async def generate_deck(brief: DeckBriefRequest) -> DeckResponse:
    """
    Generate deck from a deck brief.

    Request body:
    {
        "commander": "Zurgo Helmsmasher",
        "seeds": ["Worldslayer", "Assault Suit"],
        "objectives": {"power": 0.7, "theme": 0.8, "budget": 0.3},
        "constraints": {"max_price_usd": 500}
    }
    """
    ...

# GET /api/decks/{id}/identity
@app.get("/api/decks/{deck_id}/identity")
async def get_deck_identity(deck_id: int) -> IdentityResponse:
    """
    Return current identity weights for a deck.

    Response:
    {
        "identity": {"voltron": 0.7, "equipment": 0.5, ...},
        "top_archetypes": ["voltron", "equipment", "aggro"],
        "suggested_directions": ["Add more protection", "Consider board wipes"]
    }
    """
    ...

# POST /api/feedback/preference
@app.post("/api/feedback/preference")
async def submit_preference(pref: PreferenceRequest) -> PreferenceResponse:
    """
    Submit a pairwise preference for learning.

    Request body:
    {
        "deck_id": 123,
        "card_a": "Sword of Feast and Famine",
        "card_b": "Phyrexian Arena",
        "preference": 1  # A slightly better
    }
    """
    ...

# GET /api/feedback/prompt
@app.get("/api/feedback/prompt")
async def get_feedback_prompt(deck_id: int) -> FeedbackPromptResponse:
    """
    Get a pair of cards to compare for feedback collection.
    Selects cards where model is most uncertain.
    """
    ...
```

## Configuration

```python
# config/agent.py

@dataclass
class AgentConfig:
    # Scoring weights
    embedding_weight: float = 0.25
    archetype_weight: float = 0.35
    keyword_weight: float = 0.20
    learned_weight: float = 0.20

    # Role minimums
    min_lands: int = 35
    min_ramp: int = 10
    min_draw: int = 8
    min_removal: int = 6
    min_wincon: int = 3

    # Role penalty curve
    role_penalty_per_excess: float = 0.1
    role_penalty_floor: float = 0.5

    # Identity settings
    identity_learning_rate: float = 0.1
    llm_delta_clamp: float = 0.2
    llm_enabled: bool = True
    llm_provider: str = "openai"  # or "anthropic", "local"

    # Embedding settings
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    # Feedback settings
    min_preferences_for_training: int = 50
    feedback_model_type: str = "logistic"  # or "neural"
```

## Metrics & Observability

### Deck Coherence Metrics

```python
def compute_coherence_metrics(deck):
    return {
        "identity_concentration": gini_coefficient(deck.identity.values()),
        "keyword_overlap_avg": avg_pairwise_keyword_overlap(deck.cards),
        "embedding_cluster_tightness": avg_cosine_to_centroid(deck.cards),
        "archetype_purity": max(deck.identity.values()),
        "role_coverage": all_minimums_met(deck),
    }
```

### Generation Telemetry

```python
@dataclass
class GenerationTelemetry:
    deck_id: int
    generation_time_ms: int
    llm_calls: int
    llm_cost_usd: float
    cards_scored: int
    identity_changes: int
    final_identity: dict
    coherence_metrics: dict
```

## Open Questions

1. **Power rating source:** How do we assign power ratings to cards? EDHREC popularity? Manual curation? Learned from feedback?

2. **Theme scoring:** What is the definition of "theme" for this system, and how should it be measured without premature defaults?

3. **Novelty scoring:** What defines "novel"? Low play rate on EDHREC (if we use it)? Recency? Manual tags?

4. **Multi-commander support:** How do we handle partners, backgrounds, friends forever? Merge identities? Average?

5. **Identity conflicts:** What if seeds have conflicting archetypes? Weight by recency? Average? User chooses?

6. **Feedback cold start:** How do we bootstrap the learned model before we have preferences? Transfer learning from similar commanders?

## References

- [Discovery Brief](./discovery.md) - Original product requirements
- [Deckbuilding Heuristics](./deckbuilding-heuristics.md) - Current heuristic rules
- [Scryfall Ingestion](./patterns/data-scryfall-ingestion.md) - Data pipeline
