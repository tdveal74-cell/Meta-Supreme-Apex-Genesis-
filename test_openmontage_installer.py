"""The OpenMontage installer's guards, run offline.

`.claude/skills/openmontage/scripts/install.sh` fetches calesthio/OpenMontage at
one pinned commit and runs upstream's `make setup`. The guards are what protect
a checkout that may hold productions, and the gauntlet of 2026-10-31 found they
had no test. Every case here runs the script for real, with stub `make`, `npm`,
`npx`, `node`, `uv` and `ffmpeg` first on PATH, so nothing is downloaded and no
upstream code runs.

Every case that runs the installer runs the fixture copy described next, so a
regression that slips past a refusal fetches nothing from the network and
writes nothing into this repository. The refusal cases written first ran the
shipped script itself until the third critic of 2026-10-31 showed two of them
would reach GitHub on a regression, and one would write here. The copy's PIN
and REPO lines point at a local fixture repository, because the real pin can
only be fetched from GitHub. The copy is
made by replacing exactly those two lines, and the test fails if either line is
not found once, so the copy cannot drift from the shipped script unnoticed.
"""

import os
import pathlib
import shutil
import stat
import subprocess
import sys
import zipfile

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
if [ -z "${STUB_MAKE_NO_VENV:-}" ]; then
  mkdir -p "$dest/.venv/bin"
  ln -sf "$STUB_PYTHON" "$dest/.venv/bin/python"
fi
if [ -n "${STUB_MAKE_REGISTRY:-}" ]; then printf '%s\n' "$STUB_MAKE_REGISTRY" > "$dest/tools/tool_registry.py"; fi
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
    # Upstream's .gitignore ignores these, and an ignored .pyc still imports,
    # so the untracked check has to see ignored files as well.
    (work / ".gitignore").write_text("*.pyc\n__pycache__/\n")
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


def _inside_a_repository(script, tmp_path):
    """The fixture copy placed in a throwaway repository, as the shipped script
    sits in this one, so the guard is exercised and a regression writes nothing
    here."""
    repo = tmp_path / "a-repository"
    _git("init", "-q", str(repo))
    inner = repo / "scripts"
    inner.mkdir()
    shutil.copy(script, inner / "install.sh")
    shutil.copy(script.parent / "constraints.txt", inner / "constraints.txt")
    return inner / "install.sh", repo


def test_refuses_a_target_inside_the_repository(stubs, patched, tmp_path):
    env, record = stubs
    script, repo = _inside_a_repository(patched[0], tmp_path)
    dest = repo / "om"
    result = _run(script, env, dest)
    assert result.returncode == 3, result.stderr
    assert "is inside" in result.stderr
    assert not dest.exists()
    assert not record.exists()


def test_refuses_a_directory_that_is_not_a_checkout(stubs, patched, tmp_path):
    env, record = stubs
    dest = tmp_path / "plain"
    dest.mkdir()
    (dest / "keep.txt").write_text("someone's work")
    result = _run(patched[0], env, dest)
    assert result.returncode == 3, result.stderr
    assert "is not a git checkout" in result.stderr
    assert (dest / "keep.txt").read_text() == "someone's work"
    assert not record.exists(), "make ran on a refused target"


def test_refuses_a_checkout_with_another_origin(stubs, patched, tmp_path):
    env, record = stubs
    dest = tmp_path / "other"
    _git("init", "-q", str(dest))
    _git("commit", "-q", "--allow-empty", "-m", "x", cwd=dest)
    result = _run(patched[0], env, dest)
    assert result.returncode == 3, result.stderr
    assert "has origin 'none'" in result.stderr
    assert not record.exists()


def test_refuses_an_empty_repository_with_another_origin(stubs, patched, tmp_path):
    env, record = stubs
    dest = tmp_path / "empty"
    _git("init", "-q", str(dest))
    _git("remote", "add", "origin", "file:///nowhere/else.git", cwd=dest)
    result = _run(patched[0], env, dest)
    assert result.returncode == 3, result.stderr
    assert "else.git" in result.stderr
    assert not record.exists()


