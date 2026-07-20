from pathlib import Path

import pytest

from scripts import fetch_arxiv as fa
from scripts.fetch_arxiv import build_arxiv_query, fetch_arxiv, parse_arxiv_atom
from scripts.lib.fetch_http import FetchError

FIX = Path(__file__).parent / "fixtures" / "arxiv_response.xml"

# arXiv Atom feed with a nonzero totalResults but ZERO <entry> elements — the
# signature of a throttled / redirect-stripped response, NOT a genuinely empty
# window. fetch_arxiv must treat this as a failure, not a silent success.
_EMPTY_WITH_TOTAL = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<feed xmlns="http://www.w3.org/2005/Atom" '
    'xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">'
    "<opensearch:totalResults>277563</opensearch:totalResults>"
    "</feed>"
)

# A genuinely empty window: totalResults is 0 and there are no entries. This is
# a legitimate empty result and must NOT raise.
_EMPTY_WITH_ZERO_TOTAL = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<feed xmlns="http://www.w3.org/2005/Atom" '
    'xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">'
    "<opensearch:totalResults>0</opensearch:totalResults>"
    "</feed>"
)


def test_parse_arxiv_atom_normalizes_entries():
    papers = parse_arxiv_atom(FIX.read_text())
    assert len(papers) == 2
    p = papers[0]
    assert p.source == "arxiv"
    assert p.arxiv_id == "2406.00001"          # version stripped
    assert p.title == "A Simple Method for Better Language Models"
    assert p.authors == ["Ada Lovelace", "Alan Turing"]
    assert p.url == "http://arxiv.org/abs/2406.00001v2"
    assert p.pdf_url == "http://arxiv.org/pdf/2406.00001v2"
    assert p.is_preprint is True
    assert p.published_date.isoformat() == "2026-06-28"
    assert "language model" in (p.abstract or "").lower()


def test_parse_arxiv_atom_handles_single_author():
    papers = parse_arxiv_atom(FIX.read_text())
    assert papers[1].authors == ["Grace Hopper"]
    assert papers[1].arxiv_id == "2406.00002"


def test_build_arxiv_query_categories_and_dates():
    q = build_arxiv_query(
        categories=["cs.AI", "cs.CL"],
        since="2026-06-28",
        until="2026-07-01",
    )
    assert "cat:cs.AI" in q["search_query"]
    assert "cat:cs.CL" in q["search_query"]
    assert "submittedDate:[202606280000 TO 202607010000]" in q["search_query"]
    assert q["sortBy"] == "submittedDate"
    assert q["sortOrder"] == "descending"
    assert q["max_results"] == 50


def test_fetch_arxiv_paginates_until_short_page(monkeypatch):
    # Two full pages then a short one -> stop after the short page.
    full = FIX.read_text()  # 2 entries
    pages = [full, full, full]  # 2,2,2 entries; page size forced to 2 below

    calls = {"n": 0}

    def fake_get_text(url, params=None, **kw):
        i = calls["n"]
        calls["n"] += 1
        return pages[i] if i < len(pages) else "<feed></feed>"

    monkeypatch.setattr(fa, "get_text", fake_get_text)
    monkeypatch.setattr(fa, "ARXIV_PAGE_SIZE", 2)
    monkeypatch.setattr(fa, "ARXIV_MAX_PAGES", 10)
    papers = fetch_arxiv(["cs.AI"], "2026-07-01", "2026-07-03", sleep=lambda s: None)
    # page1=2 (==size, continue), page2=2 (continue), page3 also 2 but fixture
    # only has 3 pages then empty -> 4th call returns empty feed -> stop.
    assert calls["n"] == 4
    assert len(papers) == 6


def test_fetch_arxiv_respects_max_results(monkeypatch):
    monkeypatch.setattr(fa, "get_text", lambda *a, **k: FIX.read_text())
    monkeypatch.setattr(fa, "ARXIV_PAGE_SIZE", 2)
    papers = fetch_arxiv(
        ["cs.AI"], "2026-07-01", "2026-07-03", max_results=3, sleep=lambda s: None
    )
    assert len(papers) == 3


def test_fetch_arxiv_logs_when_ceiling_hit(monkeypatch, capsys):
    # Every page full + low ceiling -> loop exits via ceiling, must warn.
    monkeypatch.setattr(fa, "ARXIV_PAGE_SIZE", 2)
    monkeypatch.setattr(fa, "ARXIV_MAX_PAGES", 2)
    monkeypatch.setattr(fa, "get_text", lambda *a, **k: FIX.read_text())  # 2 entries = full
    papers = fetch_arxiv(["cs.AI"], "2026-07-01", "2026-07-03", sleep=lambda s: None)
    assert len(papers) == 4  # 2 pages x 2
    assert "hit the 2-page ceiling" in capsys.readouterr().err


