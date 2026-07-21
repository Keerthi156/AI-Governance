"use client";

import { useEffect, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";

import { useAuthz } from "@/hooks/useAuthz";
import { canAccessPath } from "@/lib/permissions";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";

/**
 * Client-side route guard. Backend still enforces APIs.
 */
export function RouteGuard({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, role } = useAuthz();

  const allowed = !user ? false : canAccessPath(role, pathname || "/dashboard");

  useEffect(() => {
    if (!user) return;
    if (!canAccessPath(role, pathname || "/dashboard")) {
      router.replace(
        `/forbidden?from=${encodeURIComponent(pathname || "/dashboard")}`,
      );
    }
  }, [user, role, pathname, router]);

  if (!user) {
    return (
      <div className="mx-auto max-w-3xl py-16">
        <LoadingSkeleton rows={3} />
      </div>
    );
  }

  if (!allowed) {
    return (
      <div className="mx-auto max-w-3xl py-16">
        <LoadingSkeleton rows={3} />
      </div>
    );
  }

  return <>{children}</>;
}