def test_refuses_an_openmontage_checkout_at_another_commit(stubs, patched, tmp_path):
    env, record = stubs
    script, repo, _ = patched
    dest = tmp_path / "moved"
    _git("init", "-q", str(dest))
    _git("remote", "add", "origin", repo, cwd=dest)
    _git("commit", "-q", "--allow-empty", "-m", "x", cwd=dest)
    result = _run(script, env, dest)
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
    assert "already at the pinned commit, with no change to a tracked file and nothing untracked that would load as code" in again.stdout
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
    assert shutil.which("timeout", path=env["PATH"]), "this test needs a timeout binary on PATH; without one the installer runs uncapped and says so"
    result = _run(script, env, tmp_path / "om", {"STUB_MAKE_SLEEP": "30", "OPENMONTAGE_SETUP_TIMEOUT": "1"})
    assert result.returncode == 124, result.stderr
    assert "ran past 1s" in result.stderr


def test_the_skill_names_the_commit_the_script_pins():
    pin = next(
        line.split('"')[1] for line in SCRIPT.read_text().splitlines() if line.startswith("PIN=")
    )
    text = (SKILL / "SKILL.md").read_text()
    # The full hash, once: a short prefix would still match after the PIN moved
    # to a commit that happened to share it, and SKILL.md names it in full.
    assert pin in text


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


def test_a_refusal_for_python_names_the_override(stubs, patched, tmp_path):
    """Found by the independent verifier of 2026-10-31: a machine with only
    python3.12 and no uv was refused with no hint that OPENMONTAGE_PYTHON
    exists. The refusal now names it."""
    env, record = stubs
    script, _, _ = patched
    bare = _narrow(env, tmp_path, "uv")
    result = _run(script, bare, tmp_path / "om", {"OPENMONTAGE_PYTHON": "3.99"})
    assert result.returncode == 3, result.stderr
    assert "needs uv, or a Python 3.99 or newer as python3.99, python3 or python" in result.stderr
    assert "OPENMONTAGE_PYTHON" in result.stderr
    assert not record.exists()


def test_the_install_prints_the_versions_it_found(stubs, patched, tmp_path):
    env, _ = stubs
    script, _, _ = patched
    stub_bin = pathlib.Path(env["PATH"].split(os.pathsep)[0])
    _executable(stub_bin / "uv", "#!/bin/sh\necho 'uv 0.9.7'\n")
    _executable(stub_bin / "ffmpeg", "#!/bin/sh\necho 'ffmpeg version 6.1.1 Copyright (c) the FFmpeg developers'\n")
    result = _run(script, env, tmp_path / "om")
    assert result.returncode == 0, result.stderr
    assert "==> Found node: 22; uv: uv 0.9.7; ffmpeg: 6.1.1" in result.stdout


def test_the_fetch_runs_under_the_time_limit(stubs, patched, tmp_path):
    """The fetch had no time limit while make setup had one. A recording
    timeout stub proves the fetch now goes through it with the same limit."""
    env, _ = stubs
    script, _, _ = patched
    stub_bin = pathlib.Path(env["PATH"].split(os.pathsep)[0])
    calls = tmp_path / "timeout-calls.txt"
    _executable(stub_bin / "timeout", f'#!/bin/sh\necho "$*" >> "{calls}"\nshift\nexec "$@"\n')
    result = _run(script, env, tmp_path / "om", {"OPENMONTAGE_SETUP_TIMEOUT": "77"})
    assert result.returncode == 0, result.stderr
    seen = calls.read_text().splitlines()
    assert any(line.startswith("77 git -C ") and " fetch " in line for line in seen), seen
    assert any(line.startswith("77 make -C ") for line in seen), seen


def _sysbin(tmp_path, python):
    """A bin directory holding only what the installer and its stubs call, with
    python3 pointing at the given interpreter and no python3.X beside it."""
    sysbin = tmp_path / "sysbin"
    sysbin.mkdir()
    for tool in ("bash", "sh", "git", "dirname", "env", "tee", "grep", "sed", "cut", "mkdir", "ln", "sleep", "cat"):
        found = shutil.which(tool)
        assert found, f"{tool} is needed by the installer or its stubs"
        (sysbin / tool).symlink_to(found)
    (sysbin / "python3").symlink_to(python)
    return sysbin


