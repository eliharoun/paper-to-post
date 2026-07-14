from scripts.lib import paths
from scripts.lib.config import (
    load_brand,
    load_brand_for_account,
    load_topics,
    resolve_brand,
)


def test_load_brand(config_dir):
    b = load_brand(config_dir / "brand.cs.yml")
    assert b.canvas_width == 1080 and b.canvas_height == 1350
    assert b.min_cards == 5 and b.max_cards == 7
    assert b.palette.card_type_colors["limitation"] == "#F87171"


def test_load_topics_enabled_only(config_dir):
    t = load_topics(config_dir / "topics.yml")
    ids = [x.id for x in t.enabled_topics()]
    assert "swe_ml_ai" in ids
    assert "bio_genetics_biomed" in ids
    assert t.lookback_hours == 48


def test_biomed_topic_has_guardrails_and_biomed_sources(config_dir):
    t = load_topics(config_dir / "topics.yml")
    bio = next(x for x in t.topics if x.id == "bio_genetics_biomed")
    assert bio.requires_health_guardrails is True
    assert bio.sources.pubmed is not None and bio.sources.pubmed.query  # PubMed configured
    assert "biorxiv" in bio.sources.biorxiv.servers


def test_topic_sources_active_lists_only_configured(config_dir):
    t = load_topics(config_dir / "topics.yml")
    cs = next(x for x in t.topics if x.id == "swe_ml_ai")
    bio = next(x for x in t.topics if x.id == "bio_genetics_biomed")
    # cs runs labs; bio does not. bio runs pubmed/biorxiv; cs does not.
    assert "labs" in cs.sources.active()
    assert "pubmed" not in cs.sources.active()
    assert "pubmed" in bio.sources.active() and "biorxiv" in bio.sources.active()
    assert "labs" not in bio.sources.active()
    assert cs.sources.arxiv.categories and "cs.CR" in cs.sources.arxiv.categories
    assert "1702" in cs.sources.openalex.subfields


def test_topic_publish_targets(config_dir):
    t = load_topics(config_dir / "topics.yml")
    cs = next(x for x in t.topics if x.id == "swe_ml_ai")
    ig = cs.publish_targets("instagram")
    assert len(ig) == 1
    assert ig[0].alias == "DailyCSBits" and ig[0].username == "dailycsbits"
    # Volume is a per-channel decision via max_posts.
    assert ig[0].max_posts == 5
    # The shipped config is Instagram-only; newsletter/linkedin are commented out.
    assert cs.publish_targets("newsletter") == []
    assert cs.publish_targets("linkedin") == []


def test_topic_keywords_present(config_dir):
    t = load_topics(config_dir / "topics.yml")
    cs = next(x for x in t.topics if x.id == "swe_ml_ai")
    assert "llm" in cs.keywords and "machine learning" in cs.keywords


def test_topics_map_to_accounts():
    t = load_topics()  # path-independent default
    assert t.for_account("cs")[0].id == "swe_ml_ai"
    assert t.for_account("bio")[0].id == "bio_genetics_biomed"


def test_per_account_brand_names():
    assert load_brand_for_account("cs").account_name == "Daily CS Bits"
    assert load_brand_for_account("bio").account_name == "Daily Biology Bits"


def test_resolve_motif_single_and_list():
    from scripts.lib.config import BrandConfig
    palette = {"background": "#000", "surface": "#111", "text_primary": "#fff",
               "text_muted": "#999", "accent": "#0ff", "card_type_colors": {}}
    base = dict(account_name="X", footer_text="", canvas_width=1080, canvas_height=1350,
                margin=90, max_cards=7, min_cards=5, jpeg_quality=92,
                fonts={}, type_scale={}, palette=palette)
    single = BrandConfig(motif="helix", **base)
    assert single.resolve_motif("2026-07-01") == "helix"
    rot = BrandConfig(motif=["a", "b", "c"], **base)
    # same key -> stable; different keys can differ; always in the list
    assert rot.resolve_motif("2026-07-01") in {"a", "b", "c"}
    assert rot.resolve_motif("2026-07-01") == rot.resolve_motif("2026-07-01")
    assert BrandConfig(motif=[], **base).resolve_motif("x") == "none"


