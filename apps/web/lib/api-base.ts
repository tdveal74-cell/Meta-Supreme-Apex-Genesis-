// One resolution rule for every surface that talks to the DEVON API.
// NEXT_PUBLIC_API_URL wins when set. Otherwise production builds talk to
// the deployed DEVON API on Railway and dev builds to the local API.
export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ||
  (process.env.NODE_ENV === "production"
    ? "https://api-production-5644.up.railway.app/api/v1"
    : "http://localhost:8000/api/v1");

// Same origin as API_BASE, spoken over WebSocket.
export const WS_BASE = API_BASE.replace(/^http/, "ws");

// The presence server (avatar frames, speech, barge-in) is its own service on
// its own Railway host, so it needs its own production fallback. This line
// read `|| "http://localhost:8010"` until 2026-09-09, with no production
// branch at all, which meant a deployed /presence page dialled the visitor's
// own machine and the socket could never open. Nothing failed loudly: the
// page rendered, the connection state sat waiting, and the service it was
// meant to reach had no public address either. Both halves are fixed here and
// on Railway, and scripts/presence-check.ts refuses a build whose production
// branch is missing or points at a loopback address.
//
// NEXT_PUBLIC_PRESENCE_URL still wins when set, so a preview or a self hosted
// compose deployment overrides this without a code change.
export const PRESENCE_BASE =
  process.env.NEXT_PUBLIC_PRESENCE_URL?.replace(/\/$/, "") ||
  (process.env.NODE_ENV === "production"
    ? "https://presence-production-d272.up.railway.app"
    : "http://localhost:8010");

// Same origin as PRESENCE_BASE, spoken over WebSocket.
export const PRESENCE_WS_BASE = PRESENCE_BASE.replace(/^http/, "ws");
