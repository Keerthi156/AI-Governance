import { AgentsPanel } from "@/components/AgentsPanel";
import { PageFrame } from "@/components/ui/PageFrame";
import { SectionHeader } from "@/components/ui/SectionHeader";

export default function Page() {
  return (
    <div>
      <SectionHeader
        title="AI Agents"
        description="Plan and execute multi-step agent workflows"
      />
      <PageFrame>
        <AgentsPanel />
      </PageFrame>
    </div>
  );
}
