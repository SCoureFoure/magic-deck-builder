"""Pydantic schemas for the web API."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class CommanderResult(BaseModel):
    """API response for a commander search result."""

    name: str
    type_line: str
    color_identity: list[str]
    mana_cost: Optional[str]
    cmc: float
    eligibility: Optional[str]
    commander_legal: str
    image_url: Optional[str]
    card_faces: Optional[list[dict[str, Any]]]


class CommanderSearchResponse(BaseModel):
    """API response for commander search."""

    query: str
    count: int
    results: list[CommanderResult]


class DeckGenerationRequest(BaseModel):
    """Request body for deck generation."""

    commander_name: str
    use_llm_agent: bool = False
    use_council: bool = False
    council_config_path: Optional[str] = None
    council_overrides: Optional[dict[str, Any]] = None
    routing_strategy: Optional[str] = None
    routing_agent_ids: Optional[list[str]] = None
    debate_adjudicator_id: Optional[str] = None
    trace_id: Optional[str] = None


class TrainingCard(BaseModel):
    """Card data for training prompts."""

    id: int
    name: str
    type_line: str
    color_identity: list[str]
    mana_cost: Optional[str]
    cmc: float
    oracle_text: Optional[str]
    image_url: Optional[str]
    card_faces: Optional[list[dict[str, Any]]]


class TrainingSessionResponse(BaseModel):
    """Training session payload."""

    session_id: int
    commander: TrainingCard


class TrainingCardResponse(BaseModel):
    """Training card payload."""

    session_id: int
    card: TrainingCard


class TrainingVoteRequest(BaseModel):
    """Synergy vote submission."""

    session_id: int
    card_id: int
    vote: int  # 1 = synergy, 0 = no synergy


class TrainingCardStat(BaseModel):
    """Card-level synergy stats."""

    card_name: str
    yes: int
    no: int
    ratio: float


class TrainingCommanderSummary(BaseModel):
    """Commander-level synergy stats."""

    commander_name: str
    yes: int
    no: int
    ratio: float
    cards: list[TrainingCardStat]


class TrainingStatsResponse(BaseModel):
    """Aggregate training stats."""

    total_votes: int
    commanders: list[TrainingCommanderSummary]


class CouncilOpinion(BaseModel):
    """Council opinion payload for training analysis."""

    agent_id: str
    display_name: str
    agent_type: str
    weight: float
    score: float
    metrics: str
    reason: str


class CouncilAnalysisRequest(BaseModel):
    """Council analysis request for a training card."""

    session_id: int
    card_id: int
    council_config_path: Optional[str] = None
    council_overrides: Optional[dict[str, Any]] = None
    api_key: Optional[str] = None
    routing_strategy: Optional[str] = None
    routing_agent_ids: Optional[list[str]] = None
    debate_adjudicator_id: Optional[str] = None
    trace_id: Optional[str] = None


class CouncilAnalysisResponse(BaseModel):
    """Council analysis response for a training card."""

    session_id: int
    commander_name: str
    card_name: str
    opinions: list[CouncilOpinion]
    trace_id: Optional[str]


class CouncilAgentPreferences(BaseModel):
    """Agent preference weights for council config."""

    theme_weight: float = 0.5
    efficiency_weight: float = 0.25
    budget_weight: float = 0.25
    price_cap_usd: Optional[float] = None


class CouncilAgentContextBudget(BaseModel):
    """Context budget settings for council agents."""

    max_deck_cards: int = 40
    max_candidates: int = 60
    max_commander_text_chars: int = 1200
    max_candidate_oracle_chars: int = 600


class CouncilAgentContextFilters(BaseModel):
    """Context filter settings for council agents."""

    include_commander_text: bool = True
    include_deck_cards: bool = True
    include_candidate_oracle: bool = True
    include_candidate_type_line: bool = True
    include_candidate_cmc: bool = True
    include_candidate_price: bool = True


class CouncilAgentContext(BaseModel):
    """Context configuration for a council agent."""

    budget: CouncilAgentContextBudget = CouncilAgentContextBudget()
    filters: CouncilAgentContextFilters = CouncilAgentContextFilters()


class CouncilAgentPayload(BaseModel):
    """Single council agent payload."""

    id: str
    display_name: Optional[str] = None
    type: str
    weight: float = 1.0
    model: Optional[str] = None
    temperature: float = 0.3
    system_prompt: Optional[str] = None
    user_prompt_template: Optional[str] = None
    preferences: CouncilAgentPreferences = CouncilAgentPreferences()
    context: Optional[CouncilAgentContext] = None


class CouncilConsultRequest(BaseModel):
    """Council consult request."""

    session_id: int
    card_id: int
    agents: list[CouncilAgentPayload]
    synthesizer: CouncilAgentPayload
    cached_opinions: Optional[list[CouncilOpinion]] = None
    api_key: Optional[str] = None
    trace_id: Optional[str] = None


class CouncilConsultResponse(BaseModel):
    """Council consult response."""

    session_id: int
    commander_name: str
    card_name: str
    opinions: list[CouncilOpinion]
    verdict: str
    trace_id: Optional[str]


class CouncilAgentImportRequest(BaseModel):
    """YAML import request for a single council agent."""

    yaml: str


class CouncilAgentExportResponse(BaseModel):
    """YAML export response for a single council agent."""

    yaml: str


class SynergyCardResult(BaseModel):
    """Commander synergy lookup result."""

    card_name: str
    type_line: str
    mana_cost: Optional[str]
    cmc: float
    image_url: Optional[str]
    card_faces: Optional[list[dict[str, Any]]]
    yes: int
    no: int
    ratio: float
    total_votes: int
    legal_for_commander: bool


class DeckCardResult(BaseModel):
    """A card in the generated deck."""

    name: str
    quantity: int
    role: str
    type_line: str
    mana_cost: Optional[str]
    cmc: float
    image_url: Optional[str]
    identity_score: float
    commander_score: float
    deck_score: float


class SourceAttributionResult(BaseModel):
    """Source attribution payload for selections."""

    source_type: str
    details: dict[str, Any]
    card_ids: list[int]
    card_names: list[str]


class DeckGenerationResponse(BaseModel):
    """API response for deck generation."""

    commander_name: str
    total_cards: int
    is_valid: bool
    validation_errors: list[str]
    cards_by_role: dict[str, list[DeckCardResult]]
    metrics: dict[str, Any]
    sources_by_role: dict[str, list[SourceAttributionResult]]
    trace_id: Optional[str]
