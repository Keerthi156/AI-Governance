/**
 * API client foundation.
 *
 * Why this file exists:
 * - Single place for base URL and fetch helpers.
 * - Parses structured backend error envelopes (detail/code/request_id).
 * - Ready to grow into authenticated requests in Phase 3.
 */

import type {
  AnalyticsOverviewResponse,
  ApiErrorBody,
  ApiKey,
  ApiKeyCreateRequest,
  ApiKeyCreated,
  ProviderCredential,
  ProviderCredentialUpsert,
  Webhook,
  WebhookCreateRequest,
  WebhookDeliveryListResponse,
  WebhookUpdateRequest,
  RetentionPurgeResult,
  RetentionSchedulerStatus,
  RetentionSettings,
  RetentionSettingsUpdate,
  ComplianceReport,
  ArenaHistoryResponse,
  ArenaRunRequest,
  ArenaRunResponse,
  AgentDefinition,
  AgentPlanPreviewResponse,
  AgentPlanRunRequest,
  AgentRunRequest,
  AgentRunResponse,
  AuditActionCatalogResponse,
  AuditEventListResponse,
  AuthUser,
  ClassifyRequest,
  ClassifyResponse,
  CompletionRequest,
  CompletionResponse,
  EvaluationResponse,
  EvaluationStrategy,
  HealthResponse,
  HistoryListParams,
  HistoryListResponse,
  HistoryItem,
  LoginRequest,
  MetaResponse,
  PolicyCreateRequest,
  PolicyEvaluateRequest,
  PolicyEvaluateResponse,
  PolicyResponse,
  PolicyUpdateRequest,
  PromptTemplate,
  PromptTemplateCreate,
  Organization,
  OrganizationCreate,
  OrganizationInvite,
  OrganizationInviteCreate,
  OrganizationMember,
  OrganizationMemberAdd,
  ReadyResponse,
  RegisterRequest,
  RagDocumentResponse,
  RagIngestRequest,
  RagQueryRequest,
  RagQueryResponse,
  RoleCatalogResponse,
  RouteRequest,
  RouteResponse,
  StrategyComparisonResponse,
  TokenResponse,
  UpdateUserRequest,
} from "@/types/api";
import {
  getAccessToken,
  getActiveOrganizationSlug,
  getRefreshToken,
  setAuthSession,
  clearAuthSession,
} from "@/lib/auth";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export function getApiBaseUrl(): string {
  return API_BASE_URL;
}

export class ApiError extends Error {
  status: number;
  code: string;
  requestId?: string;
  body?: ApiErrorBody;

  constructor(
    message: string,
    status: number,
    options?: { code?: string; requestId?: string; body?: ApiErrorBody },
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = options?.code ?? "http_error";
    this.requestId = options?.requestId;
    this.body = options?.body;
  }
}

let refreshInFlight: Promise<boolean> | null = null;

async function tryRefreshSession(): Promise<boolean> {
  const refresh = getRefreshToken();
  if (!refresh) return false;
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = (async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refresh }),
        cache: "no-store",
      });
      if (!response.ok) {
        clearAuthSession();
        return false;
      }
      const data = (await response.json()) as TokenResponse;
      setAuthSession(
        data.access_token,
        data.user,
        data.refresh_token ?? refresh,
      );
      return true;
    } catch {
      clearAuthSession();
      return false;
    } finally {
      refreshInFlight = null;
    }
  })();

  return refreshInFlight;
}

