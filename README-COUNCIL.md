# Council (Multi-Agent) Overview

This project now supports a **LangGraph-based council** for Commander deckbuilding. The council runs multiple agents in parallel, then aggregates their ranked card lists into a consensus pick.

## What was added

- **LangGraph Council Orchestrator**
  - Runs a configurable set of agents (heuristic + LLM) and aggregates votes.
  - Entry point: `src/engine/council/graph.py`

- **Agents**
  - **Heuristic agent**: programmatic scoring using theme/efficiency/budget weights.
  - **LLM agents**: prompt-driven ranking of candidate cards.
  - Agent logic lives in: `src/engine/council/agents.py`

- **Voting**
  - **Borda count** (default) or **majority vote**.
  - Voting logic: `src/engine/council/voting.py`

- **Configurable surface**
  - YAML config at repo root: `council.yaml`
  - Runtime overrides via API/CLI
  - Config loader: `src/engine/council/config.py`

- **Integration points**
  - `src/engine/deck_builder.py` uses the council when `use_council=true`.
  - API: `/api/decks/generate` accepts `use_council`, `council_config_path`, `council_overrides`.
  - CLI: `python -m src.cli generate deck "Atraxa" --council --council-config council.yaml`.

## Adjustable knobs

### council.yaml
- `agents`: add/remove council members, swap agent types, change preferences
- `voting.strategy`: `borda` or `majority`
- `voting.top_k`: max items considered per agent
- LLM agent settings: `model`, `temperature`
- Heuristic preferences: `theme_weight`, `efficiency_weight`, `budget_weight`, optional `price_cap_usd`

Example:
```yaml
version: 1
voting:
  strategy: borda
  top_k: 25
agents:
  - id: heuristic-core
    type: heuristic
    weight: 1.0
    preferences:
      theme_weight: 0.6
      efficiency_weight: 0.2
      budget_weight: 0.2
  - id: llm-theme-focused
    type: llm
    weight: 1.0
    model: gpt-4o-mini
    temperature: 0.4
    preferences:
      theme_weight: 0.75
      efficiency_weight: 0.15
      budget_weight: 0.10
  - id: llm-price-sensitive
    type: llm
    weight: 1.0
    model: gpt-4o-mini
    temperature: 0.3
    preferences:
      theme_weight: 0.35
      efficiency_weight: 0.15
      budget_weight: 0.50
```

### API overrides
You can override any `council.yaml` value at request time:
```json
{
  "commander_name": "Atraxa, Praetors' Voice",
  "use_council": true,
  "council_overrides": {
    "voting": {"strategy": "majority"},
    "agents": [
      {"id": "llm-theme", "temperature": 0.7}
    ]
  }
}
```

## Environment
- LLM agents require `OPENAI_API_KEY`.
- Default model set by `OPENAI_MODEL` or `settings.openai_model`.

## Related docs
- Pattern doc: `docs/patterns/architecture-multi-agent-council.md`
