import { ControlPlane } from "@/components/control/ControlPlane";
import { ProvenanceSlot } from "@/components/control/ProvenanceSlot";
import { PresenceStageLoader } from "@/components/presence/PresenceStageLoader";
import { KnowledgePanel } from "@/components/mind/KnowledgePanel";
import { AgentReadinessMatrix } from "@/components/readiness";

/**
 * The unified control plane route.
 *
 * The tiers and their honesty live in ControlPlane. This file only decides
 * which panels are mounted, so a panel that has no component yet stays
 * visibly unmounted instead of being faked inside the shell.
 */
export default function ControlPage() {
  return (
    <ControlPlane
      readiness={<AgentReadinessMatrix />}
      provenance={<ProvenanceSlot />}
      presence={<PresenceStageLoader />}
      knowledge={<KnowledgePanel />}
    />
  );
}
