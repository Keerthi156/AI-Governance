"use client";

/**
 * Multi-provider playground — defaults to free Groq models.
 * Uses SSE streaming when available (Groq/OpenAI native; others buffered).
 * Supports org-scoped saved prompt templates.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";

import {
  ApiError,
  createCompletionStream,
  createPromptTemplate,
  deletePromptTemplate,
  fetchPromptTemplates,
} from "@/lib/api";
import {
  getAccessToken,
  getActiveOrganizationSlug,
  getStoredUser,
} from "@/lib/auth";
import type { AuthUser, CompletionResponse, PromptTemplate } from "@/types/api";

type Provider = "groq" | "gemini" | "openai" | "claude";

const OPTIONS: Array<{ provider: Provider; model: string; label: string }> = [
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

export function PromptPlayground() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [templateId, setTemplateId] = useState("");
  const [saveName, setSaveName] = useState("");
  const [selected, setSelected] = useState(`${OPTIONS[0].provider}:${OPTIONS[0].model}`);
  const [prompt, setPrompt] = useState(
    "Explain enterprise AI governance in two sentences.",
  );
  const [loading, setLoading] = useState(false);
  const [streamingText, setStreamingText] = useState("");
  const [result, setResult] = useState<CompletionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const canReadTemplates = Boolean(user?.permissions?.includes("templates:read"));
  const canWriteTemplates = Boolean(
    user?.permissions?.includes("templates:write"),
  );

  const current = useMemo(() => {
    const [provider, ...rest] = selected.split(":");
    const model = rest.join(":");
    return { provider: provider as Provider, model };
  }, [selected]);

  const loadTemplates = useCallback(async () => {
    const stored = getStoredUser();
    setUser(stored);
    if (!getAccessToken() || !stored?.permissions?.includes("templates:read")) {
      setTemplates([]);
      return;
    }
    try {
      const rows = await fetchPromptTemplates();
      setTemplates(rows);
    } catch {
      // Non-fatal for playground use when templates endpoint is unavailable.
      setTemplates([]);
    }
  }, []);

  useEffect(() => {
    void loadTemplates();
    const onAuth = () => void loadTemplates();
    window.addEventListener("ai-governance-auth", onAuth);
    window.addEventListener("storage", onAuth);
    return () => {
      window.removeEventListener("ai-governance-auth", onAuth);
      window.removeEventListener("storage", onAuth);
    };
  }, [loadTemplates]);

  function applyTemplate(id: string) {
    setTemplateId(id);
    const tpl = templates.find((t) => t.id === id);
    if (!tpl) return;
    setPrompt(tpl.body);
    setSaveName(tpl.is_system ? "" : tpl.name);
    const match = OPTIONS.find(
      (opt) =>
        opt.provider === tpl.default_provider &&
        (!tpl.default_model || opt.model === tpl.default_model),
    );
    if (match) {
      setSelected(`${match.provider}:${match.model}`);
    } else if (tpl.default_provider && tpl.default_model) {
      setSelected(`${tpl.default_provider}:${tpl.default_model}`);
    }
  }

  async function onSaveTemplate() {
    if (!canWriteTemplates || !prompt.trim() || !saveName.trim()) return;
    setError(null);
    setMessage(null);
    try {
      const created = await createPromptTemplate({
        name: saveName.trim(),
        body: prompt,
        default_provider: current.provider,
        default_model: current.model,
        organization_slug: getActiveOrganizationSlug(),
      });
      setTemplates((prev) =>
        [...prev.filter((t) => t.id !== created.id), created].sort((a, b) =>
          a.name.localeCompare(b.name),
        ),
      );
      setTemplateId(created.id);
      setMessage(`Saved template “${created.name}”`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save template");
    }
  }

  async function onDeleteTemplate() {
    if (!canWriteTemplates || !templateId) return;
    const tpl = templates.find((t) => t.id === templateId);
    if (!tpl || tpl.is_system) return;
    setError(null);
    try {
      await deletePromptTemplate(templateId);
      setTemplates((prev) => prev.filter((t) => t.id !== templateId));
      setTemplateId("");
      setMessage("Template deleted");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to delete template");
    }
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setMessage(null);
    setResult(null);
    setStreamingText("");

    try {
      await createCompletionStream(
        {
          prompt,
          provider: current.provider,
          model: current.model,
          organization_slug: getActiveOrganizationSlug(),
        },
        {
          onToken: (text) => {
            setStreamingText((prev) => prev + text);
          },
          onDone: (data) => {
            setResult(data);
            setStreamingText(data.response ?? "");
          },
          onError: (msg, code) => {
            setError(`${msg}${code ? ` (${code})` : ""}`);
          },
        },
      );
    } catch (err) {
      if (err instanceof ApiError) {
        setError(
          `${err.message}${err.code ? ` (${err.code})` : ""}${
            err.requestId ? ` · request ${err.requestId}` : ""
          }`,
        );
      } else {
        setError(err instanceof Error ? err.message : "Request failed");
      }
    } finally {
      setLoading(false);
    }
  }

  const displayText = result?.response ?? streamingText;
  const selectedTemplate = templates.find((t) => t.id === templateId);

  return (
    <section className="w-full max-w-2xl border border-zinc-200 bg-white p-6 shadow-sm">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
        LLM playground
      </h2>
      <p className="mt-1 text-sm text-zinc-500">
        Streaming responses with optional saved prompt templates.
      </p>

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

      <form onSubmit={onSubmit} className="mt-4 space-y-4">
        {canReadTemplates && templates.length > 0 && (
          <label className="block text-sm">
            <span className="text-zinc-600">Template</span>
            <select
              value={templateId}
              onChange={(e) => applyTemplate(e.target.value)}
              className="mt-1 w-full border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
            >
              <option value="">Custom / blank</option>
              {templates.map((tpl) => (
                <option key={tpl.id} value={tpl.id}>
                  {tpl.name}
                  {tpl.is_system ? " (system)" : ""}
                </option>
              ))}
            </select>
            {selectedTemplate?.description ? (
              <span className="mt-1 block text-xs text-zinc-500">
                {selectedTemplate.description}
              </span>
            ) : null}
          </label>
        )}

        <label className="block text-sm">
          <span className="text-zinc-600">Provider / model</span>
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            className="mt-1 w-full border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-zinc-400"
          >
            {OPTIONS.map((opt) => (
              <option
                key={`${opt.provider}:${opt.model}`}
                value={`${opt.provider}:${opt.model}`}
              >
                {opt.label}
              </option>
            ))}
          </select>
        </label>

        <label className="block text-sm">
          <span className="text-zinc-600">Prompt</span>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={5}
            className="mt-1 w-full border border-zinc-200 px-3 py-2 text-sm outline-none focus:border-zinc-400"
            required
          />
        </label>

        {canWriteTemplates && (
          <div className="flex flex-wrap items-end gap-2">
            <label className="min-w-[12rem] flex-1 text-sm">
              <span className="text-zinc-600">Save as template</span>
              <input
                value={saveName}
                onChange={(e) => setSaveName(e.target.value)}
                placeholder="Template name"
                className="mt-1 w-full border border-zinc-200 px-3 py-2 text-sm"
              />
            </label>
            <button
              type="button"
              onClick={() => void onSaveTemplate()}
              disabled={!saveName.trim() || !prompt.trim()}
              className="border border-zinc-200 px-3 py-2 text-sm text-zinc-800 hover:bg-zinc-50 disabled:opacity-50"
            >
              Save
            </button>
            {selectedTemplate && !selectedTemplate.is_system && (
              <button
                type="button"
                onClick={() => void onDeleteTemplate()}
                className="border border-zinc-200 px-3 py-2 text-sm text-zinc-800 hover:bg-zinc-50"
              >
                Delete
              </button>
            )}
          </div>
        )}

        <button
          type="submit"
          disabled={loading || !prompt.trim()}
          className="border border-zinc-900 bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Streaming…" : "Run completion"}
        </button>
      </form>

      {(loading || result || streamingText) && (
        <div className="mt-4 space-y-3 border border-zinc-100 bg-zinc-50 p-4 text-sm">
          {result && (
            <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <div>
                <dt className="text-zinc-500">Status</dt>
                <dd className="font-medium text-emerald-700">{result.status}</dd>
              </div>
              <div>
                <dt className="text-zinc-500">Tokens</dt>
                <dd className="font-medium text-zinc-900">
                  {result.total_tokens ?? "—"}
                </dd>
              </div>
              <div>
                <dt className="text-zinc-500">Est. cost</dt>
                <dd className="font-medium text-zinc-900">
                  {result.estimated_cost_usd != null
                    ? `$${result.estimated_cost_usd}`
                    : "—"}
                </dd>
              </div>
              <div>
                <dt className="text-zinc-500">Latency</dt>
                <dd className="font-medium text-zinc-900">
                  {result.latency_ms != null ? `${result.latency_ms} ms` : "—"}
                </dd>
              </div>
              <div>
                <dt className="text-zinc-500">Model</dt>
                <dd className="font-medium text-zinc-900">
                  {result.provider} · {result.model}
                </dd>
              </div>
              <div>
                <dt className="text-zinc-500">History ID</dt>
                <dd className="truncate font-mono text-xs text-zinc-700">
                  {result.history_id}
                </dd>
              </div>
            </dl>
          )}

          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
              Response{loading && !result ? " · streaming" : ""}
            </h3>
            <p className="mt-2 whitespace-pre-wrap text-zinc-800">
              {displayText || (loading ? "…" : "")}
            </p>
          </div>
        </div>
      )}
    </section>
  );
}