def test_uses_https_endpoint():
    # arXiv 301-redirects http->https and returns an empty body on the redirect;
    # request https directly to avoid the round-trip and the empty-body artifact.
    assert fa.ARXIV_API.startswith("https://")


def test_fetch_arxiv_raises_on_empty_with_nonzero_total(monkeypatch):
    # totalResults>0 but 0 entries parsed = throttled/stripped response. Must raise
    # FetchError so gather logs a failure instead of a silent "arxiv -> 0 papers".
    monkeypatch.setattr(fa, "get_text", lambda *a, **k: _EMPTY_WITH_TOTAL)
    with pytest.raises(FetchError, match="0 entries"):
        fetch_arxiv(["cs.AI"], "2026-07-01", "2026-07-03", sleep=lambda s: None)


def test_fetch_arxiv_allows_genuinely_empty_window(monkeypatch):
    # totalResults==0 with 0 entries is a legitimate empty window, not a failure.
    monkeypatch.setattr(fa, "get_text", lambda *a, **k: _EMPTY_WITH_ZERO_TOTAL)
    papers = fetch_arxiv(["cs.AI"], "2026-07-01", "2026-07-03", sleep=lambda s: None)
    assert papers == []


def test_fetch_arxiv_fails_over_to_secondary_host(monkeypatch):
    # If the primary API host errors, fetch_arxiv should retry the same query
    # against the next configured host rather than giving up.
    assert len(fa.ARXIV_API_HOSTS) >= 2
    used = []

    def fake_get_text(url, params=None, **kw):
        used.append(url)
        if url == fa.ARXIV_API_HOSTS[0]:
            raise FetchError("primary host down")
        return FIX.read_text()

    monkeypatch.setattr(fa, "get_text", fake_get_text)
    monkeypatch.setattr(fa, "ARXIV_PAGE_SIZE", 2)
    papers = fetch_arxiv(["cs.AI"], "2026-07-01", "2026-07-03", max_results=1,
                         sleep=lambda s: None)
    assert len(papers) == 1
    assert used[0] == fa.ARXIV_API_HOSTS[0]           # tried primary first
    assert fa.ARXIV_API_HOSTS[1] in used              # then failed over


def test_fetch_arxiv_raises_when_all_hosts_fail(monkeypatch):
    # Every host erroring is a real failure -> FetchError (so gather logs/skips it).
    def always_fail(url, params=None, **kw):
        raise FetchError("host down")

    monkeypatch.setattr(fa, "get_text", always_fail)
    with pytest.raises(FetchError):
        fetch_arxiv(["cs.AI"], "2026-07-01", "2026-07-03", sleep=lambda s: None)


def test_fetch_arxiv_uses_tight_timeout_and_extra_retries(monkeypatch):
    # arXiv tarpits: a bad attempt should abandon fast (short read timeout) and
    # re-roll more times, rather than burning the default 30s x 4. Assert the
    # per-request kwargs threaded into get_text reflect that policy.
    seen = {}

    def fake_get_text(url, params=None, timeout=None, max_attempts=None, **kw):
        seen["timeout"] = timeout
        seen["max_attempts"] = max_attempts
        return FIX.read_text()

    monkeypatch.setattr(fa, "get_text", fake_get_text)
    monkeypatch.setattr(fa, "ARXIV_PAGE_SIZE", 2)
    fetch_arxiv(["cs.AI"], "2026-07-01", "2026-07-03", max_results=1, sleep=lambda s: None)
    assert seen["timeout"] is not None and seen["timeout"] <= 15
    assert seen["max_attempts"] is not None and seen["max_attempts"] >= 5


def test_fetch_arxiv_empty_later_page_is_not_an_error(monkeypatch):
    # A full first page then an empty (totalResults>0) later page is normal
    # end-of-results paging, NOT the throttle signature — must stop cleanly.
    pages = [FIX.read_text(), _EMPTY_WITH_TOTAL]
    calls = {"n": 0}

    def fake_get_text(*a, **k):
        i = calls["n"]
        calls["n"] += 1
        return pages[i] if i < len(pages) else _EMPTY_WITH_TOTAL

    monkeypatch.setattr(fa, "get_text", fake_get_text)
    monkeypatch.setattr(fa, "ARXIV_PAGE_SIZE", 2)
    papers = fetch_arxiv(["cs.AI"], "2026-07-01", "2026-07-03", sleep=lambda s: None)
    assert len(papers) == 2  # first page kept; empty second page ends paging
