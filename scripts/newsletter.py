#!/usr/bin/env python3
"""Build an email-ready newsletter digest from a run's post bundles.

Unlike Instagram/LinkedIn (one publish per paper), the newsletter is a DIGEST:
it gathers every bundled post for a topic on a given day and emits a single
formatted document (Markdown + HTML) ready to paste into an email client. It
does not send anything — the artifact is the deliverable.

Input: the account's dated output dir (e.g. outputs/2026-07-08/cs), which holds
post1/, post2/, ... each with a post.json. Output: newsletter.md + newsletter.html
in that dir.

Content style here is intentionally minimal scaffolding; the per-channel writing
guidance lives in research-post-builder/references/newsletter-writing-guide.md
(subject line, preheader, per-item length, digest structure).
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

from scripts.lib.config import load_topics

_CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}


def _load_posts(account_dir: Path) -> list[dict]:
    """Load post.json from each postN/ subdir, ordered by N (selection order)."""
    posts = []
    for d in sorted(
        account_dir.glob("post*"),
        key=lambda p: int("".join(c for c in p.name if c.isdigit()) or 0),
    ):
        pj = d / "post.json"
        if pj.exists():
            posts.append(json.loads(pj.read_text()))
    return posts


def select_posts(
    posts: list[dict],
    *,
    max_posts: int | None = None,
    sort: str = "position",
    min_confidence: str = "",
) -> list[dict]:
    """Filter and order digest items per the newsletter channel config.

    - `min_confidence` drops items whose `confidence` ranks below the threshold
      (items with an unknown/missing confidence are kept — we don't guess-drop).
    - `sort` = "position" keeps selection order; "confidence" sorts high→low
      (stable, so ties keep selection order).
    - `max_posts` caps how many items the digest shows after filtering + sorting.
    """
    items = list(posts)
    if min_confidence:
        floor = _CONFIDENCE_RANK[min_confidence]
        items = [
            p for p in items
            if _CONFIDENCE_RANK.get(str(p.get("confidence", "")).lower(), floor) >= floor
        ]
    if sort == "confidence":
        items.sort(
            key=lambda p: _CONFIDENCE_RANK.get(str(p.get("confidence", "")).lower(), -1),
            reverse=True,
        )
    if max_posts is not None and max_posts >= 0:
        items = items[:max_posts]
    return items


def build_markdown(
    posts: list[dict],
    title: str,
    date_str: str,
    *,
    subject: str = "",
    preheader: str = "",
    intro: str = "",
    show_why_it_matters: bool = True,
    footer: str = "",
) -> str:
    # Subject/preheader are inbox metadata, not body copy — keep them as an HTML
    # comment at the top so the .md stays a clean paste while still carrying them.
    lines: list[str] = []
    if subject or preheader:
        lines.append("<!--")
        if subject:
            lines.append(f"Subject: {subject}")
        if preheader:
            lines.append(f"Preheader: {preheader}")
        lines += ["-->", ""]
    lines += [f"# {title}", "", f"_{date_str} · {len(posts)} papers_", ""]
    if intro:
        lines += [intro, ""]
    for i, p in enumerate(posts, 1):
        headline = p.get("plain_english_headline") or p.get("source_title", "")
        summary = p.get("one_sentence_summary") or p.get("why_it_matters", "")
        why = p.get("why_it_matters", "")
        url = p.get("source_url", "")
        lines += [f"## {i}. {headline}", "", summary, ""]
        # Only surface why-it-matters as its own line when it adds signal beyond
        # the summary (it's the summary fallback, so skip if identical).
        if show_why_it_matters and why and why != summary:
            lines += [f"**Why it matters:** {why}", ""]
        lines += [
            f"[Read the paper]({url})" if url else "",
            "",
            "---",
            "",
        ]
    if footer:
        lines += [footer, ""]
    return "\n".join(lines).rstrip() + "\n"


# Near-neutral colors chosen to survive dark-mode inversion rather than relying on
# a white background for contrast (see references/newsletter-writing-guide.md).
_BODY_COLOR = "#222"
_MUTED_COLOR = "#555"


def build_html(
    posts: list[dict],
    title: str,
    date_str: str,
    *,
    preheader: str = "",
    intro: str = "",
    show_why_it_matters: bool = True,
    footer: str = "",
) -> str:
    def esc(s: str) -> str:
        return html.escape(s or "")

    items = []
    for i, p in enumerate(posts, 1):
        headline = esc(p.get("plain_english_headline") or p.get("source_title", ""))
        summary = esc(p.get("one_sentence_summary") or p.get("why_it_matters", ""))
        why_raw = p.get("why_it_matters", "")
        url = esc(p.get("source_url", ""))
        link = f'<a href="{url}">Read the paper →</a>' if url else ""
        why_html = ""
        if show_why_it_matters and why_raw and why_raw != (p.get("one_sentence_summary") or ""):
            why_html = (
                f'<p style="margin:0 0 8px 0;font-size:15px;line-height:1.5;'
                f'color:{_BODY_COLOR}"><strong>Why it matters:</strong> {esc(why_raw)}</p>'
            )
        items.append(
            f'<div style="margin:0 0 28px 0">'
            f'<h2 style="margin:0 0 6px 0;font-size:18px;line-height:1.3">{i}. {headline}</h2>'
            f'<p style="margin:0 0 8px 0;font-size:15px;line-height:1.5;'
            f'color:{_BODY_COLOR}">{summary}</p>'
            f"{why_html}"
            f'<p style="margin:0;font-size:14px">{link}</p>'
            f"</div>"
        )
    body = "\n".join(items)
    # Hidden preheader: shown in the inbox preview, invisible in the opened email.
    preheader_html = ""
    if preheader:
        preheader_html = (
            '<div style="display:none;max-height:0;overflow:hidden;opacity:0;'
            f'color:transparent">{esc(preheader)}</div>'
        )
    intro_html = ""
    if intro:
        intro_html = (
            f'<p style="margin:0 0 24px 0;font-size:16px;line-height:1.5;'
            f'color:{_BODY_COLOR}">{esc(intro)}</p>'
        )
    footer_html = ""
    if footer:
        footer_html = (
            f'<p style="margin:28px 0 0 0;padding-top:16px;border-top:1px solid #ccc;'
            f'font-size:13px;color:{_MUTED_COLOR}">{esc(footer)}</p>'
        )
    return (
        f"{preheader_html}"
        '<div style="max-width:600px;margin:0 auto;font-family:-apple-system,'
        f'Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:{_BODY_COLOR}">'
        f'<h1 style="font-size:22px;margin:0 0 4px 0">{esc(title)}</h1>'
        f'<p style="margin:0 0 24px 0;color:{_MUTED_COLOR};font-size:14px">{esc(date_str)} · '
        f"{len(posts)} papers</p>"
        f"{intro_html}"
        f"{body}"
        f"{footer_html}"
        "</div>\n"
    )


def build_newsletter(
    account_dir: Path,
    title: str,
    date_str: str,
    *,
    subject: str = "",
    preheader: str = "",
    intro: str = "",
    max_posts: int | None = None,
    sort: str = "position",
    min_confidence: str = "",
    show_why_it_matters: bool = True,
    footer: str = "",
) -> tuple[Path, Path] | None:
    """Write newsletter.md + newsletter.html into account_dir. Returns paths, or
    None if there are no posts to digest (after filtering).

    `subject`/`preheader`/`intro` are optional LLM-authored inbox copy (see
    references/newsletter-writing-guide.md). The subject/preheader ride along as an
    HTML comment in the .md; the preheader is also injected as a hidden preview div
    in the .html; the intro renders as a one-line TL;DR under the header.

    `max_posts`/`sort`/`min_confidence` select and order the digest items;
    `show_why_it_matters` toggles the per-item line; `footer` renders a closing
    line. These come from the topic's newsletter publish target in config.
    """
    posts = select_posts(
        _load_posts(account_dir),
        max_posts=max_posts,
        sort=sort,
        min_confidence=min_confidence,
    )
    if not posts:
        return None
    md_path = account_dir / "newsletter.md"
    html_path = account_dir / "newsletter.html"
    md_path.write_text(
        build_markdown(
            posts, title, date_str,
            subject=subject, preheader=preheader, intro=intro,
            show_why_it_matters=show_why_it_matters, footer=footer,
        )
    )
    html_path.write_text(
        build_html(
            posts, title, date_str,
            preheader=preheader, intro=intro,
            show_why_it_matters=show_why_it_matters, footer=footer,
        )
    )
    return md_path, html_path


def _newsletter_config(topic_id: str):
    """Load the newsletter publish target (a config.PublishTarget) for a topic id,
    or None if the topic has no enabled newsletter channel / isn't found."""
    topics = load_topics()
    match = [t for t in topics.topics if t.id == topic_id]
    if not match:
        return None
    targets = match[0].publish_targets(channel="newsletter")
    return targets[0] if targets else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build an email newsletter digest from post bundles")
    ap.add_argument("--dir", required=True, help="account output dir, e.g. outputs/DATE/cs")
    ap.add_argument(
        "--title", default="",
        help="newsletter title (default: topic config, else 'Research Digest')",
    )
    ap.add_argument("--date", default="", help="date label shown in the header")
    ap.add_argument("--subject", default="", help="email subject line (LLM-authored, ≤~45 chars)")
    ap.add_argument(
        "--preheader",
        default="",
        help="inbox preview text (LLM-authored, ~40–90 chars, complements the subject)",
    )
    ap.add_argument(
        "--intro", default="", help="one-line TL;DR shown under the header (LLM-authored)"
    )
    # Granular digest controls. Defaults come from the topic's newsletter publish
    # target in config/topics.yml when --topic is given; CLI flags override config.
    ap.add_argument(
        "--topic", default="",
        help="topic id — reads its newsletter config from config/topics.yml",
    )
    ap.add_argument(
        "--max-posts", type=int, default=None,
        help="cap how many posts the digest shows (default: topic config, else all)",
    )
    ap.add_argument(
        "--sort", choices=["position", "confidence"], default=None,
        help="item order: 'position' (selection order) or 'confidence' (high→low)",
    )
    ap.add_argument(
        "--min-confidence", choices=["low", "medium", "high"], default=None,
        help="drop items below this confidence",
    )
    ap.add_argument(
        "--no-why-it-matters", action="store_true",
        help="omit the per-item 'Why it matters' line",
    )
    ap.add_argument("--footer", default="", help="optional closing footer line")
    args = ap.parse_args(argv)

    account_dir = Path(args.dir)
    if not account_dir.is_dir():
        print(f"not a directory: {account_dir}", file=sys.stderr)
        return 2

    # Resolve config defaults from the topic, then let CLI flags override.
    cfg = _newsletter_config(args.topic) if args.topic else None
    if args.topic and cfg is None:
        print(f"topic {args.topic!r} has no enabled newsletter channel in config", file=sys.stderr)
        return 2

    def pick(cli, cfg_val, default):
        return cli if cli is not None else (cfg_val if cfg is not None else default)

    title = args.title or (cfg.title if cfg and cfg.title else "") or "Research Digest"
    max_posts = pick(args.max_posts, cfg.max_posts if cfg else None, None)
    sort = pick(args.sort, cfg.sort if cfg else None, "position")
    min_confidence = pick(args.min_confidence, cfg.min_confidence if cfg else None, "")
    show_why = not args.no_why_it_matters and (cfg.show_why_it_matters if cfg else True)
    footer = args.footer or (cfg.footer if cfg else "")

    result = build_newsletter(
        account_dir,
        title,
        args.date,
        subject=args.subject,
        preheader=args.preheader,
        intro=args.intro,
        max_posts=max_posts,
        sort=sort,
        min_confidence=min_confidence,
        show_why_it_matters=show_why,
        footer=footer,
    )
    if result is None:
        print(f"no post bundles found in {account_dir} (after filtering)", file=sys.stderr)
        return 2
    md_path, html_path = result
    print(f"wrote {md_path} and {html_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
