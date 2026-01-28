# Architecture: Multi-Agent Council

## Context
Use when you want multiple agents with explicit preferences to collaboratively rank deck card candidates and produce a consensus pick.

## Implementation
- Use a LangGraph StateGraph with one node per agent and an aggregation node.
- Agents can be heuristic or LLM-based; both output ranked card name lists.
- Aggregation uses a configurable voting strategy (Borda or majority) with agent weights.
- Configuration is surfaced via a YAML file and can be overridden per request (API/CLI routing overrides).
- Per-agent context budgets/filters trim deck/candidate context to control cost.
- Source attribution and trace IDs are logged for debugging and surfaced in API responses.

## Trade-offs
- Optimizes for explainable, tweakable behavior and experimentation.
- Higher runtime cost with multiple LLM calls.
- Candidate pool quality still bounds the council’s output.
- Storing agent opinions adds DB writes; failures are non-blocking.

## Examples
- src/engine/council/graph.py:1
- src/engine/council/agents.py:1
- src/web/app.py:52
- council.yaml:1
- src/engine/context.py:1
- src/engine/observability.py:1
- src/engine/llm_agent.py:1

## Updated
2026-01-25: Introduced council config + LangGraph orchestration with voting.
2026-01-28: Added context budgets, attribution, trace IDs, and API/CLI routing overrides.
