"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { ApiKeysPanel } from "@/components/ApiKeysPanel";
import { AuthPanel } from "@/components/AuthPanel";
import { BackendStatus } from "@/components/BackendStatus";
import { CompliancePanel } from "@/components/CompliancePanel";
import { CredentialsPanel } from "@/components/CredentialsPanel";
import { OrgSwitcher } from "@/components/OrgSwitcher";
import { RbacPanel } from "@/components/RbacPanel";
import { RetentionPanel } from "@/components/RetentionPanel";
import { WebhooksPanel } from "@/components/WebhooksPanel";
import { useAuthz } from "@/hooks/useAuthz";
import {
  settingsTabsForRole,
  type SettingsTabId,
} from "@/lib/permissions";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { PageFrame } from "@/components/ui/PageFrame";
import { SectionHeader } from "@/components/ui/SectionHeader";

const TAB_LABELS: Record<SettingsTabId, string> = {
  organization: "Organization",
  users: "Users",
  "api-keys": "API Keys",
  credentials: "Credentials",
  webhooks: "Webhooks",
  retention: "Retention",
  compliance: "Compliance",
  profile: "Profile",
};

function SettingsContent() {
  const router = useRouter();
  const params = useSearchParams();
  const { role } = useAuthz();
  const tabs = settingsTabsForRole(role);

  const requested = (params.get("tab") as SettingsTabId | null) ?? tabs[0];
  const initial = tabs.includes(requested) ? requested : tabs[0];
  const [tab, setTab] = useState<SettingsTabId>(initial);

  useEffect(() => {
    const next = (params.get("tab") as SettingsTabId | null) ?? tabs[0];
    setTab(tabs.includes(next) ? next : tabs[0]);
  }, [params, tabs]);

  function selectTab(id: SettingsTabId) {
    setTab(id);
    router.replace(`/settings?tab=${id}`);
  }

  const body = useMemo(() => {
    switch (tab) {
      case "organization":
        return <OrgSwitcher />;
      case "users":
        return <RbacPanel />;
      case "api-keys":
        return <ApiKeysPanel />;
      case "credentials":
        return <CredentialsPanel />;
      case "webhooks":
        return <WebhooksPanel />;
      case "retention":
        return <RetentionPanel />;
      case "compliance":
        return <CompliancePanel />;
      case "profile":
        return (
          <>
            <AuthPanel />
            <div className="mt-4">
              <BackendStatus />
            </div>
          </>
        );
      default:
        return null;
    }
  }, [tab]);

  return (
    <div>
      <SectionHeader
        title="Settings"
        description={
          tabs.length === 1
            ? "Profile and account"
            : "Organization, security, integrations, retention, and profile"
        }
      />

      <div
        className="mb-6 flex gap-1 overflow-x-auto rounded-2xl border border-border bg-card p-1 shadow-card"
        role="tablist"
        aria-label="Settings sections"
      >
        {tabs.map((id) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            onClick={() => selectTab(id)}
            className={`whitespace-nowrap rounded-xl px-3 py-2 text-sm transition ${
              tab === id
                ? "bg-primary font-medium text-primary-foreground"
                : "text-muted-foreground hover:bg-muted"
            }`}
          >
            {TAB_LABELS[id]}
          </button>
        ))}
      </div>

      <PageFrame>{body}</PageFrame>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <Suspense fallback={<LoadingSkeleton rows={5} />}>
      <SettingsContent />
    </Suspense>
  );
}
