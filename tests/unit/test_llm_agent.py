import logging

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import settings
from src.database.models import Base, Card, Commander, LLMRun
from src.engine.brief import AgentTask
from src.engine.llm_agent import (
    _call_openai,
    _search_cards,
    build_ranking_prompt,
    build_search_prompt,
    logger,
    parse_card_names,
    parse_search_queries,
    suggest_cards_for_role,
)


def test_parse_card_names_accepts_json_array() -> None:
    response = '["Card A", "Card B"]'
    assert parse_card_names(response) == ["Card A", "Card B"]


def test_parse_card_names_ignores_non_json() -> None:
    response = "Here are some cards: Card A, Card B"
    assert parse_card_names(response) == []


def test_parse_card_names_trims_wrapped_text() -> None:
    response = "Result:\n[\"Card A\", \"Card B\"]\nThanks!"
    assert parse_card_names(response) == ["Card A", "Card B"]


def test_parse_card_names_handles_leading_and_trailing_noise() -> None:
    response = 'x["Card A"]y'
    assert parse_card_names(response) == ["Card A"]


def test_parse_card_names_filters_non_strings_and_blanks() -> None:
    response = '["Card A", "", 5]'
    assert parse_card_names(response) == ["Card A"]


def test_parse_search_queries_accepts_valid_objects() -> None:
    response = """
    [
      {"oracle_contains": ["discard"], "type_contains": ["creature"], "cmc_min": 1, "cmc_max": 3, "colors": ["B"]},
      {"oracle_contains": [], "type_contains": ["artifact"], "cmc_min": null, "cmc_max": 2, "colors": []}
    ]
    """
    queries = parse_search_queries(response)
    assert len(queries) == 2
    assert queries[0].oracle_contains == ["discard"]
    assert queries[0].type_contains == ["creature"]
    assert queries[0].cmc_min == 1.0
    assert queries[0].cmc_max == 3.0
    assert queries[0].colors == ["B"]


def test_parse_search_queries_handles_leading_and_trailing_noise() -> None:
    response = (
        'x[{"oracle_contains": ["draw"], "type_contains": [], "cmc_min": 1, '
        '"cmc_max": 2, "colors": []}]y'
    )
    queries = parse_search_queries(response)
    assert len(queries) == 1
    assert queries[0].oracle_contains == ["draw"]


def test_parse_search_queries_skips_non_dict_entries() -> None:
    response = """
    [
      5,
      {"oracle_contains": ["draw"], "type_contains": [], "cmc_min": 1, "cmc_max": 2, "colors": []}
    ]
    """
    queries = parse_search_queries(response)
    assert len(queries) == 1
    assert queries[0].oracle_contains == ["draw"]


def test_parse_search_queries_drops_invalid_bounds() -> None:
    response = """
    [
      {"oracle_contains": ["discard"], "type_contains": ["creature"], "cmc_min": 5, "cmc_max": 2, "colors": ["B"]},
      {"oracle_contains": ["draw"], "type_contains": [], "cmc_min": 1, "cmc_max": 3, "colors": ["U"]}
    ]
    """
    queries = parse_search_queries(response)
    assert len(queries) == 1
    assert queries[0].oracle_contains == ["draw"]


def test_logger_is_configured() -> None:
    assert isinstance(logger, logging.Logger)


def _make_card(name: str) -> Card:
    return Card(
        scryfall_id=f"{name}-id",
        name=name,
        type_line="Instant",
        oracle_text="Draw a card.",
        colors=None,
        color_identity=["U"],
        mana_cost="{U}",
        cmc=1.0,
        legalities={"commander": "legal"},
        price_usd=None,
        image_uris=None,
        card_faces=None,
    )


