import json

from scripts.newsletter import build_html, build_markdown, build_newsletter, select_posts


def _post(headline, summary, url, confidence="high"):
    return {
        "plain_english_headline": headline,
        "one_sentence_summary": summary,
        "source_url": url,
        "source_title": headline,
        "confidence": confidence,
    }


POSTS = [
    _post("Models know their remaining length", "A probe reads it from hidden states.",
          "https://arxiv.org/abs/1"),
    _post("Web agents resist injection", "A masking layer blocks prompt injection.",
          "https://arxiv.org/abs/2"),
]


def test_build_markdown_has_each_paper_and_link():
    md = build_markdown(POSTS, "Daily CS Bits", "2026-07-08")
    assert "# Daily CS Bits" in md
    assert "2 papers" in md
    assert "1. Models know their remaining length" in md
    assert "2. Web agents resist injection" in md
    assert "(https://arxiv.org/abs/1)" in md


def test_build_html_escapes_and_links():
    posts = [_post("A <b>bold</b> title", "Summary & stuff", "https://x/1")]
    h = build_html(posts, "T", "2026-07-08")
    assert "&lt;b&gt;bold&lt;/b&gt;" in h        # headline escaped
    assert "Summary &amp; stuff" in h
    assert 'href="https://x/1"' in h


def test_build_newsletter_writes_both_files(tmp_path):
    for i, p in enumerate(POSTS, 1):
        d = tmp_path / f"post{i}"
        d.mkdir()
        (d / "post.json").write_text(json.dumps(p))
    result = build_newsletter(tmp_path, "Daily CS Bits", "2026-07-08")
    assert result is not None
    md_path, html_path = result
    assert md_path.exists() and html_path.exists()
    assert "Web agents" in md_path.read_text()


def test_build_newsletter_orders_by_post_number(tmp_path):
    # create out of order to prove numeric (not lexical) sort: post2, post10
    (tmp_path / "post2").mkdir()
    (tmp_path / "post2" / "post.json").write_text(json.dumps(_post("second", "s", "u2")))
    (tmp_path / "post10").mkdir()
    (tmp_path / "post10" / "post.json").write_text(json.dumps(_post("tenth", "s", "u10")))
    md_path, _ = build_newsletter(tmp_path, "T", "d")
    md = md_path.read_text()
    assert md.index("second") < md.index("tenth")  # post2 before post10


def test_build_newsletter_none_when_empty(tmp_path):
    assert build_newsletter(tmp_path, "T", "d") is None


def test_subject_and_preheader_in_markdown_comment():
    md = build_markdown(POSTS, "T", "d", subject="Shrink the KV cache 8×",
                        preheader="Plus: a probe that predicts failure")
    assert "<!--" in md
    assert "Subject: Shrink the KV cache 8×" in md
    assert "Preheader: Plus: a probe that predicts failure" in md


def test_intro_renders_in_both_formats():
    intro = "Two from CS today — start with the length probe."
    md = build_markdown(POSTS, "T", "d", intro=intro)
    h = build_html(POSTS, "T", "d", intro=intro)
    assert intro in md
    assert intro in h


def test_hidden_preheader_div_in_html():
    h = build_html(POSTS, "T", "d", preheader="teaser text here")
    assert "display:none" in h
    assert "teaser text here" in h


def test_why_it_matters_line_when_distinct():
    posts = [{
        "plain_english_headline": "H",
        "one_sentence_summary": "What they found.",
        "why_it_matters": "Cheaper inference at scale.",
        "source_url": "https://x/1",
    }]
    md = build_markdown(posts, "T", "d")
    h = build_html(posts, "T", "d")
    assert "Why it matters:" in md and "Cheaper inference at scale." in md
    assert "Why it matters:" in h and "Cheaper inference at scale." in h


def test_why_it_matters_suppressed_when_equal_to_summary():
    # why_it_matters is the summary fallback; don't print it twice.
    posts = [{
        "plain_english_headline": "H",
        "one_sentence_summary": "Same text.",
        "why_it_matters": "Same text.",
        "source_url": "https://x/1",
    }]
    md = build_markdown(posts, "T", "d")
    assert "Why it matters:" not in md


def test_main_passes_new_args(tmp_path):
    from scripts.newsletter import main
    d = tmp_path / "post1"
    d.mkdir()
    (d / "post.json").write_text(json.dumps(_post("H", "S", "https://x/1")))
    rc = main(["--dir", str(tmp_path), "--title", "T", "--subject", "Subj",
               "--preheader", "Pre", "--intro", "Intro line"])
    assert rc == 0
    assert "Subject: Subj" in (tmp_path / "newsletter.md").read_text()
    assert "Intro line" in (tmp_path / "newsletter.html").read_text()


# ---- granular digest config: select_posts + wiring ------------------------

def _mk(url, conf):
    return _post(f"H {url}", f"S {url}", url, confidence=conf)


def test_select_posts_max_posts_caps():
    posts = [_mk("1", "high"), _mk("2", "high"), _mk("3", "high")]
    assert len(select_posts(posts, max_posts=2)) == 2


