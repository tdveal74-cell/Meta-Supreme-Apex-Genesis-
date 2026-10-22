import assert from "node:assert/strict";
import { test } from "node:test";
import {
  parseSnapshot,
  prepareParts,
  importParts,
  type Receipt,
} from "../lib/notebook-import.ts";

const nid = "fe54b3c4-8477-403f-a9e6-1f4b73a1e401";
const sid = "6149af55-216f-4d61-b8a0-bd80cda40fe5";
const input = (content = "Exact source text\n  With whitespace. 😀") => ({
  version: 1,
  notebooks: [
    {
      id: nid,
      title: "Research reference",
      url: `https://notebook.google.com/notebook/${nid}`,
      expected_sources: 1,
      sources: [
        {
          id: sid,
          title: "Original paper",
          text: content,
          extracted_at: "2026-10-22T00:00:00Z",
        },
      ],
    },
  ],
});
const snapshot = () => parseSnapshot(JSON.stringify(input()));
const json = (v: unknown, status = 200) =>
  new Response(JSON.stringify(v), {
    status,
    headers: { "Content-Type": "application/json" },
  });
const provider = {
  embedding_provider: "openai",
  embedding_provider_simulated: false,
  embedding_provider_error: null,
};

test("reject incomplete capture, duplicates, secret-bearing notebook URL and empty text", () => {
  for (const mutate of [
    (v: any) => (v.notebooks[0].expected_sources = 2),
    (v: any) => v.notebooks.push(v.notebooks[0]),
    (v: any) => (v.notebooks[0].url += "?token=private"),
    (v: any) => (v.notebooks[0].sources[0].text = " "),
    (v: any) => (v.notebooks[0].sources[0].source_url = "javascript:alert(1)"),
    (v: any) => (v.notebooks[0].sources[0].extracted_at = "bad"),
  ]) {
    const v = input();
    mutate(v);
    assert.throws(() => parseSnapshot(JSON.stringify(v)));
  }
});
test("source parts preserve exact Unicode text and deterministic identity", async () => {
  const text = "x".repeat(7000) + "😀\n" + "y".repeat(7000);
  const parts = await prepareParts(parseSnapshot(JSON.stringify(input(text))));
  assert.ok(parts.length >= 2);
  assert.equal(
    parts
      .map((p) => p.content.split("Original source text follows:\n")[1])
      .join(""),
    text,
  );
  assert.ok(parts.every((p) => p.content.length < 8000));
  assert.deepEqual(
    parts,
    await prepareParts(parseSnapshot(JSON.stringify(input(text)))),
  );
  assert.notEqual(
    parts[0].external_id,
    (await prepareParts(snapshot()))[0].external_id,
  );
});
test("empty notebook causes zero writes", async () => {
  const v = input();
  v.notebooks[0].sources = [];
  v.notebooks[0].expected_sources = 0;
  assert.deepEqual(await prepareParts(parseSnapshot(JSON.stringify(v))), []);
});
test("read failure, bad corpus and signed-out requests never write", async () => {
  const parts = await prepareParts(snapshot());
  for (const response of [json({}, 401), json({})]) {
    const methods: string[] = [];
    await assert.rejects(
      importParts(
        parts,
        "https://devon.invalid",
        "session",
        () => {},
        () => false,
        (async (url, init) => {
          methods.push(String(init?.method));
          if (String(url).includes("/graph?")) return json(provider);
          return response;
        }) as typeof fetch,
      ),
    );
    assert.deepEqual(methods, ["GET", "GET"]);
  }
  await assert.rejects(
    importParts(
      parts,
      "https://devon.invalid",
      "",
      () => {},
      () => false,
      (async () => assert.fail("must not request")) as typeof fetch,
    ),
  );
});
test("POST, durable read and matching retrieval required; rerun skips existing URI", async () => {
  const parts = await prepareParts(snapshot());
  const p = parts[0];
  const item = {
    id: "stored",
    title: p.title,
    status: "ready",
    source_uri: p.source_uri,
    chunk_count: 2,
    metadata: { embedding_provider: "openai", simulated_embeddings: false },
  };
  for (const existing of [false, true]) {
    const paths: string[] = [];
    const receipts: Receipt[] = [];
    const request = (async (url, init) => {
      const path = String(url).replace("https://devon.invalid", "");
      paths.push(`${init?.method} ${path}`);
      if (path === "/knowledge") return json(existing ? [item] : []);
      if (path.startsWith("/knowledge/graph?")) return json(provider);
      if (path === "/knowledge/ingest") {
        const body = JSON.parse(String(init?.body));
        assert.equal(body.external_id, p.external_id);
        assert.deepEqual(body.acl_tokens, []);
        assert.equal(body.notebook_id, undefined);
        return json({ ...item, external_id: p.external_id }, 201);
      }
      if (path === "/knowledge/stored") return json(item);
      if (path === "/knowledge/search")
        return json([{ knowledge_item_id: "stored", content: p.content }]);
      assert.fail(path);
    }) as typeof fetch;
    await importParts(
      parts,
      "https://devon.invalid",
      "session",
      (r) => receipts.push(r),
      () => false,
      request,
    );
    assert.equal(paths.includes("POST /knowledge/ingest"), !existing);
    assert.equal(receipts.length, 1);
    assert.equal(receipts[0].retrieval_verified, true);
    assert.equal(receipts[0].result, existing ? "existing" : "created");
  }
});
test("unknown POST outcome is never retried", async () => {
  const parts = await prepareParts(snapshot());
  let writes = 0;
  await assert.rejects(
    importParts(
      parts,
      "https://devon.invalid",
      "session",
      () => {},
      () => false,
      (async (url, init) => {
        if (String(url).includes("/graph?")) return json(provider);
        if (init?.method === "GET") return json([]);
        writes++;
        throw new Error("connection lost after possible commit");
      }) as typeof fetch,
    ),
  );
  assert.equal(writes, 1);
});
test("mock, missing flags, failed chunks, wrong receipts and no matching retrieval halt", async () => {
  const parts = await prepareParts(snapshot());
  const p = parts[0];
  const good = {
    id: "stored",
    title: p.title,
    status: "ready",
    source_uri: p.source_uri,
    chunk_count: 2,
    external_id: p.external_id,
    metadata: { embedding_provider: "openai", simulated_embeddings: false },
  };
  for (const bad of [
    {
      ...good,
      metadata: { embedding_provider: "mock", simulated_embeddings: true },
    },
    { ...good, metadata: { embedding_provider: "openai" } },
    { ...good, status: "failed" },
    { ...good, chunk_count: 0 },
    { ...good, external_id: "wrong" },
    good,
  ]) {
    let writes = 0;
    const request = (async (url, init) => {
      if (String(url).includes("/graph?")) return json(provider);
      if (String(url).endsWith("/knowledge")) return json([]);
      if (String(url).endsWith("/ingest")) {
        writes++;
        return json(bad, 201);
      }
      if (String(url).endsWith("/stored")) return json(good);
      return json([
        { knowledge_item_id: "somebody-else", content: "irrelevant" },
      ]);
    }) as typeof fetch;
    await assert.rejects(
      importParts(
        [...parts, ...parts],
        "https://devon.invalid",
        "session",
        () => {},
        () => false,
        request,
      ),
    );
    assert.equal(writes, 1);
  }
});
test("provider preflight refuses mock or missing provider before any source write", async () => {
  const parts = await prepareParts(snapshot());
  for (const state of [
    { embedding_provider: "mock", embedding_provider_simulated: true },
    { embedding_provider: "unavailable", embedding_provider_simulated: true },
    {},
    { embedding_provider: "openai", embedding_provider_simulated: false },
    { ...provider, embedding_provider_error: "" },
    { ...provider, embedding_provider_error: false },
  ]) {
    let calls = 0;
    await assert.rejects(
      importParts(
        parts,
        "https://devon.invalid",
        "session",
        () => {},
        () => false,
        (async (_, init) => {
          calls++;
          assert.equal(init?.method, "GET");
          return json(state);
        }) as typeof fetch,
      ),
      /No source writes were attempted/,
    );
    assert.equal(calls, 1);
  }
});
