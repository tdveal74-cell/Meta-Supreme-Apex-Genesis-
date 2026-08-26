"use client";

import { useCallback, useEffect, useState } from "react";
import { API_BASE } from "@/lib/api-base";

const TOKEN_KEY = "devon-chat-token";

type IntelligenceStatus = {
  provider?: string;
  model?: string;
  simulated?: boolean;
};

type PasskeyStatus = {
  available?: boolean;
  credentials?: number;
  rp_id?: string;
};

function tokenFromStorage() {
  try {
    return localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY) || "";
  } catch {
    return "";
  }
}

function bufferFromBase64url(value: string): ArrayBuffer {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized + "=".repeat((4 - (normalized.length % 4)) % 4);
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return bytes.buffer;
}

function base64urlFromBuffer(value: ArrayBuffer | null): string | null {
  if (!value) return null;
  const bytes = new Uint8Array(value);
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function registrationOptions(value: any): PublicKeyCredentialCreationOptions {
  return {
    ...value,
    challenge: bufferFromBase64url(value.challenge),
    user: { ...value.user, id: bufferFromBase64url(value.user.id) },
    excludeCredentials: (value.excludeCredentials || []).map((item: any) => ({
      ...item,
      id: bufferFromBase64url(item.id),
    })),
  } as PublicKeyCredentialCreationOptions;
}

function authenticationOptions(value: any): PublicKeyCredentialRequestOptions {
  return {
    ...value,
    challenge: bufferFromBase64url(value.challenge),
    allowCredentials: (value.allowCredentials || []).map((item: any) => ({
      ...item,
      id: bufferFromBase64url(item.id),
    })),
  } as PublicKeyCredentialRequestOptions;
}

function serializeRegistration(credential: PublicKeyCredential) {
  const response = credential.response as AuthenticatorAttestationResponse;
  return {
    id: credential.id,
    rawId: base64urlFromBuffer(credential.rawId),
    type: credential.type,
    authenticatorAttachment: credential.authenticatorAttachment,
    clientExtensionResults: credential.getClientExtensionResults(),
    response: {
      clientDataJSON: base64urlFromBuffer(response.clientDataJSON),
      attestationObject: base64urlFromBuffer(response.attestationObject),
      transports: typeof response.getTransports === "function" ? response.getTransports() : [],
    },
  };
}

function serializeAuthentication(credential: PublicKeyCredential) {
  const response = credential.response as AuthenticatorAssertionResponse;
  return {
    id: credential.id,
    rawId: base64urlFromBuffer(credential.rawId),
    type: credential.type,
    authenticatorAttachment: credential.authenticatorAttachment,
    clientExtensionResults: credential.getClientExtensionResults(),
    response: {
      clientDataJSON: base64urlFromBuffer(response.clientDataJSON),
      authenticatorData: base64urlFromBuffer(response.authenticatorData),
      signature: base64urlFromBuffer(response.signature),
      userHandle: base64urlFromBuffer(response.userHandle),
    },
  };
}

async function errorText(response: Response) {
  try {
    const body = await response.json();
    return typeof body?.detail === "string" ? body.detail : JSON.stringify(body);
  } catch {
    return `${response.status} ${response.statusText}`;
  }
}

export function PasskeyAccess() {
  const [supported, setSupported] = useState(false);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [passkeys, setPasskeys] = useState<PasskeyStatus | null>(null);
  const [mind, setMind] = useState<IntelligenceStatus | null>(null);

  const refresh = useCallback(async () => {
    const token = tokenFromStorage();
    if (!token) {
      setPasskeys(null);
      setMind(null);
      return;
    }
    const headers = { Authorization: `Bearer ${token}` };
    const [passkeyResult, mindResult] = await Promise.allSettled([
      fetch(`${API_BASE}/auth/passkeys/status`, { headers, cache: "no-store" }),
      fetch(`${API_BASE}/intelligence/status`, { headers, cache: "no-store" }),
    ]);
    if (passkeyResult.status === "fulfilled" && passkeyResult.value.ok) {
      setPasskeys(await passkeyResult.value.json());
    }
    if (mindResult.status === "fulfilled" && mindResult.value.ok) {
      setMind(await mindResult.value.json());
    }
  }, []);

  useEffect(() => {
    setSupported(
      typeof window !== "undefined" &&
        typeof PublicKeyCredential !== "undefined" &&
        Boolean(navigator.credentials),
    );
    void refresh();
    const onFocus = () => void refresh();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [refresh]);

  async function usePasskey() {
    if (!supported || busy) return;
    setBusy(true);
    setMessage("");
    try {
      const optionResponse = await fetch(`${API_BASE}/auth/passkeys/login/options`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (!optionResponse.ok) throw new Error(await errorText(optionResponse));
      const ceremony = await optionResponse.json();
      const credential = (await navigator.credentials.get({
        publicKey: authenticationOptions(ceremony.publicKey),
      })) as PublicKeyCredential | null;
      if (!credential) throw new Error("No passkey was selected.");

      const completed = await fetch(`${API_BASE}/auth/passkeys/login/complete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          challenge_id: ceremony.challenge_id,
          credential: serializeAuthentication(credential),
        }),
      });
      if (!completed.ok) throw new Error(await errorText(completed));
      const token = await completed.json();
      localStorage.setItem(TOKEN_KEY, token.access_token);
      setMessage("Passkey accepted. Waking DEVON.");
      window.location.reload();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  async function addPasskey() {
    if (!supported || busy) return;
    const token = tokenFromStorage();
    if (!token) {
      setMessage("Sign in once with your password, then register this device as a passkey.");
      return;
    }
    setBusy(true);
    setMessage("");
    try {
      const headers = {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      };
      const optionResponse = await fetch(`${API_BASE}/auth/passkeys/register/options`, {
        method: "POST",
        headers,
      });
      if (!optionResponse.ok) throw new Error(await errorText(optionResponse));
      const ceremony = await optionResponse.json();
      const credential = (await navigator.credentials.create({
        publicKey: registrationOptions(ceremony.publicKey),
      })) as PublicKeyCredential | null;
      if (!credential) throw new Error("Passkey creation was cancelled.");

      const completed = await fetch(`${API_BASE}/auth/passkeys/register/complete`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          challenge_id: ceremony.challenge_id,
          credential: serializeRegistration(credential),
          label: "DEVON Command Center passkey",
        }),
      });
      if (!completed.ok) throw new Error(await errorText(completed));
      setMessage("Passkey registered. This device can wake DEVON without your password.");
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  const provider = mind
    ? mind.simulated
      ? "MOCK"
      : `${String(mind.provider || "unknown").toUpperCase()} · ${mind.model || "model unknown"}`
    : "LOCKED";
  const cerebrasLive = String(mind?.provider || "").toLowerCase() === "cerebras" && !mind?.simulated;

  return (
    <div className="fixed bottom-3 right-3 z-[65] sm:bottom-5 sm:right-5">
      {open && (
        <section className="mb-2 w-[min(92vw,390px)] border border-[#3e617c] bg-[#071016]/95 shadow-2xl shadow-black/50 backdrop-blur-xl">
          <header className="border-b border-[#22384a] px-4 py-3">
            <p className="font-mono text-[9px] uppercase tracking-[0.2em] text-[#c77b4a]">Trusted access</p>
            <p className="mt-1 text-sm font-semibold text-white">Passkey + live intelligence identity</p>
          </header>
          <div className="space-y-4 p-4">
            <div className="border border-[#22384a] bg-black/20 p-3">
              <div className="flex items-center justify-between gap-3">
                <span className="font-mono text-[9px] uppercase tracking-[0.14em] text-[#6f8494]">DEVON mind</span>
                <span className={`h-2 w-2 rounded-full ${cerebrasLive ? "bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,.7)]" : mind ? "bg-amber-300" : "bg-sky-300"}`} />
              </div>
              <p className="mt-2 font-mono text-[11px] text-white">{provider}</p>
              {mind && !cerebrasLive && (
                <p className="mt-2 text-[10px] leading-4 text-amber-200/80">Cerebras is expected for the live Railway lane. Current runtime reports a different provider.</p>
              )}
            </div>

            <div>
              <p className="text-xs leading-5 text-[#93a6b5]">
                {passkeys?.available
                  ? `${passkeys.credentials} passkey${passkeys.credentials === 1 ? "" : "s"} registered. Password remains recovery only.`
                  : "Use your device passkey to wake DEVON. Register it once after a normal sign-in."}
              </p>
              <div className="mt-3 grid grid-cols-2 gap-2">
                <button
                  type="button"
                  disabled={!supported || busy}
                  onClick={() => void usePasskey()}
                  className="min-h-11 border border-[#4fb3a5]/45 bg-[#4fb3a5]/10 px-3 text-xs font-semibold text-[#8fd5cb] transition hover:bg-[#4fb3a5]/20 disabled:opacity-40"
                >
                  Use passkey
                </button>
                <button
                  type="button"
                  disabled={!supported || busy}
                  onClick={() => void addPasskey()}
                  className="min-h-11 border border-[#d4a017]/40 bg-[#d4a017]/10 px-3 text-xs font-semibold text-[#e8c866] transition hover:bg-[#d4a017]/20 disabled:opacity-40"
                >
                  Add passkey
                </button>
              </div>
              {!supported && <p className="mt-2 text-[10px] text-amber-200/80">This browser does not expose WebAuthn passkeys.</p>}
              {message && <p className="mt-2 text-[10px] leading-4 text-[#93a6b5]">{message}</p>}
            </div>
          </div>
        </section>
      )}

      <button
        type="button"
        onClick={() => {
          setOpen((value) => !value);
          if (!open) void refresh();
        }}
        className="flex items-center gap-2 border border-[#d4a017]/45 bg-[#091017]/95 px-3 py-2.5 font-mono text-[9px] font-semibold uppercase tracking-[0.16em] text-[#e8c866] shadow-xl shadow-black/40 backdrop-blur transition hover:bg-[#d4a017]/10"
        aria-expanded={open}
      >
        <span className={`h-2 w-2 rounded-full ${cerebrasLive ? "bg-emerald-400" : "bg-amber-300"}`} />
        Passkey · {cerebrasLive ? "Cerebras" : "Access"}
      </button>
    </div>
  );
}
