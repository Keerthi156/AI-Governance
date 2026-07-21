"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Bot,
  DollarSign,
  FileText,
  Gauge,
  Timer,
  Zap,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useAuthz } from "@/hooks/useAuthz";
import { MetricCard } from "@/components/ui/MetricCard";
import { QuickActionLink } from "@/components/ui/PageFrame";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import {
  ApiError,
  fetchAgentRuns,
  fetchAnalyticsOverview,
  fetchAuditEvents,
  fetchHistory,
  fetchRagDocuments,
} from "@/lib/api";
import { getAccessToken } from "@/lib/auth";
import type {
  AnalyticsOverviewResponse,
  AuditEvent,
  HistoryItem,
} from "@/types/api";

const CHART_COLORS = ["#2563EB", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#06B6D4"];

function fmtMoney(v: string | number | undefined | null) {
  const n = Number(v ?? 0);
  if (Number.isNaN(n)) return "$0.00";
  return `$${n.toFixed(n >= 1 ? 2 : 4)}`;
}

function fmtMs(v: number | null | undefined) {
  if (v == null || Number.isNaN(v)) return "—";
  return `${Math.round(v)} ms`;
}

export default function DashboardPage() {
  const { role, isAdmin, isMember, isViewer } = useAuthz();
  const [data, setData] = useState<AnalyticsOverviewResponse | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [audits, setAudits] = useState<AuditEvent[]>([]);
  const [docCount, setDocCount] = useState(0);
  const [agentRunCount, setAgentRunCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!getAccessToken()) return;
    setLoading(true);
    setError(null);
    try {
      const tasks: Promise<unknown>[] = [
        fetchAnalyticsOverview(isAdmin ? 30 : 7),
        fetchHistory({ page: 1, page_size: 6 }),
      ];
      if (isAdmin) {
        tasks.push(fetchAuditEvents({ page: 1, page_size: 6 }));
        tasks.push(fetchRagDocuments().catch(() => []));
        tasks.push(fetchAgentRuns().catch(() => []));
      } else if (isMember) {
        tasks.push(fetchAgentRuns().catch(() => []));
      }

      const results = await Promise.all(tasks);
      setData(results[0] as AnalyticsOverviewResponse);
      setHistory((results[1] as { items: HistoryItem[] }).items ?? []);

      if (isAdmin) {
        setAudits((results[2] as { items: AuditEvent[] }).items ?? []);
        setDocCount(Array.isArray(results[3]) ? results[3].length : 0);
        setAgentRunCount(Array.isArray(results[4]) ? results[4].length : 0);
      } else if (isMember) {
        setAudits([]);
        setDocCount(0);
        setAgentRunCount(Array.isArray(results[2]) ? results[2].length : 0);
      } else {
        setAudits([]);
        setDocCount(0);
        setAgentRunCount(0);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load dashboard");
    } finally {
      setLoading(false);
    }
  }, [isAdmin, isMember]);

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

  const summary = data?.summary;
  const providerPie = useMemo(
    () =>
      (data?.usage_by_provider ?? []).map((p) => ({
        name: p.provider,
        value: p.requests,
      })),
    [data],
  );
  const daily = useMemo(
    () =>
      (data?.usage_by_day ?? []).map((d) => ({
        day: String(d.day).slice(5, 10),
        requests: d.requests,
        cost: Number(d.estimated_cost_usd ?? 0),
        tokens: d.tokens ?? 0,
        latency: 0,
      })),
    [data],
  );

  const successRate = useMemo(() => {
    if (!summary) return "—";
    return `${(summary.success_rate * 100).toFixed(1)}%`;
  }, [summary]);

  const title = isAdmin
    ? "Organization dashboard"
    : isMember
      ? "My productivity"
      : "My activity";

  const description = isAdmin
    ? `Org-wide operations · last ${data?.days ?? 30} days`
    : isMember
      ? "Your AI usage, agents, and quick actions"
      : "Your personal requests, tokens, and recent prompts";

  if (loading) {
    return (
      <div>
        <SectionHeader title="Dashboard" description="Loading…" />
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  if (error) {
    return (
      <EmptyState
        title="Dashboard unavailable"
        description={error}
        action={
          <button
            type="button"
            onClick={() => void load()}
            className="rounded-xl bg-primary px-4 py-2 text-sm text-primary-foreground"
          >
            Retry
          </button>
        }
      />
    );
  }

  return (
    <div className="space-y-8">
      <SectionHeader
        title={title}
        description={`${description} · role: ${role}`}
        actions={
          <button
            type="button"
            onClick={() => void load()}
            className="rounded-xl border border-border bg-card px-3 py-2 text-sm hover:bg-muted"
          >
            Refresh
          </button>
        }
      />

      {/* Metric cards — role variants */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label={isAdmin ? "Total requests" : "My requests"}
          value={String(summary?.total_requests ?? 0)}
          icon={<Zap className="h-4 w-4" />}
        />
        <MetricCard
          label={isAdmin ? "Period spend" : "My cost"}
          value={fmtMoney(summary?.total_estimated_cost_usd)}
          icon={<DollarSign className="h-4 w-4" />}
        />
        {!isViewer && (
          <MetricCard
            label="Avg latency"
            value={fmtMs(summary?.avg_latency_ms)}
            icon={<Timer className="h-4 w-4" />}
          />
        )}
        {isViewer && (
          <MetricCard
            label="My token usage"
            value={String(summary?.total_tokens ?? 0)}
            icon={<Activity className="h-4 w-4" />}
          />
        )}
        {isAdmin && (
          <>
            <MetricCard
              label="Success rate"
              value={successRate}
              tone="success"
              icon={<Gauge className="h-4 w-4" />}
            />
            <MetricCard
              label="Daily spend"
              value={fmtMoney(daily.at(-1)?.cost)}
              hint="Latest day in series"
              icon={<DollarSign className="h-4 w-4" />}
            />
            <MetricCard
              label="Policy / failed statuses"
              value={String(
                (data?.status_breakdown ?? []).find((s) =>
                  String(s.status).toLowerCase().includes("fail"),
                )?.count ?? 0,
              )}
              tone="warning"
              icon={<AlertTriangle className="h-4 w-4" />}
            />
            <MetricCard
              label="Documents indexed"
              value={String(docCount)}
              icon={<FileText className="h-4 w-4" />}
            />
            <MetricCard
              label="Agent runs"
              value={String(agentRunCount)}
              icon={<Bot className="h-4 w-4" />}
            />
          </>
        )}
        {isMember && (
          <MetricCard
            label="My agent runs"
            value={String(agentRunCount)}
            hint="Recent runs"
            icon={<Bot className="h-4 w-4" />}
          />
        )}
      </div>

      {/* Charts — admin org view; member/viewer lighter */}
      {isAdmin && (
        <div className="grid gap-4 lg:grid-cols-2">
          <ChartCard title="Provider usage">
            {providerPie.length === 0 ? (
              <p className="text-sm text-muted-foreground">No provider data yet.</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={providerPie} dataKey="value" nameKey="name" outerRadius={90}>
                    {providerPie.map((_, i) => (
                      <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            )}
          </ChartCard>
          <ChartCard title="Daily requests">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={daily}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="requests" fill="#2563EB" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
          <ChartCard title="Daily spend">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={daily}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Line type="monotone" dataKey="cost" stroke="#10B981" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>
          <ChartCard title="Token consumption">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={daily}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="tokens" fill="#F59E0B" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        </div>
      )}

      {!isAdmin && (
        <div className="grid gap-4 lg:grid-cols-2">
          <ChartCard title={isViewer ? "My daily requests" : "My usage trend"}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={daily}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="requests" fill="#2563EB" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
          <ChartCard title="My cost trend">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={daily}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Line type="monotone" dataKey="cost" stroke="#10B981" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>
        </div>
      )}

      {/* Quick actions */}
      <div>
        <h2 className="mb-3 text-sm font-semibold text-foreground">Quick actions</h2>
        <div className="flex flex-wrap gap-2">
          {isAdmin && (
            <>
              <QuickActionLink href="/playground">Run Playground</QuickActionLink>
              <QuickActionLink href="/arena">Create Arena</QuickActionLink>
              <QuickActionLink href="/rag">Upload Documents</QuickActionLink>
              <QuickActionLink href="/governance">Create Policy</QuickActionLink>
              <QuickActionLink href="/api-keys">Create API Key</QuickActionLink>
              <QuickActionLink href="/settings?tab=organization">
                Invite User
              </QuickActionLink>
            </>
          )}
          {isMember && (
            <>
              <QuickActionLink href="/playground">Run Playground</QuickActionLink>
              <QuickActionLink href="/arena">Create Arena</QuickActionLink>
              <QuickActionLink href="/rag">Upload Document</QuickActionLink>
            </>
          )}
          {isViewer && (
            <>
              <QuickActionLink href="/history">View my prompts</QuickActionLink>
              <QuickActionLink href="/analytics">View analytics</QuickActionLink>
              <QuickActionLink href="/rag">Search knowledge</QuickActionLink>
            </>
          )}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-border bg-card p-5 shadow-card">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold">
              {isAdmin ? "Recent prompt history" : "My recent prompts"}
            </h2>
            <Link href="/history" className="text-xs text-primary hover:underline">
              View all
            </Link>
          </div>
          <ul className="space-y-2">
            {history.length === 0 && (
              <li className="text-sm text-muted-foreground">No prompts yet.</li>
            )}
            {history.map((item) => (
              <li
                key={item.id}
                className="rounded-xl border border-border bg-muted/40 px-3 py-2 text-sm"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">
                    {item.provider}/{item.model}
                  </span>
                  <StatusBadge
                    label={item.status}
                    tone={item.status === "success" ? "success" : "danger"}
                  />
                </div>
                <p className="mt-1 line-clamp-1 text-xs text-muted-foreground">
                  {item.prompt}
                </p>
              </li>
            ))}
          </ul>
        </div>

        {isAdmin ? (
          <div className="rounded-2xl border border-border bg-card p-5 shadow-card">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="flex items-center gap-2 text-sm font-semibold">
                <Activity className="h-4 w-4 text-primary" />
                Recent audit events
              </h2>
              <Link href="/audit" className="text-xs text-primary hover:underline">
                View all
              </Link>
            </div>
            <ul className="space-y-2">
              {audits.length === 0 && (
                <li className="text-sm text-muted-foreground">No audit events yet.</li>
              )}
              {audits.map((ev) => (
                <li
                  key={ev.id}
                  className="rounded-xl border border-border bg-muted/40 px-3 py-2 text-sm"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium">{ev.action}</span>
                    <StatusBadge
                      label={ev.status}
                      tone={
                        ev.status === "success"
                          ? "success"
                          : ev.status === "warning"
                            ? "warning"
                            : "danger"
                      }
                    />
                  </div>
                  <p className="mt-1 line-clamp-1 text-xs text-muted-foreground">
                    {ev.summary ?? "—"}
                  </p>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <div className="rounded-2xl border border-border bg-card p-5 shadow-card">
            <h2 className="mb-3 text-sm font-semibold">Top models (your window)</h2>
            <ModelTable rows={data?.usage_by_model ?? []} />
          </div>
        )}
      </div>

      {isAdmin && (
        <div className="rounded-2xl border border-border bg-card p-5 shadow-card">
          <h2 className="mb-3 text-sm font-semibold">Top models</h2>
          <ModelTable rows={data?.usage_by_model ?? []} />
        </div>
      )}
    </div>
  );
}

function ChartCard({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-border bg-card p-5 shadow-card">
      <h2 className="text-sm font-semibold text-foreground">{title}</h2>
      <div className="mt-4 h-64">{children}</div>
    </div>
  );
}

function ModelTable({
  rows,
}: {
  rows: Array<{
    provider: string;
    model: string;
    requests: number;
    estimated_cost_usd: string;
  }>;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[28rem] text-left text-sm">
        <thead className="text-xs uppercase text-muted-foreground">
          <tr>
            <th className="pb-2 font-medium">Model</th>
            <th className="pb-2 font-medium">Provider</th>
            <th className="pb-2 font-medium">Requests</th>
            <th className="pb-2 font-medium">Cost</th>
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 8).map((row) => (
            <tr key={`${row.provider}-${row.model}`} className="border-t border-border">
              <td className="py-2">{row.model}</td>
              <td className="py-2 text-muted-foreground">{row.provider}</td>
              <td className="py-2">{row.requests}</td>
              <td className="py-2">{fmtMoney(row.estimated_cost_usd)}</td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td colSpan={4} className="py-4 text-muted-foreground">
                No model usage yet.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
