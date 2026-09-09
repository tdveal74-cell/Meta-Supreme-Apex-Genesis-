"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { TOKEN_SLOT, readDevonToken } from "@/components/presence/usePresenceSocket";

/**
 * The way in.
 *
 * Found in the shipped production bundle rather than in source, on 2026-09-09,
 * when Tee opened /control on the deployed surface: four panels tell the reader
 * to sign in through Talk to DEVON, and the page offered nothing to tap. The
 * only outbound links on the whole page were /shell and /terminal. A page that
 * names its own fix and does not offer it is a dead end, and on a phone there is
 * no address bar habit to fall back on.
 *
 * WHAT THIS DELIBERATELY DOES NOT CLAIM
 *
 * A token in this browser is not a valid session. It can be expired, revoked,
 * or minted against a different API than the one the panels call, and nothing
 * here can tell. So the signed in state reads "Session on this device", which is
 * exactly what was checked, rather than "Signed in", which is a claim about the
 * server. This is the same discipline that renamed the panel badge from "Live
 * data" to "Fully sourced" after a browser run showed it overclaiming.
 *
 * The token is read in an effect rather than during render because localStorage
 * does not exist on the server, and reading it during render would hydrate a
 * signed out shell over a signed in one.
 */

/** Both doors mint the same `devon-chat-token`, so either one unlocks the panels. */
const DOORS = {
  passkey: { href: "/command-center", label: "Sign in" },
  chat: { href: "/devon", label: "Talk to DEVON" },
} as const;

export function SessionDoor() {
  // `null` is "not read yet", which is the server render and the first client
  // paint. It is not the same as "no token" and must not render as signed out.
  const [hasToken, setHasToken] = useState<boolean | null>(null);

  useEffect(() => {
    const read = () => setHasToken(Boolean(readDevonToken()));
    read();
    // PresenceStage watches the same slot. A sign in on another tab should
    // unlock this one without a reload.
    const onStorage = (event: StorageEvent) => {
      if (event.key === null || event.key === TOKEN_SLOT) read();
    };
    window.addEventListener("storage", onStorage);
    // Signing in happens on another route, so returning to this tab is the
    // common case rather than a cross tab write.
    window.addEventListener("focus", read);
    return () => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener("focus", read);
    };
  }, []);

  if (hasToken === null) {
    // Reserve the row so the header does not jump once the read lands.
    return <div className="h-[30px]" aria-hidden />;
  }

  if (hasToken) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-400/30 bg-emerald-400/10 px-2.5 py-1.5 text-[11px] font-medium text-emerald-200">
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-300" aria-hidden />
        Session on this device
      </span>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="inline-flex items-center gap-1.5 rounded-lg border border-amber-400/30 bg-amber-400/10 px-2.5 py-1.5 text-[11px] font-medium text-amber-200">
        <span className="h-1.5 w-1.5 rounded-full bg-amber-300" aria-hidden />
        No session on this device
      </span>
      <Link
        href={DOORS.passkey.href}
        className="rounded-lg border border-white/25 px-2.5 py-1.5 text-[11px] font-semibold text-white transition hover:border-white/45"
      >
        {DOORS.passkey.label}
      </Link>
      <Link
        href={DOORS.chat.href}
        className="rounded-lg px-1.5 py-1.5 text-[11px] font-medium text-white/60 underline decoration-white/25 underline-offset-2 transition hover:text-white"
      >
        {DOORS.chat.label}
      </Link>
    </div>
  );
}
