"use client";

/**
 * Audit log panel — org-scoped security/usage event trail (admin).
 */

import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  downloadAuditExport,
  fetchAuditActions,
  fetchAuditEvents,
} from "@/lib/api";
import { getAccessToken, getStoredUser } from "@/lib/auth";
import type { AuditEvent, AuthUser } from "@/types/api";

export function AuditPanel() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [actions, setActions] = useState<string[]>([]);
  const [actionFilter, setActionFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canRead = Boolean(user?.permissions?.includes("audit:read"));

  const load = useCallback(async () => {
    const stored = getStoredUser();
    setUser(stored);
    if (!getAccessToken() || !stored?.permissions?.includes("audit:read")) {
      setEvents([]);
      setTotal(0);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [list, catalog] = await Promise.all([
        fetchAuditEvents({
          action: actionFilter || undefined,
          status: statusFilter || undefined,
          page: 1,
          page_size: 40,
        }),
        fetchAuditActions(),
      ]);
      setEvents(list.items);
      setTotal(list.total);
      setActions(catalog.actions);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load audit events");
    } finally {
      setLoading(false);
    }
  }, [actionFilter, statusFilter]);

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

  async function onExport(format: "csv" | "json") {
    if (!canRead) return;
    setExporting(true);
    setError(null);
    try {
      await downloadAuditExport({
        format,
        action: actionFilter || undefined,
        status: statusFilter || undefined,
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Export failed");
    } finally {
      setExporting(false);
    }
  }

  return (
    <section className="w-full max-w-5xl border border-zinc-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Audit logs
          </h2>
          <p className="mt-1 text-sm text-zinc-500">
            Durable trail of auth, RBAC, governance, and LLM actions for this
            organization.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void onExport("csv")}
            disabled={exporting || !canRead}
            className="border border-zinc-200 px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50"
          >
            {exporting ? "Exporting…" : "Export CSV"}
          </button>
          <button
            type="button"
            onClick={() => void onExport("json")}
            disabled={exporting || !canRead}
            className="border border-zinc-200 px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50"
          >
            Export JSON
          </button>
          <button
            type="button"
            onClick={() => void load()}
            className="border border-zinc-200 px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-50"
          >
            Refresh
          </button>
        </div>
      </div>

      {!getAccessToken() && (
        <p className="mt-4 text-sm text-zinc-600">
          Sign in as an admin to view audit logs.
        </p>
      )}

      {getAccessToken() && !canRead && (
        <p className="mt-4 text-sm text-zinc-600">
          Audit logs require the <span className="font-medium">admin</span> role
          (`audit:read`).
        </p>
      )}

      {error && (
        <div className="mt-4 border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {canRead && (
        <>
          <div className="mt-4 flex flex-wrap gap-3 text-sm">
            <label>
              <span className="text-zinc-500">Action</span>
              <select
                value={actionFilter}
                onChange={(e) => setActionFilter(e.target.value)}
                className="ml-2 border border-zinc-200 px-2 py-1"
              >
                <option value="">All</option>
                {actions.map((action) => (
                  <option key={action} value={action}>
                    {action}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span className="text-zinc-500">Status</span>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="ml-2 border border-zinc-200 px-2 py-1"
              >
                <option value="">All</option>
                <option value="success">success</option>
                <option value="failure">failure</option>
                <option value="denied">denied</option>
              </select>
            </label>
            <span className="self-center text-xs text-zinc-500">
              {total} event{total === 1 ? "" : "s"}
            </span>
          </div>

          {loading && (
            <p className="mt-4 text-sm text-zinc-600">Loading audit events…</p>
          )}

          {!loading && events.length === 0 && (
            <p className="mt-4 text-sm text-zinc-600">No audit events yet.</p>
          )}

          {events.length > 0 && (
            <div className="mt-4 overflow-x-auto">
              <table className="min-w-full border-collapse text-left text-xs">
                <thead>
                  <tr className="border-b border-zinc-200 text-zinc-500">
                    <th className="px-2 py-2">When</th>
                    <th className="px-2 py-2">Action</th>
                    <th className="px-2 py-2">Status</th>
                    <th className="px-2 py-2">Actor</th>
                    <th className="px-2 py-2">Summary</th>
                  </tr>
                </thead>
                <tbody>
                  {events.map((event) => (
                    <tr key={event.id} className="border-b border-zinc-100 align-top">
                      <td className="whitespace-nowrap px-2 py-2 text-zinc-500">
                        {new Date(event.created_at).toLocaleString()}
                      </td>
                      <td className="px-2 py-2 font-medium">{event.action}</td>
                      <td className="px-2 py-2">{event.status}</td>
                      <td className="px-2 py-2">{event.actor_email ?? "—"}</td>
                      <td className="px-2 py-2 text-zinc-600">
                        {event.summary ?? "—"}
                        {event.request_id ? (
                          <span className="mt-1 block text-[10px] text-zinc-400">
                            req {event.request_id}
                          </span>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </section>
  );
}
