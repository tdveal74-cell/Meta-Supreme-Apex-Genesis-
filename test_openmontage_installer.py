"""The OpenMontage installer's guards, run offline.

`.claude/skills/openmontage/scripts/install.sh` fetches calesthio/OpenMontage at
one pinned commit and runs upstream's `make setup`. The guards are what protect
a checkout that may hold productions, and the gauntlet of 2026-10-31 found they
had no test. Every case here runs the script for real, with stub `make`, `npm`,
`npx`, `node`, `uv` and `ffmpeg` first on PATH, so nothing is downloaded and no
upstream code runs.

The refusal cases run the shipped script itself. The cases that get as far as
`make setup` run a copy whose PIN and REPO lines point at a local fixture
repository, because the real pin can only be fetched from GitHub. The copy is
made by replacing exactly those two lines, and the test fails if either line is
not found once, so the copy cannot drift from the shipped script unnoticed.
"""

import os
import pathlib
import stat
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent
SKILL = ROOT / ".claude" / "skills" / "openmontage"
SCRIPT = SKILL / "scripts" / "install.sh"
REAL_REPO = "https://github.com/calesthio/OpenMontage.git"

STUB_MAKE = """#!/usr/bin/env bash
dest=""
args=""
while [ $# -gt 0 ]; do
  case "$1" in
    -C) dest="$2"; shift 2 ;;
    *) args="$args $1"; shift ;;
  esac
done
{
  echo "args:$args"
  echo "VIRTUAL_ENV=${VIRTUAL_ENV-unset}"
  echo "CONDA_PREFIX=${CONDA_PREFIX-unset}"
  echo "VENV_DIR=${VENV_DIR-unset}"
  echo "PIP_CONSTRAINT=${PIP_CONSTRAINT-unset}"
} > "$STUB_RECORD"
mkdir -p "$dest/.venv/bin"
ln -sf "$STUB_PYTHON" "$dest/.venv/bin/python"
if [ -n "${STUB_MAKE_OUTPUT:-}" ]; then echo "$STUB_MAKE_OUTPUT"; fi
if [ -n "${STUB_MAKE_SLEEP:-}" ]; then exec sleep "$STUB_MAKE_SLEEP"; fi
exit "${STUB_MAKE_EXIT:-0}"
"""

REGISTRY = """class _Registry:
    def discover(self):
        pass

    def provider_menu(self):
        return {
            "video": {"total": 3, "configured": 1},
            "audio": {"total": 2, "configured": 0},
        }


registry = _Registry()
"""


def _executable(path, text):
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _git(*args, cwd=None):
    return subprocess.run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", "-c", "commit.gpgsign=false", *args],
        cwd=cwd, check=True, capture_output=True, text=True,
    ).stdout.strip()


@pytest.fixture
def stubs(tmp_path):
    bin_dir = tmp_path / "stubbin"
    bin_dir.mkdir()
    _executable(bin_dir / "make", STUB_MAKE)
    _executable(bin_dir / "node", "#!/bin/sh\necho 22\n")
    for name in ("npm", "npx", "uv", "ffmpeg"):
        _executable(bin_dir / name, "#!/bin/sh\nexit 0\n")
    record = tmp_path / "make-record.txt"
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "HOME": str(tmp_path / "home"),
        "STUB_RECORD": str(record),
        "STUB_PYTHON": sys.executable,
    }
    (tmp_path / "home").mkdir()
    return env, record


@pytest.fixture
def fixture_repo(tmp_path):
    """A bare repository holding a minimal tools/tool_registry.py."""
    work = tmp_path / "upstream-work"
    (work / "tools").mkdir(parents=True)
    (work / "tools" / "__init__.py").write_text("")
    (work / "tools" / "tool_registry.py").write_text(REGISTRY)
    (work / "Makefile").write_text("setup:\n\t@echo real make never runs here\n")
    _git("init", "-q", str(work))
    _git("add", ".", cwd=work)
    _git("commit", "-q", "-m", "fixture", cwd=work)
    pin = _git("rev-parse", "HEAD", cwd=work)
    bare = tmp_path / "upstream.git"
    _git("clone", "-q", "--bare", str(work), str(bare))
    _git("config", "uploadpack.allowAnySHA1InWant", "true", cwd=bare)
    return f"file://{bare}", pin


