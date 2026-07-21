"use client";

/**
 * BYOK provider credentials — org-scoped encrypted LLM API keys.
 */

import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";

import {
  ApiError,
  deleteProviderCredential,
  fetchProviderCredentials,
  upsertProviderCredential,
} from "@/lib/api";
import {
  getAccessToken,
  getActiveOrganizationSlug,
  getStoredUser,
} from "@/lib/auth";
import type { AuthUser, ProviderCredential } from "@/types/api";

const PROVIDERS = ["groq", "openai", "claude", "gemini"] as const;

export function CredentialsPanel() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [rows, setRows] = useState<ProviderCredential[]>([]);
  const [provider, setProvider] = useState<string>("groq");
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const canRead = Boolean(user?.permissions?.includes("credentials:read"));
  const canManage = Boolean(user?.permissions?.includes("credentials:manage"));

  const load = useCallback(async () => {
    const stored = getStoredUser();
    setUser(stored);
    if (!getAccessToken() || !stored?.permissions?.includes("credentials:read")) {
      setRows([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setRows(await fetchProviderCredentials());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load credentials");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const onAuth = () => void load();
    window.addEventListener("ai-governance-auth", onAuth);
    window.addEventListener("ai-governance-org", onAuth);
    window.addEventListener("storage", onAuth);
    return () => {
      window.removeEventListener("ai-governance-auth", onAuth);
      window.removeEventListener("ai-governance-org", onAuth);
      window.removeEventListener("storage", onAuth);
    };
  }, [load]);

  async function onSave(event: FormEvent) {
    event.preventDefault();
    if (!canManage || !apiKey.trim()) return;
    setError(null);
    setMessage(null);
    try {
      const saved = await upsertProviderCredential(provider, {
        api_key: apiKey.trim(),
        organization_slug: getActiveOrganizationSlug(),
      });
      setRows((prev) => {
        const others = prev.filter((r) => r.provider !== saved.provider);
        return [...others, saved].sort((a, b) =>
          a.provider.localeCompare(b.provider),
        );
      });
      setApiKey("");
      setMessage(
        `Saved ${saved.provider} key for ${saved.organization_slug} (${saved.key_hint})`,
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Save failed");
    }
  }

  async function onDelete(row: ProviderCredential) {
    if (!canManage || row.source !== "org") return;
    setError(null);
    try {
      const updated = await deleteProviderCredential(row.provider);
      setRows((prev) =>
        prev.map((r) => (r.provider === updated.provider ? updated : r)),
      );
      setMessage(
        `Removed org key for ${row.provider}; fallback: ${updated.source}`,
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Delete failed");
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
            Provider credentials (BYOK)
          </h2>
          <p className="mt-1 text-sm text-zinc-500">
            Org-scoped encrypted LLM keys for{" "}
            <span className="font-medium text-zinc-700">
              {getActiveOrganizationSlug()}
            </span>
            . Resolution order: org key → platform env.
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

      {!canRead && (
        <p className="mt-4 text-sm text-zinc-600">
          Admin role required. Sign in again after a role change.
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

      {canManage && (
        <form className="mt-4 flex flex-wrap items-end gap-2" onSubmit={onSave}>
          <label className="text-sm">
            <span className="text-zinc-600">Provider</span>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              className="mt-1 block border border-zinc-200 px-3 py-2 text-sm"
            >
              {PROVIDERS.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </label>
          <label className="min-w-[16rem] flex-1 text-sm">
            <span className="text-zinc-600">API key</span>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Paste provider secret"
              className="mt-1 w-full border border-zinc-200 px-3 py-2 text-sm"
              required
              minLength={8}
            />
          </label>
          <button
            type="submit"
            className="border border-zinc-900 bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800"
          >
            Save org key
          </button>
        </form>
      )}

      {canRead && (
        <div className="mt-6">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
            Status
          </h3>
          {loading && <p className="mt-2 text-sm text-zinc-600">Loading…</p>}
          <ul className="mt-3 space-y-2">
            {rows.map((row) => (
              <li
                key={row.provider}
                className="flex flex-wrap items-center justify-between gap-2 border border-zinc-100 bg-zinc-50 px-3 py-2 text-sm"
              >
                <div>
                  <p className="font-medium text-zinc-900">
                    {row.provider}{" "}
                    <span className="text-xs font-normal text-zinc-500">
                      source: {row.source}
                      {row.key_hint ? ` · ${row.key_hint}` : ""}
                      {row.env_configured ? " · env available" : ""}
                    </span>
                  </p>
                </div>
                {canManage && row.source === "org" && (
                  <button
                    type="button"
                    onClick={() => void onDelete(row)}
                    className="border border-zinc-200 px-2 py-1 text-xs hover:bg-white"
                  >
                    Remove org key
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
