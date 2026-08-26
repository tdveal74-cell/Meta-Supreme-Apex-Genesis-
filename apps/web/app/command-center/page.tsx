import { CapabilityDock } from "@/components/command-center/CapabilityDock";
import { MissionAdvisor } from "@/components/command-center/MissionAdvisor";
import { UnifiedCommandCenter } from "@/components/command-center/UnifiedCommandCenter";

export default function CommandCenterPage() {
  return (
    <>
      <UnifiedCommandCenter />
      <MissionAdvisor />
      <CapabilityDock />
    </>
  );
}
