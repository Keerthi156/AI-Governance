"use client";

/**
 * Multi-LLM Arena — side-by-side comparison UI.
 * Defaults to free-tier providers: Groq + Gemini.
 */

import { useMemo, useState } from "react";
import type { FormEvent } from "react";

import { ApiError, createArenaRun } from "@/lib/api";
import { getActiveOrganizationSlug } from "@/lib/auth";
import type { ArenaParticipant, ArenaRunResponse } from "@/types/api";

type Provider = ArenaParticipant["provider"];

const CATALOG: Array<{ provider: Provider; model: string; label: string }> = [
  {
    provider: "groq",
    model: "llama-3.1-8b-instant",
    label: "Groq · Llama 3.1 8B (free)",
  },
  {
    provider: "groq",
    model: "llama-3.3-70b-versatile",
    label: "Groq · Llama 3.3 70B (free)",
  },
  {
    provider: "gemini",
    model: "gemini-2.0-flash",
    label: "Gemini · 2.0 Flash (free)",
  },
  {
    provider: "gemini",
    model: "gemini-1.5-flash",
    label: "Gemini · 1.5 Flash (free)",
  },
  { provider: "openai", model: "gpt-4o-mini", label: "OpenAI · gpt-4o-mini" },
  {
    provider: "claude",
    model: "claude-3-5-haiku-latest",
    label: "Claude · 3.5 Haiku",
  },
];

function participantKey(p: ArenaParticipant): string {
  return `${p.provider}:${p.model ?? ""}`;
}

export function ArenaPanel() {
  const [prompt, setPrompt] = useState(
    "Compare rule-based AI governance vs risk-based AI governance in 4 bullets.",
  );
  const [selected, setSelected] = useState<string[]>([
    participantKey({ provider: "groq", model: "llama-3.1-8b-instant" }),
    participantKey({ provider: "gemini", model: "gemini-2.0-flash" }),
  ]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ArenaRunResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const participants = useMemo(() => {
    return CATALOG.filter((item) =>
      selected.includes(participantKey(item)),
    ).map((item) => ({ provider: item.provider, model: item.model }));
  }, [selected]);

  function toggle(key: string) {
    setSelected((prev) => {
      if (prev.includes(key)) {
        return prev.filter((k) => k !== key);
      }
      if (prev.length >= 6) return prev;
      return [...prev, key];
    });
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (participants.length < 2) {
      setError("Select at least 2 models to compare.");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const data = await createArenaRun({
        prompt,
        participants,
        organization_slug: getActiveOrganizationSlug(),
      });
      setResult(data);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(
          `${err.message}${err.code ? ` (${err.code})` : ""}${
            err.requestId ? ` · request ${err.requestId}` : ""
          }`,
        );
      } else {
        setError(err instanceof Error ? err.message : "Arena run failed");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="w-full max-w-5xl border border-zinc-200 bg-white p-6 shadow-sm">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
        Arena Mode
      </h2>
      <p className="mt-1 text-sm text-zinc-500">
        Defaults to free providers (Groq + Gemini). Results share an{" "}
        <code className="text-xs">arena_run_id</code> in prompt history.
      </p>

      <form onSubmit={onSubmit} className="mt-4 space-y-4">
        <fieldset>
          <legend className="text-sm text-zinc-600">Participants</legend>
          <div className="mt-2 flex flex-wrap gap-2">
            {CATALOG.map((item) => {
              const key = participantKey(item);
              const active = selected.includes(key);
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => toggle(key)}
                  className={
                    active
                      ? "border border-zinc-900 bg-zinc-900 px-3 py-1.5 text-xs text-white"
                      : "border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 hover:bg-zinc-50"
                  }
                >
                  {item.label}
                </button>
              );
            })}
          </div>
        </fieldset>

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

        <button
          type="submit"
          disabled={loading || participants.length < 2}
          className="border border-zinc-900 bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Running arena…" : "Compare models"}
        </button>
      </form>

      {error && (
        <div className="mt-4 border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {result && (
        <div className="mt-6 space-y-4">
          <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <div>
              <dt className="text-zinc-500">Run ID</dt>
              <dd className="truncate font-mono text-xs text-zinc-800">
                {result.arena_run_id}
              </dd>
            </div>
            <div>
              <dt className="text-zinc-500">Success</dt>
              <dd className="font-medium text-emerald-700">
                {result.success_count}
              </dd>
            </div>
            <div>
              <dt className="text-zinc-500">Errors</dt>
              <dd className="font-medium text-amber-700">{result.error_count}</dd>
            </div>
            <div>
              <dt className="text-zinc-500">Total est. cost</dt>
              <dd className="font-medium text-zinc-900">
                {result.total_estimated_cost_usd != null
                  ? `$${result.total_estimated_cost_usd}`
                  : "—"}
              </dd>
            </div>
          </dl>

          <div className="grid gap-4 md:grid-cols-2">
            {result.results.map((item) => (
              <article
                key={item.history_id}
                className="border border-zinc-200 bg-zinc-50 p-4 text-sm"
              >
                <header className="flex items-start justify-between gap-2">
                  <div>
                    <p className="font-medium text-zinc-900">
                      {item.provider} · {item.model}
                    </p>
                    <p className="mt-1 text-xs text-zinc-500">
                      tokens {item.total_tokens ?? "—"} · latency{" "}
                      {item.latency_ms != null ? `${item.latency_ms} ms` : "—"}{" "}
                      · cost{" "}
                      {item.estimated_cost_usd != null
                        ? `$${item.estimated_cost_usd}`
                        : "—"}
                    </p>
                  </div>
                  <span
                    className={
                      item.status === "success"
                        ? "text-xs font-medium text-emerald-700"
                        : "text-xs font-medium text-amber-700"
                    }
                  >
                    {item.status}
                  </span>
                </header>

                {item.status === "success" ? (
                  <p className="mt-3 whitespace-pre-wrap text-zinc-800">
                    {item.response}
                  </p>
                ) : (
                  <p className="mt-3 text-amber-800">
                    {item.error_message ?? "Participant failed"}
                  </p>
                )}
              </article>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
