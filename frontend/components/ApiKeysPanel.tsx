"use client";

/**
 * Platform API keys — create/list/revoke service-account credentials.
 */

import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";

import {
  ApiError,
  createApiKey,
  fetchApiKeys,
  revokeApiKey,
} from "@/lib/api";
import {
  getAccessToken,
  getActiveOrganizationSlug,
  getStoredUser,
} from "@/lib/auth";
import type { ApiKey, ApiKeyCreated, AuthUser } from "@/types/api";

export function ApiKeysPanel() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [name, setName] = useState("CI deploy key");
  const [role, setRole] = useState("member");
  const [createdSecret, setCreatedSecret] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const canManage = Boolean(user?.permissions?.includes("api_keys:manage"));

  const load = useCallback(async () => {
    const stored = getStoredUser();
    setUser(stored);
    if (!getAccessToken() || !stored?.permissions?.includes("api_keys:manage")) {
      setKeys([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setKeys(await fetchApiKeys());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load API keys");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const onAuth = () => void load();
    window.addEventListener("ai-governance-auth", onAuth);
    window.addEventListener("storage", onAuth);
    return () => {
      window.removeEventListener("ai-governance-auth", onAuth);
      window.removeEventListener("storage", onAuth);
    };
  }, [load]);

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    if (!canManage || !name.trim()) return;
    setError(null);
    setMessage(null);
    setCreatedSecret(null);
    try {
      const created: ApiKeyCreated = await createApiKey({
        name: name.trim(),
        role,
        organization_slug: getActiveOrganizationSlug(),
      });
      setKeys((prev) => [created, ...prev.filter((k) => k.id !== created.id)]);
      setCreatedSecret(created.api_key);
      setMessage(
        `Created “${created.name}”. Copy the secret now — it will not be shown again.`,
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Create failed");
    }
  }

  async function onRevoke(key: ApiKey) {
    if (!canManage || key.revoked_at) return;
    setError(null);
    try {
      const revoked = await revokeApiKey(key.id);
      setKeys((prev) => prev.map((k) => (k.id === revoked.id ? revoked : k)));
      setMessage(`Revoked “${revoked.name}”`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Revoke failed");
    }
  }

  if (!getAccessToken()) {
    return null;
  }

  return (
    <section className="w-full max-w-5xl border border-zinc-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
            API keys
          </h2>
          <p className="mt-1 text-sm text-zinc-500">
            Service-account Bearer keys (<code className="text-xs">agk_…</code>)
            for CI and integrations. Scoped to an organization and role.
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

      {!canManage && (
        <p className="mt-4 text-sm text-zinc-600">
          Member or admin role required. Sign in again after a role change.
        </p>
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
      {createdSecret && (
        <div className="mt-4 border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
          <p className="font-medium">Secret (copy once)</p>
          <code className="mt-2 block break-all text-xs">{createdSecret}</code>
        </div>
      )}

      {canManage && (
        <form
          className="mt-4 flex flex-wrap items-end gap-2"
          onSubmit={onCreate}
        >
          <label className="min-w-[12rem] flex-1 text-sm">
            <span className="text-zinc-600">Name</span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 w-full border border-zinc-200 px-3 py-2 text-sm"
              required
            />
          </label>
          <label className="text-sm">
            <span className="text-zinc-600">Role</span>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="mt-1 block border border-zinc-200 px-3 py-2 text-sm"
            >
              <option value="viewer">viewer</option>
              <option value="member">member</option>
              <option value="admin">admin</option>
            </select>
          </label>
          <button
            type="submit"
            className="border border-zinc-900 bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800"
          >
            Create key
          </button>
        </form>
      )}

      {canManage && (
        <div className="mt-6">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
            Your keys
          </h3>
          {loading && <p className="mt-2 text-sm text-zinc-600">Loading…</p>}
          {!loading && keys.length === 0 && (
            <p className="mt-2 text-sm text-zinc-600">No API keys yet.</p>
          )}
          <ul className="mt-3 space-y-2">
            {keys.map((key) => (
              <li
                key={key.id}
                className="flex flex-wrap items-center justify-between gap-2 border border-zinc-100 bg-zinc-50 px-3 py-2 text-sm"
              >
                <div>
                  <p className="font-medium text-zinc-900">
                    {key.name}{" "}
                    <span className="text-xs font-normal text-zinc-500">
                      ({key.is_active ? "active" : "inactive"} · {key.role} ·{" "}
                      {key.organization_slug})
                    </span>
                  </p>
                  <p className="mt-0.5 text-xs text-zinc-500">
                    {key.key_prefix}… · created{" "}
                    {new Date(key.created_at).toLocaleString()}
                    {key.last_used_at
                      ? ` · last used ${new Date(key.last_used_at).toLocaleString()}`
                      : ""}
                  </p>
                </div>
                {key.is_active && (
                  <button
                    type="button"
                    onClick={() => void onRevoke(key)}
                    className="border border-zinc-200 px-2 py-1 text-xs hover:bg-white"
                  >
                    Revoke
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
