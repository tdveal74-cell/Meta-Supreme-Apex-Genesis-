"use client";

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { API_BASE } from "@/lib/api-base";

type Role = "you" | "devon" | "system";

type ChatMessage = {
  id: number;
  role: Role;
  text: string;
  chips?: string[];
};

type PendingApproval = {
  taskId: string;
  requestId: string;
  token: string;
  title: string;
};

type IntelligenceStatus = {
  provider: string;
  model: string;
  simulated: boolean;
};

const TOKEN_KEY = "devon-chat-token";
const EMAIL_KEY = "devon-chat-email";

const QUESTION_START =
  /^(what|who|whom|whose|why|how|when|where|which|is|are|am|was|were|can|could|should|shall|do|does|did|will|would|may|might|explain|tell me|talk to me|describe|summarize|compare)\b/i;

function looksLikeQuestion(text: string): boolean {
  const t = text.trim();
  return t.endsWith("?") || QUESTION_START.test(t);
}

function errorMessage(value: unknown): string {
  if (value instanceof Error) return value.message;
  return String(value);
}

async function readApiError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") return body.detail;
    return JSON.stringify(body);
  } catch {
    return `${response.status} ${response.statusText}`;
  }
}

/**
 * Talk to DEVON: one input, voice in and voice out, and he executes.
 * Questions go to the Council (/intelligence/ask). Directives become agent
 * tasks (/agent-tasks) — reads run, writes stop at an approval card that is
 * ruled on right here. Works on a phone: big targets, mic behind a tap.
 */
