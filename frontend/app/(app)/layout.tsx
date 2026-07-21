import type { ReactNode } from "react";

import { RouteGuard } from "@/components/authz/RouteGuard";
import { AppShell } from "@/components/layout/AppShell";
import { AuthGate } from "@/components/layout/AuthGate";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <AuthGate>
      <AppShell>
        <RouteGuard>{children}</RouteGuard>
      </AppShell>
    </AuthGate>
  );
}
