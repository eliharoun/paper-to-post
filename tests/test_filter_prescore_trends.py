import json
from datetime import date

from scripts.filter_prescore import run
from scripts.lib.store import Ledger


def _write_papers(tmp_path, n_hot, n_cold):
    papers = []
    for i in range(n_hot):
        papers.append({"title": "quantum annealing solver agent",
                       "abstract": "quantum annealing " + "detail " * 80,
                       "source": "arxiv", "arxiv_id": f"h{i}",
                       "arxiv_categories": ["cs.LG"],
                       "published_date": "2026-07-15"})
    for i in range(n_cold):
        papers.append({"title": f"obscure subject {i} kappa lambda mu",
                       "abstract": "unrelated " + "detail " * 80,
                       "source": "arxiv", "arxiv_id": f"c{i}",
                       "arxiv_categories": ["cs.LG"],
                       "published_date": "2026-07-15"})
    p = tmp_path / "papers.json"
    p.write_text(json.dumps(papers))
    return str(p)


def _topics_yaml(tmp_path, sort_bump):
    y = tmp_path / "topics.yml"
    y.write_text(f"""
topics:
  - id: cs
    enabled: true
    account: cs
    display_name: CS
    priority: 1.0
    sources:
      arxiv: {{categories: [cs.LG]}}
    trends:
      enabled: true
      sort_bump: {sort_bump}
      signals: []
""")
    return str(y)


def test_trendiness_written_to_breakdown(tmp_path):
    papers = _write_papers(tmp_path, n_hot=20, n_cold=40)
    out = tmp_path / "candidates.json"
    ledger = Ledger(str(tmp_path / "ledger.db"))
    run(papers, str(out), topics_path=_topics_yaml(tmp_path, 8.0),
        ledger=ledger, today=date(2026, 7, 15),
        only_topic="cs", data_dir=str(tmp_path))
    cands = json.loads(out.read_text())
    assert cands, "expected candidates"
    assert "trendiness" in cands[0]["score_breakdown"]
    assert 0.0 <= cands[0]["score_breakdown"]["trendiness"] <= 1.0
    assert "trend_signals" in cands[0]["score_breakdown"]


def test_sort_bump_zero_keeps_rule_score_order(tmp_path):
    papers = _write_papers(tmp_path, n_hot=20, n_cold=40)
    out = tmp_path / "c.json"
    ledger = Ledger(str(tmp_path / "l.db"))
    run(papers, str(out), topics_path=_topics_yaml(tmp_path, 0.0),
        ledger=ledger, today=date(2026, 7, 15),
        only_topic="cs", data_dir=str(tmp_path))
    cands = json.loads(out.read_text())
    scores = [c["rule_score"] for c in cands]
    assert scores == sorted(scores, reverse=True)   # pure rule_score order


def test_scorer_failure_degrades_to_rule_score_order(tmp_path, monkeypatch):
    def _boom(self, *a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "scripts.filter_prescore.TrendScorer.score_corpus", _boom
    )
    papers = _write_papers(tmp_path, n_hot=20, n_cold=40)
    out = tmp_path / "c.json"
    ledger = Ledger(str(tmp_path / "l.db"))
    # must NOT raise even though trends is enabled with a real corpus
    run(papers, str(out), topics_path=_topics_yaml(tmp_path, 8.0),
        ledger=ledger, today=date(2026, 7, 15),
        only_topic="cs", data_dir=str(tmp_path))
    cands = json.loads(out.read_text())
    assert cands, "expected candidates despite trends failure"
    scores = [c["rule_score"] for c in cands]
    assert scores == sorted(scores, reverse=True)   # fallback sort ran
