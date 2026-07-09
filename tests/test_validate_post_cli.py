import json
from pathlib import Path

from scripts.validate_post import main

FIX = Path(__file__).parent / "fixtures"


def _write(tmp_path, post_overrides=None):
    post = json.loads((FIX / "good_post.json").read_text())
    if post_overrides:
        post.update(post_overrides)
    ppath = tmp_path / "post.json"
    ppath.write_text(json.dumps(post))
    paper_path = tmp_path / "paper.json"
    paper_path.write_text((FIX / "good_paper.json").read_text())
    return ppath, paper_path


def test_cli_exit_0_on_valid(tmp_path, capsys):
    ppath, paper_path = _write(tmp_path)
    rc = main(["--post", str(ppath), "--paper", str(paper_path),
               "--account", "cs"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["passed"] is True


def test_cli_exit_1_on_invalid(tmp_path, capsys):
    ppath, paper_path = _write(tmp_path, {"caption": "no link here"})
    rc = main(["--post", str(ppath), "--paper", str(paper_path),
               "--account", "cs"])
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["passed"] is False
    assert out["errors"]
