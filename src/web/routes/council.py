"""Council agent routes."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import logging
from fastapi import APIRouter, HTTPException

from src.config import settings
from src.database.engine import get_db
from src.database.models import Card, CouncilAgentOpinion, TrainingSession
from src.engine.council.config import _parse_agent as parse_agent_config
from src.engine.council.config import load_council_config
from src.engine.council.training import council_training_opinions, council_training_synthesis
from src.engine.observability import generate_trace_id
from src.web.schemas import (
    CouncilAgentExportResponse,
    CouncilAgentImportRequest,
    CouncilAgentPayload,
    CouncilAnalysisRequest,
    CouncilAnalysisResponse,
    CouncilConsultRequest,
    CouncilConsultResponse,
    CouncilOpinion,
)
from src.web.serializers import serialize_agent_payload

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/council/agents", response_model=list[CouncilAgentPayload])
def council_agents() -> list[CouncilAgentPayload]:
    """Return the resolved council agents from the config."""
    config = load_council_config()
    return [serialize_agent_payload(agent) for agent in config.agents]


@router.post("/api/council/agent/import", response_model=CouncilAgentPayload)
def council_agent_import(request: CouncilAgentImportRequest) -> CouncilAgentPayload:
    """Parse a single council agent YAML document into agent config."""
    import yaml

    try:
        payload = yaml.safe_load(request.yaml) or {}
    except yaml.YAMLError as exc:
        raise HTTPException(status_code=400, detail="Invalid YAML.") from exc

    agent_data: Optional[dict[str, Any]] = None
    if isinstance(payload, dict) and isinstance(payload.get("agents"), list):
        agents = payload.get("agents") or []
        if len(agents) != 1:
            raise HTTPException(
                status_code=400,
                detail="Expected a single agent in YAML.",
            )
        if isinstance(agents[0], dict):
            agent_data = agents[0]
    elif isinstance(payload, dict) and isinstance(payload.get("agent"), dict):
        agent_data = payload["agent"]
    elif isinstance(payload, dict) and (
        "id" in payload or "agent_id" in payload or "type" in payload
    ):
        agent_data = payload

    if not agent_data:
        raise HTTPException(status_code=400, detail="No agent definition found.")

    agent = parse_agent_config(agent_data)
    return serialize_agent_payload(agent)


@router.post("/api/council/agent/export", response_model=CouncilAgentExportResponse)
def council_agent_export(request: CouncilAgentPayload) -> CouncilAgentExportResponse:
    """Export a single council agent to YAML."""
    import yaml

    payload: dict[str, Any] = {
        "id": request.id,
        "display_name": request.display_name,
        "type": request.type,
        "weight": request.weight,
        "model": request.model,
        "temperature": request.temperature,
        "system_prompt": request.system_prompt,
        "user_prompt_template": request.user_prompt_template,
        "preferences": request.preferences.dict(),
    }
    if request.context is not None:
        payload["context"] = request.context.dict()

    agent = parse_agent_config(payload)
    agent_payload = serialize_agent_payload(agent)
    yaml_text = yaml.safe_dump(agent_payload, sort_keys=False)
    return CouncilAgentExportResponse(yaml=yaml_text)


@router.post("/api/training/council/consult", response_model=CouncilConsultResponse)
def training_council_consult(request: CouncilConsultRequest) -> CouncilConsultResponse:
    """Consult the council agents on a training card."""
    with get_db() as db:
        training_session = (
            db.query(TrainingSession).filter(TrainingSession.id == request.session_id).first()
        )
        if not training_session:
            raise HTTPException(status_code=404, detail="Training session not found")

        card = db.query(Card).filter(Card.id == request.card_id).first()
        if not card:
            raise HTTPException(status_code=404, detail="Card not found")

        if not request.api_key and not settings.openai_api_key:
            raise HTTPException(
                status_code=400,
                detail="Consult requires OPENAI_API_KEY for synthesis.",
            )

        trace_id = request.trace_id or generate_trace_id()

        agent_payloads = []
        for agent in request.agents:
            agent_payloads.append(
                {
                    "id": agent.id,
                    "display_name": agent.display_name,
                    "type": agent.type,
                    "weight": agent.weight,
                    "model": agent.model,
                    "temperature": agent.temperature,
                    "system_prompt": agent.system_prompt,
                    "user_prompt_template": agent.user_prompt_template,
                    "preferences": agent.preferences.dict(),
                    "context": agent.context.dict() if agent.context else None,
                }
            )

        opinions: list[dict[str, object]] = []
        if request.cached_opinions:
            opinions.extend([opinion.dict() for opinion in request.cached_opinions])

        if agent_payloads:
            overrides = {"agents": agent_payloads}
            opinions.extend(
                council_training_opinions(
                    training_session.commander,
                    card,
                    overrides=overrides,
                    api_key_override=request.api_key,
                    trace_id=trace_id,
                )
            )

        synth_payload = {
            "id": request.synthesizer.id,
            "display_name": request.synthesizer.display_name,
            "type": request.synthesizer.type,
            "weight": request.synthesizer.weight,
            "model": request.synthesizer.model,
            "temperature": request.synthesizer.temperature,
            "system_prompt": request.synthesizer.system_prompt,
            "user_prompt_template": request.synthesizer.user_prompt_template,
            "preferences": request.synthesizer.preferences.dict(),
            "context": request.synthesizer.context.dict() if request.synthesizer.context else None,
        }
        synth_agent = parse_agent_config(synth_payload)
        verdict = council_training_synthesis(
            training_session.commander,
            card,
            opinions,
            synth_agent,
            api_key_override=request.api_key,
            trace_id=trace_id,
        )

        return CouncilConsultResponse(
            session_id=request.session_id,
            commander_name=training_session.commander.card.name,
            card_name=card.name,
            opinions=[CouncilOpinion(**opinion) for opinion in opinions],
            verdict=verdict,
            trace_id=trace_id,
        )


@router.post("/api/training/council/analyze", response_model=CouncilAnalysisResponse)
def training_council_analyze(request: CouncilAnalysisRequest) -> CouncilAnalysisResponse:
    """Analyze a training card using the council agents."""
    with get_db() as db:
        training_session = (
            db.query(TrainingSession).filter(TrainingSession.id == request.session_id).first()
        )
        if not training_session:
            raise HTTPException(status_code=404, detail="Training session not found")

        card = db.query(Card).filter(Card.id == request.card_id).first()
        if not card:
            raise HTTPException(status_code=404, detail="Card not found")

        overrides: dict[str, Any] = dict(request.council_overrides or {})
        routing_overrides: dict[str, Any] = {}
        if request.routing_strategy:
            routing_overrides["strategy"] = request.routing_strategy
        if request.routing_agent_ids:
            routing_overrides["agent_ids"] = request.routing_agent_ids
        if request.debate_adjudicator_id:
            routing_overrides["debate_adjudicator_id"] = request.debate_adjudicator_id
        if routing_overrides:
            overrides["routing"] = routing_overrides

        config = load_council_config(
            config_path=None
            if request.council_config_path is None
            else Path(request.council_config_path),
            overrides=overrides or None,
        )
        if (
            any(agent.agent_type == "llm" for agent in config.agents)
            and not (request.api_key or settings.openai_api_key)
        ):
            raise HTTPException(
                status_code=400,
                detail="Council analysis requires OPENAI_API_KEY to run LLM agents.",
            )

        trace_id = request.trace_id or generate_trace_id()

        opinions = council_training_opinions(
            training_session.commander,
            card,
            config_path=request.council_config_path,
            overrides=overrides or None,
            api_key_override=request.api_key,
            trace_id=trace_id,
        )

        opinion_rows = []
        for opinion in opinions:
            opinion_rows.append(
                CouncilAgentOpinion(
                    training_session_id=training_session.id,
                    commander_id=training_session.commander.id,
                    card_id=card.id,
                    role="training",
                    agent_id=opinion.get("agent_id", ""),
                    agent_type=opinion.get("agent_type", ""),
                    weight=float(opinion.get("weight", 1.0)),
                    score=float(opinion["score"]) if opinion.get("score") is not None else None,
                    metrics={"summary": opinion.get("metrics")},
                    rationale=opinion.get("reason"),
                    trace_id=trace_id,
                )
            )
        if opinion_rows:
            try:
                db.add_all(opinion_rows)
                db.flush()
            except Exception:
                db.rollback()
                logger.warning(
                    "Failed to persist council agent opinions",
                    exc_info=True,
                )

        return CouncilAnalysisResponse(
            session_id=request.session_id,
            commander_name=training_session.commander.card.name,
            card_name=card.name,
            opinions=[CouncilOpinion(**opinion) for opinion in opinions],
            trace_id=trace_id,
        )
