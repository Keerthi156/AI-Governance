import { PromptPlayground } from "@/components/PromptPlayground";
import { PageFrame } from "@/components/ui/PageFrame";
import { SectionHeader } from "@/components/ui/SectionHeader";

export default function Page() {
  return (
    <div>
      <SectionHeader
        title="Playground"
        description="Multi-LLM playground"
      />
      <PageFrame>
        <PromptPlayground />
      </PageFrame>
    </div>
  );
}
