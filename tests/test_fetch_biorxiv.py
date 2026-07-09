import json
from pathlib import Path

from scripts import fetch_biorxiv as bx
from scripts.fetch_biorxiv import build_biorxiv_url, fetch_biorxiv, parse_biorxiv_response

FIX = Path(__file__).parent / "fixtures" / "biorxiv_response.json"


def test_parse_biorxiv_normalizes():
    papers = parse_biorxiv_response(json.loads(FIX.read_text()))
    assert len(papers) == 2
    p = papers[0]
    assert p.source == "biorxiv"
    assert p.doi == "10.1101/2026.06.28.111111"
    assert p.is_preprint is True
    assert p.is_open_access is True
    assert p.authors == ["Franklin, R.", "Doudna, J."]
    assert p.published_date.isoformat() == "2026-06-28"
    assert p.url == "https://www.biorxiv.org/content/10.1101/2026.06.28.111111"


def test_parse_biorxiv_medrxiv_url():
    payload = json.loads(FIX.read_text())
    payload["collection"][0]["server"] = "medrxiv"
    p = parse_biorxiv_response(payload)[0]
    assert p.source == "medrxiv"
    assert p.url.startswith("https://www.medrxiv.org/content/")


def test_build_biorxiv_url():
    url = build_biorxiv_url("biorxiv", "2026-06-28", "2026-07-01", cursor=0)
    assert url == "https://api.biorxiv.org/details/biorxiv/2026-06-28/2026-07-01/0"


def _page(n):
    item = json.loads(FIX.read_text())["collection"][0]
    return json.dumps({"collection": [item] * n})


def test_fetch_biorxiv_paginates_cursor_until_short_page(monkeypatch):
    monkeypatch.setattr(bx, "BIORXIV_PAGE_SIZE", 2)
    monkeypatch.setattr(bx, "BIORXIV_MAX_PAGES", 10)
    cursors = []

    def fake_get_text(url, **kw):
        cursor = int(url.rstrip("/").split("/")[-1])
        cursors.append(cursor)
        # full page (2) then a short page (1) -> stop
        return _page(2) if cursor == 0 else _page(1)

    monkeypatch.setattr(bx, "get_text", fake_get_text)
    papers = fetch_biorxiv(["biorxiv"], "2026-07-06", "2026-07-08", sleep=lambda s: None)
    assert cursors == [0, 2]        # advanced by page length, stopped on short page
    assert len(papers) == 3         # 2 + 1


def test_fetch_biorxiv_multiple_servers(monkeypatch):
    monkeypatch.setattr(bx, "BIORXIV_PAGE_SIZE", 2)
    monkeypatch.setattr(bx, "get_text", lambda url, **kw: _page(1))  # each server: one short page
    papers = fetch_biorxiv(["biorxiv", "medrxiv"], "2026-07-06", "2026-07-08", sleep=lambda s: None)
    assert len(papers) == 2  # one per server
