import { AuditPanel } from "@/components/AuditPanel";
import { PageFrame } from "@/components/ui/PageFrame";
import { SectionHeader } from "@/components/ui/SectionHeader";

export default function Page() {
  return (
    <div>
      <SectionHeader
        title="Audit Logs"
        description="Searchable enterprise audit trail"
      />
      <PageFrame>
        <AuditPanel />
      </PageFrame>
    </div>
  );
}
