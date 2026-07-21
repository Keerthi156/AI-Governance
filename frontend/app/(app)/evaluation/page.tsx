import { EvaluationPanel } from "@/components/EvaluationPanel";
import { PageFrame } from "@/components/ui/PageFrame";
import { SectionHeader } from "@/components/ui/SectionHeader";

export default function Page() {
  return (
    <div>
      <SectionHeader
        title="Evaluation"
        description="Score arena runs and compare strategies"
      />
      <PageFrame>
        <EvaluationPanel />
      </PageFrame>
    </div>
  );
}
