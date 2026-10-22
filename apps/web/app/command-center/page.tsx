import { Suspense } from "react";
import { DevonWorkspace } from "@/components/command-center/DevonWorkspace";
import { AgentDispatchPanel } from "@/components/command-center/AgentDispatchPanel";
import { ControlPanels } from "@/components/control/ControlPanels";
import { CapabilityDock } from "@/components/command-center/CapabilityDock";
import { CinematicCommandHeader } from "@/components/command-center/CinematicCommandHeader";
import { MissionAdvisor } from "@/components/command-center/MissionAdvisor";
import { PasskeyAccess } from "@/components/command-center/PasskeyAccess";
import { UnifiedCommandCenter } from "@/components/command-center/UnifiedCommandCenter";

export default function CommandCenterPage() {
  return (
    <Suspense fallback={<p className="p-6">Loading DEVON workspace.</p>}>
    <DevonWorkspace control={<ControlPanels />} agents={<AgentDispatchPanel />} command={
    <div className="min-h-screen bg-[#050a0e]">
      <CinematicCommandHeader />
      <UnifiedCommandCenter />
      <MissionAdvisor />
      <PasskeyAccess />
      <CapabilityDock />
    </div>
    } />
    </Suspense>
  );
}
