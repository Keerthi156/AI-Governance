"use client";

/**
 * Enhanced Evaluation panel — richer metrics + strategy comparison.
 */

import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  compareArenaStrategies,
  evaluateArenaRun,
  fetchHistory,
} from "@/lib/api";
import type {
  EvaluationResponse,
  EvaluationStrategy,
  StrategyComparisonResponse,
} from "@/types/api";

const STRATEGIES: EvaluationStrategy[] = [
  "balanced",
  "cheapest",
  "fastest",
  "quality",
  "reliability",
];

const TASK_TYPES = [
  "",
  "coding",
  "summarization",
  "creative",
  "qa",
  "analysis",
  "translation",
  "chat",
  "general",
];

export function EvaluationPanel() {
  const [arenaRunId, setArenaRunId] = useState("");
  const [strategy, setStrategy] = useState<EvaluationStrategy>("balanced");
  const [taskType, setTaskType] = useState("");
  const [recentArenaIds, setRecentArenaIds] = useState<string[]>([]);
  const [result, setResult] = useState<EvaluationResponse | null>(null);
  const [comparison, setComparison] =
    useState<StrategyComparisonResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadRecentArenaIds = useCallback(async () => {
    try {
      const history = await fetchHistory({ arena_only: true, page_size: 30 });
      const ids = Array.from(
        new Set(
          history.items
            .map((item) => item.arena_run_id)
            .filter((id): id is string => Boolean(id)),
        ),
      );
      setRecentArenaIds(ids.slice(0, 8));
      if (!arenaRunId && ids.length > 0) {
        setArenaRunId(ids[0]);
      }
    } catch {
      // Non-blocking
    }
  }, [arenaRunId]);

  useEffect(() => {
    void loadRecentArenaIds();
    const onOrg = () => void loadRecentArenaIds();
    window.addEventListener("ai-governance-auth", onOrg);
    window.addEventListener("ai-governance-org", onOrg);
    return () => {
      window.removeEventListener("ai-governance-auth", onOrg);
      window.removeEventListener("ai-governance-org", onOrg);
    };
  }, [loadRecentArenaIds]);

  async function onEvaluate() {
    if (!arenaRunId.trim()) {
      setError("Select or paste an arena_run_id.");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    setComparison(null);
    try {
      const data = await evaluateArenaRun(
        arenaRunId.trim(),
        strategy,
        taskType || undefined,
      );
      setResult(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Evaluation failed");
    } finally {
      setLoading(false);
    }
  }

  async function onCompare() {
    if (!arenaRunId.trim()) {
      setError("Select or paste an arena_run_id.");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    setComparison(null);
    try {
      const data = await compareArenaStrategies(arenaRunId.trim(), {
        taskType: taskType || undefined,
      });
      setComparison(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Compare failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="w-full max-w-5xl border border-zinc-200 bg-white p-6 shadow-sm">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
        Enhanced evaluation engine
      </h2>
      <p className="mt-1 text-sm text-zinc-500">
        Scores success, latency, cost, substance, structure, and relevance.
        Supports task-aware weights and multi-strategy comparison.
      </p>

      <div className="mt-4 flex flex-wrap items-end gap-3 text-sm">
        <label className="min-w-[16rem] flex-1">
          <span className="text-zinc-500">Arena run ID</span>
          <input
            value={arenaRunId}
            onChange={(e) => setArenaRunId(e.target.value)}
            list="arena-run-options"
            className="mt-1 w-full border border-zinc-200 px-3 py-2 font-mono text-xs"
            placeholder="uuid from Arena / History"
          />
          <datalist id="arena-run-options">
            {recentArenaIds.map((id) => (
              <option key={id} value={id} />
            ))}
          </datalist>
        </label>

        <label>
          <span className="text-zinc-500">Strategy</span>
          <select
            value={strategy}
            onChange={(e) =>
              setStrategy(e.target.value as EvaluationStrategy)
            }
            className="mt-1 block border border-zinc-200 px-3 py-2"
          >
            {STRATEGIES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>

        <label>
          <span className="text-zinc-500">Task type</span>
          <select
            value={taskType}
            onChange={(e) => setTaskType(e.target.value)}
            className="mt-1 block border border-zinc-200 px-3 py-2"
          >
            {TASK_TYPES.map((t) => (
              <option key={t || "none"} value={t}>
                {t || "auto/general"}
              </option>
            ))}
          </select>
        </label>

        <button
          type="button"
          onClick={() => void onEvaluate()}
          disabled={loading}
          className="border border-zinc-900 bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-50"
        >
          {loading ? "Working…" : "Evaluate"}
        </button>
        <button
          type="button"
          onClick={() => void onCompare()}
          disabled={loading}
          className="border border-zinc-200 px-4 py-2 text-sm text-zinc-800 hover:bg-zinc-50 disabled:opacity-50"
        >
          Compare all strategies
        </button>
      </div>

      {error && (
        <div className="mt-4 border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {result && <EvaluationResultCard result={result} />}

      {comparison && (
        <div className="mt-6 space-y-4">
          <p className="text-sm font-medium text-zinc-800">
            Strategy comparison · {comparison.evaluations.length} runs
          </p>
          <div className="overflow-x-auto">
            <table className="min-w-full border-collapse text-left text-xs">
              <thead>
                <tr className="border-b border-zinc-200 text-zinc-500">
                  <th className="px-2 py-2">Strategy</th>
                  <th className="px-2 py-2">Winner</th>
                  <th className="px-2 py-2">Score</th>
                  <th className="px-2 py-2">Gap</th>
                </tr>
              </thead>
              <tbody>
                {comparison.evaluations.map((ev) => (
                  <tr key={ev.id} className="border-b border-zinc-100">
                    <td className="px-2 py-2">{ev.strategy}</td>
                    <td className="px-2 py-2">
                      {ev.recommended_provider
                        ? `${ev.recommended_provider} · ${ev.recommended_model}`
                        : "—"}
                    </td>
                    <td className="px-2 py-2">
                      {ev.scores[0]?.composite_score ?? "—"}
                    </td>
                    <td className="px-2 py-2">{ev.score_gap ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {comparison.evaluations[0] && (
            <EvaluationResultCard result={comparison.evaluations[0]} />
          )}
        </div>
      )}
    </section>
  );
}

function EvaluationResultCard({ result }: { result: EvaluationResponse }) {
  return (
    <div className="mt-6 space-y-4 text-sm">
      <div className="border border-emerald-200 bg-emerald-50 p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-emerald-800">
          Recommendation
        </p>
        <p className="mt-1 font-medium text-emerald-950">
          {result.recommended_provider && result.recommended_model
            ? `${result.recommended_provider} · ${result.recommended_model}`
            : "No successful model to recommend"}
        </p>
        <p className="mt-1 text-emerald-900">{result.summary}</p>
        <p className="mt-2 text-xs text-emerald-800">
          strategy={result.strategy}
          {result.task_type ? ` · task=${result.task_type}` : ""}
          {result.score_gap != null ? ` · gap=${result.score_gap}` : ""}
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full border-collapse text-left text-xs">
          <thead>
            <tr className="border-b border-zinc-200 text-zinc-500">
              <th className="px-2 py-2">Rank</th>
              <th className="px-2 py-2">Model</th>
              <th className="px-2 py-2">Status</th>
              <th className="px-2 py-2">Composite</th>
              <th className="px-2 py-2">Success</th>
              <th className="px-2 py-2">Latency</th>
              <th className="px-2 py-2">Cost</th>
              <th className="px-2 py-2">Substance</th>
              <th className="px-2 py-2">Structure</th>
              <th className="px-2 py-2">Relevance</th>
            </tr>
          </thead>
          <tbody>
            {result.scores.map((score) => (
              <tr key={score.id} className="border-b border-zinc-100">
                <td className="px-2 py-2 font-medium">{score.rank}</td>
                <td className="px-2 py-2">
                  {score.provider} · {score.model}
                </td>
                <td className="px-2 py-2">{score.status}</td>
                <td className="px-2 py-2">{score.composite_score}</td>
                <td className="px-2 py-2">{score.success_score}</td>
                <td className="px-2 py-2">{score.latency_score}</td>
                <td className="px-2 py-2">{score.cost_score}</td>
                <td className="px-2 py-2">{score.substance_score}</td>
                <td className="px-2 py-2">{score.structure_score ?? "0"}</td>
                <td className="px-2 py-2">{score.relevance_score ?? "0"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