def _narrow(env, tmp_path, *drop):
    """The stub directory, with the named stubs removed, and the system tools
    the installer needs as symlinks, so the named tools are gone whatever this
    machine keeps in /usr/bin or /bin."""
    stub_bin = pathlib.Path(env["PATH"].split(os.pathsep)[0])
    for name in drop:
        (stub_bin / name).unlink()
    path = f"{stub_bin}{os.pathsep}{_sysbin(tmp_path, sys.executable)}"
    for name in drop:
        assert shutil.which(name, path=path) is None
    return dict(env, PATH=path)


def test_python3_without_uv_or_python3_x_is_accepted(stubs, patched, tmp_path):
    """Upstream's Makefile falls back to python3 when python3.X is absent and
    accepts any version at or above the one asked for. The first fixed
    installer refused that machine. Here 3.11 is asked for, python3 is this
    interpreter, nothing named python3.11 exists, and uv is gone; the install
    goes ahead. Where this interpreter is newer than 3.11 that is the newer
    python3 case; on CI's 3.11 it is the equal one. The warning has its own
    test below, which does not depend on the interpreter."""
    env, _ = stubs
    script, _, _ = patched
    narrow = _narrow(env, tmp_path, "uv")
    assert shutil.which("python3.11", path=narrow["PATH"]) is None
    result = _run(script, narrow, tmp_path / "om", {"OPENMONTAGE_PYTHON": "3.11"})
    assert result.returncode == 0, result.stderr
    here = "%d.%d" % sys.version_info[:2]
    assert ("constraints.txt was measured on 3.11" in result.stderr) == (here != "3.11"), result.stderr


@pytest.mark.parametrize("asked, warned", [("3.11", False), ("3.12", True)])
def test_a_venv_on_another_python_is_warned_about(stubs, patched, tmp_path, asked, warned):
    """With uv on PATH the venv gets the version asked for, so this needs no
    second interpreter and runs the same on every machine."""
    env, _ = stubs
    script, _, _ = patched
    result = _run(script, env, tmp_path / "om", {"OPENMONTAGE_PYTHON": asked})
    assert result.returncode == 0, result.stderr
    assert ("WARNING: the venv will use Python 3.12, from uv; constraints.txt was measured on 3.11" in result.stderr) == warned, result.stderr


def test_a_python_below_the_pins_is_refused(stubs, patched, tmp_path):
    env, record = stubs
    script, _, _ = patched
    result = _run(script, env, tmp_path / "om", {"OPENMONTAGE_PYTHON": "3.10"})
    assert result.returncode == 3, result.stderr
    assert "below 3.11" in result.stderr
    assert not record.exists()


@pytest.mark.parametrize("tool", ["node", "npm", "npx", "make"])
def test_a_missing_prerequisite_is_refused(stubs, patched, tmp_path, tool):
    """npm and npx were checked and node was not, so a missing node read
    "Node 0 found" and then "Found node: none"."""
    env, record = stubs
    script, _, _ = patched
    result = _run(script, _narrow(env, tmp_path, tool), tmp_path / "om")
    assert result.returncode == 3, result.stderr
    assert f"missing prerequisites: {tool}" in result.stderr
    assert not record.exists()


# Answers only the two calls the installer makes, so the version expression
# itself is pinned and a changed call reads as no Node at all.
NODE_20 = '#!/bin/sh\ncase "$*" in\n  \'-p process.versions.node.split(".")[0]\') echo 20 ;;\n  --version) echo v20.1.0 ;;\n  *) exit 1 ;;\nesac\n'


def test_an_old_node_is_warned_about(stubs, patched, tmp_path):
    env, _ = stubs
    script, _, _ = patched
    _executable(pathlib.Path(env["PATH"].split(os.pathsep)[0]) / "node", NODE_20)
    result = _run(script, env, tmp_path / "om")
    assert result.returncode == 0, result.stderr
    assert "Node 20 found; HyperFrames needs 22" in result.stderr
    assert "Found node: v20.1.0" in result.stdout