def test_account_brands_have_motifs():
    # configured as rotation lists
    assert isinstance(load_brand_for_account("cs").motif, list)
    assert "circuit" in load_brand_for_account("cs").motif
    assert "helix" in load_brand_for_account("bio").motif


def test_resolve_brand_precedence(config_dir):
    # explicit path wins over account
    b = resolve_brand(brand_path=str(config_dir / "brand.bio.yml"), account="cs")
    assert b.account_name == "Daily Biology Bits"
    assert resolve_brand(account="cs").account_name == "Daily CS Bits"


def test_paths_are_repo_anchored_not_cwd():
    # resolves off the file location, so it holds regardless of CWD
    assert paths.config_dir().name == "config"
    assert paths.brand_path("cs").name == "brand.cs.yml"
    assert paths.topics_path().exists()


def test_publish_targets_channel_none_and_disabled():
    from scripts.lib.config import PublishTarget, TopicConfig
    t = TopicConfig(
        id="x", enabled=True, display_name="X", priority=1.0,
        publish=[
            PublishTarget(channel="instagram", alias="a", username="u"),
            PublishTarget(channel="linkedin", enabled=False),
            PublishTarget(channel="newsletter"),
        ],
    )
    # channel=None returns all ENABLED targets (linkedin filtered out)
    chans = [c.channel for c in t.publish_targets()]
    assert chans == ["instagram", "newsletter"]
    # explicit channel filter
    assert t.publish_targets("instagram")[0].alias == "a"
    assert t.publish_targets("linkedin") == []  # disabled


def test_max_posts_needed_is_greediest_channel():
    from scripts.lib.config import PublishTarget, TopicConfig

    def topic(*targets):
        return TopicConfig(
            id="x", enabled=True, display_name="X", priority=1.0, publish=list(targets)
        )

    # greediest cap wins
    t = topic(
        PublishTarget(channel="instagram", max_posts=5),
        PublishTarget(channel="linkedin", max_posts=3),
        PublishTarget(channel="newsletter", max_posts=10),
    )
    assert t.max_posts_needed() == 10
    # any uncapped enabled channel -> produce all (None)
    t2 = topic(
        PublishTarget(channel="instagram", max_posts=5),
        PublishTarget(channel="newsletter"),   # no cap
    )
    assert t2.max_posts_needed() is None
    # a disabled uncapped channel doesn't force None
    t3 = topic(
        PublishTarget(channel="instagram", max_posts=5),
        PublishTarget(channel="linkedin", enabled=False),  # uncapped but disabled
    )
    assert t3.max_posts_needed() == 5
    # no enabled channels -> None
    assert topic().max_posts_needed() is None


def test_hero_style_parsing(config_dir):
    b = load_brand(config_dir / "brand.cs.yml")
    assert b.hero_style is not None
    assert b.hero_style.enabled is True
    assert b.hero_style.aspect_ratio == "4:5"
    assert b.hero_style.image_model  # non-empty model id
    assert b.hero_style.style        # non-empty descriptor


def test_hero_style_absent_is_none():
    from scripts.lib.config import BrandConfig
    data = dict(
        account_name="x", footer_text="", canvas_width=1080, canvas_height=1350,
        margin=90, max_cards=7, min_cards=5, jpeg_quality=92,
        fonts={"heading": "Inter", "body": "Inter"}, type_scale={"title_px": 84},
        palette={"background": "#000", "surface": "#111", "text_primary": "#fff",
                 "text_muted": "#aaa", "accent": "#38BDF8", "card_type_colors": {}},
    )
    assert BrandConfig(**data).hero_style is None
