"use client";

/**
 * Intelligent Task Router panel.
 * Classifies a prompt, recommends a model, optionally executes it.
 */

import { useState } from "react";
import type { FormEvent } from "react";

import { ApiError, classifyPrompt, routePrompt } from "@/lib/api";
import { getActiveOrganizationSlug } from "@/lib/auth";
import type {
  ClassifyResponse,
  RouterPreference,
  RouteResponse,
} from "@/types/api";

export function TaskRouterPanel() {
  const [prompt, setPrompt] = useState(
    "Debug this Python FastAPI endpoint that returns 500 on null user_id.",
  );
  const [preference, setPreference] = useState<RouterPreference>("balanced");
  const [execute, setExecute] = useState(false);
  const [classification, setClassification] = useState<ClassifyResponse | null>(
    null,
  );
  const [route, setRoute] = useState<RouteResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onClassify(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setRoute(null);
    try {
      const data = await classifyPrompt({ prompt });
      setClassification(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Classify failed");
    } finally {
      setLoading(false);
    }
  }

  async function onRoute(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const data = await routePrompt({
        prompt,
        preference,
        execute,
        max_tokens: 256,
        organization_slug: getActiveOrganizationSlug(),
      });
      setRoute(data);
      setClassification({
        task_type: data.task_type,
        confidence: data.confidence,
        matched_signals: data.matched_signals,
        scores: {},
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Route failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="w-full max-w-5xl border border-zinc-200 bg-white p-6 shadow-sm">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
        Intelligent Task Router
      </h2>
      <p className="mt-1 text-sm text-zinc-500">
        Detects task type from the prompt, ranks providers, and optionally
        executes the recommended model. Decisions are audited in PostgreSQL.
      </p>

      <form className="mt-4 space-y-4" onSubmit={onRoute}>
        <label className="block text-sm">
          <span className="text-zinc-600">Prompt</span>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={4}
            className="mt-1 w-full border border-zinc-200 px-3 py-2 text-sm outline-none focus:border-zinc-400"
            required
          />
        </label>

        <div className="flex flex-wrap items-end gap-3 text-sm">
          <label>
            <span className="text-zinc-500">Preference</span>
            <select
              value={preference}
              onChange={(e) =>
                setPreference(e.target.value as RouterPreference)
              }
              className="mt-1 block border border-zinc-200 px-3 py-2"
            >
              <option value="balanced">balanced</option>
              <option value="cost">cost</option>
              <option value="speed">speed</option>
              <option value="quality">quality</option>
            </select>
          </label>

          <label className="flex items-center gap-2 pb-2">
            <input
              type="checkbox"
              checked={execute}
              onChange={(e) => setExecute(e.target.checked)}
            />
            <span className="text-zinc-600">Execute recommended model</span>
          </label>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={(e) => void onClassify(e)}
            disabled={loading}
            className="border border-zinc-200 px-4 py-2 text-sm text-zinc-800 hover:bg-zinc-50 disabled:opacity-50"
          >
            Classify only
          </button>
          <button
            type="submit"
            disabled={loading}
            className="border border-zinc-900 bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-50"
          >
            {loading ? "Routing…" : "Route"}
          </button>
        </div>
      </form>

      {error && (
        <div className="mt-4 border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {classification && (
        <div className="mt-4 border border-zinc-100 bg-zinc-50 p-4 text-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
            Classification
          </p>
          <p className="mt-1 font-medium text-zinc-900">
            {classification.task_type}{" "}
            <span className="text-zinc-500">
              (confidence {classification.confidence})
            </span>
          </p>
          {classification.matched_signals.length > 0 && (
            <p className="mt-2 text-xs text-zinc-500">
              Signals: {classification.matched_signals.slice(0, 6).join(" · ")}
            </p>
          )}
        </div>
      )}

      {route && (
        <div className="mt-4 space-y-4 text-sm">
          <div className="border border-emerald-200 bg-emerald-50 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-emerald-800">
              Recommendation
            </p>
            <p className="mt-1 font-medium text-emerald-950">
              {route.recommended_provider} · {route.recommended_model}
            </p>
            <p className="mt-1 text-emerald-900">{route.rationale}</p>
            <p className="mt-2 font-mono text-xs text-emerald-800">
              decision_id: {route.decision_id}
            </p>
          </div>

          <div className="overflow-x-auto">
            <table className="min-w-full border-collapse text-left text-xs">
              <thead>
                <tr className="border-b border-zinc-200 text-zinc-500">
                  <th className="px-2 py-2">Provider</th>
                  <th className="px-2 py-2">Model</th>
                  <th className="px-2 py-2">Score</th>
                  <th className="px-2 py-2">Available</th>
                  <th className="px-2 py-2">Reason</th>
                </tr>
              </thead>
              <tbody>
                {route.candidates.map((c) => (
                  <tr
                    key={`${c.provider}:${c.model}`}
                    className="border-b border-zinc-100"
                  >
                    <td className="px-2 py-2">{c.provider}</td>
                    <td className="px-2 py-2">{c.model}</td>
                    <td className="px-2 py-2">{c.score}</td>
                    <td className="px-2 py-2">
                      {c.available ? "yes" : "no"}
                    </td>
                    <td className="px-2 py-2 text-zinc-600">{c.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {route.executed && route.completion && (
            <div className="border border-zinc-200 bg-zinc-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
                Execution result
              </p>
              <p className="mt-1 text-xs text-zinc-500">
                status {route.completion.status} · tokens{" "}
                {route.completion.total_tokens ?? "—"} · latency{" "}
                {route.completion.latency_ms != null
                  ? `${route.completion.latency_ms} ms`
                  : "—"}
              </p>
              <p className="mt-2 whitespace-pre-wrap text-zinc-800">
                {route.completion.response ??
                  route.completion.error_message ??
                  "—"}
              </p>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