@pytest.mark.parametrize("value", ["0", "00", "000", "0900", "ten", "-5", "1.5"])
def test_a_time_limit_that_is_not_a_positive_number_is_refused(stubs, patched, tmp_path, value):
    """GNU timeout 0 switches the limit off while the script printed "at most 0s",
    and 00 is read the same way."""
    env, record = stubs
    script, _, _ = patched
    result = _run(script, env, tmp_path / "om", {"OPENMONTAGE_SETUP_TIMEOUT": value})
    assert result.returncode == 3, result.stderr
    assert "OPENMONTAGE_SETUP_TIMEOUT must be a whole number" in result.stderr
    assert not record.exists()


def test_no_timeout_binary_says_there_is_no_limit(stubs, patched, tmp_path):
    """Without a timeout binary nothing is capped; the script now says so in
    the line that used to print a cap it did not enforce."""
    env, _ = stubs
    script, _, _ = patched
    sysbin = _sysbin(tmp_path, shutil.which("python3"))
    narrow = dict(env, PATH=f"{env['PATH'].split(os.pathsep)[0]}{os.pathsep}{sysbin}")
    assert shutil.which("timeout", path=narrow["PATH"]) is None
    result = _run(script, narrow, tmp_path / "om")
    assert result.returncode == 0, result.stderr
    assert "timeout is not on PATH, so the fetch and make setup run with no time limit" in result.stderr
    assert "make setup with Python 3.11, no time limit" in result.stdout


def test_a_fetch_past_the_limit_says_so(stubs, patched, tmp_path):
    env, _ = stubs
    script, _, _ = patched
    stub_bin = pathlib.Path(env["PATH"].split(os.pathsep)[0])
    _executable(stub_bin / "timeout", '#!/bin/sh\ncase "$*" in *" fetch "*) exit 124 ;; esac\nshift\nexec "$@"\n')
    result = _run(script, env, tmp_path / "om")
    assert result.returncode == 124, result.stderr
    assert "FAILED: the fetch exited 124" in result.stderr


def test_a_path_with_whitespace_is_refused(stubs, patched, tmp_path):
    """pip splits PIP_CONSTRAINT on whitespace."""
    env, record = stubs
    script, _, _ = patched
    spaced = tmp_path / "with space"
    spaced.mkdir()
    shutil.copy(script, spaced / "install.sh")
    shutil.copy(script.parent / "constraints.txt", spaced / "constraints.txt")
    result = _run(spaced / "install.sh", env, tmp_path / "om")
    assert result.returncode == 3, result.stderr
    assert "has whitespace in it" in result.stderr
    assert not record.exists()


def test_runtime_unavailable_is_reported_as_degraded(stubs, patched, tmp_path):
    """The second alternative of the DEGRADED match had no test."""
    env, _ = stubs
    script, _, _ = patched
    result = _run(script, env, tmp_path / "om", {"STUB_MAKE_OUTPUT": "hyperframes_compose: runtime_available=False"})
    assert result.returncode == 4, result.stderr
    assert "DEGRADED" in result.stderr


def test_a_rerun_refuses_when_git_status_fails(stubs, patched, tmp_path):
    """The local changes check read git status in a substitution, so a failing
    status read as no changes and make ran over an unchecked tree."""
    env, record = stubs
    script, _, _ = patched
    dest = tmp_path / "om"
    assert _run(script, env, dest).returncode == 0
    record.unlink()
    (dest / ".git" / "index").write_bytes(b"not an index")
    result = _run(script, env, dest)
    assert result.returncode == 3, result.stderr
    assert "git status failed" in result.stderr
    assert not record.exists()


def test_a_rerun_refuses_untracked_python_under_tools(stubs, patched, tmp_path):
    """The registry imports every module under tools/, so an untracked .py
    there would run under the pinned name."""
    env, record = stubs
    script, _, _ = patched
    dest = tmp_path / "om"
    assert _run(script, env, dest).returncode == 0
    record.unlink()
    (dest / "tools" / "planted.py").write_text("print('ran')\n")
    result = _run(script, env, dest)
    assert result.returncode == 3, result.stderr
    assert "tools/planted.py" in result.stderr
    assert not record.exists()


