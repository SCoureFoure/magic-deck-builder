# Agent Contracts

## Roles
Agent roles map to deckbuilding responsibilities:
- lands: Mana-producing or mana-fixing lands.
- ramp: Acceleration pieces that increase mana production or land count.
- draw: Repeatable or burst card draw and card advantage.
- removal: Targeted or mass removal, interaction, or disruption.
- wincons: Primary finishers or explicit win conditions.
- synergy: Theme enablers and commander-specific synergies.
- flex: Utility slots that cover gaps not captured by other roles.

## Shared Input Schema (AgentTask)
All agent prompts should conform to this input schema:
- role (str, required): one of the roles above.
- count (int, required): number of items to return, > 0.
- commander_name (str, required)
- commander_text (str, optional)
- deck_cards (list[str], optional): names only, cleaned of blanks.

Source: `src/engine/brief.py`

## Shared Output Schema
Agents return a ranked list of card names:
- JSON array of strings, best to worst.
- Items must be valid candidate names or empty list.

## LLM Search Query Schema
LLM search tools must emit a JSON array of SearchQuery objects:
- oracle_contains (list[str])
- type_contains (list[str])
- cmc_min (number or null)
- cmc_max (number or null)
- colors (list[str])

Validation: `src/engine/brief.py` (SearchQuery)

## Failure Modes
- Invalid input schema: agent returns empty list and logs validation errors.
- Empty candidate pool: agent returns empty list.
- Invalid LLM output (non-JSON or bad schema): ignored entries are dropped.

## Prompt Template Requirements
- Always include: role needed, role definition, commander name, commander text, deck list.
- Always require: JSON-only output with no commentary.
- Council agents must include preferences payload.

## Examples
- `src/engine/llm_agent.py`: search + ranking prompt templates
- `src/engine/council/agents.py`: council LLM prompt template
