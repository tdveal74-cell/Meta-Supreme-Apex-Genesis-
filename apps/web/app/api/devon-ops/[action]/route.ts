import { createHmac } from "crypto";
import { NextRequest, NextResponse } from "next/server";

/**
 * Server-side proxy for the VPS DEVON ops gateway.
 * HMAC signing lives only here. DEVON_OPS_SECRET must never appear in
 * NEXT_PUBLIC_* vars, client bundles, logs, or responses.
 */

const GATEWAY_BASE = "https://ops.editforge.online";

const ALLOWED_ACTIONS = new Set([
  "request",
  "approve",
  "reject",
  "approval-status",
  "health",
]);

const ALLOWED_OPERATIONS: Record<string, Set<string>> = {
  run: new Set(["tqo", "nco"]),
  system: new Set(["pause", "resume"]),
};

function getSecret(): string | null {
  const secret = process.env.DEVON_OPS_SECRET;
  if (!secret || typeof secret !== "string" || secret.length < 16) {
    return null;
  }
  return secret;
}

function sign(timestamp: string, body: string, secret: string): string {
  return createHmac("sha256", secret)
    .update(`${timestamp}\n${body}`)
    .digest("hex");
}

function safeError(message: string, status = 400) {
  return NextResponse.json({ ok: false, error: message }, { status });
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ action: string }> },
) {
  const { action } = await context.params;

  if (!ALLOWED_ACTIONS.has(action)) {
    return safeError(`Unsupported action: ${action}`, 404);
  }

  if (action === "health") {
    // Public health needs no secret.
    try {
      const res = await fetch(`${GATEWAY_BASE}/health`, {
        method: "GET",
        cache: "no-store",
        signal: AbortSignal.timeout(10000),
      });
      const data = await res.json().catch(() => ({}));
      return NextResponse.json(data, { status: res.status });
    } catch {
      return safeError("Gateway health unreachable", 502);
    }
  }

  const secret = getSecret();
  if (!secret) {
    return safeError("VPS gate not configured on this host", 503);
  }

  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return safeError("Invalid JSON body");
  }

  // Enforce allowed operations for request creation.
  if (action === "request") {
    const operation = String(body.operation ?? "");
    const target = String(body.target ?? "");
    const reason = String(body.reason ?? "");

    if (!ALLOWED_OPERATIONS[operation]?.has(target)) {
      return safeError(
        `Operation not allowed. Permitted: run/tqo, run/nco, system/pause, system/resume`,
      );
    }
    if (reason.length < 3 || reason.length > 500) {
      return safeError("Reason must be 3 to 500 characters");
    }
  }

  // Force approved_by / rejected_by to Tee on the server side.
  if (action === "approve") {
    body = { ...body, approved_by: "Tee" };
  }
  if (action === "reject") {
    body = { ...body, rejected_by: "Tee" };
  }

  const pathMap: Record<string, string> = {
    request: "/v1/request",
    approve: "/v1/approve",
    reject: "/v1/reject",
    "approval-status": "/v1/approval-status",
  };

  const path = pathMap[action];
  if (!path) {
    return safeError(`No path for action: ${action}`, 404);
  }

  const exactBody = JSON.stringify(body);
  const timestamp = Math.floor(Date.now() / 1000).toString();
  const signature = sign(timestamp, exactBody, secret);

  try {
    const res = await fetch(`${GATEWAY_BASE}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Devon-Timestamp": timestamp,
        "X-Devon-Signature": signature,
      },
      body: exactBody,
      cache: "no-store",
      signal: AbortSignal.timeout(15000),
    });

    const data = await res.json().catch(() => ({
      ok: false,
      error: "Non-JSON response from gateway",
    }));

    // Strip any accidental secret leakage (defensive).
    if (data && typeof data === "object") {
      delete (data as Record<string, unknown>).secret;
      delete (data as Record<string, unknown>).DEVON_OPS_SECRET;
    }

    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "Gateway request failed";
    return safeError(message, 502);
  }
}

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ action: string }> },
) {
  const { action } = await context.params;

  if (action === "health") {
    try {
      const res = await fetch(`${GATEWAY_BASE}/health`, {
        method: "GET",
        cache: "no-store",
        signal: AbortSignal.timeout(10000),
      });
      const data = await res.json().catch(() => ({}));
      return NextResponse.json(data, { status: res.status });
    } catch {
      return safeError("Gateway health unreachable", 502);
    }
  }

  // approval-status can be queried via POST with body; also support GET with query.
  if (action === "approval-status") {
    const secret = getSecret();
    if (!secret) {
      return safeError("VPS gate not configured on this host", 503);
    }

    const requestId = request.nextUrl.searchParams.get("request_id");
    if (!requestId) {
      return safeError("request_id query parameter required");
    }

    const body = { request_id: requestId };
    const exactBody = JSON.stringify(body);
    const timestamp = Math.floor(Date.now() / 1000).toString();
    const signature = sign(timestamp, exactBody, secret);

    try {
      const res = await fetch(`${GATEWAY_BASE}/v1/approval-status`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Devon-Timestamp": timestamp,
          "X-Devon-Signature": signature,
        },
        body: exactBody,
        cache: "no-store",
        signal: AbortSignal.timeout(15000),
      });

      const data = await res.json().catch(() => ({
        ok: false,
        error: "Non-JSON response from gateway",
      }));

      if (data && typeof data === "object") {
        delete (data as Record<string, unknown>).secret;
        delete (data as Record<string, unknown>).DEVON_OPS_SECRET;
      }

      return NextResponse.json(data, { status: res.status });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Gateway request failed";
      return safeError(message, 502);
    }
  }

  return safeError(`GET not supported for action: ${action}`, 405);
}
