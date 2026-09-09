// The shape of GET /api/v1/ledger/intents/{intent_id}/provenance.
//
// Every key below was read from the two files that produce the payload, never
// guessed: `LiveStateLedger.verify_provenance` in
// `app/services/live_state_ledger.py` builds the top level and the receipt
// report, and `ChainVerdict.to_dict` in `services/devon/provenance.py` builds
// the chain block. A key the writer does not emit is not declared here.
//
// The distinction the card exists to make legible lives in two of these fields.
// `intact` means the walk over the chain found no break. `complete` means that
// AND every event carries a hash, which is why `verified` is
// `complete && receipted && receipt.verified` in the writer rather than
// `intact && receipted`. Rows written before migration 019 carry an empty hash
// and are counted as `unhashed`; a receipt over such a chain certifies those
// rows on trust rather than on proof, and the writer appends a finding saying
// exactly that. Rendering a green state for an intact but incomplete chain
// would throw away the safeguard, so this module never collapses the two.

/** The chain block: `ChainVerdict.to_dict()`. */
export type ProvenanceChain = {
  /** No break was found by the walk. Findings empty. */
  intact: boolean;
  /** Intact AND every event hashed AND the chain is not empty. */
  complete: boolean;
  /** Events on the intent, counted from the stored rows. */
  length: number;
  /** Events carrying a hash. */
  hashed: number;
  /** Events carrying an empty hash, written before migration 019. */
  unhashed: number;
  /** The last stored hash, which is what a receipt binds to. Empty is GENESIS. */
  head_hash: string;
  /** Every break by sequence number, plus the intent row identity findings. */
  findings: string[];
  /** "sha256". */
  algorithm: string;
  /** Bumped only when the canonical hashed material changes shape. */
  chain_version: number;
};

/**
 * The receipt report.
 *
 * When the intent holds no receipt the writer emits exactly three keys,
 * `present`, `verified` and `findings`, so every other field is optional here
 * rather than defaulted to something the payload never said.
 */
export type ProvenanceReceipt = {
  present: boolean;
  /** No receipt finding. False whenever the receipt is absent. */
  verified: boolean;
  findings: string[];
  receipt_id?: string;
  issued_at?: string;
  /** The chain head the receipt certifies, which can differ from the live head. */
  head_hash?: string;
  /** The event count the receipt certifies. */
  chain_length?: number;
  digest?: string;
  signature?: string;
  /** The writer emits "hmac-sha256". */
  signature_algorithm?: string;
  /** The key id recorded on the row when the receipt was issued. */
  signature_key_id?: string;
  /** The ring key that actually verified the signature. Empty when none did. */
  verified_with_key_id?: string;
  /** Whether the verifying key is the one this process signs with now. */
  signed_with_current_key?: boolean;
};

export type ProvenancePayload = {
  intent_id: string;
  /** complete chain AND a receipt that certifies exactly that chain. */
  verified: boolean;
  receipted: boolean;
  chain: ProvenanceChain;
  receipt: ProvenanceReceipt;
  verified_at: string;
};

/**
 * A real check on the body before anything renders a verdict from it.
 *
 * A 200 with a body that does not carry these keys must not become a green
 * tick by way of `undefined` reading as falsy in one place and truthy in
 * another. The card reports the mismatch instead.
 */
export function isProvenancePayload(value: unknown): value is ProvenancePayload {
  if (typeof value !== "object" || value === null) return false;
  const body = value as Record<string, unknown>;
  if (typeof body.intent_id !== "string") return false;
  if (typeof body.verified !== "boolean") return false;
  if (typeof body.receipted !== "boolean") return false;
  if (typeof body.verified_at !== "string") return false;

  const chain = body.chain as Record<string, unknown> | null | undefined;
  if (typeof chain !== "object" || chain === null) return false;
  if (typeof chain.intact !== "boolean") return false;
  if (typeof chain.complete !== "boolean") return false;
  if (typeof chain.length !== "number") return false;
  if (typeof chain.hashed !== "number") return false;
  if (typeof chain.unhashed !== "number") return false;
  if (typeof chain.head_hash !== "string") return false;
  if (!Array.isArray(chain.findings)) return false;

  const receipt = body.receipt as Record<string, unknown> | null | undefined;
  if (typeof receipt !== "object" || receipt === null) return false;
  if (typeof receipt.present !== "boolean") return false;
  if (typeof receipt.verified !== "boolean") return false;
  if (!Array.isArray(receipt.findings)) return false;

  return true;
}

