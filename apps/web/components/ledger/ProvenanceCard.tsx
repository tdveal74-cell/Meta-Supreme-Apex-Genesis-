"use client";

// The ledger provenance card: one intent's verdict from
// GET /api/v1/ledger/intents/{intent_id}/provenance.
//
// The route is owner scoped through the authenticated user, so the card reads
// the same bearer token slot every other DEVON surface here reads. It answers
// 401 when the token is missing or stale and 404 with a `reasons` list when the
// intent is not on this owner's record, and both are rendered as themselves
// rather than as one generic failure.
//
// Nothing on this card summarises a finding away. `verified` on the payload
// requires a complete chain AND a receipt certifying exactly that chain, so an
// intact but incomplete chain is shown in a warning tone with the reason spelt
// out, never with a green tick.

import { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE } from "@/lib/api-base";
import {
  isProvenancePayload,
  readVerdict,
  shortHash,
  type ProvenancePayload,
  type VerdictTone,
} from "./provenance-payload";

const TOKEN_SLOT = "devon-chat-token";

export type ProvenanceCardProps = {
  /** The intent to verify. Blank or absent renders the empty state. */
  intentId?: string;
  /** Bearer token override. Falls back to the stored DEVON session token. */
  token?: string;
  /** API origin override. Defaults to the one resolution rule in lib/api-base. */
  apiBase?: string;
  /** Re-verify on an interval, in milliseconds. Off unless set above zero. */
  refreshMs?: number;
  /** Wrapper classes, so a page can place the card without editing it. */
  className?: string;
  /** Every settled read, including a null when the read did not settle ready. */
  onPayload?: (payload: ProvenancePayload | null) => void;
};

type CardState =
  | { phase: "empty" }
  | { phase: "locked" }
  | { phase: "loading" }
  | { phase: "ready"; payload: ProvenancePayload }
  | { phase: "missing"; reasons: string[] }
  | { phase: "denied" }
  | { phase: "error"; status: number | null; message: string };

function readStoredToken(): string {
  try {
    return localStorage.getItem(TOKEN_SLOT) || sessionStorage.getItem(TOKEN_SLOT) || "";
  } catch {
    return "";
  }
}

/** The 404 body is `{"detail": {"reasons": [...]}}`, built by the route. */
async function readReasons(response: Response): Promise<string[]> {
  try {
    const body = (await response.json()) as unknown;
    const detail = (body as { detail?: unknown } | null)?.detail;
    const reasons = (detail as { reasons?: unknown } | null)?.reasons;
    if (Array.isArray(reasons)) {
      return reasons.map((reason) => String(reason));
    }
    if (typeof detail === "string" && detail) return [detail];
  } catch {
    // A 404 without a JSON body still gets an honest, non invented message.
  }
  return [];
}

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const text = await response.text();
    return text.slice(0, 600) || response.statusText || "The route answered with no body.";
  } catch {
    return response.statusText || "The route answered with a body that could not be read.";
  }
}

const TONE_BADGE: Record<VerdictTone, string> = {
  good: "border-emerald-400/45 bg-emerald-400/10 text-emerald-200",
  warn: "border-[#d4a017]/50 bg-[#d4a017]/10 text-[#e8c256]",
  bad: "border-rose-400/50 bg-rose-400/10 text-rose-200",
};

const TONE_RULE: Record<VerdictTone, string> = {
  good: "border-emerald-400/35",
  warn: "border-[#d4a017]/40",
  bad: "border-rose-400/40",
};

function Shell({
  children,
  className,
  onRefresh,
  status,
}: {
  children: React.ReactNode;
  className?: string;
  onRefresh?: () => void;
  status?: string;
}) {
  return (
    <section
      className={`border border-[#3e617c] bg-[#071016]/95 shadow-2xl shadow-black/50 ${className || ""}`}
      aria-label="Ledger provenance"
    >
      <header className="flex items-start justify-between gap-3 border-b border-[#22384a] px-4 py-3">
        <div className="min-w-0">
          <p className="font-mono text-[9px] uppercase tracking-[0.2em] text-[#c77b4a]">
            Live State Ledger
          </p>
          <p className="mt-1 text-xs font-semibold text-white">Provenance verdict</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {status ? (
            <span className="font-mono text-[9px] uppercase tracking-[0.12em] text-[#526979]">
              {status}
            </span>
          ) : null}
          {onRefresh ? (
            <button
              type="button"
              onClick={onRefresh}
              className="border border-[#22384a] px-2 py-1 font-mono text-[9px] uppercase tracking-[0.12em] text-[#93a6b5] hover:border-[#c77b4a]/60 hover:text-white"
            >
              Re-verify
            </button>
          ) : null}
        </div>
      </header>
      {children}
    </section>
  );
}

