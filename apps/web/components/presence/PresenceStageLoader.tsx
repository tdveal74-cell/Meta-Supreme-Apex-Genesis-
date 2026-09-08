"use client";

// WebGL cannot render on the server, and a Server Component page may not pass
// ssr:false to next/dynamic itself, so this client shim does the deferring.
import dynamic from "next/dynamic";

const PresenceStage = dynamic(() => import("./PresenceStage").then((module) => module.PresenceStage), {
  ssr: false,
  loading: () => (
    <div className="flex min-h-[40vh] items-center justify-center border border-[#2b4558]/60 bg-[#050a0e] font-mono text-[10px] uppercase tracking-[0.2em] text-[#668092]">
      Loading the stage
    </div>
  ),
});

export function PresenceStageLoader() {
  return <PresenceStage />;
}