def test_the_repository_guard_ignores_git_stderr(stubs, patched, tmp_path):
    """The guard captured git's stderr with its stdout, so any trace or warning
    on a successful call turned the path into nonsense and switched the guard
    off with no warning. GIT_TRACE writes to stderr on success. The script is a
    copy pointed at the local fixture, placed in a throwaway repository, so a
    regression fetches nothing from the network and writes nothing here."""
    env, record = stubs
    script, repo = _inside_a_repository(patched[0], tmp_path)
    target = repo / "om"
    result = _run(script, env, target, {"GIT_TRACE": "1"})
    assert result.returncode == 3, result.stderr
    assert "is inside" in result.stderr
    assert not target.exists()
    assert not record.exists()


def test_constraints_name_the_pin_the_script_fetches():
    """Nothing tied constraints.txt to the PIN; its header has to name it."""
    pin = next(line.split('"')[1] for line in SCRIPT.read_text().splitlines() if line.startswith("PIN="))
    header = "".join(line for line in (SCRIPT.parent / "constraints.txt").read_text().splitlines(True) if line.startswith("#"))
    assert pin in header


def test_a_rerun_with_git_writing_to_stderr_reuses_a_clean_checkout(stubs, patched, tmp_path):
    """The rerun checks captured git's stderr with its stdout and treated any
    output as a finding, so a trace or warning on a successful call refused a
    clean checkout as changed."""
    env, _ = stubs
    script, _, _ = patched
    dest = tmp_path / "om"
    assert _run(script, env, dest).returncode == 0
    again = _run(script, env, dest, {"GIT_TRACE": "1"})
    assert again.returncode == 0, again.stderr
    assert "already at the pinned commit" in again.stdout


@pytest.mark.parametrize("planted", [
    "tools/lone.pyc", "tools/native.so", "json.py", "lone.pyc", "native.so", "json/__init__.py",
    "json/__init__.pyc", "json/__init__.cpython-313-x86_64-linux-gnu.so",
])
def test_a_rerun_refuses_untracked_code_the_registry_or_make_would_load(stubs, patched, tmp_path, planted):
    """The registry imports sourceless .pyc and extension .so modules under
    tools/ as well as .py, and make runs python from the top of the checkout,
    where a stray json.py, .pyc, .so or package shadows the standard module."""
    env, record = stubs
    script, _, _ = patched
    dest = tmp_path / "om"
    assert _run(script, env, dest).returncode == 0
    record.unlink()
    (dest / planted).parent.mkdir(parents=True, exist_ok=True)
    (dest / planted).write_bytes(b"")
    result = _run(script, env, dest)
    assert result.returncode == 3, result.stderr
    assert planted in result.stderr
    assert not record.exists()


def _replace_venv_python(dest, text):
    venv_python = dest / ".venv" / "bin" / "python"
    venv_python.unlink()
    _executable(venv_python, text)


def test_an_existing_venv_is_the_python_reported(stubs, patched, tmp_path):
    """make setup reuses an existing .venv before it looks at uv or python, so
    the version check and the warning have to describe that venv. The stub
    answers the version probe as 3.12; make's stub relinks it before the
    registry loads."""
    env, _ = stubs
    script, _, _ = patched
    dest = tmp_path / "om"
    assert _run(script, env, dest).returncode == 0
    _replace_venv_python(dest, '#!/bin/sh\ncase "$2" in *print*) echo 3.12 ;; esac\nexit 0\n')
    again = _run(script, env, dest)
    assert again.returncode == 0, again.stderr
    assert "WARNING: the venv will use Python 3.12, the existing .venv" in again.stderr


def test_an_existing_venv_older_than_asked_is_refused(stubs, patched, tmp_path):
    env, record = stubs
    script, _, _ = patched
    dest = tmp_path / "om"
    assert _run(script, env, dest).returncode == 0
    record.unlink()
    _replace_venv_python(dest, "#!/bin/sh\nexit 1\n")
    result = _run(script, env, dest)
    assert result.returncode == 3, result.stderr
    assert "make setup would reuse it" in result.stderr
    assert not record.exists()


def test_a_missing_ffmpeg_is_warned_about(stubs, patched, tmp_path):
    env, _ = stubs
    script, _, _ = patched
    result = _run(script, _narrow(env, tmp_path, "ffmpeg"), tmp_path / "om")
    assert result.returncode == 0, result.stderr
    assert "WARNING: ffmpeg is not on PATH, so rendering will not work." in result.stderr


