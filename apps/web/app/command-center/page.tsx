import { CapabilityDock } from "@/components/command-center/CapabilityDock";
import { CinematicCommandHeader } from "@/components/command-center/CinematicCommandHeader";
import { MissionAdvisor } from "@/components/command-center/MissionAdvisor";
import { PasskeyAccess } from "@/components/command-center/PasskeyAccess";
import { UnifiedCommandCenter } from "@/components/command-center/UnifiedCommandCenter";

export default function CommandCenterPage() {
  return (
    <div className="min-h-screen bg-[#050a0e]">
      <CinematicCommandHeader />
      <UnifiedCommandCenter />
      <MissionAdvisor />
      <PasskeyAccess />
      <CapabilityDock />
    </div>
  );
}