@pytest.fixture
def patched(tmp_path, fixture_repo):
    """A copy of the shipped script pointed at the fixture repository."""
    repo, pin = fixture_repo
    text = SCRIPT.read_text()
    pin_line = next(line for line in text.splitlines() if line.startswith("PIN="))
    repo_line = f'REPO="{REAL_REPO}"'
    assert text.count(pin_line + "\n") == 1, "the PIN line moved; update this test"
    assert text.count(repo_line + "\n") == 1, "the REPO line moved; update this test"
    text = text.replace(pin_line + "\n", f'PIN="{pin}"\n')
    text = text.replace(repo_line + "\n", f'REPO="{repo}"\n')
    copy = tmp_path / "copy" / "install.sh"
    copy.parent.mkdir()
    copy.write_text(text)
    (copy.parent / "constraints.txt").write_text((SCRIPT.parent / "constraints.txt").read_text())
    return copy, repo, pin


def _run(script, env, dest, extra=None, timeout=60):
    full = dict(env, OPENMONTAGE_HOME=str(dest))
    full.update(extra or {})
    return subprocess.run(
        ["bash", str(script)], env=full, capture_output=True, text=True, timeout=timeout,
    )


def test_refuses_a_target_inside_the_repository(stubs):
    env, _ = stubs
    dest = ROOT / ".claude" / "worktrees" / "openmontage-installer-test-never-created"
    result = _run(SCRIPT, env, dest)
    assert result.returncode == 3, result.stderr
    assert "is inside" in result.stderr
    assert not dest.exists()


def test_refuses_a_directory_that_is_not_a_checkout(stubs, tmp_path):
    env, record = stubs
    dest = tmp_path / "plain"
    dest.mkdir()
    (dest / "keep.txt").write_text("someone's work")
    result = _run(SCRIPT, env, dest)
    assert result.returncode == 3, result.stderr
    assert "is not a git checkout" in result.stderr
    assert (dest / "keep.txt").read_text() == "someone's work"
    assert not record.exists(), "make ran on a refused target"


def test_refuses_a_checkout_with_another_origin(stubs, tmp_path):
    env, record = stubs
    dest = tmp_path / "other"
    _git("init", "-q", str(dest))
    _git("commit", "-q", "--allow-empty", "-m", "x", cwd=dest)
    result = _run(SCRIPT, env, dest)
    assert result.returncode == 3, result.stderr
    assert "has origin 'none'" in result.stderr
    assert not record.exists()


def test_refuses_an_empty_repository_with_another_origin(stubs, tmp_path):
    env, record = stubs
    dest = tmp_path / "empty"
    _git("init", "-q", str(dest))
    _git("remote", "add", "origin", "https://example.com/else.git", cwd=dest)
    result = _run(SCRIPT, env, dest)
    assert result.returncode == 3, result.stderr
    assert "else.git" in result.stderr
    assert not record.exists()


def test_refuses_an_openmontage_checkout_at_another_commit(stubs, tmp_path):
    env, record = stubs
    dest = tmp_path / "moved"
    _git("init", "-q", str(dest))
    _git("remote", "add", "origin", REAL_REPO, cwd=dest)
    _git("commit", "-q", "--allow-empty", "-m", "x", cwd=dest)
    result = _run(SCRIPT, env, dest)
    assert result.returncode == 3, result.stderr
    assert "not the pinned" in result.stderr
    assert not record.exists()


def test_origin_is_read_raw_so_insteadof_does_not_refuse_our_own_checkout(stubs, patched, tmp_path):
    env, _ = stubs
    script, repo, pin = patched
    dest = tmp_path / "om"
    assert _run(script, env, dest).returncode == 0
    gitconfig = tmp_path / "home" / ".gitconfig"
    gitconfig.write_text(f'[url "file:///nowhere/"]\n\tinsteadOf = {repo}\n')
    again = _run(script, env, dest)
    assert again.returncode == 0, again.stderr


def test_fresh_install_clears_the_callers_environment(stubs, patched, tmp_path):
    env, record = stubs
    script, _, pin = patched
    dest = tmp_path / "om"
    leaked = {"VIRTUAL_ENV": "/caller/venv", "CONDA_PREFIX": "/caller/conda", "VENV_DIR": "/caller/dir"}
    result = _run(script, env, dest, leaked)
    assert result.returncode == 0, result.stderr
    assert _git("rev-parse", "HEAD", cwd=dest) == pin
    seen = record.read_text()
    assert "VIRTUAL_ENV=unset" in seen
    assert "CONDA_PREFIX=unset" in seen
    assert "VENV_DIR=unset" in seen
    assert "PYTHON_VERSION=3.11" in seen
    assert "VENV_DIR=.venv" in seen
    assert f"PIP_CONSTRAINT={script.parent / 'constraints.txt'}" in seen
    assert "tool registry loaded: 5 tools in 2 capability groups, 1 usable now" in result.stdout
    assert f"OK: OpenMontage {pin} installed" in result.stdout
    assert (dest / "openmontage-setup.log").is_file()


