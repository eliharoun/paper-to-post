"""Repo-root-anchored path resolution so scripts work from any working directory.

Everything resolves relative to this file's location (the installed/checked-out
repo), not the current working directory. Data and output locations can be
overridden with the DATA_DIR / OUTPUT_DIR environment variables.
"""
from __future__ import annotations

import os
from pathlib import Path

# scripts/lib/paths.py -> parents[2] == repo root
REPO_ROOT = Path(__file__).resolve().parents[2]


def config_dir() -> Path:
    return REPO_ROOT / "config"


def templates_dir() -> Path:
    return REPO_ROOT / "templates"


def _resolve(env_value: str | None, default: Path) -> Path:
    """Use the env value if set (absolute as-is, relative under repo root), else default."""
    if not env_value:
        return default
    p = Path(env_value)
    return p if p.is_absolute() else (REPO_ROOT / p)


def data_dir() -> Path:
    return _resolve(os.environ.get("DATA_DIR"), REPO_ROOT / "data")


def outputs_dir() -> Path:
    return _resolve(os.environ.get("OUTPUT_DIR"), REPO_ROOT / "outputs")


def topics_path() -> Path:
    return config_dir() / "topics.yml"


def ledger_path() -> Path:
    return data_dir() / "ledger.db"


def brand_path(account: str) -> Path:
    """Path to a per-account brand config, e.g. account='cs' -> config/brand.cs.yml."""
    return config_dir() / f"brand.{account}.yml"
