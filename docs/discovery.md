# Commander Deckbuilder Discovery Brief

## 1) Product statement (concise, testable)
- Target users: casual EDH brewers, semi-competitive players, and content creators who need rapid deck iteration.
- Primary outcome: "I input a commander and constraints and get a legal 100-card deck with a clear plan and editable categories within minutes."
- Success metrics: time to first legal deck, number of user edits to accept, export rate, satisfaction rating, and edit distance from baseline.
- Non-goals (MVP): full gameplay simulation, matchup modeling, RL optimization, or "optimal play" claims.

## 2) Hard constraints (format + legality)
- Rules: 100 cards including commander, singleton except basics, must match commander color identity, and banned list enforced.
- Validation scope:
  - Commander legality: legendary creature or explicit "can be your commander" text.
  - Banned list: must check against current EDH ban list; prefer a single authoritative source and cache daily.
  - Color identity: derived from mana symbols and color indicators; exclude off-identity cards.
  - Companion: if used, enforce companion deck-building rule and count in 100.
- Assumptions needing confirmation:
  - Ban list source and cadence: use official EDH Rules Committee list unless Scryfall legalities are deemed sufficient.
  - Companion enforcement: companion is part of 100; no sideboard in EDH.
  - Split/adventure/MDFC: use Scryfall `color_identity` and `oracle_text` for mana symbols in text.

## 3) Data feasibility matrix (sources + risks + mitigations)

| Source | Data Provided | Access Method | Rate Limits | Terms/Constraints | Freshness | Cost | Risks | Mitigations |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Scryfall | Oracle text, types, colors, legalities, prices, images, rulings | API + bulk data | ~10 req/s with 50-100ms delay | Must send `User-Agent` + `Accept`. No paywalling. No repackaging. Strict image handling. art_crop requires artist/copyright attribution or full image elsewhere. | Daily bulk; prices daily | Free | ToS violations, over-requesting | Bulk ingestion + cache >= 24h, strict rate limiter, compliant image use and attribution |
| EDHREC | Aggregated deck stats, popularity, themes | No verified public API | Unknown | Scraping risk; ToS must be verified | Daily-ish | Free | Legal/ToS risk | Avoid for MVP unless official API access confirmed |
| Archidekt | Decklists, categories, tags | API availability unverified | Community mentions ~80 req/60s (non-authoritative) | ToS/API must be confirmed | Near real-time | Free | ToS/API uncertainty | Prefer user-imported data or confirm official API |

Recommended MVP data sources: Scryfall only + user-imported decklists. Defer EDHREC/Archidekt until official API and ToS compliance are verified.

## 4) User workflows -> requirements

### Inputs
- Commander name (required)
- Budget cap
- Power target
- Themes/subthemes
- Exclusions
- Owned collection
- Meta considerations
- Import/export: text and CSV. API imports only if ToS verified.

### Outputs
- Categorized 100-card list (ramp/removal/draw/lands/wincons)
- Short plan: opening/early/mid/win lines
- Swaps/upgrades
- Explainability: "why this card" and top synergies

### Editing loop
- User actions: lock cards, thumbs up/down, adjust role counts/budget
- System response: re-balance counts, replace with legal alternatives, preserve locked cards, maintain curve + color identity

## 5) MVP definition (build something real)

### MVP capabilities
- Commander ingestion (Scryfall lookup, color identity, mechanics extraction)
- Commander eligibility: legendary creatures plus cards with "can be your commander."
- Candidate pool generation (heuristics + oracle text matching)
- Deck assembly to 100 cards with a stable template
- Legality checks + automatic fixes
- Basic explanations + export
- Minimum UI: CLI that generates a decklist and exports text/CSV.
- Initial archetype support: 3 themes (tribal, spellslinger, sacrifice) plus generic goodstuff fallback.

### Out of scope (initially)
- Full gameplay simulation
- Matchup modeling
- RL training
- "Optimal play" claims

## 6) Recommendation engine approach (layered)

### Stage A — Rules/Heuristics (MVP facts)
- Theme detection from oracle text + commander tags
- Curve targets, staple packages, land counts
- Must include / nice to have per archetype

### Stage B — Retrieval + Embeddings (R&D speculation)
- Vectorize oracle text + EDH roles
- Blend similarity with role coverage and curve balancing

### Stage C — Graph + Co-occurrence (R&D speculation)
- Build synergy graph from decklist co-occurrence (where permitted)

### Stage D — Optimization (R&D speculation)
- Constrained optimization: maximize synergy + role coverage - anti-synergy
- Constraints: legality, budget, curve, color pips, archetype proportions

### Stage E — "AlphaGo-like" aspiration (R&D speculation)
- Requires training data + simulation
- Focus on goldfish speed and consistency before full EDH gameplay

## 7) Architecture and services (engineerable)

