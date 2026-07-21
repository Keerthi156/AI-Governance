"use client";

/**
 * Prompt history browser — list, filter, and inspect past LLM / Arena runs.
 */

import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  fetchArenaHistory,
  fetchHistory,
  fetchHistoryItem,
} from "@/lib/api";
import type {
  ArenaHistoryResponse,
  HistoryItem,
  HistoryListResponse,
} from "@/types/api";

function truncate(text: string, max = 120): string {
  if (text.length <= max) return text;
  return `${text.slice(0, max)}…`;
}

export function PromptHistoryPanel() {
  const [provider, setProvider] = useState("");
  const [status, setStatus] = useState("");
  const [arenaOnly, setArenaOnly] = useState(false);
  const [page, setPage] = useState(1);
  const [list, setList] = useState<HistoryListResponse | null>(null);
  const [selected, setSelected] = useState<HistoryItem | null>(null);
  const [arenaDetail, setArenaDetail] = useState<ArenaHistoryResponse | null>(
    null,
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchHistory({
        provider: provider || undefined,
        status: (status as "success" | "error" | "pending") || undefined,
        arena_only: arenaOnly || undefined,
        page,
        page_size: 10,
      });
      setList(data);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Failed to load history");
      }
    } finally {
      setLoading(false);
    }
  }, [provider, status, arenaOnly, page]);

  useEffect(() => {
    void load();
    const onOrg = () => {
      setPage(1);
      void load();
    };
    window.addEventListener("ai-governance-auth", onOrg);
    window.addEventListener("ai-governance-org", onOrg);
    window.addEventListener("storage", onOrg);
    return () => {
      window.removeEventListener("ai-governance-auth", onOrg);
      window.removeEventListener("ai-governance-org", onOrg);
      window.removeEventListener("storage", onOrg);
    };
  }, [load]);

  async function openItem(item: HistoryItem) {
    setError(null);
    setArenaDetail(null);
    try {
      const full = await fetchHistoryItem(item.id);
      setSelected(full);
      if (full.arena_run_id) {
        const arena = await fetchArenaHistory(full.arena_run_id);
        setArenaDetail(arena);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load item");
    }
  }

  return (
    <section className="w-full max-w-5xl border border-zinc-200 bg-white p-6 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Prompt history
          </h2>
          <p className="mt-1 text-sm text-zinc-500">
            Browse past completions and Arena runs with filters.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          className="shrink-0 border border-zinc-200 px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-50"
        >
          Refresh
        </button>
      </div>

      <div className="mt-4 flex flex-wrap items-end gap-3 text-sm">
        <label>
          <span className="text-zinc-500">Provider</span>
          <select
            value={provider}
            onChange={(e) => {
              setPage(1);
              setProvider(e.target.value);
            }}
            className="mt-1 block border border-zinc-200 px-2 py-1.5"
          >
            <option value="">All</option>
            <option value="groq">groq</option>
            <option value="gemini">gemini</option>
            <option value="openai">openai</option>
            <option value="claude">claude</option>
          </select>
        </label>

        <label>
          <span className="text-zinc-500">Status</span>
          <select
            value={status}
            onChange={(e) => {
              setPage(1);
              setStatus(e.target.value);
            }}
            className="mt-1 block border border-zinc-200 px-2 py-1.5"
          >
            <option value="">All</option>
            <option value="success">success</option>
            <option value="error">error</option>
            <option value="pending">pending</option>
          </select>
        </label>

        <label className="flex items-center gap-2 pb-1.5">
          <input
            type="checkbox"
            checked={arenaOnly}
            onChange={(e) => {
              setPage(1);
              setArenaOnly(e.target.checked);
            }}
          />
          <span className="text-zinc-600">Arena only</span>
        </label>
      </div>

      {error && (
        <div className="mt-4 border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {loading && !list && (
        <p className="mt-4 text-sm text-zinc-600">Loading history…</p>
      )}

      {list && (
        <div className="mt-4 space-y-3">
          <p className="text-xs text-zinc-500">
            {list.total} total · page {list.page} of {list.pages || 1}
          </p>

          <ul className="divide-y divide-zinc-100 border border-zinc-100">
            {list.items.length === 0 && (
              <li className="p-4 text-sm text-zinc-500">No history yet.</li>
            )}
            {list.items.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => void openItem(item)}
                  className="flex w-full flex-col gap-1 px-4 py-3 text-left hover:bg-zinc-50"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                    <span className="font-medium text-zinc-900">
                      {item.provider} · {item.model}
                    </span>
                    <span
                      className={
                        item.status === "success"
                          ? "text-xs text-emerald-700"
                          : "text-xs text-amber-700"
                      }
                    >
                      {item.status}
                      {item.arena_run_id ? " · arena" : ""}
                    </span>
                  </div>
                  <p className="text-xs text-zinc-500">
                    {new Date(item.created_at).toLocaleString()} · tokens{" "}
                    {item.total_tokens ?? "—"} · cost{" "}
                    {item.estimated_cost_usd != null
                      ? `$${item.estimated_cost_usd}`
                      : "—"}
                  </p>
                  <p className="text-sm text-zinc-700">
                    {truncate(item.prompt)}
                  </p>
                </button>
              </li>
            ))}
          </ul>

          <div className="flex gap-2">
            <button
              type="button"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="border border-zinc-200 px-3 py-1.5 text-xs disabled:opacity-40"
            >
              Previous
            </button>
            <button
              type="button"
              disabled={!list.pages || page >= list.pages}
              onClick={() => setPage((p) => p + 1)}
              className="border border-zinc-200 px-3 py-1.5 text-xs disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      )}

      {selected && (
        <div className="mt-6 border border-zinc-200 bg-zinc-50 p-4 text-sm">
          <div className="flex items-start justify-between gap-3">
            <h3 className="font-medium text-zinc-900">
              Detail · {selected.provider} · {selected.model}
            </h3>
            <button
              type="button"
              onClick={() => {
                setSelected(null);
                setArenaDetail(null);
              }}
              className="text-xs text-zinc-500 hover:text-zinc-800"
            >
              Close
            </button>
          </div>
          <dl className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
            <div>
              <dt className="text-zinc-500">Status</dt>
              <dd>{selected.status}</dd>
            </div>
            <div>
              <dt className="text-zinc-500">Tokens</dt>
              <dd>{selected.total_tokens ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-zinc-500">Cost</dt>
              <dd>
                {selected.estimated_cost_usd != null
                  ? `$${selected.estimated_cost_usd}`
                  : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-zinc-500">Latency</dt>
              <dd>
                {selected.latency_ms != null
                  ? `${selected.latency_ms} ms`
                  : "—"}
              </dd>
            </div>
          </dl>
          <div className="mt-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
              Prompt
            </p>
            <p className="mt-1 whitespace-pre-wrap text-zinc-800">
              {selected.prompt}
            </p>
          </div>
          <div className="mt-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
              Response
            </p>
            <p className="mt-1 whitespace-pre-wrap text-zinc-800">
              {selected.response ?? selected.error_message ?? "—"}
            </p>
          </div>

          {arenaDetail && (
            <div className="mt-4 border-t border-zinc-200 pt-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
                Arena run · {arenaDetail.arena_run_id}
              </p>
              <p className="mt-1 text-xs text-zinc-500">
                {arenaDetail.success_count} success · {arenaDetail.error_count}{" "}
                error · total cost{" "}
                {arenaDetail.total_estimated_cost_usd != null
                  ? `$${arenaDetail.total_estimated_cost_usd}`
                  : "—"}
              </p>
              <ul className="mt-2 space-y-2">
                {arenaDetail.items.map((peer) => (
                  <li
                    key={peer.id}
                    className="border border-zinc-200 bg-white px-3 py-2 text-xs"
                  >
                    <span className="font-medium">
                      {peer.provider} · {peer.model}
                    </span>{" "}
                    · {peer.status}
                    {peer.total_tokens != null
                      ? ` · ${peer.total_tokens} tokens`
                      : ""}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
