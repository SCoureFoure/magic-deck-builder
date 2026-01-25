from src.engine.council.voting import aggregate_rankings


def test_borda_ranking_prefers_consensus():
    rankings = {
        "a": ["Card1", "Card2", "Card3"],
        "b": ["Card2", "Card1", "Card3"],
        "c": ["Card2", "Card3", "Card1"],
    }
    weights = {"a": 1.0, "b": 1.0, "c": 1.0}
    result = aggregate_rankings(rankings, weights, strategy="borda", top_k=3)
    assert result[0] == "Card2"


def test_majority_ranking_prefers_broad_support():
    rankings = {
        "a": ["CardA", "CardB"],
        "b": ["CardA", "CardC"],
        "c": ["CardB", "CardA"],
    }
    weights = {"a": 1.0, "b": 1.0, "c": 1.0}
    result = aggregate_rankings(rankings, weights, strategy="majority", top_k=2)
    assert result[0] == "CardA"
