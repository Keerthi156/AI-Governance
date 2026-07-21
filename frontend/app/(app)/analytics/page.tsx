import { AnalyticsDashboard } from "@/components/AnalyticsDashboard";
import { PageFrame } from "@/components/ui/PageFrame";
import { SectionHeader } from "@/components/ui/SectionHeader";

export default function Page() {
  return (
    <div>
      <SectionHeader
        title="Analytics"
        description="Usage, cost, latency, and reliability charts"
      />
      <PageFrame>
        <AnalyticsDashboard />
      </PageFrame>
    </div>
  );
}
