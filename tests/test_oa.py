import httpx

from scripts.lib.oa import parse_unpaywall, resolve_oa_pdf


def test_parse_unpaywall_oa_with_pdf():
    payload = {"is_oa": True,
               "best_oa_location": {"url_for_pdf": "https://x/paper.pdf", "url": "https://x/land"}}
    assert parse_unpaywall(payload) == (True, "https://x/paper.pdf")


def test_parse_unpaywall_falls_back_to_locations():
    payload = {"is_oa": True, "best_oa_location": {},
               "oa_locations": [{"url": "https://x/land"}, {"url_for_pdf": "https://x/p.pdf"}]}
    assert parse_unpaywall(payload) == (True, "https://x/land")


def test_parse_unpaywall_not_oa():
    assert parse_unpaywall({"is_oa": False}) == (False, None)


def test_resolve_oa_pdf_success():
    def handler(request):
        assert "email=" in str(request.url)
        return httpx.Response(200, json={"is_oa": True,
                              "best_oa_location": {"url_for_pdf": "https://x/y.pdf"}})
    is_oa, url = resolve_oa_pdf("10.1/x", "me@example.com",
                                transport=httpx.MockTransport(handler))
    assert is_oa and url == "https://x/y.pdf"


def test_resolve_oa_pdf_no_email_or_doi():
    assert resolve_oa_pdf("", "me@example.com") == (False, None)
    assert resolve_oa_pdf("10.1/x", "") == (False, None)


def test_resolve_oa_pdf_404_returns_false():
    t = httpx.MockTransport(lambda r: httpx.Response(404, text="not found"))
    assert resolve_oa_pdf("10.1/missing", "me@example.com", transport=t) == (False, None)


def test_enrich_skips_existing_pdf_and_fills_from_doi(monkeypatch):
    import scripts.lib.oa as oa
    monkeypatch.setattr(oa, "resolve_oa_pdf", lambda doi, email: (True, "https://x/z.pdf"))
    papers = [
        {"pdf_url": "https://arxiv/a.pdf", "doi": "10.1/a"},   # skipped (has pdf)
        {"doi": "10.2/b"},                                     # enriched
        {"title": "no doi"},                                   # skipped (no doi)
    ]
    n = oa.enrich_papers_with_oa(papers, "me@example.com")
    assert n == 1
    assert papers[1]["pdf_url"] == "https://x/z.pdf" and papers[1]["is_open_access"] is True
    assert papers[0]["pdf_url"] == "https://arxiv/a.pdf"