def test_refuses_a_checkout_git_cannot_read(stubs, patched, tmp_path):
    env, record = stubs
    script, _, _ = patched
    dest = tmp_path / "broken"
    (dest / ".git").mkdir(parents=True)
    result = _run(script, env, dest)
    assert result.returncode == 3, result.stderr
    assert "git cannot read" in result.stderr
    assert not record.exists()


def test_a_resumed_fetch_with_planted_code_fails_before_make(stubs, patched, tmp_path):
    """A repository with this origin and no commit is resumed. Files already
    in it stay beside the checkout, so the untracked check runs after the
    fetch too."""
    env, record = stubs
    script, repo, pin = patched
    dest = tmp_path / "om"
    _git("init", "-q", str(dest))
    _git("remote", "add", "origin", repo, cwd=dest)
    (dest / "tools").mkdir()
    (dest / "tools" / "planted.py").write_text("print('ran')\n")
    result = _run(script, env, dest)
    assert result.returncode == 1, result.stderr
    assert "FAILED:" in result.stderr and "tools/planted.py" in result.stderr
    assert _git("rev-parse", "HEAD", cwd=dest) == pin
    assert not record.exists(), "make ran over planted code"


def test_make_leaving_no_venv_python_exits_1(stubs, patched, tmp_path):
    env, _ = stubs
    script, _, _ = patched
    result = _run(script, env, tmp_path / "om", {"STUB_MAKE_NO_VENV": "1"})
    assert result.returncode == 1, result.stderr
    assert "FAILED: make setup finished but" in result.stderr


EMPTY_REGISTRY = """class R:
    def discover(self):
        pass

    def provider_menu(self):
        return {}


registry = R()"""


@pytest.mark.parametrize("registry, expected", [
    ("raise RuntimeError('registry blew up')", "FAILED: the tool registry did not load"),
    (EMPTY_REGISTRY, "FAILED: the registry discovered no tools"),
])
def test_a_registry_that_fails_exits_1_with_a_failed_line(stubs, patched, tmp_path, registry, expected):
    """A registry that crashed on import used to exit 1 with only a traceback,
    where the header promised a FAILED line."""
    env, _ = stubs
    script, _, _ = patched
    result = _run(script, env, tmp_path / "om", {"STUB_MAKE_REGISTRY": registry})
    assert result.returncode == 1, result.stderr
    assert expected in result.stderr


