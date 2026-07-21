"use client";

/**
 * Audit webhooks — HTTPS endpoints with delivery log + retries.
 */

import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";

import {
  ApiError,
  createWebhook,
  deleteWebhook,
  fetchWebhookDeliveries,
  fetchWebhooks,
  testWebhook,
  updateWebhook,
} from "@/lib/api";
import {
  getAccessToken,
  getActiveOrganizationSlug,
  getStoredUser,
} from "@/lib/auth";
import type {
  AuthUser,
  Webhook,
  WebhookDelivery,
} from "@/types/api";

export function WebhooksPanel() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [hooks, setHooks] = useState<Webhook[]>([]);
  const [deliveries, setDeliveries] = useState<WebhookDelivery[]>([]);
  const [deliveryTotal, setDeliveryTotal] = useState(0);
  const [filterWebhookId, setFilterWebhookId] = useState<string>("");
  const [name, setName] = useState("SIEM collector");
  const [url, setUrl] = useState("https://example.com/hooks/ai-governance");
  const [secret, setSecret] = useState("change-me-webhook-secret");
  const [filters, setFilters] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const canManage = Boolean(user?.permissions?.includes("webhooks:manage"));

  const load = useCallback(async () => {
    const stored = getStoredUser();
    setUser(stored);
    if (!getAccessToken() || !stored?.permissions?.includes("webhooks:manage")) {
      setHooks([]);
      setDeliveries([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [hookList, deliveryList] = await Promise.all([
        fetchWebhooks(),
        fetchWebhookDeliveries({
          webhookId: filterWebhookId || undefined,
          limit: 40,
        }),
      ]);
      setHooks(hookList);
      setDeliveries(deliveryList.items);
      setDeliveryTotal(deliveryList.total);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load webhooks");
    } finally {
      setLoading(false);
    }
  }, [filterWebhookId]);

  useEffect(() => {
    void load();
    const onAuth = () => void load();
    window.addEventListener("ai-governance-auth", onAuth);
    window.addEventListener("ai-governance-org", onAuth);
    return () => {
      window.removeEventListener("ai-governance-auth", onAuth);
      window.removeEventListener("ai-governance-org", onAuth);
    };
  }, [load]);

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    if (!canManage) return;
    setError(null);
    setMessage(null);
    try {
      const created = await createWebhook({
        name: name.trim(),
        url: url.trim(),
        secret: secret.trim(),
        action_filters: filters
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        organization_slug: getActiveOrganizationSlug(),
      });
      setHooks((prev) => [created, ...prev]);
      setMessage(`Created webhook “${created.name}”`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Create failed");
    }
  }

  async function onToggle(hook: Webhook) {
    if (!canManage) return;
    try {
      const updated = await updateWebhook(hook.id, { is_active: !hook.is_active });
      setHooks((prev) => prev.map((h) => (h.id === updated.id ? updated : h)));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Update failed");
    }
  }

  async function onTest(hook: Webhook) {
    if (!canManage) return;
    setError(null);
    try {
      const updated = await testWebhook(hook.id);
      setHooks((prev) => prev.map((h) => (h.id === updated.id ? updated : h)));
      setMessage(
        updated.last_error
          ? `Test finished with error: ${updated.last_error}`
          : `Test delivered (HTTP ${updated.last_status_code ?? "—"})`,
      );
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Test failed");
    }
  }

  async function onDelete(hook: Webhook) {
    if (!canManage) return;
    try {
      await deleteWebhook(hook.id);
      setHooks((prev) => prev.filter((h) => h.id !== hook.id));
      setMessage("Webhook deleted");
      await load();
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
            Audit webhooks
          </h2>
          <p className="mt-1 text-sm text-zinc-500">
            Push org audit events to HTTPS endpoints with{" "}
            <code className="text-xs">X-AI-Governance-Signature</code> (HMAC-SHA256).
            Failed deliveries retry with backoff. Active org:{" "}
            <span className="font-medium text-zinc-700">
              {getActiveOrganizationSlug()}
            </span>
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
        <form className="mt-4 space-y-3" onSubmit={onCreate}>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="text-zinc-600">Name</span>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="mt-1 w-full border border-zinc-200 px-3 py-2 text-sm"
                required
              />
            </label>
            <label className="block text-sm">
              <span className="text-zinc-600">Signing secret</span>
              <input
                type="password"
                value={secret}
                onChange={(e) => setSecret(e.target.value)}
                className="mt-1 w-full border border-zinc-200 px-3 py-2 text-sm"
                required
                minLength={8}
              />
            </label>
          </div>
          <label className="block text-sm">
            <span className="text-zinc-600">URL</span>
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="mt-1 w-full border border-zinc-200 px-3 py-2 text-sm"
              required
            />
          </label>
          <label className="block text-sm">
            <span className="text-zinc-600">
              Action filters (comma-separated, empty = all)
            </span>
            <input
              value={filters}
              onChange={(e) => setFilters(e.target.value)}
              placeholder="llm.completion, governance.policy_violation"
              className="mt-1 w-full border border-zinc-200 px-3 py-2 text-sm"
            />
          </label>
          <button
            type="submit"
            className="border border-zinc-900 bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800"
          >
            Create webhook
          </button>
        </form>
      )}

      {canManage && (
        <div className="mt-6">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
            Endpoints
          </h3>
          {loading && <p className="mt-2 text-sm text-zinc-600">Loading…</p>}
          {!loading && hooks.length === 0 && (
            <p className="mt-2 text-sm text-zinc-600">No webhooks yet.</p>
          )}
          <ul className="mt-3 space-y-2">
            {hooks.map((hook) => (
              <li
                key={hook.id}
                className="border border-zinc-100 bg-zinc-50 px-3 py-2 text-sm"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="font-medium text-zinc-900">
                      {hook.name}{" "}
                      <span className="text-xs font-normal text-zinc-500">
                        ({hook.is_active ? "active" : "inactive"} · {hook.secret_hint})
                      </span>
                    </p>
                    <p className="mt-0.5 break-all text-xs text-zinc-500">{hook.url}</p>
                    <p className="mt-0.5 text-xs text-zinc-500">
                      filters:{" "}
                      {(hook.action_filters ?? []).join(", ") || "all"}
                      {hook.last_status_code != null
                        ? ` · last HTTP ${hook.last_status_code}`
                        : ""}
                      {hook.last_error ? ` · ${hook.last_error}` : ""}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => void onTest(hook)}
                      className="border border-zinc-200 px-2 py-1 text-xs hover:bg-white"
                    >
                      Test
                    </button>
                    <button
                      type="button"
                      onClick={() => void onToggle(hook)}
                      className="border border-zinc-200 px-2 py-1 text-xs hover:bg-white"
                    >
                      {hook.is_active ? "Disable" : "Enable"}
                    </button>
                    <button
                      type="button"
                      onClick={() => void onDelete(hook)}
                      className="border border-zinc-200 px-2 py-1 text-xs hover:bg-white"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {canManage && (
        <div className="mt-8">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
              Delivery log ({deliveryTotal})
            </h3>
            <select
              value={filterWebhookId}
              onChange={(e) => setFilterWebhookId(e.target.value)}
              className="border border-zinc-200 px-2 py-1 text-xs"
            >
              <option value="">All endpoints</option>
              {hooks.map((h) => (
                <option key={h.id} value={h.id}>
                  {h.name}
                </option>
              ))}
            </select>
          </div>
          {deliveries.length === 0 ? (
            <p className="mt-2 text-sm text-zinc-600">No delivery attempts yet.</p>
          ) : (
            <ul className="mt-3 max-h-64 space-y-1 overflow-y-auto text-xs text-zinc-700">
              {deliveries.map((d) => (
                <li
                  key={d.id}
                  className="border border-zinc-100 bg-zinc-50 px-2 py-1.5"
                >
                  <span className="font-medium">{d.status}</span>
                  {" · "}
                  attempt {d.attempt_number}
                  {d.http_status_code != null ? ` · HTTP ${d.http_status_code}` : ""}
                  {" · "}
                  {d.webhook_name ?? d.webhook_id.slice(0, 8)}
                  {" · "}
                  {new Date(d.created_at).toLocaleString()}
                  {d.next_retry_at && (
                    <> · retry {new Date(d.next_retry_at).toLocaleString()}</>
                  )}
                  {d.error_message && (
                    <span className="mt-0.5 block text-red-700">{d.error_message}</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
