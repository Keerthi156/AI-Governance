"use client";

/**
 * Enterprise RAG panel — ingest documents and ask grounded questions.
 */

import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";

import {
  ApiError,
  deleteRagDocument,
  fetchRagDocuments,
  ingestRagDocument,
  ingestRagUpload,
  queryRag,
} from "@/lib/api";
import {
  getAccessToken,
  getActiveOrganizationSlug,
  getStoredUser,
} from "@/lib/auth";
import type {
  AuthUser,
  RagDocumentResponse,
  RagQueryResponse,
} from "@/types/api";

const SAMPLE_DOC = `AI_GOVERNANCE Platform Policy
Effective date: 2026-07-20

1. Approved providers for production workloads are Groq and Gemini.
2. OpenAI and Claude may be used only with admin approval.
3. Prompts must not include secrets, SSNs, or customer payment data.
4. Maximum completion tokens for playground use is 512 unless overridden by policy.
5. All LLM calls are logged in prompt history and audit events for compliance review.
6. Knowledge answers must cite retrieved source chunks when available.`;

export function RagPanel() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [docs, setDocs] = useState<RagDocumentResponse[]>([]);
  const [title, setTitle] = useState("Platform policy handbook");
  const [content, setContent] = useState(SAMPLE_DOC);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [question, setQuestion] = useState(
    "Which providers are approved for production?",
  );
  const [result, setResult] = useState<RagQueryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const canRead = Boolean(user?.permissions?.includes("rag:read"));
  const canWrite = Boolean(user?.permissions?.includes("rag:write"));
  const canQuery = Boolean(user?.permissions?.includes("rag:query"));

  const load = useCallback(async () => {
    const stored = getStoredUser();
    setUser(stored);
    if (!getAccessToken() || !stored?.permissions?.includes("rag:read")) {
      setDocs([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setDocs(await fetchRagDocuments());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, []);

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

  async function onIngest(event: FormEvent) {
    event.preventDefault();
    if (!canWrite) return;
    setError(null);
    setMessage(null);
    setLoading(true);
    try {
      const created = await ingestRagDocument({
        title,
        content,
        source: "manual",
        organization_slug: getActiveOrganizationSlug(),
      });
      setDocs((prev) => [created, ...prev]);
      setMessage(
        `Ingested “${created.title}” (${created.chunk_count} chunks via ${created.embedding_model})`,
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Ingest failed");
    } finally {
      setLoading(false);
    }
  }

  async function onUpload(event: FormEvent) {
    event.preventDefault();
    if (!canWrite || !uploadFile) return;
    setError(null);
    setMessage(null);
    setLoading(true);
    try {
      const created = await ingestRagUpload(uploadFile, {
        title: title.trim() || undefined,
        organization_slug: getActiveOrganizationSlug(),
      });
      setDocs((prev) => [created, ...prev]);
      setMessage(
        `Uploaded “${created.title}” (${created.chunk_count} chunks via ${created.embedding_model})`,
      );
      setUploadFile(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed");
    } finally {
      setLoading(false);
    }
  }

  async function onDelete(id: string) {
    if (!canWrite) return;
    setError(null);
    try {
      await deleteRagDocument(id);
      setDocs((prev) => prev.filter((d) => d.id !== id));
      setMessage("Document deleted");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Delete failed");
    }
  }

  async function onQuery(event: FormEvent) {
    event.preventDefault();
    if (!canQuery) return;
    setError(null);
    setLoading(true);
    try {
      setResult(
        await queryRag({
          question,
          top_k: 4,
          provider: "groq",
          organization_slug: getActiveOrganizationSlug(),
          max_tokens: 256,
        }),
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Query failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="w-full max-w-5xl border border-zinc-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Enterprise RAG
          </h2>
          <p className="mt-1 text-sm text-zinc-500">
            Ingest org knowledge (paste or upload .txt / .md / .pdf / .docx), retrieve
            relevant chunks, and generate grounded answers with citations.
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
          Sign in to ingest documents and run RAG queries.
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

      {canWrite && (
        <form className="mt-6 space-y-3" onSubmit={onIngest}>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
            Ingest document (paste)
          </h3>
          <label className="block text-sm">
            <span className="text-zinc-600">Title</span>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="mt-1 w-full border border-zinc-200 px-3 py-2 text-sm"
              required
            />
          </label>
          <label className="block text-sm">
            <span className="text-zinc-600">Content</span>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              rows={8}
              className="mt-1 w-full border border-zinc-200 px-3 py-2 text-sm"
              required
            />
          </label>
          <button
            type="submit"
            disabled={loading}
            className="bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-50"
          >
            {loading ? "Working…" : "Ingest"}
          </button>
        </form>
      )}

      {canWrite && (
        <form className="mt-6 space-y-3" onSubmit={onUpload}>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
            Upload file
          </h3>
          <p className="text-xs text-zinc-500">
            Accepted: .txt, .md, .pdf, .docx · max 2 MiB · optional title override above
          </p>
          <label className="block text-sm">
            <span className="text-zinc-600">File</span>
            <input
              type="file"
              accept=".txt,.md,.markdown,.pdf,.docx,text/plain,text/markdown,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)}
              className="mt-1 block w-full text-sm text-zinc-700"
              required
            />
          </label>
          <button
            type="submit"
            disabled={loading || !uploadFile}
            className="border border-zinc-200 px-4 py-2 text-sm font-medium text-zinc-800 hover:bg-zinc-50 disabled:opacity-50"
          >
            {loading ? "Uploading…" : "Upload & ingest"}
          </button>
        </form>
      )}

      {canRead && (
        <div className="mt-6">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
            Documents ({docs.length})
          </h3>
          {loading && docs.length === 0 && (
            <p className="mt-2 text-sm text-zinc-600">Loading…</p>
          )}
          <ul className="mt-3 space-y-2">
            {docs.map((doc) => (
              <li
                key={doc.id}
                className="flex flex-wrap items-start justify-between gap-2 border border-zinc-100 bg-zinc-50 px-3 py-2 text-sm"
              >
                <div>
                  <p className="font-medium text-zinc-900">{doc.title}</p>
                  <p className="text-xs text-zinc-500">
                    {doc.chunk_count} chunks · {doc.embedding_model}
                  </p>
                  <p className="mt-1 text-xs text-zinc-600">{doc.content_preview}</p>
                </div>
                {canWrite && (
                  <button
                    type="button"
                    onClick={() => void onDelete(doc.id)}
                    className="border border-zinc-200 px-2 py-1 text-xs hover:bg-white"
                  >
                    Delete
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {canQuery && (
        <form className="mt-6 space-y-3" onSubmit={onQuery}>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
            Ask the knowledge base
          </h3>
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            rows={3}
            className="w-full border border-zinc-200 px-3 py-2 text-sm"
            required
          />
          <button
            type="submit"
            disabled={loading}
            className="border border-zinc-200 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50"
          >
            {loading ? "Retrieving…" : "Query"}
          </button>

          {result && (
            <div className="border border-zinc-100 bg-zinc-50 p-4 text-sm">
              <p className="text-xs uppercase tracking-wide text-zinc-500">
                Answer · {result.provider}/{result.model} · {result.status}
              </p>
              <p className="mt-2 whitespace-pre-wrap text-zinc-900">
                {result.answer}
              </p>
              {result.sources.length > 0 && (
                <div className="mt-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
                    Sources
                  </p>
                  <ul className="mt-2 space-y-2">
                    {result.sources.map((src, idx) => (
                      <li key={src.chunk_id} className="text-xs text-zinc-600">
                        <span className="font-medium text-zinc-800">
                          [{idx + 1}] {src.document_title}
                        </span>{" "}
                        (score {src.score})
                        <p className="mt-1 line-clamp-3">{src.content}</p>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </form>
      )}
    </section>
  );
}
