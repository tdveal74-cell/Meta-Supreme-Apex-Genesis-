"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { API_BASE } from "@/lib/api-base";
import { readDevonToken } from "@/components/presence/usePresenceSocket";
import {
  importParts,
  parseSnapshot,
  prepareParts,
  type ImportPart,
  type Receipt,
  type Snapshot,
} from "@/lib/notebook-import";

export default function NotebookImport() {
  const [raw, setRaw] = useState("");
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [parts, setParts] = useState<ImportPart[]>([]);
  const [receipts, setReceipts] = useState<Receipt[]>([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const running = useRef(false);
  const stop = useRef(false);
  async function review() {
    if (running.current) return;
    setReviewing(true);
    setSnapshot(null);
    setParts([]);
    setReceipts([]);
    setMessage("");
    try {
      const s = parseSnapshot(raw);
      const p = await prepareParts(s);
      setSnapshot(s);
      setParts(p);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Invalid snapshot.");
    } finally {
      setReviewing(false);
    }
  }
  async function run() {
    if (running.current || !snapshot || !parts.length) return;
    running.current = true;
    stop.current = false;
    setBusy(true);
    setReceipts([]);
    setMessage(
      "Import running. Keep this tab open; use one import tab at a time.",
    );
    try {
      const token = readDevonToken();
      if (!navigator.locks)
        throw new Error(
          "This browser cannot coordinate import tabs. Use a browser with Web Locks support.",
        );
      await navigator.locks.request(
        "devon-notebooklm-import",
        { ifAvailable: true },
        async (lock) => {
          if (!lock)
            throw new Error(
              "Another import is running in this browser. Wait for that job to finish.",
            );
          await importParts(
            parts,
            API_BASE,
            token,
            (r) => setReceipts((old) => [...old, r]),
            () => stop.current,
          );
        },
      );
      setMessage(
        stop.current
          ? "Stopped after the current source part. Review receipts before resuming."
          : "Import complete. Every source part has a persistence and retrieval receipt.",
      );
    } catch (e) {
      setMessage(
        e instanceof Error
          ? e.message
          : "Import stopped. Inspect the corpus before resuming.",
      );
    } finally {
      running.current = false;
      setBusy(false);
    }
  }
  function download(value: unknown, name: string) {
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return (
    <main className="mx-auto max-w-5xl space-y-7 px-5 py-10 text-white">
      <Link href="/control#cognitive" className="text-sm text-amber-200">
        Back to knowledge
      </Link>
      <header className="space-y-3">
        <p className="text-xs uppercase tracking-widest text-amber-200">
          DEVON reference library
        </p>
        <h1 className="text-3xl font-semibold">Import NotebookLM sources</h1>
        <p className="max-w-3xl text-sm leading-6 text-white/70">
          Bring original source text into your private knowledge corpus.
          Notebook links alone do not expose their contents. Import a captured
          JSON snapshot using your existing DEVON session.
        </p>
        <p className="text-sm text-white/60">
          This is a dated snapshot. Automatic Google sync is not configured.
          Source guides, generated summaries and chat answers are excluded.
          References do not become approved canon.
        </p>
      </header>
      <section className="space-y-3 rounded-xl border border-white/15 bg-black/20 p-5">
        <label htmlFor="notebook-snapshot" className="block font-medium">
          Source snapshot JSON
        </label>
        <textarea
          id="notebook-snapshot"
          disabled={busy || reviewing}
          value={raw}
          onChange={(e) => {
            setRaw(e.target.value);
            setSnapshot(null);
            setParts([]);
            setReceipts([]);
            setMessage("");
          }}
          rows={8}
          className="w-full rounded-lg border border-white/20 bg-black/40 p-3 font-mono text-xs"
          placeholder={
            '{"version":1,"notebooks":[{"id":"...","title":"...","url":"https://notebook.google.com/notebook/...","expected_sources":1,"sources":[{"id":"...","title":"...","text":"Original source text","extracted_at":"2026-10-22T00:00:00Z"}]}]}'
          }
        />
        <button
          onClick={() => void review()}
          disabled={busy || reviewing || !raw.trim()}
          className="rounded-lg bg-amber-200 px-4 py-3 font-medium text-black disabled:opacity-40"
        >
          {reviewing ? "Reviewing snapshot..." : "Review snapshot"}
        </button>
        <p className="text-xs text-white/60">
          Review computes hashes locally and sends nothing. Maximum 50 MB and
          1000 sources. Run one import job at a time. A lost response stops the
          job; resuming checks the corpus before writing.
        </p>
      </section>
      {snapshot && (
        <section className="space-y-4 rounded-xl border border-white/15 p-5">
          <h2 className="text-xl font-medium">Ready for review</h2>
          <p>
            {snapshot.notebooks.length} notebooks,{" "}
            {snapshot.notebooks.reduce((n, b) => n + b.sources.length, 0)}{" "}
            original sources, {parts.length} source parts.
          </p>
          <ul className="space-y-1 text-sm text-white/75">
            {snapshot.notebooks.map((n) => (
              <li key={n.id}>
                {n.title}: {n.sources.length} sources
                {!n.sources.length ? " (empty notebook, no write)" : ""}
              </li>
            ))}
          </ul>
          <p className="text-sm text-white/60">
            Import uses DEVON's configured embedding provider and can consume
            its provider quota. Failed, simulated or unverified embeddings stop
            the job. Each completed part is read back and searched before the
            next part begins.
          </p>
          <div className="flex flex-wrap gap-3">
            <button
              onClick={() => void run()}
              disabled={busy || !parts.length}
              className="rounded-lg bg-amber-200 px-4 py-3 font-medium text-black disabled:opacity-40"
            >
              Import reviewed sources
            </button>
            <button
              disabled={busy}
              onClick={() =>
                download(snapshot, "notebooklm-source-snapshot.json")
              }
              className="rounded-lg border border-white/20 px-4 py-3"
            >
              Download snapshot
            </button>
            {busy && (
              <button
                onClick={() => {
                  stop.current = true;
                  setMessage("Stopping after the current source part...");
                }}
                className="rounded-lg border border-white/20 px-4 py-3"
              >
                Stop after current source
              </button>
            )}
          </div>
        </section>
      )}
      {message && (
        <p
          role="status"
          className="rounded-lg border border-amber-200/30 p-4 text-sm"
        >
          {message}
        </p>
      )}
      {!!receipts.length && (
        <section className="space-y-4">
          <h2 className="text-xl">
            Verified receipts:{" "}
            {receipts.filter((r) => r.retrieval_verified).length} /{" "}
            {parts.length} parts
          </h2>
          <button
            disabled={busy}
            onClick={() =>
              download(
                { version: 1, receipts },
                "notebooklm-import-receipts.json",
              )
            }
            className="rounded-lg border border-white/20 px-4 py-3 disabled:opacity-40"
          >
            Download receipts
          </button>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr>
                  <th className="p-2">Stored item</th>
                  <th className="p-2">Action</th>
                  <th className="p-2">Chunks</th>
                  <th className="p-2">Embeddings</th>
                  <th className="p-2">Retrieval</th>
                </tr>
              </thead>
              <tbody>
                {receipts.map((r) => (
                  <tr
                    key={`${r.id}:${r.part}`}
                    className="border-t border-white/10"
                  >
                    <td className="p-2 font-mono">{r.id}</td>
                    <td className="p-2">{r.result}</td>
                    <td className="p-2">{r.chunks}</td>
                    <td className="p-2">{r.embedding_provider}</td>
                    <td className="p-2">
                      {r.retrieval_verified ? "verified" : "not verified"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </main>
  );
}
