"""The repobrief CLI: flags, exit codes, output targets."""

import json
import os
import subprocess
import sys

import pytest

from repobrief.cli import main
from repobrief.version import __version__

from conftest import NOW, requires_git


def run_cli(args, capsys):
    code = main(args)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_version_flag_prints_package_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"repobrief {__version__}"


def test_markdown_brief_on_directory(sample_repo, capsys):
    code, out, err = run_cli([str(sample_repo), "--no-git", "--now", str(NOW)], capsys)
    assert code == 0 and err == ""
    assert out.startswith("# Repo brief: acme-relay")
    assert "| `src/` |" in out  # layout table present


def test_json_flag_emits_parseable_json(sample_repo, capsys):
    code, out, _ = run_cli([str(sample_repo), "--json", "--no-git", "--now", str(NOW)], capsys)
    assert code == 0
    data = json.loads(out)
    assert data["name"] == "acme-relay" and data["git"] is None


def test_out_flag_writes_file_instead_of_stdout(sample_repo, tmp_path, capsys):
    target = tmp_path / "BRIEF.md"
    code, out, _ = run_cli(
        [str(sample_repo), "--no-git", "--now", str(NOW), "--out", str(target)], capsys
    )
    assert code == 0 and out == ""
    assert target.read_text(encoding="utf-8").startswith("# Repo brief:")


def test_bad_path_and_bad_options_exit_2(sample_repo, capsys):
    code, out, err = run_cli(["/no/such/dir/anywhere"], capsys)
    assert code == 2 and out == "" and "not a directory" in err
    code, _, err = run_cli([str(sample_repo), "--depth", "0"], capsys)
    assert code == 2 and "out of range" in err


@requires_git
def test_top_flag_limits_hot_file_rows(git_repo, capsys):
    code, out, _ = run_cli([str(git_repo), "--top", "1", "--now", str(NOW)], capsys)
    assert code == 0
    hot_rows = [l for l in out.splitlines() if l.startswith("| 1 | `")]
    assert len(hot_rows) == 1 and "core.py" in hot_rows[0]
    assert not any(l.startswith("| 2 | `") for l in out.splitlines())


@requires_git
def test_no_git_flag_suppresses_history(git_repo, capsys):
    code, out, _ = run_cli([str(git_repo), "--no-git", "--now", str(NOW)], capsys)
    assert code == 0
    assert "- **Git:** no history available" in out


def test_python_dash_m_invocation_matches_console_script(sample_repo):
    # One real subprocess round-trip: `python -m repobrief` is the documented
    # zero-install invocation, so it must work from a plain checkout.
    src = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
    env = dict(os.environ, PYTHONPATH=src + os.pathsep + os.environ.get("PYTHONPATH", ""))
    proc = subprocess.run(
        [sys.executable, "-m", "repobrief", str(sample_repo), "--no-git", "--now", str(NOW)],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0
    assert proc.stdout.startswith("# Repo brief: acme-relay")
