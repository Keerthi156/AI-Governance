/**
 * Platform roles — keep aligned with backend RoleName values.
 */

export const ROLES = ["viewer", "member", "admin"] as const;

export type Role = (typeof ROLES)[number];

export const ROLE_RANK: Record<Role, number> = {
  viewer: 1,
  member: 2,
  admin: 3,
};

export function normalizeRole(role: string | null | undefined): Role {
  const cleaned = (role || "").trim().toLowerCase();
  if (cleaned === "viewer" || cleaned === "member" || cleaned === "admin") {
    return cleaned;
  }
  return "viewer";
}

export function roleAtLeast(role: string | null | undefined, minimum: Role): boolean {
  return ROLE_RANK[normalizeRole(role)] >= ROLE_RANK[minimum];
}

export function isRole(role: string | null | undefined, expected: Role): boolean {
  return normalizeRole(role) === expected;
}
