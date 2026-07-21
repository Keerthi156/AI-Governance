"use client";

import type { ReactNode } from "react";

import { useAuthz } from "@/hooks/useAuthz";
import type { ActionPermission } from "@/lib/permissions";

/**
 * Conditionally render children when the user holds a backend permission code.
 */
export function Can({
  permission,
  children,
  fallback = null,
}: {
  permission: ActionPermission | string;
  children: ReactNode;
  fallback?: ReactNode;
}) {
  const { can } = useAuthz();
  if (!can(permission)) return <>{fallback}</>;
  return <>{children}</>;
}
