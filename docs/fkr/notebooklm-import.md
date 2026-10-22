# NotebookLM source snapshots

The knowledge panel links to `/knowledge/import`. This page imports captured
source text into the signed-in owner's existing knowledge corpus. It does not
authenticate to Google, fetch notebooks from links, poll, change notebook sharing,
or promote a reference to canon. Generated source guides and chat responses must
not be represented as source text. A report already saved as a notebook source
retains its title and remains an external reference.

## Snapshot format

```json
{
  "version": 1,
  "notebooks": [{
    "id": "fe54b3c4-8477-403f-a9e6-1f4b73a1e401",
    "title": "Notebook title",
    "url": "https://notebook.google.com/notebook/fe54b3c4-8477-403f-a9e6-1f4b73a1e401",
    "expected_sources": 1,
    "sources": [{
      "id": "6149af55-216f-4d61-b8a0-bd80cda40fe5",
      "title": "Source title",
      "source_url": null,
      "extracted_at": "2026-10-22T00:00:00Z",
      "text": "Original source text as rendered in the source viewer."
    }]
  }]
}
```

IDs must be UUIDs. Notebook URLs must match the ID without a query or fragment.
Every notebook's source count must match the captured array; an empty notebook is
valid and causes no write. The page accepts at most 50 MB, 100 notebooks and 1000
sources per snapshot. Use separate snapshots when those bounds would be exceeded.
Source URLs can be omitted if the viewer does not expose them.

Reviewing computes SHA-256 over each exact original text locally. No Google
credential is needed or exported. Each source part carries the notebook, source,
extraction time, original-text hash and part count. Whole request content is
bounded below the existing distiller's 8000-character body limit. Splitting
preserves surrogate pairs and reconstructs the exact source string.

## Writes and receipts

1. The existing authenticated graph route identifies the configured embedding
   provider. An unavailable, simulated or unknown provider stops before source
   writes. This importer supports real OpenAI and OpenRouter embeddings.
2. The complete owner-scoped corpus is read. A failed or malformed read never
   becomes an empty corpus.
3. A content-addressed source URI identifies a notebook/source/hash/part. A
   matching existing item is checked; an ambiguous match stops. New parts use
   the existing `POST /knowledge/ingest`, with no shared ACL tokens or project.
4. Ready status, persisted chunk rows and explicit real embedding metadata are
   checked through the existing item route. The beginning and ending source
   excerpts must be returned by searches against that stored item before its
   retrieval receipt is verified. This is a coverage check, not an answer-quality
   evaluation or an assertion that every conceivable query will retrieve it.
5. Receipts contain stored item ID, action, source hash/part, chunk count,
   embedding provider, retrieval verdict and check time. They contain no session
   token. Snapshot and receipt downloads are available separately.

No source POST is automatically retried. After a lost response, inspect the
corpus and resume; the next run reads the corpus before deciding to write.
Stopping takes effect after the current part, and does not undo completed parts.
A failed existing item stops the job rather than silently creating another one.

Web Locks reject a simultaneous import in another tab on the same origin. Run
only one import job across devices. This page does not add a database uniqueness
constraint or promise server-wide idempotency. Content appearing in separate
notebooks retains separate membership/provenance and can create separate items.

## Verification

`pnpm --filter @meta-supreme/web check:notebook-import` exercises source fidelity,
bounded splitting, empty notebooks, auth/read failure, provider preflight,
POST/read/search receipts, duplicate replay, unknown write outcome and failure
stops. The web workflow runs it before the production build. Live completion
requires actual persistence and retrieval receipts; passing fixtures or deploying
the page alone does not mean any notebook has been imported.

## OpenRouter configuration

Set `EMBEDDING_PROVIDER=openrouter` and use the existing `OPENROUTER_API_KEY`
on the API service. Leave `EMBEDDING_MODEL` unset or set it to
`openai/text-embedding-3-small`. This adapter accepts only that model and
1536 finite, nonzero dimensions, with complete, unique batch indices.
No separate OpenAI key is needed. OpenRouter account credit and key limits
still apply. Missing credentials, funding refusals and malformed responses
fail explicitly, without switching to mock or another model. The chat provider
is independent and is not changed.

Do not mix existing mock vectors with real vectors. Start from an empty corpus
or perform an explicit rebuild of existing items. Import receipts are required
before claiming success. OpenRouter is not automatically added to the separate
hybrid retrieval or episode-coverage trust allowlists; those require their own
quality measurement. The importer verifies the existing semantic search route.

API contract: https://openrouter.ai/docs/api/api-reference/embeddings/submit-an-embedding-request
