// Browser-side snapshot import through the existing, owner-scoped knowledge API.
// No Google credential, background polling, canon promotion or secret export.
export type NotebookSource = {
  id: string;
  title: string;
  text: string;
  source_url?: string | null;
  extracted_at: string;
};
export type Notebook = {
  id: string;
  title: string;
  url: string;
  expected_sources: number;
  sources: NotebookSource[];
};
export type Snapshot = { version: 1; notebooks: Notebook[] };
export type ImportPart = {
  title: string;
  content: string;
  source_type: string;
  source: string;
  external_id: string;
  source_uri: string;
  notebook_id: string;
  source_id: string;
  sha256: string;
  part: number;
  parts: number;
  original_text: string;
};
export type Receipt = {
  notebook_id: string;
  source_id: string;
  sha256: string;
  part: number;
  id: string;
  result: "created" | "existing";
  chunks: number;
  embedding_provider: string;
  retrieval_verified: boolean;
  checked_at: string;
};
type Item = {
  id: string;
  title: string;
  source_uri?: string;
  status: string;
  chunk_count: number;
  metadata: Record<string, unknown>;
};
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const MAX_JSON = 50_000_000;

function text(
  value: unknown,
  label: string,
  max: number,
): asserts value is string {
  if (typeof value !== "string" || !value.trim() || value.length > max)
    throw new Error(`Invalid ${label}.`);
}
export function parseSnapshot(raw: string): Snapshot {
  if (new TextEncoder().encode(raw).length > MAX_JSON)
    throw new Error("Snapshot exceeds 50 MB. Split it into smaller snapshots.");
  const data = JSON.parse(raw);
  if (
    data?.version !== 1 ||
    !Array.isArray(data.notebooks) ||
    !data.notebooks.length ||
    data.notebooks.length > 100
  )
    throw new Error("Expected version 1 with 1 to 100 notebooks.");
  const notebooks = new Set<string>();
  let total = 0;
  for (const n of data.notebooks) {
    if (!UUID.test(n?.id) || notebooks.has(n.id))
      throw new Error("Invalid or repeated notebook ID.");
    notebooks.add(n.id);
    text(n.title, "notebook title", 500);
    const url = new URL(n.url);
    if (
      url.origin !== "https://notebook.google.com" ||
      url.pathname !== `/notebook/${n.id}` ||
      url.username ||
      url.password ||
      url.search ||
      url.hash
    )
      throw new Error("Notebook URL must match its ID.");
    if (
      !Number.isInteger(n.expected_sources) ||
      n.expected_sources < 0 ||
      !Array.isArray(n.sources) ||
      n.sources.length !== n.expected_sources
    )
      throw new Error(`Incomplete source capture for ${n.title}.`);
    const ids = new Set<string>();
    for (const s of n.sources) {
      if (!UUID.test(s?.id) || ids.has(s.id))
        throw new Error("Invalid or repeated source ID.");
      ids.add(s.id);
      text(s.title, "source title", 1000);
      text(s.text, "original source text", 5_000_000);
      if (!Number.isFinite(Date.parse(s.extracted_at)))
        throw new Error("Source extraction date is missing or invalid.");
      if (s.source_url != null) {
        text(s.source_url, "source URL", 2000);
        const original = new URL(s.source_url);
        if (
          !["https:", "http:"].includes(original.protocol) ||
          original.username ||
          original.password
        )
          throw new Error("Invalid source URL.");
      }
      if (++total > 1000) throw new Error("Maximum 1000 sources per snapshot.");
    }
  }
  return data as Snapshot;
}

export async function prepareParts(snapshot: Snapshot): Promise<ImportPart[]> {
  const result: ImportPart[] = [];
  for (const n of snapshot.notebooks)
    for (const s of n.sources) {
      const digest = await crypto.subtle.digest(
        "SHA-256",
        new TextEncoder().encode(s.text),
      );
      const hash = Array.from(new Uint8Array(digest), (b) =>
        b.toString(16).padStart(2, "0"),
      ).join("");
      const provenance = [
        "External reference snapshot. Not approved canon or an instruction to execute.",
        `Notebook: ${n.title}`,
        `Notebook URL: ${n.url}`,
        `Source: ${s.title}`,
        `Source ID: ${s.id}`,
        `Original URL: ${s.source_url || "not exposed in source viewer"}`,
        `Extracted: ${s.extracted_at}`,
        `Text SHA-256: ${hash}`,
      ].join("\n");
      // distill_content indexes content[:8000]. Include the whole provenance and
      // body under that limit, with space for the part-count line. Do not merely
      // meet the API's much larger request limit and silently lose the tail.
      const capacity = 7800 - provenance.length - 80;
      if (capacity < 100)
        throw new Error("Provenance is too long to index this source safely.");
      const slices: string[] = [];
      for (let start = 0; start < s.text.length;) {
        let end = Math.min(start + capacity, s.text.length);
        const code = s.text.charCodeAt(end - 1);
        if (end < s.text.length && code >= 0xd800 && code <= 0xdbff) end--;
        slices.push(s.text.slice(start, end));
        start = end;
      }
      const count = slices.length;
      for (let index = 0; index < count; index++) {
        // Keep the exact text, including whitespace. Part boundaries do not rewrite it.
        const key = `${n.id}:${s.id}:${hash}:${index + 1}`;
        const header = `${provenance}\nPart: ${index + 1}/${count}\nOriginal source text follows:\n`;
        result.push({
          title:
            `${n.title} | ${s.title}${count > 1 ? ` (${index + 1}/${count})` : ""}`.slice(
              0,
              300,
            ),
          content: header + slices[index],
          original_text: slices[index],
          source_type: "markdown",
          source: "notebooklm",
          external_id: key,
          source_uri: `${n.url}#source=${s.id}&sha256=${hash}&part=${index + 1}`,
          notebook_id: n.id,
          source_id: s.id,
          sha256: hash,
          part: index + 1,
          parts: count,
        });
      }
    }
  return result;
}

