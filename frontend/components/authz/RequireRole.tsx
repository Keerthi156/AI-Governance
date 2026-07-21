"use client";

import type { ReactNode } from "react";

import { useAuthz } from "@/hooks/useAuthz";
import type { FeatureKey } from "@/lib/permissions";
import { roleAtLeast, type Role } from "@/lib/roles";

export function RequireFeature({
  feature,
  children,
  fallback = null,
}: {
  feature: FeatureKey;
  children: ReactNode;
  fallback?: ReactNode;
}) {
  const { canFeature } = useAuthz();
  if (!canFeature(feature)) return <>{fallback}</>;
  return <>{children}</>;
}

export function RequireRole({
  role,
  minimum,
  children,
  fallback = null,
}: {
  role?: Role;
  minimum?: Role;
  children: ReactNode;
  fallback?: ReactNode;
}) {
  const { role: current } = useAuthz();
  if (role && current !== role) return <>{fallback}</>;
  if (minimum && !roleAtLeast(current, minimum)) return <>{fallback}</>;
  return <>{children}</>;
}