Text diagram:
- UI: commander picker, sliders, deck editor, export
- API gateway: auth, validation, rate limits
- Ingestion service: Scryfall client, caching, bulk refresh scheduler
- Card store: Postgres (structured), vector DB (embeddings)
- Deck engine: constraint solver + scoring
- Explainability service: reasons, archetype tags, substitutions
- Observability: telemetry on edits, replacements, drift metrics

### Technical stack (initial proposal)
- Language: Python 3.12 for ingestion/deck engine and CLI; optional FastAPI for service mode.
- UI: Start with CLI; web UI later via Next.js or Vite + React.
- Database: Postgres 15+ for structured card data.
- Vector DB: pgvector extension (avoid extra service in MVP).
- Deployment target: local dev and single-container Docker; hosted deployment deferred.

## 8) Deliverables

### Requirements brief
- Functional: commander search, constraints input, deck generation, legality validation, edits, export
- Non-functional: Scryfall ToS compliance, caching, deterministic reproducibility, latency < 10s for first build, edit regen < 2s for small changes

### MVP feature list + deferred
- MVP: Scryfall-only data, heuristics, legal 100 cards, export, basic reasons
- Deferred: embeddings, co-occurrence graphs, matchup tuning, external API imports

### System architecture diagram + responsibilities
- See section 7

### Algorithm plan with scoring features
- Score = (synergy score * 0.35) + (role coverage * 0.30) - (curve deviation * 0.15) - (color pip stress * 0.10) - (budget overage * 0.10)
- Normalize each component to 0-1 before weighting to keep penalties comparable.
- Synergy: shared tribe, shared keywords, commander interactions
- Role coverage: minimum counts per category
- Curve: target mana curve shape and land count
- Legality: hard constraints

### Open questions ranked by risk
- Highest: official APIs and ToS for EDHREC/Archidekt/Moxfield
- High: ban list source (EDH RC list vs. Scryfall legalities) and update cadence
- High: companion enforcement details (EDH has no sideboard)
- Medium: mapping power level slider to card choices
- Medium: handling budget vs collection ownership
- Medium: split/adventure/MDFC color identity handling (confirm Scryfall fields are sufficient)
- Low: export formats priority

### Backlog (two 2-week sprints)
Sprint 1
- Ingest Scryfall bulk to local store
- Commander search + color identity extraction
- Heuristic tagger (tribal/keywords)
- Deck engine v0 (template fill + legality checks)
- Export: text/CSV

Sprint 2
- Editor UI: CLI editing loop (lock/exclude/adjust counts); web UI deferred
- Explainability: reasons per card
- Caching + rate limiter
- Telemetry: edit distance, acceptance
- Thin vertical slice demo (commander -> deck -> export)

### Test plan
- Frameworks: pytest for unit/integration; Hypothesis for property-based tests
- Coverage target: 80% for core engine modules
- Legality tests: 100 cards, singleton, color identity, banned list, companion rules
- Property-based tests: generated decks always legal
- Metrics: curve sanity, role coverage, budget adherence
- User edit distance: edits to acceptance

## 9) Data model (MVP)
- Card: scryfall_id, name, type_line, oracle_text, colors, color_identity, mana_cost, cmc, legalities, prices, image_uris.
- Commander: card_id, eligibility_reason, color_identity.
- Deck: id, commander_id, created_at, constraints (budget, themes, exclusions).
- DeckCard: deck_id, card_id, role_id, quantity, locked (bool).
- Role: id, name (ramp, removal, draw, lands, wincons, flex), description.
- Archetype: id, name (tribal, spellslinger, sacrifice, goodstuff), description.
- DeckArchetype: deck_id, archetype_id, weight (0-1).
- Indexes: Card.name, Card.color_identity, Card.cmc, DeckCard.deck_id, DeckCard.card_id, Role.name, Archetype.name.

## 10) Error handling and fallbacks
- If no legal deck can be built: return partial list with blocking constraints and suggested relaxations (e.g., increase budget, reduce exclusions).
- If constraints conflict: prioritize legality, then locked cards, then role coverage.
- If Scryfall API fails: fall back to cached data and warn user about staleness.

## 11) Performance and security targets
- Performance:
  - First build < 10s
  - Edit regeneration < 2s for small changes
  - Bulk ingest target < 10 minutes on a dev machine
  - Deck query latency < 200ms for common lookups
- Security:
  - Input validation on commander name, constraints, and exports
  - Rate limiting per IP and per user if auth is introduced
  - Auth: optional for MVP; use token-based auth for hosted mode

## 12) Scryfall compliance notes
- Required headers on every request: `User-Agent` (app/version) and `Accept`.
- Rate limiting: 50-100ms delay per request (~10 req/s average).
- Cache data for at least 24 hours; prefer daily bulk files for ingestion.
- No paywalling access to Scryfall data.
- Do not repackage or proxy data; must add user value.
- Image rules: no cropping/covering artist/copyright, no distortion or color shifts, no watermarks.
- art_crop usage requires artist/copyright attribution or a full card image elsewhere in the same UI.
