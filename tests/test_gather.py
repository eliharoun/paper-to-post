import pytest

from scripts import gather as g
from scripts.lib.config import load_topics
from scripts.lib.models import PaperInput


def _paper(pid, title, cats=None):
    return PaperInput(
        source="arxiv", source_id=pid, arxiv_id=pid, title=title,
        abstract="x" * 500, url=f"https://arxiv.org/abs/{pid}",
        raw_payload={"arxiv_categories": cats or ["cs.AI"]},
    )


def test_window_computation():
    since, until = g._window("2026-07-08", 48)
    assert until == "2026-07-08"
    assert since == "2026-07-06"


def test_gather_runs_only_configured_sources(tmp_path, monkeypatch, config_dir):
    cfg = load_topics(config_dir / "topics.yml")
    cs = next(t for t in cfg.topics if t.id == "swe_ml_ai")

    called = []

    def fake_fetch(name, src, since, until):
        called.append(name)
        return [_paper(f"{name}1", f"{name} paper about machine learning llm")]

    monkeypatch.setattr(g, "_fetch_source", fake_fetch)
    n, ok = g.gather(cs, "2026-07-06", "2026-07-08", str(tmp_path),
                     topics_path=str(config_dir / "topics.yml"))

    # cs config lists arxiv, openalex, crossref, semantic_scholar, labs (not pubmed/biorxiv)
    assert set(called) == {"arxiv", "openalex", "crossref", "semantic_scholar", "labs"}
    assert "pubmed" not in called and "biorxiv" not in called
    assert ok == 5
    assert (tmp_path / "candidates.json").exists()
    assert (tmp_path / "raw_arxiv.json").exists()


def test_gather_resilient_to_one_source_failing(tmp_path, monkeypatch, config_dir):
    cfg = load_topics(config_dir / "topics.yml")
    cs = next(t for t in cfg.topics if t.id == "swe_ml_ai")

    def flaky(name, src, since, until):
        if name == "semantic_scholar":
            from scripts.lib.fetch_http import FetchError
            raise FetchError("429 rate limited")
        return [_paper(f"{name}1", f"{name} machine learning paper")]

    monkeypatch.setattr(g, "_fetch_source", flaky)
    n, ok = g.gather(cs, "2026-07-06", "2026-07-08", str(tmp_path),
                     topics_path=str(config_dir / "topics.yml"))
    assert ok == 4  # one failed, run continued
    assert not (tmp_path / "raw_semantic_scholar.json").exists()


def test_gather_raises_when_all_sources_fail(tmp_path, monkeypatch, config_dir):
    cfg = load_topics(config_dir / "topics.yml")
    cs = next(t for t in cfg.topics if t.id == "swe_ml_ai")

    def all_fail(name, src, since, until):
        from scripts.lib.fetch_http import FetchError
        raise FetchError("down")

    monkeypatch.setattr(g, "_fetch_source", all_fail)
    with pytest.raises(RuntimeError, match="all .* sources failed"):
        g.gather(cs, "2026-07-06", "2026-07-08", str(tmp_path),
                 topics_path=str(config_dir / "topics.yml"))


def test_main_unknown_topic_exits_2(tmp_path):
    rc = g.main(["--topic", "nope", "--out", str(tmp_path)])
    assert rc == 2


def test_gather_resilient_to_xml_parse_error(tmp_path, monkeypatch, config_dir):
    # A malformed XML source (e.g. PubMed 200 + HTML) must be skipped, not fatal.
    from xml.etree.ElementTree import ParseError
    cfg = load_topics(config_dir / "topics.yml")
    bio = next(t for t in cfg.topics if t.id == "bio_genetics_biomed")

    def flaky(name, src, since, until):
        if name == "pubmed":
            raise ParseError("not well-formed")
        return [_paper(f"{name}1", f"{name} genomics cancer paper")]

    monkeypatch.setattr(g, "_fetch_source", flaky)
    n, ok = g.gather(bio, "2026-07-06", "2026-07-08", str(tmp_path),
                     topics_path=str(config_dir / "topics.yml"))
    assert not (tmp_path / "raw_pubmed.json").exists()  # skipped, run continued
    assert ok >= 1


def test_main_success_path(tmp_path, monkeypatch, config_dir):
    # main() success: monkeypatch fetch so no network, run through the CLI.
    monkeypatch.setattr(
        g, "_fetch_source",
        lambda name, src, since, until: [_paper(f"{name}1", f"{name} machine learning llm")],
    )
    rc = g.main(["--topic", "swe_ml_ai", "--date", "2026-07-08",
                 "--out", str(tmp_path), "--topics", str(config_dir / "topics.yml")])
    assert rc == 0
    assert (tmp_path / "candidates.json").exists()


def test_main_all_sources_fail_exits_2(tmp_path, monkeypatch, config_dir):
    def all_fail(name, src, since, until):
        from scripts.lib.fetch_http import FetchError
        raise FetchError("down")
    monkeypatch.setattr(g, "_fetch_source", all_fail)
    rc = g.main(["--topic", "swe_ml_ai", "--date", "2026-07-08",
                 "--out", str(tmp_path), "--topics", str(config_dir / "topics.yml")])
    assert rc == 2
