"use client";

/**
 * Platform status panel — health, readiness (DB), and metadata.
 */

import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  fetchHealth,
  fetchMeta,
  fetchReady,
  getApiBaseUrl,
} from "@/lib/api";
import type { HealthResponse, MetaResponse, ReadyResponse } from "@/types/api";

type PanelState =
  | { kind: "loading" }
  | {
      kind: "ok";
      health: HealthResponse;
      meta: MetaResponse;
      ready: ReadyResponse;
    }
  | { kind: "error"; message: string; code?: string; requestId?: string };

export function BackendStatus() {
  const [state, setState] = useState<PanelState>({ kind: "loading" });

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const [health, meta, ready] = await Promise.all([
        fetchHealth(),
        fetchMeta(),
        fetchReady(),
      ]);
      setState({ kind: "ok", health, meta, ready });
    } catch (error) {
      if (error instanceof ApiError) {
        setState({
          kind: "error",
          message: error.message,
          code: error.code,
          requestId: error.requestId,
        });
        return;
      }
      setState({
        kind: "error",
        message:
          error instanceof Error ? error.message : "Unable to reach backend",
      });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section className="w-full max-w-2xl border border-zinc-200 bg-white p-6 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Platform status
          </h2>
          <p className="mt-1 text-xs text-zinc-400">{getApiBaseUrl()}</p>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          className="shrink-0 border border-zinc-200 px-3 py-1.5 text-xs font-medium text-zinc-700 transition hover:bg-zinc-50"
        >
          Refresh
        </button>
      </div>

      {state.kind === "loading" && (
        <p className="mt-4 text-sm text-zinc-600">
          Checking API health, readiness & meta…
        </p>
      )}

      {state.kind === "ok" && (
        <div className="mt-4 space-y-6">
          <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-zinc-500">API</dt>
              <dd className="font-medium text-emerald-700">{state.health.status}</dd>
            </div>
            <div>
              <dt className="text-zinc-500">Database</dt>
              <dd
                className={
                  state.ready.database.status === "ok"
                    ? "font-medium text-emerald-700"
                    : "font-medium text-amber-700"
                }
              >
                {state.ready.database.status}
              </dd>
            </div>
            <div>
              <dt className="text-zinc-500">Ready</dt>
              <dd
                className={
                  state.ready.status === "ok"
                    ? "font-medium text-emerald-700"
                    : "font-medium text-amber-700"
                }
              >
                {state.ready.status}
              </dd>
            </div>
            <div>
              <dt className="text-zinc-500">Service</dt>
              <dd className="font-medium text-zinc-900">{state.meta.name}</dd>
            </div>
            <div>
              <dt className="text-zinc-500">Version</dt>
              <dd className="font-medium text-zinc-900">{state.meta.version}</dd>
            </div>
            <div>
              <dt className="text-zinc-500">Environment</dt>
              <dd className="font-medium text-zinc-900">{state.meta.environment}</dd>
            </div>
          </dl>

          {state.ready.database.status !== "ok" && (
            <p className="text-sm text-amber-800">
              Database detail: {state.ready.database.detail}. Run the Postgres
              bootstrap script and <code className="text-xs">alembic upgrade head</code>.
            </p>
          )}

          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
              Enabled features
            </h3>
            <ul className="mt-2 flex flex-wrap gap-2">
              {state.meta.features.map((feature) => (
                <li
                  key={feature}
                  className="border border-zinc-200 bg-zinc-50 px-2 py-1 text-xs text-zinc-700"
                >
                  {feature}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {state.kind === "error" && (
        <div className="mt-4 text-sm">
          <p className="font-medium text-red-700">Unreachable</p>
          <p className="mt-1 text-zinc-600">{state.message}</p>
          {(state.code || state.requestId) && (
            <dl className="mt-3 grid grid-cols-2 gap-2 text-xs text-zinc-500">
              {state.code && (
                <div>
                  <dt>Code</dt>
                  <dd className="font-mono text-zinc-800">{state.code}</dd>
                </div>
              )}
              {state.requestId && (
                <div>
                  <dt>Request ID</dt>
                  <dd className="break-all font-mono text-zinc-800">
                    {state.requestId}
                  </dd>
                </div>
              )}
            </dl>
          )}
        </div>
      )}
    </section>
  );
}