def test_a_copy_outside_any_repository_says_the_guard_is_off(stubs, patched, tmp_path):
    env, _ = stubs
    script, _, _ = patched
    result = _run(script, env, tmp_path / "om")
    assert result.returncode == 0, result.stderr
    assert "inside-the-repository guard is off" in result.stderr


def test_a_rerun_reuses_a_clean_checkout(stubs, patched, tmp_path):
    env, _ = stubs
    script, _, pin = patched
    dest = tmp_path / "om"
    assert _run(script, env, dest).returncode == 0
    again = _run(script, env, dest)
    assert again.returncode == 0, again.stderr
    assert "already at the pinned commit, with no local changes" in again.stdout
    assert _git("rev-parse", "HEAD", cwd=dest) == pin


def test_a_rerun_refuses_local_changes_to_tracked_files(stubs, patched, tmp_path):
    env, record = stubs
    script, _, _ = patched
    dest = tmp_path / "om"
    assert _run(script, env, dest).returncode == 0
    record.unlink()
    (dest / "Makefile").write_text("setup:\n\t@echo edited\n")
    again = _run(script, env, dest)
    assert again.returncode == 3, again.stderr
    assert "local changes to tracked files" in again.stderr
    assert not record.exists(), "make ran over an edited checkout"


def test_resumes_an_interrupted_fetch(stubs, patched, tmp_path):
    env, _ = stubs
    script, repo, pin = patched
    dest = tmp_path / "om"
    _git("init", "-q", str(dest))
    _git("remote", "add", "origin", repo, cwd=dest)
    result = _run(script, env, dest)
    assert result.returncode == 0, result.stderr
    assert "Resuming an interrupted fetch" in result.stdout
    assert _git("rev-parse", "HEAD", cwd=dest) == pin


def test_an_upstream_skip_is_reported_as_degraded(stubs, patched, tmp_path):
    env, _ = stubs
    script, _, _ = patched
    result = _run(script, env, tmp_path / "om", {"STUB_MAKE_OUTPUT": "  [skip] piper-tts install failed"})
    assert result.returncode == 4, result.stderr
    assert "DEGRADED" in result.stderr
    assert "piper-tts install failed" in result.stderr
    assert "OK:" not in result.stdout


def test_a_failing_make_setup_keeps_its_exit_code(stubs, patched, tmp_path):
    env, _ = stubs
    script, _, _ = patched
    result = _run(script, env, tmp_path / "om", {"STUB_MAKE_EXIT": "2"})
    assert result.returncode == 2, result.stderr
    assert "FAILED: make setup exited 2" in result.stderr


def test_make_setup_is_stopped_at_the_time_limit(stubs, patched, tmp_path):
    env, _ = stubs
    script, _, _ = patched
    result = _run(script, env, tmp_path / "om", {"STUB_MAKE_SLEEP": "30", "OPENMONTAGE_SETUP_TIMEOUT": "1"})
    assert result.returncode == 124, result.stderr
    assert "ran past 1s" in result.stderr


def test_the_skill_names_the_commit_the_script_pins():
    pin = next(
        line.split('"')[1] for line in SCRIPT.read_text().splitlines() if line.startswith("PIN=")
    )
    assert pin[:7] in (SKILL / "SKILL.md").read_text()


def test_refuses_to_run_without_its_constraints(stubs, patched, tmp_path):
    env, record = stubs
    script, _, _ = patched
    (script.parent / "constraints.txt").unlink()
    result = _run(script, env, tmp_path / "om")
    assert result.returncode == 3, result.stderr
    assert "constraints.txt is missing" in result.stderr
    assert not (tmp_path / "om").exists()
    assert not record.exists()


def test_constraints_pin_every_package_exactly():
    lines = [
        line for line in (SCRIPT.parent / "constraints.txt").read_text().splitlines()
        if line and not line.startswith("#")
    ]
    assert lines, "constraints.txt pins nothing"
    loose = [line for line in lines if "==" not in line]
    assert not loose, f"not pinned to one version: {loose}"


def test_the_echoed_recipe_line_is_not_a_skip(stubs, patched, tmp_path):
    """make prints this recipe line before running it on every install. The first
    version of the skip check matched it and called a full install DEGRADED,
    which a real install on 2026-10-31 showed."""
    env, _ = stubs
    script, _, pin = patched
    echoed = '.venv/bin/python -m pip install piper-tts || echo "  [skip] piper-tts install failed"'
    result = _run(script, env, tmp_path / "om", {"STUB_MAKE_OUTPUT": echoed})
    assert result.returncode == 0, result.stderr
    assert f"OK: OpenMontage {pin} installed" in result.stdout