def test_build_search_prompt_includes_required_fields_and_limits() -> None:
    deck_cards = [f"Card {idx}" for idx in range(1, 42)]
    task = AgentTask(
        role="draw",
        count=5,
        commander_name="Test Commander",
        commander_text="Whenever you draw a card, gain 1 life.",
        deck_cards=deck_cards,
    )
    prompt = build_search_prompt(task)
    expected_deck_list = ", ".join(deck_cards[:40])

    lines = prompt.splitlines()
    assert lines[0] == "You are a Commander deckbuilding assistant."
    assert lines[1] == "Return ONLY a JSON array of search objects, with no extra text."
    assert lines[2] == (
        "Each object must use these keys: oracle_contains (list), type_contains (list), "
        "cmc_min (number or null), cmc_max (number or null), colors (list)."
    )
    assert lines[3] == ""
    assert lines[4] == "Role definition: Repeatable or burst card draw and card advantage."
    assert lines[5] == "Commander: Test Commander"
    assert lines[6] == "Commander text: Whenever you draw a card, gain 1 life."
    assert lines[7] == f"Deck so far (names): {expected_deck_list}"
    assert lines[8] == "Role needed: draw"
    assert lines[9] == "Count: 5"
    assert "Card 41" not in prompt


def test_build_ranking_prompt_includes_candidates_and_limits() -> None:
    deck_cards = [f"Deck {idx}" for idx in range(1, 45)]
    candidates = [_make_card(f"Candidate {idx}") for idx in range(1, 62)]
    task = AgentTask(
        role="removal",
        count=7,
        commander_name="Test Commander",
        commander_text="Destroy target creature.",
        deck_cards=deck_cards,
    )
    prompt = build_ranking_prompt(task, candidates)
    expected_deck_list = ", ".join(deck_cards[:40])
    expected_candidates = ", ".join(card.name for card in candidates[:60])

    lines = prompt.splitlines()
    assert lines[0] == "You are a Commander deckbuilding assistant."
    assert lines[1] == "Return ONLY a JSON array of card names (strings), ordered best to worst."
    assert lines[2] == ""
    assert lines[3] == "Role definition: Targeted or mass removal, interaction, or disruption."
    assert lines[4] == "Commander: Test Commander"
    assert lines[5] == "Commander text: Destroy target creature."
    assert lines[6] == f"Deck so far (names): {expected_deck_list}"
    assert lines[7] == "Role needed: removal"
    assert lines[8] == f"Candidates: {expected_candidates}"
    assert lines[9] == "Count: 7"
    assert "Deck 41" not in prompt
    assert "Candidate 61" not in prompt


def _db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def test_call_openai_returns_response(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"choices": [{"message": {"content": "ok"}}]}

    def fake_post(*args, **kwargs):
        return DummyResponse()

    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr(httpx, "post", fake_post)

    result = _call_openai("prompt", "system", 0.1)
    assert result == "ok"


def test_call_openai_sends_expected_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class DummyResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"choices": [{"message": {"content": "ok"}}]}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return DummyResponse()

    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr(settings, "openai_model", "test-model")
    monkeypatch.setattr(httpx, "post", fake_post)

    result = _call_openai("prompt", "system", 0.9)
    assert result == "ok"
    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["headers"]["Content-Type"] == "application/json"
    assert captured["json"] == {
        "model": "test-model",
        "messages": [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "prompt"},
        ],
        "temperature": 0.9,
    }
    assert captured["timeout"] == 30


def test_call_openai_handles_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(*args, **kwargs):
        raise httpx.HTTPError("boom")

    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr(httpx, "post", fake_post)

    result = _call_openai("prompt", "system", 0.1)
    assert result is None


