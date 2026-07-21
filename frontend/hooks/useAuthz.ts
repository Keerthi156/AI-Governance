"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  hasFeature,
  hasPermission,
  type ActionPermission,
  type FeatureKey,
} from "@/lib/permissions";
import { getStoredUser } from "@/lib/auth";
import { normalizeRole, type Role } from "@/lib/roles";
import type { AuthUser } from "@/types/api";

export function useAuthUser(): AuthUser | null {
  const [user, setUser] = useState<AuthUser | null>(() =>
    typeof window === "undefined" ? null : getStoredUser(),
  );

  useEffect(() => {
    const sync = () => setUser(getStoredUser());
    sync();
    window.addEventListener("ai-governance-auth", sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener("ai-governance-auth", sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  return user;
}

export function useRole(): Role {
  const user = useAuthUser();
  return normalizeRole(user?.role);
}

export function useAuthz() {
  const user = useAuthUser();
  const role = normalizeRole(user?.role);
  const permissions = user?.permissions ?? [];

  const can = useCallback(
    (permission: ActionPermission | string) =>
      hasPermission(permissions, permission),
    [permissions],
  );

  const canFeature = useCallback(
    (feature: FeatureKey) => hasFeature(role, feature),
    [role],
  );

  return useMemo(
    () => ({
      user,
      role,
      permissions,
      can,
      canFeature,
      isAdmin: role === "admin",
      isMember: role === "member",
      isViewer: role === "viewer",
    }),
    [user, role, permissions, can, canFeature],
  );
}