export type VerdictTone = "good" | "warn" | "bad";

export type VerdictCode =
  | "verified"
  | "chain_broken"
  | "no_chain"
  | "receipted_on_trust"
  | "incomplete_unreceipted"
  | "unreceipted"
  | "receipt_unsound"
  | "payload_disagrees";

export type Verdict = {
  code: VerdictCode;
  label: string;
  tone: VerdictTone;
  /** Why this is the verdict, in the payload's own terms. */
  sentence: string;
};

function plural(count: number, one: string, many: string): string {
  return count === 1 ? one : many;
}

/**
 * The verdict, in the order the writer's own definition of `verified` implies.
 *
 * A break outranks everything, because nothing downstream of a broken chain
 * can be trusted. An intact chain that is not complete is next, and it never
 * reaches a good tone no matter how sound the receipt is: that is the case the
 * migration produced and the case a green tick would erase.
 */
export function readVerdict(payload: ProvenancePayload): Verdict {
  const { chain, receipt } = payload;

  if (!chain.intact) {
    const count = chain.findings.length;
    return {
      code: "chain_broken",
      label: "CHAIN BROKEN",
      tone: "bad",
      sentence:
        `The walk over ${chain.length} stored ${plural(chain.length, "event", "events")} found ` +
        `${count} ${plural(count, "break", "breaks")}. Each one is listed below, verbatim, ` +
        "as the verifier wrote it.",
    };
  }

  if (chain.length === 0) {
    return {
      code: "no_chain",
      label: "NO CHAIN",
      tone: "bad",
      sentence:
        "The intent holds no events, so there is no chain to walk and nothing a receipt " +
        "could certify. The verifier reports this rather than reading an empty chain as sound.",
    };
  }

  if (!chain.complete) {
    const rows = `${chain.unhashed} of ${chain.length} ${plural(chain.length, "event", "events")}`;
    if (receipt.present) {
      return {
        code: "receipted_on_trust",
        label: "RECEIPTED ON TRUST",
        tone: "warn",
        sentence:
          `No break was found, so the chain is intact, but ${rows} carry no hash, so it is ` +
          "not complete. The receipt certifies those rows on trust, not on proof, and the " +
          "verifier cannot tell history written before migration 019 from rows planted to " +
          "look like it. This is not a verified intent.",
      };
    }
    return {
      code: "incomplete_unreceipted",
      label: "INCOMPLETE, UNRECEIPTED",
      tone: "bad",
      sentence:
        `No break was found, but ${rows} carry no hash, so the chain is intact and not ` +
        "complete. No receipt certifies it either, on trust or otherwise.",
    };
  }

  if (!payload.receipted) {
    return {
      code: "unreceipted",
      label: "UNRECEIPTED",
      tone: "warn",
      sentence:
        `Every one of the ${chain.length} ${plural(chain.length, "event", "events")} is hashed ` +
        "and every link is sound, so the chain is complete. The intent holds no receipt, so " +
        "nothing certifies that chain and the intent is not verified.",
    };
  }

  if (!receipt.verified) {
    const count = receipt.findings.length;
    return {
      code: "receipt_unsound",
      label: "RECEIPT UNSOUND",
      tone: "bad",
      sentence:
        "The chain is complete, but the receipt over it does not check out. " +
        `${count} receipt ${plural(count, "finding", "findings")} ${plural(count, "is", "are")} ` +
        "listed below, verbatim.",
    };
  }

  if (payload.verified) {
    return {
      code: "verified",
      label: "VERIFIED",
      tone: "good",
      sentence:
        `All ${chain.length} ${plural(chain.length, "event", "events")} are hashed, every link ` +
        "recomputes, and the receipt certifies exactly this chain head and length under a key " +
        "this process holds.",
    };
  }

  return {
    code: "payload_disagrees",
    label: "PAYLOAD DISAGREES WITH ITSELF",
    tone: "bad",
    sentence:
      "The chain reads complete, a receipt is present and the receipt report reads verified, " +
      "yet the payload's own `verified` is false. The card reports the disagreement rather " +
      "than picking the half it prefers.",
  };
}

/**
 * A hash shortened for reading, at the twelve characters the verifier itself
 * uses in its findings. The full value belongs in a title attribute, never
 * dropped.
 */
export function shortHash(hash: string, keep = 12): string {
  if (!hash) return "";
  return hash.length <= keep ? hash : `${hash.slice(0, keep)}...`;
}
