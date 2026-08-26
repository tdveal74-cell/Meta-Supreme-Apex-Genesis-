"use client";

/**
 * A real terminal: xterm.js in the browser, WebSocket to the API's
 * /operator/shell endpoint, bash in a PTY on the server. Pipes, redirects,
 * arrow keys, interactive programs — everything a local terminal gives.
 *
 * This is the human operator's door. DEVON's own gated command path is a
 * separate surface and stays approval-gated.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";
import { WS_BASE } from "@/lib/api-base";

const KEY_SLOT = "devon-operator-key";

type ShellState = "locked" | "connecting" | "live" | "closed" | "error";

export function RealShell() {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const termRef = useRef<Terminal | null>(null);
  const fitRef = useRef<FitAddon | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const [key, setKey] = useState("");
  const [state, setState] = useState<ShellState>("locked");
  const [note, setNote] = useState("");

  // The terminal key is shared with the gated Operator Terminal.
  useEffect(() => {
    try {
      const saved = localStorage.getItem(KEY_SLOT) || "";
      if (saved) setKey(saved);
    } catch {
      // Storage refusal only costs convenience.
    }
  }, []);

  const disconnect = useCallback(() => {
    socketRef.current?.close();
    socketRef.current = null;
  }, []);

  const connect = useCallback(() => {
    if (!key || state === "connecting" || state === "live") return;
    setState("connecting");
    setNote("");
    try {
      localStorage.setItem(KEY_SLOT, key);
    } catch {
      // Fine — the key still works for this visit.
    }

    const host = containerRef.current;
    if (!host) return;

    // Fresh terminal per connection keeps scrollback honest.
    termRef.current?.dispose();
    const term = new Terminal({
      cursorBlink: true,
      fontSize: 13,
      fontFamily:
        "ui-monospace, SFMono-Regular, Menlo, Monaco, 'Cascadia Mono', monospace",
      theme: {
        background: "#090d12",
        foreground: "#e8edf2",
        cursor: "#fcd34d",
        selectionBackground: "#fcd34d44",
      },
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(host);
    fit.fit();
    termRef.current = term;
    fitRef.current = fit;

    const socket = new WebSocket(`${WS_BASE}/operator/shell`);
    socketRef.current = socket;

    socket.onopen = () => {
      socket.send(
        JSON.stringify({
          type: "hello",
          key,
          cols: term.cols,
          rows: term.rows,
        }),
      );
    };

    socket.onmessage = (event) => {
      let frame: { type?: string; data?: string; message?: string; code?: number };
      try {
        frame = JSON.parse(String(event.data));
      } catch {
        return;
      }
      if (frame.type === "output" && typeof frame.data === "string") {
        term.write(frame.data);
      } else if (frame.type === "ready") {
        setState("live");
        term.focus();
      } else if (frame.type === "exit") {
        setNote(`Shell exited (code ${frame.code}). Reconnect to start a new one.`);
      } else if (frame.type === "error") {
        setState("error");
        setNote(frame.message || "The shell refused the connection.");
      }
    };

    socket.onclose = () => {
      socketRef.current = null;
      setState((current) => (current === "error" ? "error" : "closed"));
    };
    socket.onerror = () => {
      setState("error");
      setNote((current) => current || "Connection failed. Is the API reachable?");
    };

    term.onData((data) => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: "input", data }));
      }
    });
    term.onResize(({ cols, rows }) => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: "resize", cols, rows }));
      }
    });
  }, [key, state]);

  // Keep the terminal sized to its container.
  useEffect(() => {
    const onResize = () => fitRef.current?.fit();
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      socketRef.current?.close();
      termRef.current?.dispose();
    };
  }, []);

  const live = state === "live";

  return (
    <section className="flex min-h-[70vh] flex-col overflow-hidden rounded-2xl border border-amber-300/20 bg-[#090d12] shadow-2xl shadow-black/30">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 bg-black/20 px-4 py-3 text-xs">
        <div className="flex items-center gap-2">
          <span
            className={`h-2.5 w-2.5 rounded-full ${
              live ? "bg-emerald-400" : state === "connecting" ? "bg-amber-400" : "bg-red-400/80"
            }`}
          />
          <span className="font-mono text-white/60">tee@devon — real shell</span>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="password"
            value={key}
            onChange={(event) => setKey(event.target.value)}
            placeholder="Operator key"
            autoComplete="off"
            className="w-44 rounded-lg border border-white/10 bg-black/30 px-3 py-1.5 font-mono text-xs text-white outline-none transition placeholder:text-white/25 focus:border-amber-300/40"
          />
          {live ? (
            <button
              type="button"
              onClick={disconnect}
              className="rounded-lg border border-red-400/30 bg-red-400/10 px-3 py-1.5 font-semibold text-red-200 transition hover:bg-red-400/20"
            >
              Disconnect
            </button>
          ) : (
            <button
              type="button"
              onClick={connect}
              disabled={!key || state === "connecting"}
              className="rounded-lg bg-amber-300 px-4 py-1.5 font-bold text-[#151006] transition hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-30"
            >
              {state === "connecting" ? "Connecting…" : "Connect"}
            </button>
          )}
        </div>
      </div>

      <div className="relative flex-1 p-2">
        <div ref={containerRef} className="h-full min-h-[55vh] w-full" />
        {!live && (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center px-6 text-center">
            <p className="max-w-md text-sm leading-6 text-white/40">
              {note ||
                (state === "connecting"
                  ? "Opening the PTY…"
                  : "Enter your operator key and Connect. This is a full bash shell on the DEVON API container — pipes, redirects, everything.")}
            </p>
          </div>
        )}
      </div>

      <p className="border-t border-white/10 bg-black/25 px-4 py-2.5 text-[11px] leading-4 text-white/30">
        Full shell, no per-command gate: the operator key IS the authority here. The
        container filesystem is ephemeral — redeploys reset anything outside the
        database. DEVON's own execution stays approval-gated on the other terminal.
      </p>
    </section>
  );
}
