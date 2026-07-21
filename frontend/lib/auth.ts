/**
 * Client-side auth session helpers (JWT + refresh in localStorage).
 *
 * Why this exists:
 * - Keeps token/user persistence out of React components.
 * - api.ts can attach Bearer headers and silently refresh on 401.
 */

import type { AuthUser } from "@/types/api";

const TOKEN_KEY = "ai_governance_access_token";
const REFRESH_KEY = "ai_governance_refresh_token";
const USER_KEY = "ai_governance_auth_user";
const ACTIVE_ORG_KEY = "ai_governance_active_org_slug";

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(REFRESH_KEY);
}

export function getStoredUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

/** Active tenant slug for API calls (local preference; defaults to home org). */
export function getActiveOrganizationSlug(): string {
  if (typeof window === "undefined") return "default";
  const stored = window.localStorage.getItem(ACTIVE_ORG_KEY);
  if (stored && stored.trim()) return stored.trim().toLowerCase();
  const user = getStoredUser();
  return (user?.organization_slug || "default").trim().toLowerCase() || "default";
}

export function setActiveOrganizationSlug(slug: string): void {
  const cleaned = slug.trim().toLowerCase() || "default";
  window.localStorage.setItem(ACTIVE_ORG_KEY, cleaned);
  window.dispatchEvent(new Event("ai-governance-org"));
  window.dispatchEvent(new Event("ai-governance-auth"));
}

export function setAuthSession(
  token: string,
  user: AuthUser,
  refreshToken?: string | null,
): void {
  window.localStorage.setItem(TOKEN_KEY, token);
  window.localStorage.setItem(USER_KEY, JSON.stringify(user));
  if (refreshToken) {
    window.localStorage.setItem(REFRESH_KEY, refreshToken);
  }
  // Prefer home org on login unless user already selected one this browser session.
  if (!window.localStorage.getItem(ACTIVE_ORG_KEY) && user.organization_slug) {
    window.localStorage.setItem(
      ACTIVE_ORG_KEY,
      user.organization_slug.trim().toLowerCase(),
    );
  }
  window.dispatchEvent(new Event("ai-governance-auth"));
}

export function clearAuthSession(): void {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_KEY);
  window.localStorage.removeItem(USER_KEY);
  window.dispatchEvent(new Event("ai-governance-auth"));
}
