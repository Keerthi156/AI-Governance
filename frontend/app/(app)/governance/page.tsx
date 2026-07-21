import { GovernancePanel } from "@/components/GovernancePanel";
import { PageFrame } from "@/components/ui/PageFrame";
import { SectionHeader } from "@/components/ui/SectionHeader";

export default function Page() {
  return (
    <div>
      <SectionHeader
        title="Governance"
        description="Policies, spend caps, and PII controls"
      />
      <PageFrame>
        <GovernancePanel />
      </PageFrame>
    </div>
  );
}
