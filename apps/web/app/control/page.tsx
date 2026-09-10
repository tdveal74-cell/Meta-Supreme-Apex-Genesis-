import { ControlPlane } from "@/components/control/ControlPlane";
import { ProvenanceSlot } from "@/components/control/ProvenanceSlot";
import { PresenceStageLoader } from "@/components/presence/PresenceStageLoader";
import { KnowledgePanel } from "@/components/mind/KnowledgePanel";
import { KnowledgeGraphPanel } from "@/components/mind/KnowledgeGraphPanel";
import { LearningPanel } from "@/components/mind/LearningPanel";
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
      knowledge={
        <div className="space-y-5">
          <KnowledgePanel />
          <div className="border-t border-white/10 pt-5">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/70">
              Knowledge graph
            </p>
            <div className="mt-2.5">
              <KnowledgeGraphPanel />
            </div>
          </div>
        </div>
      }
      learning={<LearningPanel />}
    />
  );
}
