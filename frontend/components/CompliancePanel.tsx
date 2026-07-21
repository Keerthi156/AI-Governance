"use client";

/**
 * Compliance report — org governance posture preview + JSON download.
 */

import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  downloadComplianceReport,
  fetchComplianceReport,
} from "@/lib/api";
import {
  getAccessToken,
  getActiveOrganizationSlug,
  getStoredUser,
} from "@/lib/auth";
import type { AuthUser, ComplianceReport } from "@/types/api";

export function CompliancePanel() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [report, setReport] = useState<ComplianceReport | null>(null);
  const [days, setDays] = useState(30);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const canRead = Boolean(user?.permissions?.includes("compliance:read"));

  const load = useCallback(async () => {
    const stored = getStoredUser();
    setUser(stored);
    if (!getAccessToken() || !stored?.permissions?.includes("compliance:read")) {
      setReport(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setReport(await fetchComplianceReport(days));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load report");
    } finally {
      setLoading(false);
    }
  }, [days]);

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

  async function onDownload() {
    if (!canRead) return;
    setError(null);
    setMessage(null);
    try {
      await downloadComplianceReport(days, getActiveOrganizationSlug());
      setMessage("Compliance report downloaded");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Download failed");
    }
  }

  if (!getAccessToken()) {
    return null;
  }

  const controls = report?.controls ?? {};

  return (
    <section className="w-full max-w-5xl border border-zinc-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Compliance report
          </h2>
          <p className="mt-1 text-sm text-zinc-500">
            Governance posture for{" "}
            <span className="font-medium text-zinc-700">
              {getActiveOrganizationSlug()}
            </span>
            — policies, spend, retention, credentials, violations.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="border border-zinc-200 px-3 py-1.5 text-sm"
          >
            <option value={7}>7 days</option>
            <option value={30}>30 days</option>
            <option value={90}>90 days</option>
          </select>
          <button
            type="button"
            onClick={() => void load()}
            className="border border-zinc-200 px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-50"
          >
            Refresh
          </button>
        </div>
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

      {canRead && (
        <div className="mt-4">
          <button
            type="button"
            onClick={() => void onDownload()}
            className="border border-zinc-900 bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800"
          >
            Download JSON
          </button>
        </div>
      )}

      {canRead && loading && (
        <p className="mt-4 text-sm text-zinc-600">Loading report…</p>
      )}

      {canRead && report && !loading && (
        <div className="mt-6 space-y-4 text-sm">
          <div className="grid gap-2 border border-zinc-100 bg-zinc-50 p-3 text-xs text-zinc-600 sm:grid-cols-2">
            <p>
              Org: {report.organization_name} ({report.organization_slug})
            </p>
            <p>Generated: {new Date(report.generated_at).toLocaleString()}</p>
            <p>
              Spend (UTC): day ${String(report.spend_daily_usd)} · month $
              {String(report.spend_monthly_usd)}
            </p>
            <p>
              Members: {report.members.length} · Policies: {report.policies.length}{" "}
              · Webhooks: {report.webhook_count} · API keys:{" "}
              {report.active_api_key_count}
            </p>
          </div>

          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
              Control checklist
            </h3>
            <ul className="mt-2 grid gap-1 text-xs text-zinc-700 sm:grid-cols-2">
              {Object.entries(controls).map(([key, value]) => (
                <li key={key}>
                  {key}:{" "}
                  <span className="font-medium">
                    {typeof value === "boolean"
                      ? value
                        ? "yes"
                        : "no"
                      : String(value)}
                  </span>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
              Recent violations / PII events
            </h3>
            {report.recent_violations.length === 0 ? (
              <p className="mt-2 text-xs text-zinc-600">None in catalog query.</p>
            ) : (
              <ul className="mt-2 space-y-1 text-xs text-zinc-700">
                {report.recent_violations.slice(0, 8).map((v) => (
                  <li key={v.id}>
                    {new Date(v.created_at).toLocaleString()} · {v.action} ·{" "}
                    {v.summary ?? "—"}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
