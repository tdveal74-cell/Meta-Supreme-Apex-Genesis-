"use client";

import { useEffect, useState } from "react";
import { ProvenanceCard } from "@/components/ledger/ProvenanceCard";

/**
 * The provenance card verifies one intent, so something has to choose which.
 *
 * There is no route that lists an owner's intents: the ledger exposes a read of
 * one intent by id and nothing that enumerates them. So this asks for the id
 * rather than pretending to offer a picker, and remembers the last one on the
 * device so a reload does not lose it. When a list route exists this is the one
 * place that changes.
 */

const SLOT = "devon-control-intent-id";

export function ProvenanceSlot() {
  const [draft, setDraft] = useState("");
  const [intentId, setIntentId] = useState("");

  useEffect(() => {
    try {
      const stored = localStorage.getItem(SLOT) || "";
      if (stored) {
        setDraft(stored);
        setIntentId(stored);
      }
    } catch {
      // A browser with storage blocked still works, it just does not remember.
    }
  }, []);

  function verify(next: string) {
    const trimmed = next.trim();
    setIntentId(trimmed);
    try {
      if (trimmed) {
        localStorage.setItem(SLOT, trimmed);
      } else {
        localStorage.removeItem(SLOT);
      }
    } catch {
      // Not remembering is acceptable; failing to verify would not be.
    }
  }

  return (
    <div className="space-y-3">
      <form
        onSubmit={(event) => {
          event.preventDefault();
          verify(draft);
        }}
        className="flex flex-col gap-2 sm:flex-row"
      >
        <label className="sr-only" htmlFor="control-intent-id">
          Intent id to verify
        </label>
        <input
          id="control-intent-id"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Intent id, for example 3f6c1e2a-..."
          spellCheck={false}
          autoComplete="off"
          className="min-w-0 flex-1 rounded-lg border border-white/10 bg-black/30 px-3 py-2 font-mono text-xs text-white/85 outline-none transition placeholder:text-white/25 focus:border-white/25"
        />
        <button
          type="submit"
          className="rounded-lg border border-white/15 px-3 py-2 text-xs font-medium text-white/75 transition hover:border-white/30 hover:text-white"
        >
          Verify
        </button>
      </form>

      <ProvenanceCard intentId={intentId} />

      <p className="text-xs leading-relaxed text-white/35">
        No route lists an owner's intents, only a read of one by id, so this asks
        for the id instead of offering a picker it cannot populate. The last id is
        remembered on this device only.
      </p>
    </div>
  );
}
