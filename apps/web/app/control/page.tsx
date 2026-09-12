import { ControlPlane } from "@/components/control/ControlPlane";
import { ProvenanceSlot } from "@/components/control/ProvenanceSlot";
import { PresenceStageLoader } from "@/components/presence/PresenceStageLoader";
import { KnowledgePanel } from "@/components/mind/KnowledgePanel";
import { KnowledgeGraphPanel } from "@/components/mind/KnowledgeGraphPanel";
import { LearningPanel } from "@/components/mind/LearningPanel";
import { MemoryPanel } from "@/components/mind/MemoryPanel";
import { ProjectsPanel } from "@/components/projects/ProjectsPanel";
import { AgentRosterPanel } from "@/components/roster/AgentRosterPanel";
import { DecisionRecordPanel } from "@/components/council/DecisionRecordPanel";
import { WorkflowDoor } from "@/components/control/WorkflowDoor";
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
        <>
          <KnowledgePanel />
          <KnowledgeGraphPanel />
        </>
      }
      learning={<LearningPanel />}
      roster={<AgentRosterPanel />}
      decisions={<DecisionRecordPanel />}
      projects={<ProjectsPanel />}
      memory={<MemoryPanel />}
      workflows={<WorkflowDoor />}
    />
  );
}
