import { TaskRouterPanel } from "@/components/TaskRouterPanel";
import { PageFrame } from "@/components/ui/PageFrame";
import { SectionHeader } from "@/components/ui/SectionHeader";

export default function Page() {
  return (
    <div>
      <SectionHeader
        title="Task Router"
        description="Classify and route prompts to optimal models"
      />
      <PageFrame>
        <TaskRouterPanel />
      </PageFrame>
    </div>
  );
}
