import pytest
from pydantic import ValidationError

from scripts.lib.config import SignalConfig, TopicsConfig, TrendsConfig


def test_topic_defaults_to_enabled_trends_when_absent():
    cfg = TopicsConfig(topics=[{
        "id": "cs", "enabled": True, "display_name": "CS", "priority": 1.0,
    }])
    t = cfg.topics[0]
    assert isinstance(t.trends, TrendsConfig)
    assert t.trends.enabled is True
    assert t.trends.sort_bump == 8.0
    assert t.trends.blend.method == "weighted"
    assert t.trends.corpus_burst.window_days == 14


def test_trends_block_parses_signals_list():
    cfg = TopicsConfig(topics=[{
        "id": "cs", "enabled": True, "display_name": "CS", "priority": 1.0,
        "trends": {
            "enabled": True, "sort_bump": 5.0,
            "signals": [
                {"name": "hackernews", "weight": 1.0, "params": {"min_points": 50}},
                {"name": "gdelt", "enabled": False},
            ],
        },
    }])
    trends = cfg.topics[0].trends
    assert isinstance(trends.signals[0], SignalConfig)
    assert [s.name for s in trends.signals] == ["hackernews", "gdelt"]
    assert trends.signals[0].params["min_points"] == 50
    assert trends.signals[1].enabled is False
    assert [s.name for s in trends.active_signals()] == ["hackernews"]


def test_invalid_blend_method_rejected():
    with pytest.raises(ValidationError):
        TrendsConfig(blend={"method": "bogus"})


def test_unknown_trends_key_rejected():
    with pytest.raises(ValidationError):
        TrendsConfig(nonsense=1)


def test_new_signals_parse_with_params():
    cfg = TrendsConfig(signals=[
        {"name": "bluesky", "params": {"max_keywords": 5, "since_hours": 48}},
        {"name": "wikipedia", "params": {"titles": {"llm": "Large_language_model"},
                                         "baseline_days": 10}},
        {"name": "reddit", "enabled": True,
         "params": {"subreddits": ["MachineLearning", "LocalLLaMA"],
                    "listing": "top", "timespan": "week"}},
    ])
    names = [s.name for s in cfg.active_signals()]
    assert names == ["bluesky", "wikipedia", "reddit"]
    reddit = cfg.signals[2]
    assert reddit.params["subreddits"] == ["MachineLearning", "LocalLLaMA"]
