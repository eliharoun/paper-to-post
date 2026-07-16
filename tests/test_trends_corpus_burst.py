from datetime import date

from scripts.lib.config import CorpusBurstConfig, TopicConfig
from scripts.lib.trends.base import RunContext
from scripts.lib.trends.corpus_burst import CorpusBurstSignal
from scripts.lib.trends.history import TermHistory


def _topic():
    return TopicConfig(id="cs", enabled=True, display_name="CS", priority=1.0)


# distinct vocabulary so each cold paper's terms are unique (df=1 < min_doc_freq)
_VOCAB = ("alpha beta gamma delta epsilon zeta eta theta iota kappa mu nu "
          "apple bridge cloud dune ember frost grove harbor ivory jade koala "
          "lotus maple nectar opal pearl quartz river stone timber umbra violet "
          "walnut yarrow zephyr cedar birch willow cypress").split()


def _hot(i):
    # papers sharing the distinctive bigram "quantum annealing" (no stopwords)
    return {"title": "quantum annealing solver", "abstract": "",
            "source": "arxiv", "arxiv_id": f"h{i}"}


def _cold(i):
    # two unique words per paper -> df=1 per term -> below min_doc_freq
    return {"title": f"{_VOCAB[(2 * i) % len(_VOCAB)]} {_VOCAB[(2 * i + 1) % len(_VOCAB)]}",
            "abstract": "", "source": "arxiv", "arxiv_id": f"c{i}"}


def _corpus(hot_n, cold_n):
    return [_hot(i) for i in range(hot_n)] + [_cold(i) for i in range(cold_n)]


def _seed_history(tmp_path, terms):
    h = TermHistory(tmp_path / "term_history.json")
    for d in (13, 14):
        h.upsert("cs", date(2026, 7, d), n=100, df={t: 2 for t in terms})
    h.save()


def test_bursting_term_scores_higher_than_cold(tmp_path):
    cfg = CorpusBurstConfig(min_corpus=5, min_doc_freq=3)
    sig = CorpusBurstSignal(cfg)
    ctx = RunContext(topic_id="cs", today=date(2026, 7, 15), data_dir=tmp_path)
    _seed_history(tmp_path, ["quantum", "annealing", "quantum annealing",
                             "solver", "annealing solver"])
    corpus = _corpus(hot_n=20, cold_n=40)
    state = sig.prepare(corpus, _topic(), ctx)
    assert state.basis == "rolling"
    hot = sig.score(corpus[0], state)        # a hot paper (corpus member!)
    cold = sig.score(corpus[-1], state)      # a cold paper (unique terms)
    assert hot is not None and cold is not None
    assert 0.0 <= cold < hot <= 1.0


def test_cold_start_uses_cluster_basis(tmp_path):
    cfg = CorpusBurstConfig(min_corpus=5, min_doc_freq=3)
    sig = CorpusBurstSignal(cfg)
    ctx = RunContext(topic_id="cs", today=date(2026, 7, 15), data_dir=tmp_path)
    corpus = _corpus(hot_n=20, cold_n=40)    # no history file -> cold start
    state = sig.prepare(corpus, _topic(), ctx)
    assert state.basis == "cluster"
    cluster_paper = sig.score(corpus[0], state)   # shares a 20-paper cluster
    singleton = sig.score(corpus[-1], state)      # unique terms, df=1
    assert cluster_paper is not None and singleton is not None
    assert cluster_paper > singleton              # cluster prominence beats singleton


def test_tiny_corpus_returns_none(tmp_path):
    cfg = CorpusBurstConfig(min_corpus=30)
    sig = CorpusBurstSignal(cfg)
    ctx = RunContext(topic_id="cs", today=date(2026, 7, 15), data_dir=tmp_path)
    corpus = _corpus(2, 3)                    # only 5 papers
    state = sig.prepare(corpus, _topic(), ctx)
    assert state.basis == "insufficient_corpus"
    assert sig.score(corpus[0], state) is None


def test_persist_writes_history(tmp_path):
    cfg = CorpusBurstConfig(min_corpus=5)
    sig = CorpusBurstSignal(cfg)
    ctx = RunContext(topic_id="cs", today=date(2026, 7, 15), data_dir=tmp_path)
    state = sig.prepare(_corpus(20, 40), _topic(), ctx)
    sig.persist(state, ctx)
    assert (tmp_path / "term_history.json").exists()
    assert date(2026, 7, 15) in TermHistory(tmp_path / "term_history.json").dates("cs")


def test_trend_terms_reports_bursting_terms(tmp_path):
    cfg = CorpusBurstConfig(min_corpus=5, min_doc_freq=3, top_terms=5)
    sig = CorpusBurstSignal(cfg)
    ctx = RunContext(topic_id="cs", today=date(2026, 7, 15), data_dir=tmp_path)
    _seed_history(tmp_path, ["quantum", "quantum annealing"])
    corpus = _corpus(20, 40)
    state = sig.prepare(corpus, _topic(), ctx)
    terms = sig.terms_for(corpus[0], state)
    assert any("quantum" in t or "annealing" in t for t in terms)


def test_terms_for_is_deterministic_order(tmp_path):
    cfg = CorpusBurstConfig(min_corpus=5, min_doc_freq=3, top_terms=5)
    sig = CorpusBurstSignal(cfg)
    ctx = RunContext(topic_id="cs", today=date(2026, 7, 15), data_dir=tmp_path)
    _seed_history(tmp_path, ["quantum", "quantum annealing"])
    corpus = _corpus(20, 40)
    state = sig.prepare(corpus, _topic(), ctx)
    terms = sig.terms_for(corpus[0], state)
    assert terms == sig.terms_for(corpus[0], state)   # repeatable
    # already in deterministic (weight, term) order -> stable across processes
    assert terms == sorted(
        terms, key=lambda t: (state.term_weight.get(t, 0.0), t), reverse=True)


def test_determinism_same_inputs_same_percentiles(tmp_path):
    cfg = CorpusBurstConfig(min_corpus=5, min_doc_freq=3)
    ctx = RunContext(topic_id="cs", today=date(2026, 7, 15), data_dir=tmp_path)
    corpus = _corpus(20, 40)
    s1 = CorpusBurstSignal(cfg).prepare(corpus, _topic(), ctx)
    s2 = CorpusBurstSignal(cfg).prepare(corpus, _topic(), ctx)
    assert [s1.percentile[id(p)] for p in corpus] == [s2.percentile[id(p)] for p in corpus]
