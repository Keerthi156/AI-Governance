"use client";

/**
 * RBAC admin panel — manage org users' roles and active status.
 */

import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  fetchAdminUsers,
  fetchRoleCatalog,
  updateAdminUser,
} from "@/lib/api";
import { getAccessToken, getStoredUser } from "@/lib/auth";
import type { AuthUser, RoleCatalogResponse } from "@/types/api";

export function RbacPanel() {
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [catalog, setCatalog] = useState<RoleCatalogResponse | null>(null);
  const [current, setCurrent] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const canManage = Boolean(
    current?.permissions?.includes("users:manage") || current?.role === "admin",
  );

  const load = useCallback(async () => {
    const stored = getStoredUser();
    setCurrent(stored);
    if (!getAccessToken() || !stored?.permissions?.includes("users:manage")) {
      setUsers([]);
      setCatalog(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [list, roles] = await Promise.all([
        fetchAdminUsers(),
        fetchRoleCatalog(),
      ]);
      setUsers(list);
      setCatalog(roles);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load RBAC data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const onStorage = () => void load();
    window.addEventListener("storage", onStorage);
    window.addEventListener("ai-governance-auth", onStorage);
    return () => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener("ai-governance-auth", onStorage);
    };
  }, [load]);

  async function changeRole(userId: string, role: string) {
    setMessage(null);
    setError(null);
    try {
      const updated = await updateAdminUser(userId, { role });
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
      setMessage(`Updated ${updated.email} → ${updated.role}`);
      if (current && current.id === updated.id) {
        // Caller should re-login for fresh JWT claims; permissions on /me still update via reload.
        void load();
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Role update failed");
    }
  }

  async function toggleActive(user: AuthUser) {
    setMessage(null);
    setError(null);
    try {
      const updated = await updateAdminUser(user.id, {
        is_active: !user.is_active,
      });
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
      setMessage(
        `${updated.email} is now ${updated.is_active ? "active" : "inactive"}`,
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Status update failed");
    }
  }

  return (
    <section className="w-full max-w-5xl border border-zinc-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
            RBAC
          </h2>
          <p className="mt-1 text-sm text-zinc-500">
            Roles: viewer (read), member (run models), admin (manage users).
          </p>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          className="border border-zinc-200 px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-50"
        >
          Refresh
        </button>
      </div>

      {!getAccessToken() && (
        <p className="mt-4 text-sm text-zinc-600">
          Sign in to see your permissions. Admin role required to manage users.
        </p>
      )}

      {getAccessToken() && !canManage && (
        <div className="mt-4 border border-zinc-100 bg-zinc-50 px-4 py-3 text-sm text-zinc-700">
          Signed in as <span className="font-medium">{current?.role}</span>. You
          can use features granted by your role; user management requires{" "}
          <span className="font-medium">admin</span>.
          {current?.permissions && current.permissions.length > 0 && (
            <p className="mt-2 text-xs text-zinc-500">
              Permissions: {current.permissions.join(", ")}
            </p>
          )}
        </div>
      )}

      {error && (
        <div className="mt-4 border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          {error}
        </div>
      )}
      {message && (
        <div className="mt-4 border border-zinc-200 bg-zinc-50 p-3 text-sm text-zinc-700">
          {message}
        </div>
      )}

      {canManage && catalog && (
        <div className="mt-4 overflow-x-auto">
          <table className="min-w-full border-collapse text-left text-xs">
            <thead>
              <tr className="border-b border-zinc-200 text-zinc-500">
                <th className="px-2 py-2">Role</th>
                <th className="px-2 py-2">Permissions</th>
              </tr>
            </thead>
            <tbody>
              {catalog.roles.map((role) => (
                <tr key={role} className="border-b border-zinc-100">
                  <td className="px-2 py-2 font-medium">{role}</td>
                  <td className="px-2 py-2 text-zinc-600">
                    {(catalog.matrix[role] ?? []).join(", ")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {canManage && (
        <div className="mt-6">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
            Organization users
          </h3>
          {loading && (
            <p className="mt-2 text-sm text-zinc-600">Loading users…</p>
          )}
          {!loading && users.length === 0 && (
            <p className="mt-2 text-sm text-zinc-600">No users found.</p>
          )}
          {users.length > 0 && (
            <div className="mt-2 overflow-x-auto">
              <table className="min-w-full border-collapse text-left text-xs">
                <thead>
                  <tr className="border-b border-zinc-200 text-zinc-500">
                    <th className="px-2 py-2">Email</th>
                    <th className="px-2 py-2">Role</th>
                    <th className="px-2 py-2">Active</th>
                    <th className="px-2 py-2">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((user) => (
                    <tr key={user.id} className="border-b border-zinc-100">
                      <td className="px-2 py-2">
                        {user.email}
                        {user.full_name ? (
                          <span className="text-zinc-500"> · {user.full_name}</span>
                        ) : null}
                      </td>
                      <td className="px-2 py-2">
                        <select
                          value={user.role}
                          onChange={(e) =>
                            void changeRole(user.id, e.target.value)
                          }
                          className="border border-zinc-200 px-2 py-1"
                        >
                          {(catalog?.roles ?? ["viewer", "member", "admin"]).map(
                            (role) => (
                              <option key={role} value={role}>
                                {role}
                              </option>
                            ),
                          )}
                        </select>
                      </td>
                      <td className="px-2 py-2">
                        {user.is_active ? "yes" : "no"}
                      </td>
                      <td className="px-2 py-2">
                        <button
                          type="button"
                          onClick={() => void toggleActive(user)}
                          className="border border-zinc-200 px-2 py-1 hover:bg-zinc-50"
                        >
                          {user.is_active ? "Deactivate" : "Activate"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
