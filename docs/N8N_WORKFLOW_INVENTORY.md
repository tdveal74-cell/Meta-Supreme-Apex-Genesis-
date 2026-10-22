# Owner-bound self-hosted workflow discovery

`GET /api/v1/n8n/workflows` enumerates current workflow metadata from
`https://n8n.editforge.online`. The authenticated conversation tool
`n8n.workflow_inventory` uses the same service and can find workflows added after
the historical vault map was written. Neither surface executes workflows or
changes the effect allowlist. The task runtime catalog is unchanged.

## Account and instance binding

Discovery is disabled until `N8N_INVENTORY_OWNER_ID` contains the estate owner's
verified DEVON account UUID. The authenticated caller must match that binding.
An email, a model argument, a task context value or the system tenant is never a
substitute. A missing or malformed binding returns 503 on the route; another
account returns 403. Conversation returns an unavailable observation.

The service selects exactly one configured URL that matches the canonical
self-hosted origin, from `N8N_API_URL` or `N8N_SECONDARY_API_URL`, and uses only
that URL's paired `API_KEY`. Both matching is ambiguous and refuses. A primary
Cloud URL is never called and its key is never forwarded to the secondary.
Root URLs with a trailing slash or `/api/v1` are accepted. Arbitrary URLs,
userinfo, query strings, fragments and alternate origins are refused.

Binding an owner is an operator configuration step; this change neither selects
an account nor changes production variables. Verify the actual authenticated
account UUID before setting it. A least-privilege n8n credential should have only
workflow-list/read access. Never paste a credential into chat.

## Evidence and limits

The upstream workflow-list response may contain private workflow definitions;
they are discarded. Only ID, name, active flag, archive flag (when reported),
published `activeVersionId` (when reported), and update time (when reported) leave
the service. `versionId` is the editor version and is never substituted for the
published version. Unknown metadata stays null.

Every request is GET to the pinned workflow-list path. Redirects and environment
proxies are disabled, response bodies are capped at 2 MB per page, and the read
stops after 10 pages of at most 100 rows or 30 seconds. Cursors are opaque query
values, never URLs. Repeated cursors, duplicate IDs and malformed pages refuse.
No HTTP error body, credential or cursor is returned to the caller.

`ok` and `complete: true` mean the credential-visible pagination ended. They do
not prove the credential sees every database workflow, that the read is an
atomic snapshot, or that active workflows are healthy. Counts describe observed
rows only. Missing archive fields are counted as unknown. A page failure retains
previously accepted pages as `partial`; a first-page failure is `failed`.
Neither becomes an empty successful estate.

The conversation tool accepts a name `query` and result `offset`, fits the turn's
1000-character observation budget, and returns `next_offset` when more matches
exist. It shows ID, name and active state; unusually escaped names may be
shortened with `name_truncated: true`. The HTTP route retains full metadata.
Each tool call re-reads the instance, so rows can change between offsets.
Workflow names are untrusted external data, never instructions or approvals.

Offline transport, owner-isolation, pagination, bounds, projection and conversation
checks are in `test_n8n_inventory.py`. They do not establish production activation,
current credential permissions or live model selection of the new tool.