def test_search_cards_filters_by_query_and_colors() -> None:
    session = _db_session()
    card_ok = _make_card("Match")
    card_ok.oracle_text = "Draw a card."
    card_ok.type_line = "Instant"
    card_ok.cmc = 2.0
    card_ok.legalities = {"commander": "legal"}
    card_ok.color_identity = ["U"]

    card_bad_color = _make_card("OffColor")
    card_bad_color.color_identity = ["R"]

    card_banned = _make_card("Banned")
    card_banned.legalities = {"commander": "banned"}

    session.add_all([card_ok, card_bad_color, card_banned])
    session.commit()

    query = AgentTask(
        role="draw",
        count=1,
        commander_name="Test",
        commander_text="",
        deck_cards=[],
    )
    search_query = parse_search_queries(
        '[{"oracle_contains": ["draw"], "type_contains": ["instant"], "cmc_min": 1, "cmc_max": 3, "colors": []}]'
    )[0]

    results = _search_cards(
        session=session,
        query=search_query,
        commander_colors={"U"},
        exclude_ids=set(),
        limit=10,
    )
    assert [card.name for card in results] == ["Match"]

    search_query = parse_search_queries(
        '[{"oracle_contains": ["draw"], "type_contains": ["instant"], "cmc_min": 1, "cmc_max": 3, "colors": ["G"]}]'
    )[0]
    results = _search_cards(
        session=session,
        query=search_query,
        commander_colors={"U"},
        exclude_ids=set(),
        limit=10,
    )
    assert results == []
    session.close()


def test_search_cards_respects_cmc_bounds_and_exclude_ids() -> None:
    session = _db_session()
    card_low = _make_card("Low")
    card_low.cmc = 1.0
    card_low.oracle_text = "Draw a card."

    card_mid = _make_card("Mid")
    card_mid.cmc = 3.0
    card_mid.oracle_text = "Draw a card."

    card_high = _make_card("High")
    card_high.cmc = 6.0
    card_high.oracle_text = "Draw a card."

    session.add_all([card_low, card_mid, card_high])
    session.commit()

    search_query = parse_search_queries(
        '[{"oracle_contains": ["draw"], "type_contains": ["instant"], "cmc_min": 2, "cmc_max": 4, "colors": []}]'
    )[0]

    results = _search_cards(
        session=session,
        query=search_query,
        commander_colors={"U"},
        exclude_ids=set(),
        limit=10,
    )
    assert [card.name for card in results] == ["Mid"]

    results = _search_cards(
        session=session,
        query=search_query,
        commander_colors={"U"},
        exclude_ids={card_mid.id},
        limit=10,
    )
    assert results == []
    session.close()


def test_search_cards_allows_subset_query_colors() -> None:
    session = _db_session()
    card_ok = _make_card("OnColor")
    card_ok.cmc = 2.0
    card_ok.oracle_text = "Draw a card."
    card_ok.color_identity = ["U"]

    session.add(card_ok)
    session.commit()

    search_query = parse_search_queries(
        '[{"oracle_contains": ["draw"], "type_contains": ["instant"], "cmc_min": 0, "cmc_max": 3, "colors": ["U"]}]'
    )[0]
    results = _search_cards(
        session=session,
        query=search_query,
        commander_colors={"U"},
        exclude_ids=set(),
        limit=10,
    )
    assert [card.name for card in results] == ["OnColor"]
    session.close()


def test_suggest_cards_for_role_invalid_task_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _db_session()
    commander_card = _make_card("Commander")
    commander_card.oracle_text = "Draw a card."
    commander_card.color_identity = ["U"]
    session.add(commander_card)
    session.commit()

    commander = Commander(
        card_id=commander_card.id,
        eligibility_reason="legendary creature",
        color_identity=["U"],
    )
    session.add(commander)
    session.commit()
    session.refresh(commander)

    called = False

    def fake_call_openai(*args, **kwargs):
        nonlocal called
        called = True
        return "[]"

    monkeypatch.setattr("src.engine.llm_agent._call_openai", fake_call_openai)

    selected = suggest_cards_for_role(
        session=session,
        deck_id=1,
        commander=commander,
        deck_cards=[commander_card],
        role="draw",
        count=0,
        exclude_ids=set(),
    )
    assert selected == []
    assert called is False
    session.close()


