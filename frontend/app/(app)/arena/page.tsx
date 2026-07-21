import { ArenaPanel } from "@/components/ArenaPanel";
import { PageFrame } from "@/components/ui/PageFrame";
import { SectionHeader } from "@/components/ui/SectionHeader";

export default function Page() {
  return (
    <div>
      <SectionHeader
        title="Arena"
        description="Side-by-side model comparison"
      />
      <PageFrame>
        <ArenaPanel />
      </PageFrame>
    </div>
  );
}
