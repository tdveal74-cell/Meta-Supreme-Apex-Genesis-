# DEVON code worker: deploy and prove

Ruled by Tee 2026-10-24: DEVON writes code through the Claude Agent SDK hosted
on a box of his own, separate from the n8n VPS. This directory is that worker. The Agent Runtime reaches it through
`code.task` and `code.status` (`services/code_worker`).

## What it does, in order

1. Takes one job: an allowlisted repository, a task, a base ref, a test command,
   a turn limit and a dollar limit.
2. Clones the repository into a fresh directory and checks out
   `devon/code-<job id>` from the base ref.
3. Runs the Agent SDK there with a test writer and a reviewer as subagents,
   `permission_mode` `dontAsk`, tools Read, Edit, Write, Glob, Grep, Bash and
   Task, and `git push`, `git remote`, `curl` and `wget` denied.
4. Runs the test command itself after the agent stops.
5. Pushes the branch and opens a DRAFT pull request carrying the test result
   and the estimated cost. A failing run is still opened, titled
   `[TESTS FAILING]`. It never merges and never pushes to the base ref.

## What only Tee can do

These are settings on a box and on a deployment, so they are his.

On DEVON's box, as a user that is not root:

```bash
sudo mkdir -p /opt/devon-code-worker && sudo chown "$USER" /opt/devon-code-worker
cp deploy/code-worker/worker.py deploy/code-worker/server.py deploy/code-worker/requirements.txt /opt/devon-code-worker/
cd /opt/devon-code-worker
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

`/etc/devon-code-worker.env`, mode 600:

```
DEVON_CODE_WORKER_KEY=<a long random value>
DEVON_CODE_WORKER_GITHUB_TOKEN=<fine-grained token: contents and pull requests, write, on the allowlisted repositories only>
DEVON_CODE_WORKER_REPOS=tdveal74-cell/Meta-Supreme-Apex-Genesis-
ANTHROPIC_API_KEY=<a key with a spend limit set in the Console>
```

Then install `devon-code-worker.service`, put it behind a reverse proxy with TLS
on that box (`devon.editforge.online`), and set on the API deployment:

```
DEVON_CODE_WORKER_URL=https://<the proxied host>
DEVON_CODE_WORKER_KEY=<the same value>
DEVON_CODE_WORKER_REPOS=tdveal74-cell/Meta-Supreme-Apex-Genesis-
```

## The one live proof

Nothing below has run. Every test in CI uses a fake agent and a recorded
GitHub. The proof is one real job, watched end to end:

1. `curl https://<host>/health` reads `key_set`, `github_token_set` and
   `agent_installed` all true.
2. In DEVON, an agent task with one `code.task` step: a one line change to a
   scratch file, `test_command` `python3 -m pytest -q test_devon_integrity.py`,
   `max_budget_usd` 1. Approve the card.
3. `code.status` reaches `done`, and the draft pull request it names exists,
   is a draft, targets `main`, and carries the test output.

Close that draft without merging. The receipt is the pull request URL.

## Residual risk, stated

The agent runs as the same Unix user as the worker. Its shell can therefore read
the worker's process environment through /proc, which holds the GitHub token
and `ANTHROPIC_API_KEY`, however carefully the agent's own environment is
blanked. What the worker does enforce: the token is never written to any config,
and the push and pull request are made from a second clone the agent never
touched, with hooks and local config disabled, so a planted hook or a rewritten
remote in the agent's tree gains nothing. What bounds the rest is yours: a fine
grained GitHub token with contents and pull request rights on the allowlisted
repositories only, a Console spend limit on the API key, `max_budget_usd` on
each job, and an allowlist of repositories whose content you trust. Running the
agent as a separate user is stage two of this box.
