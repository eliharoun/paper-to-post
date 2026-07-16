from datetime import date

from scripts.lib.trends.cache import read_cache, write_cache


def test_write_then_read_within_ttl(tmp_path):
    write_cache(tmp_path, "hackernews", "cs", date(2026, 7, 15), {"hot": ["llm"]},
                now_ts=1_000_000)
    got = read_cache(tmp_path, "hackernews", "cs", date(2026, 7, 15),
                     ttl_min=180, now_ts=1_000_000 + 60)
    assert got == {"hot": ["llm"]}


def test_read_miss_returns_none(tmp_path):
    assert read_cache(tmp_path, "gdelt", "cs", date(2026, 7, 15),
                      ttl_min=180, now_ts=1_000_000) is None


def test_expired_cache_returns_none(tmp_path):
    write_cache(tmp_path, "hackernews", "cs", date(2026, 7, 15), {"hot": []},
                now_ts=1_000_000)
    assert read_cache(tmp_path, "hackernews", "cs", date(2026, 7, 15),
                      ttl_min=180, now_ts=1_000_000 + 4 * 3600) is None   # 4h > 180min