def test_suggest_cards_for_role_tracks_prompts_and_updates_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _db_session()
    commander_card = _make_card("Commander")
    commander_card.oracle_text = None
    commander_card.color_identity = ["U"]
    session.add(commander_card)
    session.commit()

    commander = Commander(
        card_id=commander_card.id,
        eligibility_reason="legendary creature",
        color_identity=["U"],
    )
    session.add(commander)
    session.commit()
    session.refresh(commander)

    excluded = _make_card("Excluded")
    excluded.color_identity = ["U"]
    session.add(excluded)
    session.commit()

    candidate = _make_card("Candidate Draw")
    candidate.oracle_text = "Draw a card."
    candidate.type_line = "Instant"
    candidate.color_identity = ["U"]
    candidate.legalities = {"commander": "legal"}
    session.add(candidate)
    session.commit()

    responses = [
        '[{"oracle_contains": ["draw"], "type_contains": ["instant"], "cmc_min": 1, "cmc_max": 3, "colors": []}]',
        '["Candidate Draw"]',
    ]
    captured_calls: list[dict[str, object]] = []
    search_limits: list[int] = []

    def fake_call_openai(prompt, system_prompt, temperature):
        captured_calls.append(
            {"prompt": prompt, "system_prompt": system_prompt, "temperature": temperature}
        )
        return responses.pop(0)

    def fake_search_cards(session, query, commander_colors, exclude_ids, limit):
        search_limits.append(limit)
        return [candidate, candidate]

    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr("src.engine.llm_agent._call_openai", fake_call_openai)
    monkeypatch.setattr("src.engine.llm_agent._search_cards", fake_search_cards)
    monkeypatch.setattr("src.engine.llm_agent.compute_similarity", lambda *args, **kwargs: {})

    selected = suggest_cards_for_role(
        session=session,
        deck_id=99,
        commander=commander,
        deck_cards=[commander_card, excluded],
        role="draw",
        count=1,
        exclude_ids={excluded.id},
    )
    assert [card.name for card in selected] == ["Candidate Draw"]

    assert search_limits == [50]
    assert len(captured_calls) == 2
    assert captured_calls[0]["system_prompt"] == (
        "You produce structured search queries for Commander deckbuilding.\n"
        "Return JSON only. Avoid commentary. Ensure queries align with the role and commander."
    )
    assert captured_calls[0]["temperature"] == 0.6
    assert captured_calls[1]["system_prompt"] == (
        "You rank candidate cards for a Commander deck role.\n"
        "Return JSON only. Order from best fit to worst."
    )
    assert captured_calls[1]["temperature"] == 0.2
    assert "Excluded" not in captured_calls[0]["prompt"]
    assert captured_calls[1]["prompt"].count("Candidate Draw") == 1

    runs = session.query(LLMRun).filter(LLMRun.deck_id == 99).all()
    roles = {run.role: run for run in runs}
    assert "draw:search" in roles
    assert "draw:rank" in roles
    assert roles["draw:rank"].success is True
    session.close()