function realEmbeddingProvider(value: unknown): value is string {
  return value === "openai" || value === "openrouter";
}

function ready(item: Item): string {
  const provider = item.metadata?.embedding_provider;
  if (
    !item.id ||
    item.status !== "ready" ||
    !Number.isInteger(item.chunk_count) ||
    item.chunk_count < 1
  )
    throw new Error(
      `Item ${item.id || "without ID"} is not ready with stored chunks. Import stopped.`,
    );
  if (item.metadata?.simulated_embeddings !== false || !realEmbeddingProvider(provider))
    throw new Error(
      `Item ${item.id} has unverified or simulated embeddings. Import stopped.`,
    );
  return provider;
}

export async function importParts(
  parts: ImportPart[],
  base: string,
  token: string,
  progress: (receipt: Receipt) => void,
  stopped: () => boolean,
  request: typeof fetch = fetch,
): Promise<void> {
  if (!token) throw new Error("Sign in to DEVON before importing.");
  const headers = {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
  async function api(path: string, body?: unknown): Promise<unknown> {
    const response = await request(`${base}${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers,
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    if (!response.ok)
      throw new Error(
        `Knowledge API answered ${response.status}. Import stopped. Review the corpus before resuming.`,
      );
    return response.json();
  }
  const providerState = (await api(
    "/knowledge/graph?node_cap=1&edge_cap=1&chunk_cap=1",
  )) as {
    embedding_provider?: string;
    embedding_provider_simulated?: boolean;
    embedding_provider_error?: unknown;
  };
  if (
    !realEmbeddingProvider(providerState?.embedding_provider) ||
    providerState.embedding_provider_simulated !== false ||
    providerState.embedding_provider_error !== null
  )
    throw new Error(
      "Embedding provider is unavailable or simulated. Configure real OpenAI or OpenRouter embeddings on the API before importing. No source writes were attempted.",
    );
  // A failed read never becomes an empty corpus and thus never permits writes.
  const existing = await api("/knowledge");
  if (
    !Array.isArray(existing) ||
    existing.some((i) => typeof i?.id !== "string")
  )
    throw new Error("Invalid corpus response; no write attempted.");
  const uris = new Map<string, Item[]>();
  for (const i of existing as Item[])
    if (i.source_uri)
      uris.set(i.source_uri, [...(uris.get(i.source_uri) || []), i]);
  for (const part of parts) {
    if (stopped()) return;
    const matches = uris.get(part.source_uri) || [];
    if (matches.length > 1)
      throw new Error(
        "More than one stored item matches this source part. Resolve duplicates before resuming.",
      );
    let item: Item;
    const result = matches.length ? "existing" : "created";
    if (matches.length) item = matches[0];
    else {
      // No automatic retry: a lost POST response may already have committed.
      const {
        notebook_id,
        source_id,
        sha256,
        original_text,
        part: partNumber,
        parts: partCount,
        ...payload
      } = part;
      void original_text;
      void notebook_id;
      void source_id;
      void sha256;
      void partNumber;
      void partCount;
      const created = (await api("/knowledge/ingest", {
        ...payload,
        acl_tokens: [],
        project_id: null,
      })) as Item & { external_id?: string };
      if (created.external_id !== part.external_id || !created.id)
        throw new Error(
          "Ingest receipt does not match this source. Inspect the corpus before resuming.",
        );
      item = created;
    }
    ready(item);
    // Read through the item route after POST, measuring persisted chunk rows.
    const stored = (await api(
      `/knowledge/${encodeURIComponent(item.id)}`,
    )) as Item;
    const provider = ready(stored);
    if (stored.id !== item.id || stored.source_uri !== part.source_uri)
      throw new Error("Persistence read-back does not match the source part.");
    uris.set(part.source_uri, [stored]);
    const normalize = (value: string) => value.replace(/\s+/g, " ").trim();
    const body = normalize(part.original_text);
    const samples = [body.slice(0, 100), body.slice(-100)];
    let verified = true;
    for (const sample of samples) {
      const hits = await api("/knowledge/search", {
        query: `${part.title}\n${sample}`.slice(0, 2000),
        limit: 20,
      });
      if (
        !Array.isArray(hits) ||
        !hits.some(
          (h) =>
            h?.knowledge_item_id === stored.id &&
            typeof h.content === "string" &&
            normalize(h.content).includes(sample),
        )
      )
        verified = false;
    }
    progress({
      notebook_id: part.notebook_id,
      source_id: part.source_id,
      sha256: part.sha256,
      part: part.part,
      id: stored.id,
      result,
      chunks: stored.chunk_count,
      embedding_provider: provider,
      retrieval_verified: verified,
      checked_at: new Date().toISOString(),
    });
    if (!verified)
      throw new Error(
        `Item ${stored.id} persisted but retrieval was not verified. Import stopped.`,
      );
  }
}