def _wheel(directory, name, version):
    """A minimal pure Python wheel, built here so pip needs no index."""
    dist = f"{name}-{version}.dist-info"
    with zipfile.ZipFile(directory / f"{name}-{version}-py3-none-any.whl", "w") as wheel:
        wheel.writestr(f"{name}/__init__.py", f"VERSION = {version!r}\n")
        wheel.writestr(f"{dist}/METADATA", f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n")
        wheel.writestr(f"{dist}/WHEEL", "Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
        wheel.writestr(f"{dist}/RECORD", "")


def _pip_install(tmp_path, wheels, constraint, target):
    env = dict(os.environ, PIP_NO_INDEX="1", PIP_FIND_LINKS=str(wheels), PIP_DISABLE_PIP_VERSION_CHECK="1")
    env.pop("PIP_CONSTRAINT", None)
    if constraint is not None:
        env["PIP_CONSTRAINT"] = str(constraint)
    return subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", "--target", str(target), "ompin"],
        env=env, capture_output=True, text=True, timeout=120,
    )


def test_pip_honours_the_constraint_file_the_installer_exports(tmp_path):
    """The installer hands pip constraints.txt through PIP_CONSTRAINT, and
    upstream's make setup installs with that venv's own pip (Makefile:5, :45).
    Nothing showed pip applying the variable. Offline: two local wheels, and
    the constraint alone decides which one lands. A path with a space is split,
    which is why the installer refuses to run from one."""
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    for version in ("1.0", "2.0"):
        _wheel(wheels, "ompin", version)
    constraints = tmp_path / "constraints.txt"
    constraints.write_text("ompin==1.0\n")

    pinned = _pip_install(tmp_path, wheels, constraints, tmp_path / "pinned")
    assert pinned.returncode == 0, pinned.stderr
    assert (tmp_path / "pinned" / "ompin-1.0.dist-info").is_dir()

    free = _pip_install(tmp_path, wheels, None, tmp_path / "free")
    assert free.returncode == 0, free.stderr
    assert (tmp_path / "free" / "ompin-2.0.dist-info").is_dir()

    spaced = tmp_path / "with space"
    spaced.mkdir()
    shutil.copy(constraints, spaced / "constraints.txt")
    split = _pip_install(tmp_path, wheels, spaced / "constraints.txt", tmp_path / "split")
    assert split.returncode != 0, split.stdout
    assert f"No such file or directory: '{tmp_path / 'with'}'" in split.stderr, split.stderr


def _marker_python(directory, marker):
    """An executable .venv/bin/python that leaves a marker when it runs."""
    venv_python = directory / ".venv" / "bin" / "python"
    venv_python.parent.mkdir(parents=True)
    _executable(venv_python, f'#!/bin/sh\necho ran >> "{marker}"\nexit 0\n')


def _not_a_checkout(tmp_path, script, env, repo):
    dest = tmp_path / "plain"
    dest.mkdir()
    return dest, "is not a git checkout"


def _other_origin(tmp_path, script, env, repo):
    dest = tmp_path / "other"
    _git("init", "-q", str(dest))
    _git("commit", "-q", "--allow-empty", "-m", "x", cwd=dest)
    return dest, "has origin 'none'"


def _other_commit(tmp_path, script, env, repo):
    dest = tmp_path / "moved"
    _git("init", "-q", str(dest))
    _git("remote", "add", "origin", repo, cwd=dest)
    _git("commit", "-q", "--allow-empty", "-m", "x", cwd=dest)
    return dest, "not the pinned"


def _installed_then(change):
    def make(tmp_path, script, env, repo):
        dest = tmp_path / "om"
        assert _run(script, env, dest).returncode == 0
        (pathlib.Path(env["STUB_RECORD"])).unlink()
        (dest / ".venv" / "bin" / "python").unlink()
        (dest / ".venv" / "bin").rmdir()
        (dest / ".venv").rmdir()
        return dest, change(dest)
    return make


def _local_change(dest):
    (dest / "Makefile").write_text("setup:\n\t@echo edited\n")
    return "local changes to tracked files"


def _untracked_code(dest):
    (dest / "tools" / "planted.py").write_text("print('ran')\n")
    return "files the pin does not carry"


@pytest.mark.parametrize("make_target", [
    _not_a_checkout, _other_origin, _other_commit,
    _installed_then(_local_change), _installed_then(_untracked_code),
], ids=["not-a-checkout", "other-origin", "other-commit", "local-change", "untracked-code"])
def test_a_refused_target_s_venv_is_never_run(stubs, patched, tmp_path, make_target):
    """Found by Codex on PR #452 and by the final check: the existing .venv's
    python ran before the target was shown to be OpenMontage, so a target the
    installer then refused had already had its code executed. Every refusal
    that looks at the target is covered, and each asserts which one fired, so
    a reordering that runs the venv before any of them turns a case red."""
    env, record = stubs
    script, repo, _ = patched
    dest, refusal = make_target(tmp_path, script, env, repo)
    marker = tmp_path / "ran.txt"
    _marker_python(dest, marker)
    result = _run(script, env, dest)
    assert result.returncode == 3, result.stderr
    assert refusal in result.stderr, result.stderr
    assert not marker.exists(), "the refused target's python ran"
    assert not record.exists()


def test_a_resumed_fetch_with_an_old_venv_fails_before_make(stubs, patched, tmp_path):
    """On the resume path the fetch has already happened when the .venv is
    checked, so an old one is a FAILED exit 1, not a refusal."""
    env, record = stubs
    script, repo, pin = patched
    dest = tmp_path / "om"
    _git("init", "-q", str(dest))
    _git("remote", "add", "origin", repo, cwd=dest)
    venv_python = dest / ".venv" / "bin" / "python"
    venv_python.parent.mkdir(parents=True)
    _executable(venv_python, "#!/bin/sh\nexit 1\n")
    result = _run(script, env, dest)
    assert result.returncode == 1, result.stderr
    assert "FAILED:" in result.stderr and "make setup would reuse it" in result.stderr
    assert _git("rev-parse", "HEAD", cwd=dest) == pin
    assert not record.exists()