def test_select_posts_min_confidence_drops_below_floor():
    posts = [_mk("1", "low"), _mk("2", "medium"), _mk("3", "high")]
    kept = select_posts(posts, min_confidence="medium")
    assert [p["source_url"] for p in kept] == ["2", "3"]


def test_select_posts_sort_confidence_high_first():
    posts = [_mk("1", "low"), _mk("2", "high"), _mk("3", "medium")]
    ordered = select_posts(posts, sort="confidence")
    assert [p["source_url"] for p in ordered] == ["2", "3", "1"]


def test_select_posts_position_is_default_stable_order():
    posts = [_mk("1", "low"), _mk("2", "high")]
    assert [p["source_url"] for p in select_posts(posts)] == ["1", "2"]


def test_select_posts_combines_filter_sort_cap():
    posts = [_mk("1", "low"), _mk("2", "high"), _mk("3", "medium"), _mk("4", "high")]
    kept = select_posts(posts, min_confidence="medium", sort="confidence", max_posts=2)
    # low dropped; remaining sorted high→low; capped to 2 → the two highs (stable)
    assert [p["source_url"] for p in kept] == ["2", "4"]


def test_show_why_it_matters_false_omits_line():
    posts = [{
        "plain_english_headline": "H", "one_sentence_summary": "Sum.",
        "why_it_matters": "Distinct payoff.", "source_url": "https://x/1",
    }]
    md = build_markdown(posts, "T", "d", show_why_it_matters=False)
    h = build_html(posts, "T", "d", show_why_it_matters=False)
    assert "Why it matters:" not in md and "Why it matters:" not in h


def test_footer_rendered_in_both():
    md = build_markdown(POSTS, "T", "d", footer="Forward it along.")
    h = build_html(POSTS, "T", "d", footer="Forward it along.")
    assert "Forward it along." in md and "Forward it along." in h


def test_build_newsletter_applies_selection(tmp_path):
    for i, conf in enumerate(["low", "high", "medium"], 1):
        d = tmp_path / f"post{i}"
        d.mkdir()
        (d / "post.json").write_text(json.dumps(_mk(str(i), conf)))
    md_path, _ = build_newsletter(
        tmp_path, "T", "d", min_confidence="medium", sort="confidence", max_posts=1
    )
    md = md_path.read_text()
    assert "1 papers" in md            # capped to 1 after filtering low
    assert "S 2" in md                 # the single high-confidence item
    assert "S 1" not in md             # low dropped


def test_build_newsletter_none_when_filter_empties(tmp_path):
    d = tmp_path / "post1"
    d.mkdir()
    (d / "post.json").write_text(json.dumps(_mk("1", "low")))
    assert build_newsletter(tmp_path, "T", "d", min_confidence="high") is None


def test_main_reads_topic_config(tmp_path, monkeypatch):
    # --topic pulls newsletter options (title, min_confidence, footer) from the
    # topic's newsletter publish target. The shipped config is Instagram-only
    # (newsletter commented out), so we inject a topic with a newsletter target to
    # exercise the config-resolution code path independent of the channel lineup.
    import scripts.newsletter as nl
    from scripts.lib.config import PublishTarget, TopicConfig, TopicsConfig

    topic = TopicConfig(
        id="demo_topic", enabled=True, account="cs", display_name="Demo", priority=1.0,
        publish=[PublishTarget(
            channel="newsletter", max_posts=10, title="Daily CS Bits",
            sort="confidence", min_confidence="medium",
            footer="Know someone who'd find this useful? Forward it along.",
        )],
    )
    monkeypatch.setattr(nl, "load_topics", lambda: TopicsConfig(topics=[topic]))

    for i, conf in enumerate(["low", "high"], 1):
        d = tmp_path / f"post{i}"
        d.mkdir()
        (d / "post.json").write_text(json.dumps(_mk(str(i), conf)))
    rc = nl.main(["--dir", str(tmp_path), "--topic", "demo_topic", "--date", "d"])
    assert rc == 0
    md = (tmp_path / "newsletter.md").read_text()
    assert "Daily CS Bits" in md       # title from config
    assert "S 1" not in md             # low dropped by config min_confidence=medium
    assert "Forward it along" in md    # footer from config


def test_main_unknown_topic_newsletter_exits_2(tmp_path):
    from scripts.newsletter import main
    d = tmp_path / "post1"
    d.mkdir()
    (d / "post.json").write_text(json.dumps(_mk("1", "high")))
    assert main(["--dir", str(tmp_path), "--topic", "bio_genetics_biomed"]) == 2


def test_main_not_a_directory_exits_2(tmp_path):
    from scripts.newsletter import main
    assert main(["--dir", str(tmp_path / "nope"), "--title", "T"]) == 2


def test_main_no_bundles_exits_2(tmp_path):
    from scripts.newsletter import main
    assert main(["--dir", str(tmp_path), "--title", "T"]) == 2  # empty dir, no post*/
