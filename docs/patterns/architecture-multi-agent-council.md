# Architecture: Multi-Agent Council

## Context
Use when you want multiple agents with explicit preferences to collaboratively rank deck card candidates and produce a consensus pick.

## Implementation
- Use a LangGraph StateGraph with one node per agent and an aggregation node.
- Agents can be heuristic or LLM-based; both output ranked card name lists.
- Aggregation uses a configurable voting strategy (Borda or majority) with agent weights.
- Configuration is surfaced via a YAML file and can be overridden per request.

## Trade-offs
- Optimizes for explainable, tweakable behavior and experimentation.
- Higher runtime cost with multiple LLM calls.
- Candidate pool quality still bounds the council’s output.

## Examples
- src/engine/council/graph.py:1
- src/engine/council/agents.py:1
- src/web/app.py:52
- council.yaml:1

## Updated
2026-01-25: Introduced council config + LangGraph orchestration with voting.
