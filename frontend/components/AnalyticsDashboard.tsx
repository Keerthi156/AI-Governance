"use client";

/**
 * Analytics Dashboard — KPIs + Recharts visualizations from /analytics/overview.
 */

import { useCallback, useEffect, useState, type ReactNode } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { ApiError, fetchAnalyticsOverview } from "@/lib/api";
import type { AnalyticsOverviewResponse } from "@/types/api";

const PROVIDER_COLORS = ["#18181b", "#3f3f46", "#71717a", "#a1a1aa", "#d4d4d8"];

export function AnalyticsDashboard() {
  const [days, setDays] = useState(7);
  const [data, setData] = useState<AnalyticsOverviewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const overview = await fetchAnalyticsOverview(days);
      setData(overview);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load analytics");
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    void load();
    const onOrg = () => void load();
    window.addEventListener("ai-governance-auth", onOrg);
    window.addEventListener("ai-governance-org", onOrg);
    window.addEventListener("storage", onOrg);
    return () => {
      window.removeEventListener("ai-governance-auth", onOrg);
      window.removeEventListener("ai-governance-org", onOrg);
      window.removeEventListener("storage", onOrg);
    };
  }, [load]);

  const summary = data?.summary;

  return (
    <section className="w-full max-w-5xl border border-zinc-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Analytics dashboard
          </h2>
          <p className="mt-1 text-sm text-zinc-500">
            Usage, cost, reliability, and router task mix from live PostgreSQL
            aggregates.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="border border-zinc-200 px-3 py-1.5 text-sm"
          >
            <option value={7}>Last 7 days</option>
            <option value={14}>Last 14 days</option>
            <option value={30}>Last 30 days</option>
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

      {error && (
        <div className="mt-4 border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {loading && !data && (
        <p className="mt-4 text-sm text-zinc-600">Loading analytics…</p>
      )}

      {summary && (
        <div className="mt-6 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
          <Kpi label="Requests" value={String(summary.total_requests)} />
          <Kpi
            label="Success rate"
            value={`${(summary.success_rate * 100).toFixed(1)}%`}
          />
          <Kpi label="Tokens" value={summary.total_tokens.toLocaleString()} />
          <Kpi
            label="Est. cost"
            value={`$${summary.total_estimated_cost_usd}`}
          />
          <Kpi
            label="Avg latency"
            value={
              summary.avg_latency_ms != null
                ? `${summary.avg_latency_ms} ms`
                : "—"
            }
          />
          <Kpi label="Arena runs" value={String(summary.arena_run_count)} />
          <Kpi
            label="Router decisions"
            value={String(summary.routing_decision_count)}
          />
          <Kpi label="Evaluations" value={String(summary.evaluation_count)} />
        </div>
      )}

      {data && (
        <div className="mt-8 grid gap-8 lg:grid-cols-2">
          <ChartCard title="Requests over time">
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={data.usage_by_day}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e4e4e7" />
                <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="requests"
                  stroke="#18181b"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="error_count"
                  stroke="#b45309"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Tokens by provider">
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={data.usage_by_provider}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e4e4e7" />
                <XAxis dataKey="provider" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="tokens" fill="#3f3f46" />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Status breakdown">
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={data.status_breakdown}
                  dataKey="count"
                  nameKey="status"
                  cx="50%"
                  cy="50%"
                  outerRadius={70}
                  label
                >
                  {data.status_breakdown.map((entry, index) => (
                    <Cell
                      key={entry.status}
                      fill={PROVIDER_COLORS[index % PROVIDER_COLORS.length]}
                    />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Router task mix">
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={data.routing_by_task_type}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e4e4e7" />
                <XAxis dataKey="task_type" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="count" fill="#18181b" />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        </div>
      )}

      {data && data.usage_by_model.length > 0 && (
        <div className="mt-8">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
            Top models
          </h3>
          <div className="mt-2 overflow-x-auto">
            <table className="min-w-full border-collapse text-left text-xs">
              <thead>
                <tr className="border-b border-zinc-200 text-zinc-500">
                  <th className="px-2 py-2">Provider</th>
                  <th className="px-2 py-2">Model</th>
                  <th className="px-2 py-2">Requests</th>
                  <th className="px-2 py-2">Tokens</th>
                  <th className="px-2 py-2">Cost</th>
                  <th className="px-2 py-2">Avg latency</th>
                </tr>
              </thead>
              <tbody>
                {data.usage_by_model.map((row) => (
                  <tr
                    key={`${row.provider}:${row.model}`}
                    className="border-b border-zinc-100"
                  >
                    <td className="px-2 py-2">{row.provider}</td>
                    <td className="px-2 py-2">{row.model}</td>
                    <td className="px-2 py-2">{row.requests}</td>
                    <td className="px-2 py-2">{row.tokens}</td>
                    <td className="px-2 py-2">${row.estimated_cost_usd}</td>
                    <td className="px-2 py-2">
                      {row.avg_latency_ms != null
                        ? `${row.avg_latency_ms} ms`
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-zinc-100 bg-zinc-50 px-3 py-3">
      <p className="text-xs text-zinc-500">{label}</p>
      <p className="mt-1 text-lg font-semibold text-zinc-900">{value}</p>
    </div>
  );
}

function ChartCard({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-500">
        {title}
      </h3>
      <div className="border border-zinc-100 bg-zinc-50 p-2">{children}</div>
    </div>
  );
}
