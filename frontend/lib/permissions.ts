/**
 * Frontend feature / capability matrix.
 *
 * Backend RBAC remains authoritative. These flags only drive UX
 * (sidebar, redirects, hiding actions).
 */

import { normalizeRole, type Role } from "@/lib/roles";

/** Product features used for navigation and page access. */
export type FeatureKey =
  | "dashboard"
  | "playground"
  | "arena"
  | "history"
  | "router"
  | "evaluation"
  | "rag"
  | "agents"
  | "analytics"
  | "governance"
  | "audit"
  | "users"
  | "api_keys"
  | "settings"
  | "settings_admin";

/** Settings tabs (subset for non-admins). */
export type SettingsTabId =
  | "organization"
  | "users"
  | "api-keys"
  | "credentials"
  | "webhooks"
  | "retention"
  | "compliance"
  | "profile";

const ROLE_FEATURES: Record<Role, readonly FeatureKey[]> = {
  viewer: [
    "dashboard",
    "history",
    "analytics",
    "rag", // query-oriented UX; backend still enforces rag:query
    "settings", // profile only
  ],
  member: [
    "dashboard",
    "playground",
    "arena",
    "history",
    "router",
    "evaluation",
    "rag",
    "agents",
    "analytics",
    "settings", // profile only
  ],
  admin: [
    "dashboard",
    "playground",
    "arena",
    "history",
    "router",
    "evaluation",
    "rag",
    "agents",
    "analytics",
    "governance",
    "audit",
    "users",
    "api_keys",
    "settings",
    "settings_admin",
  ],
};

/** Sidebar should not list Settings for viewer/member (profile via navbar). */
export const SIDEBAR_HIDDEN_FEATURES: Record<Role, readonly FeatureKey[]> = {
  viewer: ["settings"],
  member: ["settings"],
  admin: [],
};

export const ROUTE_FEATURE: Record<string, FeatureKey> = {
  "/dashboard": "dashboard",
  "/playground": "playground",
  "/arena": "arena",
  "/history": "history",
  "/router": "router",
  "/evaluation": "evaluation",
  "/rag": "rag",
  "/agents": "agents",
  "/analytics": "analytics",
  "/governance": "governance",
  "/audit": "audit",
  "/users": "users",
  "/api-keys": "api_keys",
  "/settings": "settings",
};

export const ADMIN_SETTINGS_TABS: readonly SettingsTabId[] = [
  "organization",
  "users",
  "api-keys",
  "credentials",
  "webhooks",
  "retention",
  "compliance",
  "profile",
];

export const PROFILE_ONLY_SETTINGS_TABS: readonly SettingsTabId[] = ["profile"];

export function featuresForRole(role: string | null | undefined): readonly FeatureKey[] {
  return ROLE_FEATURES[normalizeRole(role)];
}

export function hasFeature(
  role: string | null | undefined,
  feature: FeatureKey,
): boolean {
  return featuresForRole(role).includes(feature);
}

export function canAccessPath(
  role: string | null | undefined,
  pathname: string,
): boolean {
  const path = pathname.split("?")[0].replace(/\/$/, "") || "/";
  // Exact or prefix match for known app routes
  const match =
    Object.keys(ROUTE_FEATURE)
      .sort((a, b) => b.length - a.length)
      .find((route) => path === route || path.startsWith(`${route}/`)) ?? null;
  if (!match) return true; // unknown routes: allow (e.g. /forbidden)
  return hasFeature(role, ROUTE_FEATURE[match]);
}

export function settingsTabsForRole(
  role: string | null | undefined,
): readonly SettingsTabId[] {
  return hasFeature(role, "settings_admin")
    ? ADMIN_SETTINGS_TABS
    : PROFILE_ONLY_SETTINGS_TABS;
}

/** Action-level UX helpers (map to backend permission codes when present). */
export type ActionPermission =
  | "llm:run"
  | "arena:run"
  | "evaluation:run"
  | "router:route"
  | "history:read"
  | "analytics:read"
  | "users:manage"
  | "governance:manage"
  | "governance:read"
  | "audit:read"
  | "rag:write"
  | "rag:query"
  | "rag:read"
  | "agents:run"
  | "agents:manage"
  | "api_keys:manage"
  | "credentials:manage"
  | "webhooks:manage"
  | "retention:manage"
  | "compliance:read"
  | "organizations:manage";

export function hasPermission(
  permissions: string[] | null | undefined,
  permission: ActionPermission | string,
): boolean {
  if (!permissions?.length) return false;
  return permissions.includes(permission);
}