function Fact({
  label,
  value,
  title,
  tone,
  note,
}: {
  label: string;
  value: string;
  title?: string;
  tone?: VerdictTone;
  note?: string;
}) {
  const valueTone =
    tone === "good"
      ? "text-emerald-200"
      : tone === "warn"
        ? "text-[#e8c256]"
        : tone === "bad"
          ? "text-rose-200"
          : "text-white";
  return (
    <div className="min-w-0 border-t border-[#22384a] pt-2.5">
      <p className="font-mono text-[9px] uppercase tracking-[0.14em] text-[#526979]">{label}</p>
      <p className={`mt-1 break-words font-mono text-[11px] leading-4 ${valueTone}`} title={title}>
        {value}
      </p>
      {note ? <p className="mt-1 text-[10px] leading-4 text-[#6f8494]">{note}</p> : null}
    </div>
  );
}

function Findings({
  heading,
  findings,
}: {
  heading: string;
  findings: string[];
}) {
  return (
    <div>
      <p className="font-mono text-[9px] uppercase tracking-[0.14em] text-[#c77b4a]">
        {heading} ({findings.length})
      </p>
      {findings.length === 0 ? (
        <p className="mt-1.5 text-[11px] leading-5 text-[#6f8494]">
          None reported. That is the payload reporting no finding, not this card withholding one.
        </p>
      ) : (
        <ul className="mt-1.5 space-y-1.5">
          {findings.map((finding, index) => (
            <li
              key={`${index}:${finding}`}
              className="whitespace-pre-wrap break-words border-l-2 border-[#d4a017]/45 bg-[#0b1a24]/70 px-2.5 py-1.5 font-mono text-[11px] leading-[1.45] text-[#dbe6ee]"
            >
              {finding}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function ProvenanceCard({
  intentId,
  token,
  apiBase,
  refreshMs = 0,
  className,
  onPayload,
}: ProvenanceCardProps) {
  const [state, setState] = useState<CardState>({ phase: "empty" });
  const [nonce, setNonce] = useState(0);
  const reportRef = useRef(onPayload);

  useEffect(() => {
    reportRef.current = onPayload;
  }, [onPayload]);

  const reVerify = useCallback(() => setNonce((current) => current + 1), []);

  const id = (intentId || "").trim();
  const base = (apiBase || API_BASE).replace(/\/$/, "");

  useEffect(() => {
    if (!id) {
      setState({ phase: "empty" });
      reportRef.current?.(null);
      return;
    }
    const bearer = (token ?? readStoredToken()).trim();
    if (!bearer) {
      setState({ phase: "locked" });
      reportRef.current?.(null);
      return;
    }

    const controller = new AbortController();
    setState({ phase: "loading" });

    const run = async () => {
      let settled: CardState;
      try {
        const response = await fetch(
          `${base}/ledger/intents/${encodeURIComponent(id)}/provenance`,
          {
            cache: "no-store",
            signal: controller.signal,
            headers: { Authorization: `Bearer ${bearer}` },
          },
        );
        if (response.status === 401) {
          settled = { phase: "denied" };
        } else if (response.status === 404) {
          settled = { phase: "missing", reasons: await readReasons(response) };
        } else if (!response.ok) {
          settled = {
            phase: "error",
            status: response.status,
            message: await readErrorMessage(response),
          };
        } else {
          const body = (await response.json()) as unknown;
          settled = isProvenancePayload(body)
            ? { phase: "ready", payload: body }
            : {
                phase: "error",
                status: response.status,
                message:
                  "The route answered 200 with a body that does not carry the provenance keys, " +
                  "so no verdict was read from it.",
              };
        }
      } catch (error) {
        if (controller.signal.aborted) return;
        settled = {
          phase: "error",
          status: null,
          message:
            error instanceof Error
              ? error.message
              : "The request failed before any response arrived.",
        };
      }
      if (controller.signal.aborted) return;
      setState(settled);
      reportRef.current?.(settled.phase === "ready" ? settled.payload : null);
    };

    void run();
    return () => controller.abort();
  }, [id, token, base, nonce]);

  useEffect(() => {
    if (!refreshMs || refreshMs <= 0 || !id) return;
    const timer = window.setInterval(() => setNonce((current) => current + 1), refreshMs);
    return () => window.clearInterval(timer);
  }, [refreshMs, id]);

  if (state.phase === "empty") {
    return (
      <Shell className={className}>
        <div className="px-4 py-5">
          <p className="text-sm font-medium text-[#93a6b5]">No intent selected.</p>
          <p className="mt-2 text-[11px] leading-5 text-[#6f8494]">
            Give the card an intent id and it verifies that intent&apos;s hash chain and receipt.
            Nothing is read until then, so this is not a claim that any chain is sound.
          </p>
        </div>
      </Shell>
    );
  }

  if (state.phase === "locked") {
    return (
      <Shell className={className} onRefresh={reVerify}>
        <div className="px-4 py-5">
          <p className="text-sm font-medium text-sky-200">Session token not held.</p>
          <p className="mt-2 text-[11px] leading-5 text-[#6f8494]">
            The provenance route is owner scoped, so it needs the DEVON session token. Sign in
            through Talk to DEVON, then re-verify. Intent <span className="font-mono">{id}</span> has
            not been read.
          </p>
        </div>
      </Shell>
    );
  }

  if (state.phase === "loading") {
    return (
      <Shell className={className} status="reading">
        <div className="px-4 py-5">
          <p className="flex items-center gap-2 text-sm font-medium text-[#8fd5cb]">
            <span className="h-2 w-2 animate-pulse rounded-full bg-amber-300" />
            Walking the chain...
          </p>
          <p className="mt-2 font-mono text-[10px] leading-4 text-[#526979]">{id}</p>
          <p className="mt-2 text-[11px] leading-5 text-[#6f8494]">
            The verifier recomputes every hash and the receipt digest from the stored rows. No
            verdict is shown until it answers.
          </p>
        </div>
      </Shell>
    );
  }

  if (state.phase === "denied") {
    return (
      <Shell className={className} onRefresh={reVerify} status="401">
        <div className="px-4 py-5">
          <p className="text-sm font-medium text-rose-200">Refused: 401 not authenticated.</p>
          <p className="mt-2 text-[11px] leading-5 text-[#6f8494]">
            The token is missing, expired or not accepted. This says nothing about intent{" "}
            <span className="font-mono">{id}</span>: its chain was never walked.
          </p>
        </div>
      </Shell>
    );
  }

  if (state.phase === "missing") {
    return (
      <Shell className={className} onRefresh={reVerify} status="404">
        <div className="px-4 py-5">
          <p className="text-sm font-medium text-[#e8c256]">No such intent on this record.</p>
          <p className="mt-2 font-mono text-[10px] leading-4 text-[#526979]">{id}</p>
          {state.reasons.length > 0 ? (
            <ul className="mt-2.5 space-y-1.5">
              {state.reasons.map((reason, index) => (
                <li
                  key={`${index}:${reason}`}
                  className="whitespace-pre-wrap break-words border-l-2 border-[#d4a017]/45 bg-[#0b1a24]/70 px-2.5 py-1.5 font-mono text-[11px] leading-[1.45] text-[#dbe6ee]"
                >
                  {reason}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-[11px] leading-5 text-[#6f8494]">
              The route answered 404 without naming a reason.
            </p>
          )}
          <p className="mt-2.5 text-[11px] leading-5 text-[#6f8494]">
            The route is owner scoped, so an intent belonging to another account reads the same as
            one that does not exist. Neither is a provenance failure.
          </p>
        </div>
      </Shell>
    );
  }

  if (state.phase === "error") {
    return (
      <Shell
        className={className}
        onRefresh={reVerify}
        status={state.status === null ? "no response" : String(state.status)}
      >
        <div className="px-4 py-5">
          <p className="text-sm font-medium text-rose-200">
            {state.status === null
              ? "The provenance read did not reach the API."
              : `The provenance read failed with HTTP ${state.status}.`}
          </p>
          <p className="mt-2 font-mono text-[10px] leading-4 text-[#526979]">{id}</p>
          <p className="mt-2.5 whitespace-pre-wrap break-words border-l-2 border-rose-400/45 bg-[#0b1a24]/70 px-2.5 py-1.5 font-mono text-[11px] leading-[1.45] text-[#dbe6ee]">
            {state.message}
          </p>
          <p className="mt-2.5 text-[11px] leading-5 text-[#6f8494]">
            No verdict is implied either way: the chain was not walked.
          </p>
        </div>
      </Shell>
    );
  }

  const payload = state.payload;
  const chain = payload.chain;
  const receipt = payload.receipt;
  const verdict = readVerdict(payload);

  const receiptCertifies =
    receipt.present && typeof receipt.head_hash === "string"
      ? `${shortHash(receipt.head_hash) || "none (genesis)"} over ${receipt.chain_length ?? "unknown"} event(s)`
      : "nothing";
  const signatureVerified = receipt.present && receipt.verified;
  const verifyingKey = receipt.verified_with_key_id || "";
  const recordedKey = receipt.signature_key_id || "";

  return (
    <Shell className={className} onRefresh={reVerify} status={chain.algorithm}>
      <div className={`border-b bg-[#0a141c]/70 px-4 py-3.5 ${TONE_RULE[verdict.tone]}`}>
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={`inline-flex border px-2 py-0.5 font-mono text-[9px] font-semibold uppercase tracking-[0.14em] ${TONE_BADGE[verdict.tone]}`}
          >
            {verdict.label}
          </span>
          <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-[#526979]">
            payload verified: {String(payload.verified)}
          </span>
          <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-[#526979]">
            receipted: {String(payload.receipted)}
          </span>
        </div>
        <p className="mt-2 text-[11px] leading-5 text-[#c8d6e0]">{verdict.sentence}</p>
        <p className="mt-2 break-all font-mono text-[10px] leading-4 text-[#526979]">
          {payload.intent_id}
        </p>
      </div>

      <div className="border-b border-[#22384a] px-4 py-3">
        <p className="text-[11px] leading-5 text-[#93a6b5]">
          <span className="text-white">Intact</span> means the walk found no break.{" "}
          <span className="text-white">Complete</span> means that and every event carries a hash. A
          verdict of verified needs a complete chain AND a receipt certifying exactly that chain, so
          an intact chain that is not complete is receipted on trust rather than on proof.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-x-4 gap-y-2.5 px-4 py-3 sm:grid-cols-3">
        <Fact
          label="Chain intact"
          value={chain.intact ? "yes" : "no"}
          tone={chain.intact ? "good" : "bad"}
          note={chain.intact ? "no break found" : "breaks listed below"}
        />
        <Fact
          label="Chain complete"
          value={chain.complete ? "yes" : "no"}
          tone={chain.complete ? "good" : "warn"}
          note={chain.complete ? "every event hashed" : "not every event carries a hash"}
        />
        <Fact label="Events on chain" value={String(chain.length)} />
        <Fact
          label="Hashed"
          value={String(chain.hashed)}
          tone={chain.hashed > 0 ? "good" : "warn"}
        />
        <Fact
          label="Unhashed"
          value={String(chain.unhashed)}
          tone={chain.unhashed === 0 ? "good" : "warn"}
          note={chain.unhashed === 0 ? undefined : "written before migration 019"}
        />
        <Fact
          label="Head hash"
          value={shortHash(chain.head_hash) || "none (genesis)"}
          title={chain.head_hash || "empty: the chain has no stored hash"}
          note={`chain version ${chain.chain_version}, ${chain.algorithm}`}
        />
        <Fact
          label="Receipt present"
          value={receipt.present ? "yes" : "no"}
          tone={receipt.present ? "good" : "warn"}
          note={receipt.receipt_id ? receipt.receipt_id : undefined}
        />
        <Fact
          label="Signature verified"
          value={receipt.present ? (signatureVerified ? "yes" : "no") : "no receipt"}
          tone={receipt.present ? (signatureVerified ? "good" : "bad") : "warn"}
          note={receipt.signature_algorithm}
        />
        <Fact
          label="Verified under key"
          value={verifyingKey || (receipt.present ? "no key in the ring verified it" : "not applicable")}
          tone={verifyingKey ? "good" : receipt.present ? "bad" : undefined}
          note={
            receipt.present
              ? recordedKey
                ? `recorded at issue: ${recordedKey}`
                : "no key id recorded at issue"
              : undefined
          }
        />
        <Fact
          label="Current signing key"
          value={
            receipt.present
              ? receipt.signed_with_current_key === true
                ? "yes"
                : receipt.signed_with_current_key === false
                  ? "no"
                  : "not reported"
              : "not applicable"
          }
          tone={
            receipt.present && receipt.signed_with_current_key === false ? "warn" : undefined
          }
          note={
            receipt.present && receipt.signed_with_current_key === false
              ? "signed before a rotation, verified from the ring"
              : undefined
          }
        />
        <Fact
          label="Receipt certifies"
          value={receiptCertifies}
          title={receipt.head_hash || undefined}
          note={
            receipt.present && receipt.head_hash !== undefined && receipt.head_hash !== chain.head_hash
              ? "this is not the chain's current head"
              : undefined
          }
        />
        <Fact
          label="Issued / verified at"
          value={`${receipt.issued_at || "not issued"} / ${payload.verified_at}`}
          title={`receipt digest: ${receipt.digest || "none"}`}
          note={receipt.signature ? `signature ${shortHash(receipt.signature)}` : undefined}
        />
      </div>

      <div className="space-y-3.5 border-t border-[#22384a] px-4 py-3.5">
        <Findings heading="Chain findings" findings={chain.findings} />
        <Findings heading="Receipt findings" findings={receipt.findings} />
      </div>

      <footer className="border-t border-[#22384a] px-4 py-2.5 text-[9px] leading-4 text-[#526979]">
        Read only. Every field is recomputed from the stored rows by the verifier and reported
        verbatim here; a verdict is never repaired, and no finding is summarised away.
      </footer>
    </Shell>
  );
}

export default ProvenanceCard;
