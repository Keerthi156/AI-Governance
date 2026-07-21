import { RbacPanel } from "@/components/RbacPanel";
import { PageFrame } from "@/components/ui/PageFrame";
import { SectionHeader } from "@/components/ui/SectionHeader";

export default function Page() {
  return (
    <div>
      <SectionHeader
        title="Users & RBAC"
        description="Roles, permissions, and user administration"
      />
      <PageFrame>
        <RbacPanel />
      </PageFrame>
    </div>
  );
}
