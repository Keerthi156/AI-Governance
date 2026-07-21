import { RagPanel } from "@/components/RagPanel";
import { PageFrame } from "@/components/ui/PageFrame";
import { SectionHeader } from "@/components/ui/SectionHeader";

export default function Page() {
  return (
    <div>
      <SectionHeader
        title="Enterprise RAG"
        description="Ingest documents and run grounded retrieval"
      />
      <PageFrame>
        <RagPanel />
      </PageFrame>
    </div>
  );
}
