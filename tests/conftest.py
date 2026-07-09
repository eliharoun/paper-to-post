from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CONFIG_DIR = REPO / "config"


@pytest.fixture
def config_dir() -> Path:
    return CONFIG_DIR
