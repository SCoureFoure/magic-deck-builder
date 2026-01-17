from src.engine.llm_agent import parse_card_names, parse_search_queries


def test_parse_card_names_accepts_json_array() -> None:
    response = '["Card A", "Card B"]'
    assert parse_card_names(response) == ["Card A", "Card B"]


def test_parse_card_names_ignores_non_json() -> None:
    response = "Here are some cards: Card A, Card B"
    assert parse_card_names(response) == []


def test_parse_card_names_trims_wrapped_text() -> None:
    response = "Result:\n[\"Card A\", \"Card B\"]\nThanks!"
    assert parse_card_names(response) == ["Card A", "Card B"]


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