export function DevonChat() {
  const [token, setToken] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [authBusy, setAuthBusy] = useState(false);
  const [authError, setAuthError] = useState("");
  const [status, setStatus] = useState<IntelligenceStatus | null>(null);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<"auto" | "ask" | "do">("auto");
  const [pending, setPending] = useState<PendingApproval | null>(null);

  const [voiceOut, setVoiceOut] = useState(true);
  const [listening, setListening] = useState(false);
  const [voiceSupported, setVoiceSupported] = useState(false);

  const sequence = useRef(10);
  const endRef = useRef<HTMLDivElement | null>(null);
  const recognitionRef = useRef<any>(null);
  const voiceOutRef = useRef(voiceOut);
  voiceOutRef.current = voiceOut;

  const authed = Boolean(token);

  const append = useCallback((role: Role, text: string, chips?: string[]) => {
    if (!text) return;
    sequence.current += 1;
    setMessages((current) => [...current, { id: sequence.current, role, text, chips }]);
  }, []);

  const speak = useCallback((text: string) => {
    if (!voiceOutRef.current) return;
    try {
      const synth = window.speechSynthesis;
      if (!synth) return;
      synth.cancel();
      const utterance = new SpeechSynthesisUtterance(
        text.replace(/[*_#`>]/g, "").slice(0, 600),
      );
      const voices = synth.getVoices();
      const preferred =
        voices.find((v) => /en[-_]GB/i.test(v.lang) && /male|daniel|arthur/i.test(v.name)) ||
        voices.find((v) => /en[-_]/i.test(v.lang));
      if (preferred) utterance.voice = preferred;
      utterance.rate = 1.02;
      synth.speak(utterance);
    } catch {
      // Voice output is a convenience; silence is an acceptable failure.
    }
  }, []);

  // Restore a session and greet once.
  useEffect(() => {
    try {
      const saved = sessionStorage.getItem(TOKEN_KEY) || "";
      const savedEmail = sessionStorage.getItem(EMAIL_KEY) || "";
      if (saved) setToken(saved);
      if (savedEmail) setEmail(savedEmail);
    } catch {
      // Private browsing can refuse storage; the session just will not persist.
    }
    setVoiceSupported(
      typeof window !== "undefined" &&
        Boolean((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition),
    );
    append(
      "devon",
      "DEVON online. Ask me anything, or tell me what needs doing — reads run on my say-so, writes wait on yours.",
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, pending]);

  const authedFetch = useCallback(
    (path: string, init?: RequestInit) =>
      fetch(`${API_BASE}${path}`, {
        ...init,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
          ...(init?.headers || {}),
        },
      }),
    [token],
  );

  // Once signed in, learn whether the mind is live or simulated — and say so.
  useEffect(() => {
    if (!token) return;
    let active = true;
    authedFetch("/intelligence/status")
      .then(async (r) => (r.ok ? ((await r.json()) as IntelligenceStatus) : null))
      .then((data) => {
        if (active && data) setStatus(data);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [token, authedFetch]);

  async function signIn(event?: FormEvent) {
    event?.preventDefault();
    if (!email || !password || authBusy) return;
    setAuthBusy(true);
    setAuthError("");
    try {
      let response = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (response.status === 401) {
        // No account yet — create one, then sign in with the same credentials.
        const registered = await fetch(`${API_BASE}/auth/register`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password, full_name: "Tee" }),
        });
        if (!registered.ok && registered.status !== 409) {
          throw new Error(await readApiError(registered));
        }
        response = await fetch(`${API_BASE}/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });
      }
      if (!response.ok) throw new Error(await readApiError(response));
      const data = await response.json();
      setToken(data.access_token);
      try {
        sessionStorage.setItem(TOKEN_KEY, data.access_token);
        sessionStorage.setItem(EMAIL_KEY, email);
      } catch {
        // Storage refusal only costs persistence.
      }
      append("devon", "Signed in. I'm listening.");
    } catch (error) {
      setAuthError(errorMessage(error));
    } finally {
      setAuthBusy(false);
    }
  }

  function signOut() {
    setToken("");
    setStatus(null);
    setPending(null);
    try {
      sessionStorage.removeItem(TOKEN_KEY);
    } catch {
      // Nothing to clean if storage was never writable.
    }
  }

  const runTask = useCallback(
    async (taskId: string) => {
      const response = await authedFetch(`/agent-tasks/${taskId}/run`, {
        method: "POST",
        headers: { "Idempotency-Key": `chat-${taskId}-${Date.now()}` },
        body: JSON.stringify({ max_steps: 20 }),
      });
      if (!response.ok) throw new Error(await readApiError(response));
      const result = await response.json();
      const task = result.task || {};
      const state = String(task.state || "");

      if (state === "waiting_approval") {
        const steps = task.plan?.steps || [];
        const step = steps[task.current_step] || null;
        const requestId = step?.approval_request_id || "";
        const title = step?.title || "an effectful step";
        if (result.approval_token && requestId) {
          setPending({ taskId, requestId, token: result.approval_token, title });
          const line = `This next move writes something real: ${title}. I need your ruling before I touch it.`;
          append("devon", line);
          speak(line);
        } else {
          append("system", "Waiting on an approval that was raised earlier for this task.");
        }
        return;
      }

      if (state === "completed") {
        const summary = String(task.final_summary || "Done.");
        append("devon", summary);
        speak(summary);
        return;
      }

      if (state === "failed" || state === "cancelled") {
        const reason = String(task.failure_reason || state);
        const line =
          state === "cancelled"
            ? `Understood — standing down. ${reason}`
            : `That one didn't land: ${reason}`;
        append("devon", line);
        speak(line);
        return;
      }

      append("system", `Task ${state}: ${String(result.message || "")}`);
    },
    [append, authedFetch, speak],
  );

  const execute = useCallback(
    async (goal: string) => {
      const created = await authedFetch("/agent-tasks", {
        method: "POST",
        body: JSON.stringify({ goal }),
      });
      if (!created.ok) throw new Error(await readApiError(created));
      const task = await created.json();
      const stepTitles = (task.plan?.steps || [])
        .map((s: any) => String(s.title || ""))
        .filter(Boolean);
      const opener =
        stepTitles.length > 0
          ? `On it. ${stepTitles.length} step${stepTitles.length === 1 ? "" : "s"}: ${stepTitles.join(" → ")}. Running now.`
          : "On it.";
      append("devon", opener);
      speak(opener);
      await runTask(String(task.task_id));
    },
    [append, authedFetch, runTask, speak],
  );

  const ask = useCallback(
    async (question: string) => {
      const response = await authedFetch("/intelligence/ask", {
        method: "POST",
        body: JSON.stringify({ message: question }),
      });
      if (!response.ok) throw new Error(await readApiError(response));
      const data = await response.json();
      append("devon", String(data.response || ""), data.agents_consulted || []);
      speak(String(data.response || ""));
    },
    [append, authedFetch, speak],
  );

  const send = useCallback(
    async (raw?: string) => {
      const text = (raw ?? input).trim();
      if (!text || busy || !token) return;
      setInput("");
      append("you", text);
      setBusy(true);
      try {
        const doExecute = mode === "do" || (mode === "auto" && !looksLikeQuestion(text));
        if (doExecute) {
          await execute(text);
        } else {
          await ask(text);
        }
      } catch (error) {
        const line = `Hit a wall: ${errorMessage(error)}`;
        append("system", line);
        speak("I hit a wall on that one. The details are on screen.");
      } finally {
        setBusy(false);
      }
    },
    [append, ask, busy, execute, input, mode, speak, token],
  );

  const sendRef = useRef(send);
  sendRef.current = send;

  async function decide(decision: "approve" | "refuse") {
    if (!pending || busy) return;
    const current = pending;
    setBusy(true);
    try {
      const response = await fetch(`${API_BASE}/devon/approvals/decide`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          request_id: current.requestId,
          token: current.token,
          decision,
          decided_by: "Tee",
        }),
      });
      if (!response.ok) throw new Error(await readApiError(response));
      setPending(null);
      if (decision === "approve") {
        append("devon", "Ruling received. Executing.");
      }
      await runTask(current.taskId);
    } catch (error) {
      append("system", `Approval flow failed: ${errorMessage(error)}`);
    } finally {
      setBusy(false);
    }
  }

  function toggleMic() {
    if (!voiceSupported) return;
    if (listening) {
      recognitionRef.current?.stop?.();
      setListening(false);
      return;
    }
    try {
      const Recognition =
        (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      const recognition = new Recognition();
      recognition.lang = "en-US";
      recognition.interimResults = true;
      recognition.continuous = false;
      let finalText = "";
      recognition.onresult = (event: any) => {
        let interim = "";
        for (let i = event.resultIndex; i < event.results.length; i += 1) {
          const chunk = event.results[i][0].transcript;
          if (event.results[i].isFinal) finalText += chunk;
          else interim += chunk;
        }
        setInput(finalText + interim);
      };
      recognition.onend = () => {
        setListening(false);
        const spoken = finalText.trim();
        if (spoken) void sendRef.current(spoken);
      };
      recognition.onerror = () => setListening(false);
      recognitionRef.current = recognition;
      setListening(true);
      recognition.start();
    } catch {
      setListening(false);
    }
  }

  const mindLabel = useMemo(() => {
    if (!status) return "";
    return status.simulated
      ? "Simulated mind (mock provider) — add a live key in Railway for the real one"
      : `Live mind: ${status.provider} · ${status.model}`;
  }, [status]);

  return (
    <section className="flex min-h-[60vh] flex-col overflow-hidden rounded-2xl border border-amber-300/20 bg-[#090d12] shadow-2xl shadow-black/30">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 bg-black/20 px-4 py-3 text-xs">
        <div className="flex items-center gap-2">
          <span className={`h-2.5 w-2.5 rounded-full ${authed ? "bg-emerald-400" : "bg-amber-400"}`} />
          <span className="font-mono text-white/60">devon</span>
          {mindLabel && (
            <span className="hidden rounded-full border border-white/10 bg-black/30 px-3 py-1 text-white/45 sm:inline">
              {mindLabel}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setVoiceOut((v) => !v)}
            className={`rounded-full border px-3 py-1 transition ${
              voiceOut
                ? "border-amber-300/40 bg-amber-300/10 text-amber-200"
                : "border-white/10 bg-black/30 text-white/45"
            }`}
          >
            Voice {voiceOut ? "on" : "off"}
          </button>
          {authed && (
            <button
              type="button"
              onClick={signOut}
              className="rounded-md px-2 py-1 text-white/45 transition hover:bg-white/5 hover:text-white/80"
            >
              Sign out
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-5 sm:px-6">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`max-w-[92%] sm:max-w-[80%] ${message.role === "you" ? "ml-auto" : ""}`}
          >
            <div
              className={`whitespace-pre-wrap break-words rounded-2xl px-4 py-3 text-sm leading-6 ${
                message.role === "you"
                  ? "bg-amber-300/15 text-amber-100"
                  : message.role === "devon"
                    ? "border border-white/10 bg-white/[0.04] text-white/85"
                    : "text-white/40"
              }`}
            >
              {message.text}
            </div>
            {message.chips && message.chips.length > 0 && (
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {message.chips.map((chip) => (
                  <span
                    key={chip}
                    className="rounded-full border border-white/10 bg-black/30 px-2 py-0.5 text-[10px] uppercase tracking-wide text-white/40"
                  >
                    {chip}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
        {busy && <p className="text-xs text-white/35">DEVON is working…</p>}
        <div ref={endRef} />
      </div>

      {pending && (
        <div className="border-t border-sky-400/20 bg-sky-400/[0.06] px-4 py-4 sm:px-6">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-sky-300">
            Your ruling required
          </p>
          <p className="mt-1 text-sm text-white">{pending.title}</p>
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={() => void decide("refuse")}
              className="min-h-11 flex-1 rounded-lg border border-white/15 px-4 text-sm font-medium text-white/70 transition hover:bg-white/5 disabled:opacity-40 sm:flex-none sm:px-6"
            >
              Refuse
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void decide("approve")}
              className="min-h-11 flex-1 rounded-lg bg-sky-300 px-4 text-sm font-semibold text-[#071017] transition hover:bg-sky-200 disabled:opacity-40 sm:flex-none sm:px-6"
            >
              Approve and execute
            </button>
          </div>
        </div>
      )}

      {!authed ? (
        <form onSubmit={signIn} className="border-t border-white/10 bg-black/25 p-4 sm:p-5">
          <p className="mb-3 text-xs text-white/45">
            Sign in to wake DEVON. First time with an email creates the account.
          </p>
          <div className="grid gap-3 sm:grid-cols-[1fr_1fr_auto]">
            <input
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              type="email"
              inputMode="email"
              autoComplete="email"
              placeholder="you@example.com"
              className="min-h-11 w-full rounded-lg border border-white/10 bg-black/30 px-3 text-sm text-white outline-none transition placeholder:text-white/25 focus:border-amber-300/40"
            />
            <input
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              type="password"
              autoComplete="current-password"
              placeholder="Password (8+ characters)"
              className="min-h-11 w-full rounded-lg border border-white/10 bg-black/30 px-3 text-sm text-white outline-none transition placeholder:text-white/25 focus:border-amber-300/40"
            />
            <button
              type="submit"
              disabled={authBusy || !email || password.length < 8}
              className="min-h-11 rounded-lg bg-amber-300 px-6 text-sm font-bold text-[#151006] transition hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-30"
            >
              {authBusy ? "Signing in…" : "Sign in"}
            </button>
          </div>
          {authError && <p className="mt-2 text-xs text-red-300">{authError}</p>}
        </form>
      ) : (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void send();
          }}
          className="border-t border-white/10 bg-black/25 p-4 sm:p-5"
        >
          <div className="mb-3 flex flex-wrap items-center gap-2 text-[11px]">
            {(["auto", "ask", "do"] as const).map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => setMode(option)}
                className={`rounded-full border px-3 py-1 uppercase tracking-wide transition ${
                  mode === option
                    ? "border-amber-300/40 bg-amber-300/10 text-amber-200"
                    : "border-white/10 bg-black/30 text-white/40"
                }`}
              >
                {option === "auto" ? "Auto" : option === "ask" ? "Answer" : "Execute"}
              </button>
            ))}
            <span className="text-white/30">
              Auto: questions get answers, directives get done.
            </span>
          </div>
          <div className="flex items-end gap-2">
            {voiceSupported && (
              <button
                type="button"
                onClick={toggleMic}
                aria-label={listening ? "Stop listening" : "Talk to DEVON"}
                className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full border text-lg transition ${
                  listening
                    ? "animate-pulse border-red-400/50 bg-red-400/15 text-red-300"
                    : "border-amber-300/30 bg-amber-300/10 text-amber-200 hover:bg-amber-300/20"
                }`}
              >
                {listening ? "■" : "🎙"}
              </button>
            )}
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void send();
                }
              }}
              disabled={busy}
              rows={2}
              placeholder={listening ? "Listening…" : "Talk to DEVON, or type it"}
              className="min-h-12 flex-1 resize-none rounded-xl border border-white/10 bg-[#05080c] px-4 py-3 text-sm leading-6 text-white outline-none transition placeholder:text-white/25 focus:border-amber-300/35 disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={busy || !input.trim()}
              className="min-h-12 rounded-lg bg-amber-300 px-5 text-xs font-bold text-[#151006] transition hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-30"
            >
              SEND
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
