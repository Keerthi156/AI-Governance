"use client";

/**
 * Data retention — keep-windows, opt-in scheduled purge, manual purge.
 */

import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";

import {
  ApiError,
  fetchRetentionScheduler,
  fetchRetentionSettings,
  purgeRetention,
  updateRetentionSettings,
} from "@/lib/api";
import {
  getAccessToken,
  getActiveOrganizationSlug,
  getStoredUser,
} from "@/lib/auth";
import type {
  AuthUser,
  RetentionSchedulerStatus,
  RetentionSettings,
} from "@/types/api";

export function RetentionPanel() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [settings, setSettings] = useState<RetentionSettings | null>(null);
  const [scheduler, setScheduler] = useState<RetentionSchedulerStatus | null>(
    null,
  );
  const [historyDays, setHistoryDays] = useState("");
  const [auditDays, setAuditDays] = useState("");
  const [autoPurge, setAutoPurge] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const canManage = Boolean(user?.permissions?.includes("retention:manage"));

  const load = useCallback(async () => {
    const stored = getStoredUser();
    setUser(stored);
    if (!getAccessToken() || !stored?.permissions?.includes("retention:manage")) {
      setSettings(null);
      setScheduler(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [data, sched] = await Promise.all([
        fetchRetentionSettings(),
        fetchRetentionScheduler(),
      ]);
      setSettings(data);
      setScheduler(sched);
      setHistoryDays(
        data.prompt_history_retention_days != null
          ? String(data.prompt_history_retention_days)
          : "",
      );
      setAuditDays(
        data.audit_events_retention_days != null
          ? String(data.audit_events_retention_days)
          : "",
      );
      setAutoPurge(data.retention_auto_purge_enabled);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load retention");
    } finally {
      setLoading(false);
    }
  }, []);

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

  async function onSave(event: FormEvent) {
    event.preventDefault();
    if (!canManage) return;
    setError(null);
    setMessage(null);
    try {
      const updated = await updateRetentionSettings({
        organization_slug: getActiveOrganizationSlug(),
        prompt_history_retention_days: historyDays.trim()
          ? Number(historyDays)
          : null,
        audit_events_retention_days: auditDays.trim() ? Number(auditDays) : null,
        retention_auto_purge_enabled: autoPurge,
      });
      setSettings(updated);
      setMessage(
        autoPurge
          ? "Retention saved — scheduled auto-purge enabled for this org"
          : "Retention settings saved",
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Save failed");
    }
  }

  async function onPurge(dryRun: boolean) {
    if (!canManage) return;
    setError(null);
    setMessage(null);
    try {
      const result = await purgeRetention(dryRun);
      setMessage(
        `${dryRun ? "Dry-run" : "Purged"}: history ${result.prompt_history_deleted}, audit ${result.audit_events_deleted}`,
      );
      if (!dryRun) {
        await load();
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Purge failed");
    }
  }

  if (!getAccessToken()) {
    return null;
  }

  const intervalLabel = scheduler
    ? scheduler.interval_seconds >= 3600
      ? `${Math.round(scheduler.interval_seconds / 3600)}h`
      : `${scheduler.interval_seconds}s`
    : "—";

  return (
    <section className="w-full max-w-5xl border border-zinc-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Data retention
          </h2>
          <p className="mt-1 text-sm text-zinc-500">
            Keep-windows for prompt history and audit events (active org:{" "}
            <span className="font-medium text-zinc-700">
              {getActiveOrganizationSlug()}
            </span>
            ). Empty = keep forever. Scheduled purge is opt-in per org.
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

      {canManage && scheduler && (
        <div className="mt-4 border border-zinc-100 bg-zinc-50 px-3 py-2 text-xs text-zinc-600">
          <p>
            Platform scheduler:{" "}
            {scheduler.enabled ? (
              <span className="font-medium text-zinc-800">
                {scheduler.thread_alive ? "running" : "enabled (starting)"}
              </span>
            ) : (
              <span className="font-medium text-zinc-800">disabled</span>
            )}{" "}
            · interval {intervalLabel}
            {scheduler.last_cycle_finished_at && (
              <>
                {" "}
                · last cycle{" "}
                {new Date(scheduler.last_cycle_finished_at).toLocaleString()} (
                {scheduler.last_orgs_processed} orgs, history{" "}
                {scheduler.last_prompt_history_deleted}, audit{" "}
                {scheduler.last_audit_events_deleted})
              </>
            )}
          </p>
          {scheduler.last_error && (
            <p className="mt-1 text-red-700">Last error: {scheduler.last_error}</p>
          )}
        </div>
      )}

      {canManage && (
        <form className="mt-4 space-y-3" onSubmit={onSave}>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="text-zinc-600">Prompt history days</span>
              <input
                type="number"
                min={1}
                max={3650}
                value={historyDays}
                onChange={(e) => setHistoryDays(e.target.value)}
                placeholder="forever"
                className="mt-1 w-full border border-zinc-200 px-3 py-2 text-sm"
              />
            </label>
            <label className="block text-sm">
              <span className="text-zinc-600">Audit events days</span>
              <input
                type="number"
                min={1}
                max={3650}
                value={auditDays}
                onChange={(e) => setAuditDays(e.target.value)}
                placeholder="forever"
                className="mt-1 w-full border border-zinc-200 px-3 py-2 text-sm"
              />
            </label>
          </div>
          <label className="flex items-start gap-2 text-sm text-zinc-700">
            <input
              type="checkbox"
              checked={autoPurge}
              onChange={(e) => setAutoPurge(e.target.checked)}
              className="mt-1"
            />
            <span>
              Enable scheduled auto-purge for this organization
              <span className="mt-0.5 block text-xs text-zinc-500">
                Only runs when keep-windows are set and the platform scheduler is
                enabled.
              </span>
            </span>
          </label>
          <button
            type="submit"
            className="border border-zinc-900 bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800"
          >
            Save retention
          </button>
        </form>
      )}

      {canManage && settings && (
        <div className="mt-6 space-y-3 text-sm">
          {loading && <p className="text-zinc-600">Loading…</p>}
          <div className="border border-zinc-100 bg-zinc-50 px-3 py-2 text-xs text-zinc-600">
            <p>
              Prompt history: {settings.prompt_history_total} total ·{" "}
              {settings.prompt_history_expired} expired
            </p>
            <p className="mt-1">
              Audit events: {settings.audit_events_total} total ·{" "}
              {settings.audit_events_expired} expired
            </p>
            <p className="mt-1">
              Auto-purge:{" "}
              {settings.retention_auto_purge_enabled ? "enabled" : "off"}
              {settings.retention_last_auto_purge_at && (
                <>
                  {" "}
                  · last run{" "}
                  {new Date(
                    settings.retention_last_auto_purge_at,
                  ).toLocaleString()}
                </>
              )}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void onPurge(true)}
              className="border border-zinc-200 px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-50"
            >
              Dry-run purge
            </button>
            <button
              type="button"
              onClick={() => void onPurge(false)}
              className="border border-red-200 px-3 py-1.5 text-xs font-medium text-red-800 hover:bg-red-50"
            >
              Purge expired now
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
