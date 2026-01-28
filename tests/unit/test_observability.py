from src.engine.observability import estimate_tokens


def test_estimate_tokens_empty() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens(None) == 0


def test_estimate_tokens_rounding() -> None:
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcde") == 2
