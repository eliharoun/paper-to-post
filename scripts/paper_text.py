#!/usr/bin/env python3
"""Extract the fullest available text for a selected paper.

Prefers full PDF body text (arXiv/open-access, where a PDF is fetchable); falls
back to the stored abstract otherwise. Prints JSON: {source, chars, text}.
So the skill can write from the whole paper, not just the abstract, when possible.
"""
from __future__ import annotations

import argparse
import json
import os

from scripts.lib.pdf import extract_text_from_pdf_bytes, fetch_pdf, pdf_url_for


def paper_text(paper: dict) -> dict:
    """Return {source: 'full_text'|'abstract'|'none', chars, text, url}."""
    if os.environ.get("ENABLE_FULL_TEXT", "true").lower() != "false":
        url = pdf_url_for(paper)
        if url:
            max_bytes = int(os.environ.get("PDF_MAX_BYTES", 52_428_800))
            timeout = int(os.environ.get("PDF_FETCH_TIMEOUT_SECONDS", 30))
            pdf_bytes = fetch_pdf(url, max_bytes=max_bytes, timeout=timeout)
            if pdf_bytes:
                text = extract_text_from_pdf_bytes(pdf_bytes)
                if text:
                    return {"source": "full_text", "chars": len(text),
                            "text": text, "url": url}

    abstract = paper.get("abstract")
    if abstract:
        return {"source": "abstract", "chars": len(abstract),
                "text": abstract, "url": paper.get("url")}
    return {"source": "none", "chars": 0, "text": "", "url": paper.get("url")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Extract full paper text (fallback: abstract)")
    ap.add_argument("--paper", required=True)
    ap.add_argument("--out", help="optional path to write the text to; else prints JSON")
    args = ap.parse_args(argv)

    with open(args.paper) as f:
        paper = json.load(f)
    result = paper_text(paper)

    if args.out:
        with open(args.out, "w") as f:
            f.write(result["text"])
        print(json.dumps({k: v for k, v in result.items() if k != "text"}
                         | {"out": args.out}))
    else:
        print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
