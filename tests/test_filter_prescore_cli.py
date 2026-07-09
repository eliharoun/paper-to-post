import json
from datetime import date

from scripts.filter_prescore import run
from scripts.lib.store import Ledger


def _paper(**over) -> dict:
    base = {
        "source": "arxiv", "source_id": "2406.1", "arxiv_id": "2406.1", "doi": None,
        "semantic_scholar_id": None, "openalex_id": None,
        "title": "Machine Learning for Software Systems",
        "abstract": "x" * 600, "authors": [], "url": "https://arxiv.org/abs/2406.1",
        "pdf_url": "https://x/y.pdf", "published_date": "2026-07-01",
        "citation_count": 1, "field_of_study": None, "arxiv_categories": ["cs.LG"],
    }
    base.update(over)
    return base


def test_run_filters_scores_and_ranks(tmp_path):
    papers = [
        _paper(arxiv_id="2406.1", title="Deep Learning for Compilers",
               arxiv_categories=["cs.LG"]),
        _paper(arxiv_id="2406.2", title="Short one", abstract="too short",
               arxiv_categories=["cs.AI"]),  # dropped: abstract_too_short
        _paper(arxiv_id="2406.3", title="Medieval History", abstract="y" * 600,
               arxiv_categories=[], field_of_study="History"),  # dropped: no_topic
    ]
    papers_path = tmp_path / "papers.json"
    papers_path.write_text(json.dumps(papers))
    out_path = tmp_path / "candidates.json"
    ledger = Ledger(tmp_path / "led.db")

    n = run(str(papers_path), str(out_path),
            ledger=ledger, today=date(2026, 7, 1))

    candidates = json.loads(out_path.read_text())
    assert n == 1
    assert len(candidates) == 1
    c = candidates[0]
    assert c["paper"]["arxiv_id"] == "2406.1"
    assert c["topic_id"] == "swe_ml_ai"
    assert c["rule_score"] > 0
    assert c["filter_status"] == "passed"


def test_run_excludes_delivered(tmp_path):
    papers = [_paper(arxiv_id="2406.9", title="Neural Nets for Code")]
    papers_path = tmp_path / "papers.json"
    papers_path.write_text(json.dumps(papers))
    ledger = Ledger(tmp_path / "led.db")
    ledger.mark_delivered("arxiv:2406.9", "2026-06-30", post_id="old")

    n = run(str(papers_path), str(tmp_path / "out.json"),
            ledger=ledger, today=date(2026, 7, 1))
    assert n == 0


def test_only_topic_limits_to_one_account(tmp_path):
    papers = [
        _paper(arxiv_id="2406.1", title="Deep Learning for Compilers",
               arxiv_categories=["cs.LG"]),  # -> swe_ml_ai
        _paper(arxiv_id="2406.5", title="CRISPR genomics cancer screen",
               arxiv_categories=[], field_of_study="Biology"),  # -> bio_genetics_biomed
    ]
    papers_path = tmp_path / "papers.json"
    papers_path.write_text(json.dumps(papers))
    out = tmp_path / "out.json"
    n = run(str(papers_path), str(out), ledger=Ledger(tmp_path / "l.db"),
            today=date(2026, 7, 1), only_topic="swe_ml_ai")
    cands = json.loads(out.read_text())
    assert n == 1
    assert all(c["topic_id"] == "swe_ml_ai" for c in cands)


def test_run_sorts_best_first(tmp_path):
    papers = [
        _paper(arxiv_id="2406.a", title="AI systems", published_date="2026-06-20"),  # older
        _paper(arxiv_id="2406.b", title="AI systems", published_date="2026-07-01"),  # newer
    ]
    papers_path = tmp_path / "papers.json"
    papers_path.write_text(json.dumps(papers))
    out_path = tmp_path / "out.json"
    run(str(papers_path), str(out_path),
        ledger=Ledger(tmp_path / "l.db"), today=date(2026, 7, 1))
    cands = json.loads(out_path.read_text())
    assert cands[0]["paper"]["arxiv_id"] == "2406.b"  # newer ranked first
    assert cands[0]["rule_score"] >= cands[1]["rule_score"]
