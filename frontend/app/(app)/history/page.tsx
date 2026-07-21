import { PromptHistoryPanel } from "@/components/PromptHistoryPanel";
import { PageFrame } from "@/components/ui/PageFrame";
import { SectionHeader } from "@/components/ui/SectionHeader";

export default function Page() {
  return (
    <div>
      <SectionHeader
        title="Prompt History"
        description="Browse and filter past completions"
      />
      <PageFrame>
        <PromptHistoryPanel />
      </PageFrame>
    </div>
  );
}