def test_suggest_cards_for_role_reranks_with_similarity(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _db_session()
    commander_card = _make_card("Commander")
    commander_card.oracle_text = "Draw a card."
    commander_card.color_identity = ["U"]
    session.add(commander_card)
    session.commit()

    commander = Commander(
        card_id=commander_card.id,
        eligibility_reason="legendary creature",
        color_identity=["U"],
    )
    session.add(commander)
    session.commit()
    session.refresh(commander)

    card_a = _make_card("Card A")
    card_a.oracle_text = "Draw a card."
    card_a.color_identity = ["U"]
    card_b = _make_card("Card B")
    card_b.oracle_text = "Draw a card."
    card_b.color_identity = ["U"]
    session.add_all([card_a, card_b])
    session.commit()

    responses = [
        '[{"oracle_contains": ["draw"], "type_contains": ["instant"], "cmc_min": 1, "cmc_max": 3, "colors": []}]',
        '["Card A", "Card B"]',
    ]

    def fake_call_openai(*args, **kwargs):
        return responses.pop(0)

    def fake_search_cards(*args, **kwargs):
        return [card_a, card_b]

    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr("src.engine.llm_agent._call_openai", fake_call_openai)
    monkeypatch.setattr("src.engine.llm_agent._search_cards", fake_search_cards)
    monkeypatch.setattr(
        "src.engine.llm_agent.compute_similarity",
        lambda *args, **kwargs: {card_a.id: 0.0, card_b.id: 1.2},
    )

    selected = suggest_cards_for_role(
        session=session,
        deck_id=1,
        commander=commander,
        deck_cards=[commander_card],
        role="draw",
        count=1,
        exclude_ids=set(),
    )
    assert [card.name for card in selected] == ["Card B"]
    session.close()


def test_suggest_cards_for_role_respects_rank_order(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _db_session()
    commander_card = _make_card("Commander")
    commander_card.oracle_text = "Draw a card."
    commander_card.color_identity = ["U"]
    session.add(commander_card)
    session.commit()

    commander = Commander(
        card_id=commander_card.id,
        eligibility_reason="legendary creature",
        color_identity=["U"],
    )
    session.add(commander)
    session.commit()
    session.refresh(commander)

    card_a = _make_card("Card A")
    card_a.oracle_text = "Draw a card."
    card_a.color_identity = ["U"]
    card_b = _make_card("Card B")
    card_b.oracle_text = "Draw a card."
    card_b.color_identity = ["U"]
    session.add_all([card_a, card_b])
    session.commit()

    responses = [
        '[{"oracle_contains": ["draw"], "type_contains": ["instant"], "cmc_min": 1, "cmc_max": 3, "colors": []}]',
        '["Card A", "Card B"]',
    ]

    def fake_call_openai(*args, **kwargs):
        return responses.pop(0)

    def fake_search_cards(*args, **kwargs):
        return [card_a, card_b]

    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr("src.engine.llm_agent._call_openai", fake_call_openai)
    monkeypatch.setattr("src.engine.llm_agent._search_cards", fake_search_cards)
    monkeypatch.setattr(
        "src.engine.llm_agent.compute_similarity",
        lambda *args, **kwargs: {card_a.id: 0.0, card_b.id: 0.5},
    )

    selected = suggest_cards_for_role(
        session=session,
        deck_id=1,
        commander=commander,
        deck_cards=[commander_card],
        role="draw",
        count=1,
        exclude_ids=set(),
    )
    assert [card.name for card in selected] == ["Card A"]
    session.close()

def test_suggest_cards_for_role_end_to_end(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _db_session()
    commander_card = _make_card("Commander")
    commander_card.oracle_text = "Draw a card."
    commander_card.color_identity = ["U"]
    session.add(commander_card)
    session.commit()

    commander = Commander(
        card_id=commander_card.id,
        eligibility_reason="legendary creature",
        color_identity=["U"],
    )
    session.add(commander)
    session.commit()
    session.refresh(commander)

    candidate = _make_card("Candidate Draw")
    candidate.oracle_text = "Draw a card."
    candidate.type_line = "Instant"
    candidate.color_identity = ["U"]
    candidate.legalities = {"commander": "legal"}
    session.add(candidate)
    session.commit()

    session.add(
        LLMRun(
            deck_id=1,
            commander_id=commander.id,
            role="draw:search",
            model="test",
            prompt="",
            response="",
            success=False,
        )
    )
    session.commit()

    responses = [
        '[{"oracle_contains": ["draw"], "type_contains": ["instant"], "cmc_min": 1, "cmc_max": 3, "colors": []}]',
        '["Candidate Draw"]',
    ]

    def fake_call_openai(*args, **kwargs):
        return responses.pop(0)

    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr("src.engine.llm_agent._call_openai", fake_call_openai)
    monkeypatch.setattr("src.engine.llm_agent.compute_similarity", lambda *args, **kwargs: {})

    selected = suggest_cards_for_role(
        session=session,
        deck_id=1,
        commander=commander,
        deck_cards=[commander_card],
        role="draw",
        count=1,
        exclude_ids=set(),
    )
    assert [card.name for card in selected] == ["Candidate Draw"]
    session.close()
