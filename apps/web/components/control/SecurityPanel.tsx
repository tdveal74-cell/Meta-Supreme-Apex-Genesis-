"use client";

import Link from "next/link";

/**
 * Module 5 from the brief: the security shell and the secret vault.
 *
 * The shell half is live and predates this arc, so this panel points at it
 * rather than embedding a second copy. Embedding a live PTY inside the control
 * plane would widen the blast radius of any bug on this page to a shell on the
 * API container, which is not a trade this tier should make quietly.
 *
 * The vault half is deliberately absent. Nothing in the repository generates or
 * stores secrets: every key lives in the environment, and app/core/config.py
 * refuses to start in production on a public default. Adding a vault is a
 * design decision that belongs to Tee, not a file to add on the way past.
 */

const DOORS = [
  {
    href: "/shell",
    label: "Real shell",
    note: "A full PTY on the API container. Two factors: a valid DEVON session and a separate shell key compared in constant time.",
  },
  {
    href: "/terminal",
    label: "Gated terminal",
    note: "DEVON's own execution path, where every WRITE and HIGH_IMPACT call waits for a human.",
  },
] as const;

export function SecurityPanel() {
  return (
    <div className="space-y-4">
      <div className="grid gap-2 sm:grid-cols-2">
        {DOORS.map((door) => (
          <Link
            key={door.href}
            href={door.href}
            className="group rounded-xl border border-white/10 bg-black/25 px-3 py-2.5 transition hover:border-white/25"
          >
            <p className="text-sm font-medium text-white/85 group-hover:text-white">
              {door.label}
            </p>
            <p className="mt-1 text-xs leading-relaxed text-white/50">{door.note}</p>
          </Link>
        ))}
      </div>

      <div className="space-y-2 text-xs leading-relaxed text-white/50">
        <p>
          The shell is not embedded here on purpose. A bug on this page should not
          be able to reach a shell on the API container, so the door stays its own
          route behind its own second factor.
        </p>
        <p>
          A per request signature over the command body is not built. The gate is
          two factors at connect time, and calling that a signed request would
          overstate it.
        </p>
        <p>
          There is no secret vault, no ephemeral password generator and no
          injection into executors. That is deliberate: every key lives in the
          environment and the API refuses to start in production on a public
          default. Whether a vault should exist at all is a ruling for Tee rather
          than something to add quietly.
        </p>
      </div>
    </div>
  );
}