async function request<T>(
  path: string,
  init?: RequestInit,
  retried = false,
): Promise<T> {
  const token = getAccessToken();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  const requestId = response.headers.get("X-Request-ID") ?? undefined;

  if (
    response.status === 401 &&
    !retried &&
    !path.startsWith("/auth/login") &&
    !path.startsWith("/auth/register") &&
    !path.startsWith("/auth/refresh")
  ) {
    const refreshed = await tryRefreshSession();
    if (refreshed) {
      return request<T>(path, init, true);
    }
  }

  if (!response.ok) {
    let body: ApiErrorBody | undefined;
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      body = undefined;
    }

    throw new ApiError(
      body?.detail ??
        `API request failed: ${response.status} ${response.statusText}`,
      response.status,
      {
        code: body?.code ?? "http_error",
        requestId: body?.request_id ?? requestId,
        body,
      },
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

/**
 * Readiness may return HTTP 503 with a valid ReadyResponse body when DB is down.
 * Parse JSON on both 200 and 503 so the UI can show database status.
 */
export async function fetchReady(): Promise<ReadyResponse> {
  const response = await fetch(`${API_BASE_URL}/ready`, {
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
  });

  const requestId = response.headers.get("X-Request-ID") ?? undefined;
  let payload: ReadyResponse | undefined;
  try {
    payload = (await response.json()) as ReadyResponse;
  } catch {
    payload = undefined;
  }

  if (!payload) {
    throw new ApiError(
      `API request failed: ${response.status} ${response.statusText}`,
      response.status,
      { requestId },
    );
  }

  return payload;
}

export async function fetchHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

export async function fetchMeta(): Promise<MetaResponse> {
  return request<MetaResponse>("/meta");
}

export async function createCompletion(
  body: CompletionRequest,
): Promise<CompletionResponse> {
  return request<CompletionResponse>("/llm/completions", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function fetchOrganizations(): Promise<Organization[]> {
  return request<Organization[]>("/organizations");
}

export async function createOrganization(
  body: OrganizationCreate,
): Promise<Organization> {
  return request<Organization>("/organizations", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function fetchOrganizationMembers(
  slug: string,
): Promise<OrganizationMember[]> {
  return request<OrganizationMember[]>(
    `/organizations/${encodeURIComponent(slug)}/members`,
  );
}

export async function addOrganizationMember(
  slug: string,
  body: OrganizationMemberAdd,
): Promise<OrganizationMember> {
  return request<OrganizationMember>(
    `/organizations/${encodeURIComponent(slug)}/members`,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
  );
}

export async function removeOrganizationMember(
  slug: string,
  userId: string,
): Promise<void> {
  await request<unknown>(
    `/organizations/${encodeURIComponent(slug)}/members/${encodeURIComponent(userId)}`,
    { method: "DELETE" },
  );
}

export async function fetchOrganizationInvites(
  slug: string,
): Promise<OrganizationInvite[]> {
  return request<OrganizationInvite[]>(
    `/organizations/${encodeURIComponent(slug)}/invites`,
  );
}

export async function createOrganizationInvite(
  slug: string,
  body: OrganizationInviteCreate,
): Promise<OrganizationInvite> {
  return request<OrganizationInvite>(
    `/organizations/${encodeURIComponent(slug)}/invites`,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
  );
}

export async function revokeOrganizationInvite(
  slug: string,
  inviteId: string,
): Promise<void> {
  await request<unknown>(
    `/organizations/${encodeURIComponent(slug)}/invites/${encodeURIComponent(inviteId)}`,
    { method: "DELETE" },
  );
}

export async function acceptOrganizationInvite(body: {
  token: string;
  password?: string | null;
  full_name?: string | null;
  email?: string | null;
}): Promise<TokenResponse> {
  return request<TokenResponse>("/auth/invites/accept", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function logoutAccount(refreshToken?: string | null): Promise<void> {
  await request<unknown>("/auth/logout", {
    method: "POST",
    body: JSON.stringify({ refresh_token: refreshToken ?? null }),
  });
}

export async function fetchApiKeys(): Promise<ApiKey[]> {
  return request<ApiKey[]>("/api-keys");
}

export async function createApiKey(
  body: ApiKeyCreateRequest,
): Promise<ApiKeyCreated> {
  return request<ApiKeyCreated>("/api-keys", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function revokeApiKey(keyId: string): Promise<ApiKey> {
  return request<ApiKey>(`/api-keys/${encodeURIComponent(keyId)}`, {
    method: "DELETE",
  });
}

export async function fetchProviderCredentials(
  organizationSlug = getActiveOrganizationSlug(),
): Promise<ProviderCredential[]> {
  const query = new URLSearchParams({ organization_slug: organizationSlug });
  return request<ProviderCredential[]>(`/credentials?${query}`);
}

export async function upsertProviderCredential(
  provider: string,
  body: ProviderCredentialUpsert,
): Promise<ProviderCredential> {
  return request<ProviderCredential>(
    `/credentials/${encodeURIComponent(provider)}`,
    {
      method: "PUT",
      body: JSON.stringify(body),
    },
  );
}

export async function deleteProviderCredential(
  provider: string,
  organizationSlug = getActiveOrganizationSlug(),
): Promise<ProviderCredential> {
  const query = new URLSearchParams({ organization_slug: organizationSlug });
  return request<ProviderCredential>(
    `/credentials/${encodeURIComponent(provider)}?${query}`,
    { method: "DELETE" },
  );
}

export async function fetchWebhooks(
  organizationSlug = getActiveOrganizationSlug(),
): Promise<Webhook[]> {
  const query = new URLSearchParams({ organization_slug: organizationSlug });
  return request<Webhook[]>(`/webhooks?${query}`);
}

export async function createWebhook(
  body: WebhookCreateRequest,
): Promise<Webhook> {
  return request<Webhook>("/webhooks", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function updateWebhook(
  webhookId: string,
  body: WebhookUpdateRequest,
): Promise<Webhook> {
  return request<Webhook>(`/webhooks/${encodeURIComponent(webhookId)}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function deleteWebhook(webhookId: string): Promise<void> {
  await request<unknown>(`/webhooks/${encodeURIComponent(webhookId)}`, {
    method: "DELETE",
  });
}

export async function testWebhook(webhookId: string): Promise<Webhook> {
  return request<Webhook>(
    `/webhooks/${encodeURIComponent(webhookId)}/test`,
    { method: "POST" },
  );
}

export async function fetchWebhookDeliveries(params?: {
  organizationSlug?: string;
  webhookId?: string;
  limit?: number;
}): Promise<WebhookDeliveryListResponse> {
  const query = new URLSearchParams({
    organization_slug: params?.organizationSlug ?? getActiveOrganizationSlug(),
    limit: String(params?.limit ?? 50),
  });
  if (params?.webhookId) {
    query.set("webhook_id", params.webhookId);
  }
  return request<WebhookDeliveryListResponse>(`/webhooks/deliveries?${query}`);
}

export async function fetchRetentionSettings(
  organizationSlug = getActiveOrganizationSlug(),
): Promise<RetentionSettings> {
  const query = new URLSearchParams({ organization_slug: organizationSlug });
  return request<RetentionSettings>(`/retention?${query}`);
}

export async function updateRetentionSettings(
  body: RetentionSettingsUpdate,
): Promise<RetentionSettings> {
  return request<RetentionSettings>("/retention", {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export async function purgeRetention(
  dryRun: boolean,
  organizationSlug = getActiveOrganizationSlug(),
): Promise<RetentionPurgeResult> {
  return request<RetentionPurgeResult>("/retention/purge", {
    method: "POST",
    body: JSON.stringify({
      organization_slug: organizationSlug,
      dry_run: dryRun,
    }),
  });
}

export async function fetchRetentionScheduler(): Promise<RetentionSchedulerStatus> {
  return request<RetentionSchedulerStatus>("/retention/scheduler");
}

export async function fetchComplianceReport(
  days = 30,
  organizationSlug = getActiveOrganizationSlug(),
): Promise<ComplianceReport> {
  const query = new URLSearchParams({
    days: String(days),
    organization_slug: organizationSlug,
  });
  return request<ComplianceReport>(`/compliance/report?${query}`);
}

export async function downloadComplianceReport(
  days = 30,
  organizationSlug = getActiveOrganizationSlug(),
): Promise<void> {
  const token = getAccessToken();
  const query = new URLSearchParams({
    days: String(days),
    organization_slug: organizationSlug,
  });
  const response = await fetch(
    `${getApiBaseUrl()}/compliance/report/export?${query}`,
    {
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      cache: "no-store",
    },
  );
  if (!response.ok) {
    let body: ApiErrorBody | undefined;
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      body = undefined;
    }
    throw new ApiError(
      body?.detail ??
        `API request failed: ${response.status} ${response.statusText}`,
      response.status,
      {
        code: body?.code ?? "http_error",
        requestId: body?.request_id ?? undefined,
        body,
      },
    );
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `compliance-${organizationSlug}-${days}d.json`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export async function fetchPromptTemplates(
  organizationSlug = getActiveOrganizationSlug(),
): Promise<PromptTemplate[]> {
  const query = new URLSearchParams({ organization_slug: organizationSlug });
  return request<PromptTemplate[]>(`/prompt-templates?${query}`);
}

export async function createPromptTemplate(
  body: PromptTemplateCreate,
): Promise<PromptTemplate> {
  return request<PromptTemplate>("/prompt-templates", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function deletePromptTemplate(templateId: string): Promise<void> {
  await request<unknown>(`/prompt-templates/${templateId}`, {
    method: "DELETE",
  });
}

export type CompletionStreamHandlers = {
  onMeta?: (meta: {
    history_id: string;
    provider: string;
    model: string;
    organization_slug?: string;
  }) => void;
  onToken?: (text: string) => void;
  onDone?: (result: CompletionResponse) => void;
  onError?: (message: string, code?: string) => void;
};

/**
 * Consume SSE from POST /llm/completions/stream.
 * Event payloads: meta | token | done | error.
 */
export async function createCompletionStream(
  body: CompletionRequest,
  handlers: CompletionStreamHandlers,
): Promise<void> {
  const token = getAccessToken();
  const response = await fetch(`${API_BASE_URL}/llm/completions/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
    cache: "no-store",
  });

  if (!response.ok) {
    let errBody: ApiErrorBody | undefined;
    try {
      errBody = (await response.json()) as ApiErrorBody;
    } catch {
      errBody = undefined;
    }
    throw new ApiError(
      errBody?.detail ??
        `API request failed: ${response.status} ${response.statusText}`,
      response.status,
      {
        code: errBody?.code ?? "http_error",
        requestId: errBody?.request_id ?? undefined,
        body: errBody,
      },
    );
  }

  if (!response.body) {
    throw new ApiError("Empty stream body", 502, { code: "empty_stream" });
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const handleDataLine = (raw: string) => {
    const trimmed = raw.trim();
    if (!trimmed || trimmed === "[DONE]") return;
    let event: Record<string, unknown>;
    try {
      event = JSON.parse(trimmed) as Record<string, unknown>;
    } catch {
      return;
    }
    const type = event.type;
    if (type === "meta") {
      handlers.onMeta?.({
        history_id: String(event.history_id ?? ""),
        provider: String(event.provider ?? ""),
        model: String(event.model ?? ""),
        organization_slug:
          event.organization_slug != null
            ? String(event.organization_slug)
            : undefined,
      });
    } else if (type === "token") {
      handlers.onToken?.(String(event.text ?? ""));
    } else if (type === "done") {
      handlers.onDone?.(event as unknown as CompletionResponse);
    } else if (type === "error") {
      handlers.onError?.(
        String(event.message ?? "Stream failed"),
        event.code != null ? String(event.code) : undefined,
      );
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";
    for (const chunk of chunks) {
      for (const line of chunk.split("\n")) {
        if (line.startsWith("data:")) {
          handleDataLine(line.slice(5));
        }
      }
    }
  }
  if (buffer.trim()) {
    for (const line of buffer.split("\n")) {
      if (line.startsWith("data:")) {
        handleDataLine(line.slice(5));
      }
    }
  }
}

export async function createArenaRun(
  body: ArenaRunRequest,
): Promise<ArenaRunResponse> {
  return request<ArenaRunResponse>("/arena/runs", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function fetchHistory(
  params: HistoryListParams = {},
): Promise<HistoryListResponse> {
  const query = new URLSearchParams();
  query.set(
    "organization_slug",
    params.organization_slug?.trim() || getActiveOrganizationSlug(),
  );
  if (params.provider) query.set("provider", params.provider);
  if (params.status) query.set("status", params.status);
  if (params.arena_run_id) query.set("arena_run_id", params.arena_run_id);
  if (params.arena_only) query.set("arena_only", "true");
  if (params.page) query.set("page", String(params.page));
  if (params.page_size) query.set("page_size", String(params.page_size));

  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request<HistoryListResponse>(`/history${suffix}`);
}

export async function fetchHistoryItem(id: string): Promise<HistoryItem> {
  return request<HistoryItem>(`/history/${id}`);
}

export async function fetchArenaHistory(
  arenaRunId: string,
): Promise<ArenaHistoryResponse> {
  return request<ArenaHistoryResponse>(`/history/arena/${arenaRunId}`);
}

export async function evaluateArenaRun(
  arenaRunId: string,
  strategy: EvaluationStrategy = "balanced",
  taskType?: string,
): Promise<EvaluationResponse> {
  return request<EvaluationResponse>("/evaluation/arena", {
    method: "POST",
    body: JSON.stringify({
      arena_run_id: arenaRunId,
      strategy,
      task_type: taskType || null,
    }),
  });
}

export async function compareArenaStrategies(
  arenaRunId: string,
  options?: { taskType?: string; strategies?: EvaluationStrategy[] },
): Promise<StrategyComparisonResponse> {
  return request<StrategyComparisonResponse>("/evaluation/arena/compare", {
    method: "POST",
    body: JSON.stringify({
      arena_run_id: arenaRunId,
      task_type: options?.taskType || null,
      strategies: options?.strategies || null,
    }),
  });
}

export async function listArenaEvaluations(
  arenaRunId: string,
): Promise<EvaluationResponse[]> {
  return request<EvaluationResponse[]>(`/evaluation/arena/${arenaRunId}`);
}

export async function fetchEvaluation(
  evaluationId: string,
): Promise<EvaluationResponse> {
  return request<EvaluationResponse>(`/evaluation/${evaluationId}`);
}

export async function classifyPrompt(
  body: ClassifyRequest,
): Promise<ClassifyResponse> {
  return request<ClassifyResponse>("/router/classify", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function routePrompt(body: RouteRequest): Promise<RouteResponse> {
  return request<RouteResponse>("/router/route", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function fetchAnalyticsOverview(
  days = 7,
  organizationSlug = getActiveOrganizationSlug(),
): Promise<AnalyticsOverviewResponse> {
  const query = new URLSearchParams({
    days: String(days),
    organization_slug: organizationSlug,
  });
  return request<AnalyticsOverviewResponse>(`/analytics/overview?${query}`);
}

export async function registerAccount(
  body: RegisterRequest,
): Promise<TokenResponse> {
  return request<TokenResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function loginAccount(body: LoginRequest): Promise<TokenResponse> {
  return request<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function fetchCurrentUser(): Promise<AuthUser> {
  return request<AuthUser>("/auth/me");
}

export async function fetchAdminUsers(): Promise<AuthUser[]> {
  return request<AuthUser[]>("/admin/users");
}

export async function updateAdminUser(
  userId: string,
  body: UpdateUserRequest,
): Promise<AuthUser> {
  return request<AuthUser>(`/admin/users/${userId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function fetchRoleCatalog(): Promise<RoleCatalogResponse> {
  return request<RoleCatalogResponse>("/admin/roles");
}

export async function fetchPolicies(
  organizationSlug = getActiveOrganizationSlug(),
  activeOnly = false,
): Promise<PolicyResponse[]> {
  const query = new URLSearchParams({
    organization_slug: organizationSlug,
    active_only: String(activeOnly),
  });
  return request<PolicyResponse[]>(`/governance/policies?${query}`);
}

export async function createPolicy(
  body: PolicyCreateRequest,
): Promise<PolicyResponse> {
  return request<PolicyResponse>("/governance/policies", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function updatePolicy(
  policyId: string,
  body: PolicyUpdateRequest,
): Promise<PolicyResponse> {
  return request<PolicyResponse>(`/governance/policies/${policyId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function deletePolicy(policyId: string): Promise<void> {
  await request<unknown>(`/governance/policies/${policyId}`, {
    method: "DELETE",
  });
}

export async function evaluatePolicy(
  body: PolicyEvaluateRequest,
): Promise<PolicyEvaluateResponse> {
  return request<PolicyEvaluateResponse>("/governance/evaluate", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function fetchAuditEvents(params?: {
  action?: string;
  status?: string;
  page?: number;
  page_size?: number;
}): Promise<AuditEventListResponse> {
  const query = new URLSearchParams();
  if (params?.action) query.set("action", params.action);
  if (params?.status) query.set("status", params.status);
  if (params?.page) query.set("page", String(params.page));
  if (params?.page_size) query.set("page_size", String(params.page_size));
  const suffix = query.toString() ? `?${query}` : "";
  return request<AuditEventListResponse>(`/audit/events${suffix}`);
}

export async function downloadAuditExport(params?: {
  format?: "csv" | "json";
  action?: string;
  status?: string;
}): Promise<void> {
  const format = params?.format ?? "csv";
  const query = new URLSearchParams({ format });
  if (params?.action) query.set("action", params.action);
  if (params?.status) query.set("status", params.status);

  const token = getAccessToken();
  const response = await fetch(`${API_BASE_URL}/audit/events/export?${query}`, {
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    let body: ApiErrorBody | undefined;
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      body = undefined;
    }
    throw new ApiError(
      body?.detail ??
        `API request failed: ${response.status} ${response.statusText}`,
      response.status,
      {
        code: body?.code ?? "http_error",
        requestId: body?.request_id ?? undefined,
        body,
      },
    );
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = format === "json" ? "audit-events.json" : "audit-events.csv";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export async function fetchAuditActions(): Promise<AuditActionCatalogResponse> {
  return request<AuditActionCatalogResponse>("/audit/actions");
}

export async function fetchRagDocuments(
  organizationSlug = getActiveOrganizationSlug(),
): Promise<RagDocumentResponse[]> {
  const query = new URLSearchParams({ organization_slug: organizationSlug });
  return request<RagDocumentResponse[]>(`/rag/documents?${query}`);
}

export async function ingestRagDocument(
  body: RagIngestRequest,
): Promise<RagDocumentResponse> {
  return request<RagDocumentResponse>("/rag/documents", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function ingestRagUpload(
  file: File,
  options?: { title?: string; organization_slug?: string },
): Promise<RagDocumentResponse> {
  const form = new FormData();
  form.append("file", file);
  if (options?.title?.trim()) {
    form.append("title", options.title.trim());
  }
  form.append(
    "organization_slug",
    options?.organization_slug?.trim() || getActiveOrganizationSlug(),
  );

  const token = getAccessToken();
  const response = await fetch(`${API_BASE_URL}/rag/documents/upload`, {
    method: "POST",
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: form,
    cache: "no-store",
  });

  const requestId = response.headers.get("X-Request-ID") ?? undefined;
  if (!response.ok) {
    let body: ApiErrorBody | undefined;
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      body = undefined;
    }
    throw new ApiError(
      body?.detail ??
        `API request failed: ${response.status} ${response.statusText}`,
      response.status,
      {
        code: body?.code ?? "http_error",
        requestId: body?.request_id ?? requestId,
        body,
      },
    );
  }
  return response.json() as Promise<RagDocumentResponse>;
}

export async function deleteRagDocument(documentId: string): Promise<void> {
  await request<unknown>(`/rag/documents/${documentId}`, { method: "DELETE" });
}

export async function queryRag(
  body: RagQueryRequest,
): Promise<RagQueryResponse> {
  return request<RagQueryResponse>("/rag/query", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function fetchAgentDefinitions(
  organizationSlug = getActiveOrganizationSlug(),
): Promise<AgentDefinition[]> {
  const query = new URLSearchParams({ organization_slug: organizationSlug });
  return request<AgentDefinition[]>(`/agents/definitions?${query}`);
}

export async function runAgent(
  body: AgentRunRequest,
): Promise<AgentRunResponse> {
  return request<AgentRunResponse>("/agents/runs", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function previewAgentPlan(
  body: AgentPlanRunRequest,
): Promise<AgentPlanPreviewResponse> {
  return request<AgentPlanPreviewResponse>("/agents/plan", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function runPlannedAgent(
  body: AgentPlanRunRequest,
): Promise<AgentRunResponse> {
  return request<AgentRunResponse>("/agents/runs/plan", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function fetchAgentRuns(
  organizationSlug = getActiveOrganizationSlug(),
  limit = 20,
): Promise<AgentRunResponse[]> {
  const query = new URLSearchParams({
    organization_slug: organizationSlug,
    limit: String(limit),
  });
  return request<AgentRunResponse[]>(`/agents/runs?${query}`);
}
