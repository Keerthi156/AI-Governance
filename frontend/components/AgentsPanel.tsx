"use client";

/**
 * AI Agents panel — fixed definitions + free-form planner.
 */

import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";

import {
  ApiError,
  fetchAgentDefinitions,
  fetchAgentRuns,
  previewAgentPlan,
  runAgent,
  runPlannedAgent,
} from "@/lib/api";
import {
  getAccessToken,
  getActiveOrganizationSlug,
  getStoredUser,
} from "@/lib/auth";
import type {
  AgentDefinition,
  AgentPlanPreviewResponse,
  AgentRunResponse,
  AuthUser,
} from "@/types/api";

type Mode = "definition" | "planner";

export function AgentsPanel() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [definitions, setDefinitions] = useState<AgentDefinition[]>([]);
  const [runs, setRuns] = useState<AgentRunResponse[]>([]);
  const [mode, setMode] = useState<Mode>("definition");
  const [definitionId, setDefinitionId] = useState("");
  const [inputText, setInputText] = useState(
    "Which providers are approved for production workloads?",
  );
  const [goal, setGoal] = useState(
    "Answer from our knowledge base which providers are approved for production.",
  );
  const [planPreview, setPlanPreview] = useState<AgentPlanPreviewResponse | null>(
    null,
  );
  const [latest, setLatest] = useState<AgentRunResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canRead = Boolean(user?.permissions?.includes("agents:read"));
  const canRun = Boolean(user?.permissions?.includes("agents:run"));

  const load = useCallback(async () => {
    const stored = getStoredUser();
    setUser(stored);
    if (!getAccessToken() || !stored?.permissions?.includes("agents:read")) {
      setDefinitions([]);
      setRuns([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [defs, recent] = await Promise.all([
        fetchAgentDefinitions(),
        fetchAgentRuns(getActiveOrganizationSlug(), 10),
      ]);
      setDefinitions(defs);
      setRuns(recent);
      if (!definitionId) {
        const firstFixed = defs.find((d) => d.name !== "Free-form Planner");
        if (firstFixed) setDefinitionId(firstFixed.id);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load agents");
    } finally {
      setLoading(false);
    }
  }, [definitionId]);

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

  async function onRun(event: FormEvent) {
    event.preventDefault();
    if (!canRun || !definitionId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await runAgent({
        definition_id: definitionId,
        input_text: inputText,
        provider: "groq",
        organization_slug: getActiveOrganizationSlug(),
      });
      setLatest(result);
      setRuns((prev) => [result, ...prev].slice(0, 10));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Agent run failed");
    } finally {
      setLoading(false);
    }
  }

  async function onPreviewPlan() {
    if (!canRead || !goal.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const preview = await previewAgentPlan({
        goal,
        organization_slug: getActiveOrganizationSlug(),
      });
      setPlanPreview(preview);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Plan preview failed");
    } finally {
      setLoading(false);
    }
  }

  async function onRunPlanner(event: FormEvent) {
    event.preventDefault();
    if (!canRun || !goal.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const result = await runPlannedAgent({
        goal,
        provider: "groq",
        organization_slug: getActiveOrganizationSlug(),
      });
      setLatest(result);
      setPlanPreview({
        goal: result.input_text,
        tools: result.steps_log
          .filter((s) => s.tool !== "plan_tools" && s.tool !== "runner")
          .map((s) => s.tool),
        rationale:
          result.steps_log.find((s) => s.tool === "plan_tools")?.summary || "",
        planner: String(
          (result.steps_log.find((s) => s.tool === "plan_tools")?.detail as
            | { planner?: string }
            | undefined)?.planner || "heuristic_v1",
        ),
      });
      setRuns((prev) => [result, ...prev].slice(0, 10));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Planner run failed");
    } finally {
      setLoading(false);
    }
  }

  const selected = definitions.find((d) => d.id === definitionId);

  return (
    <section className="w-full max-w-5xl border border-zinc-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
            AI Agents
          </h2>
          <p className="mt-1 text-sm text-zinc-500">
            Fixed tool workflows or free-form planner (goal → tool plan → same
            runner) with durable run logs.
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
          Sign in to run agents. Members can execute; admins can create custom
          definitions via API.
        </p>
      )}

      {error && (
        <div className="mt-4 border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {(canRead || canRun) && (
        <div className="mt-6 flex gap-2 text-xs">
          <button
            type="button"
            onClick={() => setMode("definition")}
            className={
              mode === "definition"
                ? "bg-zinc-900 px-3 py-1.5 font-medium text-white"
                : "border border-zinc-200 px-3 py-1.5 text-zinc-700 hover:bg-zinc-50"
            }
          >
            Fixed agent
          </button>
          <button
            type="button"
            onClick={() => setMode("planner")}
            className={
              mode === "planner"
                ? "bg-zinc-900 px-3 py-1.5 font-medium text-white"
                : "border border-zinc-200 px-3 py-1.5 text-zinc-700 hover:bg-zinc-50"
            }
          >
            Free-form planner
          </button>
        </div>
      )}

      {canRun && mode === "definition" && (
        <form className="mt-6 space-y-3" onSubmit={onRun}>
          <label className="block text-sm">
            <span className="text-zinc-600">Agent</span>
            <select
              value={definitionId}
              onChange={(e) => setDefinitionId(e.target.value)}
              className="mt-1 w-full border border-zinc-200 px-3 py-2 text-sm"
              required
            >
              {definitions
                .filter((def) => def.name !== "Free-form Planner")
                .map((def) => (
                <option key={def.id} value={def.id}>
                  {def.name}
                </option>
              ))}
            </select>
          </label>
          {selected && (
            <p className="text-xs text-zinc-500">
              Steps: {selected.steps.join(" → ")}
              {selected.description ? ` · ${selected.description}` : ""}
            </p>
          )}
          <label className="block text-sm">
            <span className="text-zinc-600">Input</span>
            <textarea
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              rows={3}
              className="mt-1 w-full border border-zinc-200 px-3 py-2 text-sm"
              required
            />
          </label>
          <button
            type="submit"
            disabled={loading || !definitionId}
            className="bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-50"
          >
            {loading ? "Running…" : "Run agent"}
          </button>
        </form>
      )}

      {mode === "planner" && (canRead || canRun) && (
        <form className="mt-6 space-y-3" onSubmit={onRunPlanner}>
          <label className="block text-sm">
            <span className="text-zinc-600">Goal</span>
            <textarea
              value={goal}
              onChange={(e) => {
                setGoal(e.target.value);
                setPlanPreview(null);
              }}
              rows={3}
              className="mt-1 w-full border border-zinc-200 px-3 py-2 text-sm"
              required
            />
          </label>
          {planPreview && (
            <p className="text-xs text-zinc-600">
              Plan ({planPreview.planner}): {planPreview.tools.join(" → ")}
              <span className="mt-1 block text-zinc-500">
                {planPreview.rationale}
              </span>
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            {canRead && (
              <button
                type="button"
                onClick={() => void onPreviewPlan()}
                disabled={loading || !goal.trim()}
                className="border border-zinc-200 px-4 py-2 text-sm font-medium text-zinc-800 hover:bg-zinc-50 disabled:opacity-50"
              >
                Preview plan
              </button>
            )}
            {canRun && (
              <button
                type="submit"
                disabled={loading || !goal.trim()}
                className="bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-50"
              >
                {loading ? "Running…" : "Plan & run"}
              </button>
            )}
          </div>
        </form>
      )}

      {latest && (
        <div className="mt-6 border border-zinc-100 bg-zinc-50 p-4 text-sm">
          <p className="text-xs uppercase tracking-wide text-zinc-500">
            Latest run · {latest.definition_name} · {latest.status}
          </p>
          <p className="mt-2 whitespace-pre-wrap text-zinc-900">
            {latest.output_text || latest.error_message || "—"}
          </p>
          <ol className="mt-4 space-y-2">
            {latest.steps_log.map((step) => (
              <li key={`${step.step}-${step.tool}`} className="text-xs text-zinc-600">
                <span className="font-medium text-zinc-800">
                  {step.step}. {step.tool}
                </span>{" "}
                ({step.status}) — {step.summary}
              </li>
            ))}
          </ol>
        </div>
      )}

      {canRead && runs.length > 0 && (
        <div className="mt-6">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
            Recent runs
          </h3>
          <ul className="mt-2 space-y-2 text-xs text-zinc-600">
            {runs.map((run) => (
              <li
                key={run.id}
                className="flex flex-wrap justify-between gap-2 border border-zinc-100 px-3 py-2"
              >
                <span>
                  {run.definition_name} · {run.status}
                </span>
                <span className="text-zinc-400">
                  {new Date(run.created_at).toLocaleString()}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
