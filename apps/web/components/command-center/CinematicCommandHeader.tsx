"use client";

import { useCallback, useEffect, useState } from "react";
import { CinematicHud } from "@/components/command-center/CinematicHud";
import { API_BASE } from "@/lib/api-base";

type HudState = "checking" | "online" | "offline" | "locked" | "scheduled";

type IntelligenceStatus = {
  provider?: string;
  model?: string;
  simulated?: boolean;
};

export function CinematicCommandHeader() {
  const [apiState, setApiState] = useState<HudState>("checking");
  const [mindState, setMindState] = useState<HudState>("checking");
  const [operatorState, setOperatorState] = useState<HudState>("checking");
  const [mind, setMind] = useState<IntelligenceStatus | null>(null);
  const [timeLabel, setTimeLabel] = useState("--:--:--");

  const probe = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/health`, { cache: "no-store" });
      setApiState(response.ok ? "online" : "offline");
    } catch {
      setApiState("offline");
    }

    try {
      const response = await fetch(`${API_BASE}/operator/status`, { cache: "no-store" });
      if (!response.ok) throw new Error("operator unavailable");
      const data = await response.json();
      setOperatorState(data?.enabled && data?.configured ? "online" : "locked");
    } catch {
      setOperatorState("offline");
    }

    let token = "";
    try {
      token = localStorage.getItem("devon-chat-token") || sessionStorage.getItem("devon-chat-token") || "";
    } catch {
      token = "";
    }
    if (!token) {
      setMind(null);
      setMindState("locked");
      return;
    }

    try {
      const response = await fetch(`${API_BASE}/intelligence/status`, {
        cache: "no-store",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error("mind unavailable");
      const data = (await response.json()) as IntelligenceStatus;
      setMind(data);
      setMindState("online");
    } catch {
      setMind(null);
      setMindState("offline");
    }
  }, []);

  useEffect(() => {
    void probe();
    const probeTimer = window.setInterval(() => void probe(), 30000);
    const tick = () =>
      setTimeLabel(
        new Intl.DateTimeFormat("en-US", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hour12: false,
        }).format(new Date()),
      );
    tick();
    const clockTimer = window.setInterval(tick, 1000);
    const onFocus = () => void probe();
    window.addEventListener("focus", onFocus);
    return () => {
      window.clearInterval(probeTimer);
      window.clearInterval(clockTimer);
      window.removeEventListener("focus", onFocus);
    };
  }, [probe]);

  const provider = mind
    ? mind.simulated
      ? "SIMULATED · MOCK"
      : String(mind.provider || "UNKNOWN").toUpperCase()
    : undefined;

  return (
    <div className="relative z-20 mx-auto max-w-[1780px] px-3 pt-3 sm:px-5 lg:px-7">
      <CinematicHud
        apiState={apiState}
        mindState={mindState}
        operatorState={operatorState}
        provider={provider}
        model={mind?.model}
        timeLabel={timeLabel}
      />
    </div>
  );
}
