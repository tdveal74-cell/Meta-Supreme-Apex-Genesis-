// One resolution rule for every surface that talks to the DEVON API.
// NEXT_PUBLIC_API_URL wins when set. Otherwise production builds talk to
// the deployed DEVON API on Railway and dev builds to the local API.
export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ||
  (process.env.NODE_ENV === "production"
    ? "https://api-production-5644.up.railway.app/api/v1"
    : "http://localhost:8000/api/v1");
