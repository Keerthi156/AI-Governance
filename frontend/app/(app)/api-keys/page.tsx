import { ApiKeysPanel } from "@/components/ApiKeysPanel";
import { PageFrame } from "@/components/ui/PageFrame";
import { SectionHeader } from "@/components/ui/SectionHeader";

export default function Page() {
  return (
    <div>
      <SectionHeader
        title="API Keys"
        description="Manage platform API keys for integrations"
      />
      <PageFrame>
        <ApiKeysPanel />
      </PageFrame>
    </div>
  );
}
