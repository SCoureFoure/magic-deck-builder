"""Council orchestration module."""
from src.engine.council.config import CouncilConfig, load_council_config


def select_cards_with_council(*args, **kwargs):
    from src.engine.council.graph import select_cards_with_council as _select_cards_with_council

    return _select_cards_with_council(*args, **kwargs)


__all__ = ["CouncilConfig", "load_council_config", "select_cards_with_council"]
