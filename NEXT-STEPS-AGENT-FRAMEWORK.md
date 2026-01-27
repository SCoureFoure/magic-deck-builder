# Next Steps for Agent Framework

This TODO list focuses on splitting responsibilities into clean agents, enabling multiple routing mechanics, and improving evaluation/observability so we can iterate quickly.

## 1) Agent boundaries + contracts (core)
- [x] Define agent roles and IO contracts (task, inputs, outputs, failure modes). (docs + config)
  - Where: `docs/` (new doc), `council.yaml`, `src/engine/council/config.py`
- [x] Add a shared message schema with validation (pydantic dataclasses). (enforces clean prompts)
  - Where: `src/engine/brief.py`, `src/engine/validator.py`, `src/engine/llm_agent.py`
- [x] Standardize prompt templates per agent role (single responsibility). (avoid prompt sprawl)
  - Where: `src/engine/council/agents.py`, `src/engine/llm_agent.py`

## 2) Routing mechanics (how agents run)
- [x] Add a routing layer that selects agent subsets per task. (cleanly divides load)
  - Where: `src/engine/council/graph.py`, `src/engine/council/agents.py`
- [x] Implement multiple mechanics as pluggable strategies:
  - [x] Sequential chain (planner -> retriever -> critic -> executor)
  - [x] Parallel council (current)
  - [x] Debate/consensus (two or more agents, with adjudicator)
  - Where: `src/engine/council/graph.py`, `src/engine/council/config.py`
- [x] Add failover rules (if an agent fails or times out). (robustness)
  - Where: `src/engine/council/graph.py`, `src/engine/llm_agent.py`

## 3) Context + retrieval hygiene
- [ ] Centralize context assembly (so each agent gets only what it needs).
  - Where: `src/engine/brief.py`, `src/engine/selector.py`, `src/engine/text_vectorizer.py`
- [ ] Add per-agent context filters and token budgets. (reduce cost/latency)
  - Where: `src/engine/council/config.py`, `src/engine/llm_agent.py`
- [ ] Add structured “source attribution” in agent outputs. (debuggability)
  - Where: `src/engine/council/agents.py`, `src/engine/metrics.py`

## 4) Evaluation + feedback loops
- [ ] Create an evaluation harness for agent comparisons (A/B mechanics). (repeatable experiments)
  - Where: `tests/integration/`, `src/engine/metrics.py`
- [ ] Store agent-level scores + rationale in the DB/logs. (traceability)
  - Where: `src/engine/metrics.py`, `src/database/models.py`
- [ ] Add a “golden set” of tasks for regression testing. (stability)
  - Where: `data/test/`, `tests/integration/`

## 5) Observability + cost controls
- [ ] Add per-agent latency/cost metrics. (budget awareness)
  - Where: `src/engine/metrics.py`, `src/engine/llm_agent.py`
- [ ] Add rate limit/backoff strategy per agent. (stability)
  - Where: `src/engine/llm_agent.py`
- [ ] Add per-request tracing IDs through the council flow. (debuggability)
  - Where: `src/engine/council/graph.py`, `src/engine/metrics.py`

## 6) API/CLI surface
- [ ] Expose routing strategy + agent list in API/CLI parameters. (experiment faster)
  - Where: `src/web/app.py`, `src/cli/commands.py`, `src/engine/council/config.py`
- [ ] Add lightweight API response metadata (strategy used, agent summaries). (visibility)
  - Where: `src/web/app.py`, `src/engine/council/graph.py`

## 7) Tests
- [ ] Unit tests for routing strategy selection. (correctness)
  - Where: `tests/unit/test_council_voting.py` or new `tests/unit/test_council_routing.py`
- [ ] Integration test for multi-agent run with overrides. (regression)
  - Where: `tests/integration/`

## 8) Documentation
- [ ] Update council pattern doc with routing mechanics options. (pattern consistency)
  - Where: `docs/patterns/architecture-multi-agent-council.md`
- [ ] Add “agent contracts” doc (roles, IO schema, example prompts). (onboarding)
  - Where: `docs/agent-contracts.md` (new)

---

### Suggested ordering
1. Agent IO schema + validation
2. Routing layer + mechanics
3. Context hygiene + token budgets
4. Observability + cost
5. Evaluation harness + golden set
6. API/CLI exposure
7. Docs + tests
