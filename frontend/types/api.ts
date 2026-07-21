/**
 * Shared TypeScript types for API contracts.
 * Keep frontend types aligned with backend Pydantic schemas.
 */

export interface HealthResponse {
  status: string;
  service: string;
  environment: string;
  timestamp: string;
}

export interface DatabaseStatus {
  status: string;
  detail: string;
}

export interface ReadyResponse {
  status: string;
  service: string;
  environment: string;
  timestamp: string;
  database: DatabaseStatus;
}

export interface MetaResponse {
  name: string;
  version: string;
  environment: string;
  api_version: string;
  docs_url: string;
  health_url: string;
  features: string[];
}

/** Matches backend ErrorResponse schema. */
export interface ApiErrorBody {
  detail: string;
  code: string;
  request_id?: string | null;
  errors?: Array<Record<string, unknown>> | null;
}

export interface CompletionRequest {
  prompt: string;
  provider?: "groq" | "gemini" | "openai" | "claude";
  model?: string;
  organization_slug?: string;
  temperature?: number;
  max_tokens?: number;
}

export interface PromptTemplate {
  id: string;
  organization_id: string;
  organization_slug: string;
  name: string;
  description: string | null;
  body: string;
  default_provider: string;
  default_model: string | null;
  is_system: boolean;
  created_at: string;
}

export interface PromptTemplateCreate {
  name: string;
  body: string;
  description?: string | null;
  default_provider?: string;
  default_model?: string | null;
  organization_slug?: string;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  created_at: string;
}

export interface OrganizationCreate {
  name: string;
  slug: string;
  description?: string | null;
}

export interface OrganizationMember {
  id: string;
  user_id: string;
  email: string;
  full_name: string | null;
  membership_role: string;
  organization_id: string;
  organization_slug: string;
  created_at: string;
}

export interface OrganizationMemberAdd {
  email: string;
  role?: string;
}

export interface OrganizationInvite {
  id: string;
  organization_id: string;
  organization_slug: string;
  email: string | null;
  role: string;
  token_hint: string;
  expires_at: string;
  accepted_at: string | null;
  revoked_at: string | null;
  created_at: string;
  token?: string | null;
}

export interface OrganizationInviteCreate {
  email?: string | null;
  role?: string;
  expires_in_hours?: number;
}

export interface ApiKey {
  id: string;
  name: string;
  key_prefix: string;
  role: string;
  organization_id: string;
  organization_slug: string;
  user_id: string;
  last_used_at: string | null;
  expires_at: string | null;
  revoked_at: string | null;
  notes: string | null;
  created_at: string;
  is_active: boolean;
}

export interface ApiKeyCreateRequest {
  name: string;
  role?: string;
  organization_slug?: string;
  expires_at?: string | null;
  notes?: string | null;
}

export interface ApiKeyCreated extends ApiKey {
  api_key: string;
}

export interface ProviderCredential {
  id: string | null;
  provider: string;
  organization_id: string | null;
  organization_slug: string;
  has_credential: boolean;
  key_hint: string | null;
  source: "org" | "env" | "none" | string;
  env_configured: boolean;
  notes: string | null;
  updated_at: string | null;
}

export interface ProviderCredentialUpsert {
  api_key: string;
  notes?: string | null;
  organization_slug?: string;
}

export interface Webhook {
  id: string;
  organization_id: string;
  organization_slug: string;
  name: string;
  url: string;
  secret_hint: string;
  action_filters: string[] | null;
  is_active: boolean;
  last_delivery_at: string | null;
  last_status_code: number | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface WebhookCreateRequest {
  name: string;
  url: string;
  secret: string;
  action_filters?: string[];
  is_active?: boolean;
  organization_slug?: string;
}

export interface WebhookUpdateRequest {
  name?: string;
  url?: string;
  secret?: string;
  action_filters?: string[] | null;
  is_active?: boolean;
}

export interface WebhookDelivery {
  id: string;
  webhook_id: string;
  webhook_name?: string | null;
  audit_event_id: string | null;
  attempt_number: number;
  status: string;
  http_status_code: number | null;
  error_message: string | null;
  response_snippet: string | null;
  next_retry_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface WebhookDeliveryListResponse {
  items: WebhookDelivery[];
  total: number;
}

export interface RetentionSettings {
  organization_id: string;
  organization_slug: string;
  prompt_history_retention_days: number | null;
  audit_events_retention_days: number | null;
  retention_auto_purge_enabled: boolean;
  retention_last_auto_purge_at: string | null;
  prompt_history_total: number;
  prompt_history_expired: number;
  audit_events_total: number;
  audit_events_expired: number;
}

export interface RetentionSettingsUpdate {
  prompt_history_retention_days?: number | null;
  audit_events_retention_days?: number | null;
  retention_auto_purge_enabled?: boolean | null;
  organization_slug?: string;
}

export interface RetentionSchedulerStatus {
  enabled: boolean;
  interval_seconds: number;
  initial_delay_seconds: number;
  thread_alive: boolean;
  last_cycle_started_at: string | null;
  last_cycle_finished_at: string | null;
  last_error: string | null;
  last_orgs_processed: number;
  last_prompt_history_deleted: number;
  last_audit_events_deleted: number;
}

export interface RetentionPurgeResult {
  organization_slug: string;
  dry_run: boolean;
  prompt_history_deleted: number;
  audit_events_deleted: number;
  cutoff_prompt_history: string | null;
  cutoff_audit_events: string | null;
}

export interface ComplianceReport {
  generated_at: string;
  organization_id: string;
  organization_slug: string;
  organization_name: string;
  report_days: number;
  retention: Record<string, unknown>;
  members: Array<{
    email: string;
    membership_role: string;
    full_name?: string | null;
  }>;
  policies: Array<{
    id: string;
    name: string;
    is_active: boolean;
    priority: number;
    blocked_providers: string[];
    pii_block_categories: string[];
    pii_redact_categories: string[];
    max_daily_cost_usd?: string | number | null;
    max_monthly_cost_usd?: string | number | null;
    max_tokens_limit?: number | null;
  }>;
  credentials: Array<{
    provider: string;
    source: string;
    has_credential: boolean;
    env_configured: boolean;
  }>;
  spend_daily_usd: string | number;
  spend_monthly_usd: string | number;
  analytics_summary: Record<string, unknown>;
  webhook_count: number;
  active_api_key_count: number;
  recent_violations: Array<{
    id: string;
    action: string;
    status: string;
    summary: string | null;
    created_at: string;
  }>;
  controls: Record<string, unknown>;
}

export interface CompletionResponse {
  history_id: string;
  provider: string;
  model: string;
  prompt: string;
  response: string | null;
  status: string;
  error_message?: string | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
  estimated_cost_usd: string | null;
  latency_ms: number | null;
  organization_slug: string;
  arena_run_id?: string | null;
}

export interface ArenaParticipant {
  provider: "groq" | "gemini" | "openai" | "claude";
  model?: string;
}

export interface ArenaRunRequest {
  prompt: string;
  participants: ArenaParticipant[];
  organization_slug?: string;
  temperature?: number;
  max_tokens?: number;
}

export interface ArenaRunResponse {
  arena_run_id: string;
  prompt: string;
  organization_slug: string;
  results: CompletionResponse[];
  total_estimated_cost_usd: string | null;
  success_count: number;
  error_count: number;
}

export interface HistoryItem {
  id: string;
  organization_slug: string;
  provider: string;
  model: string;
  prompt: string;
  response: string | null;
  status: string;
  error_message?: string | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
  estimated_cost_usd: string | null;
  latency_ms: number | null;
  arena_run_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface HistoryListResponse {
  items: HistoryItem[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface ArenaHistoryResponse {
  arena_run_id: string;
  organization_slug: string;
  prompt: string;
  items: HistoryItem[];
  success_count: number;
  error_count: number;
  total_estimated_cost_usd: string | null;
}

export interface HistoryListParams {
  organization_slug?: string;
  provider?: string;
  status?: "pending" | "success" | "error";
  arena_run_id?: string;
  arena_only?: boolean;
  page?: number;
  page_size?: number;
}

export type EvaluationStrategy =
  | "balanced"
  | "cheapest"
  | "fastest"
  | "quality"
  | "reliability";

export type RouterPreference = "balanced" | "cost" | "speed" | "quality";

export type TaskType =
  | "coding"
  | "summarization"
  | "creative"
  | "qa"
  | "analysis"
  | "translation"
  | "chat"
  | "general";

export interface ClassifyRequest {
  prompt: string;
}

export interface ClassifyResponse {
  task_type: TaskType;
  confidence: number;
  matched_signals: string[];
  scores: Record<string, number>;
}

export interface RouteCandidateItem {
  provider: string;
  model: string;
  score: number;
  available: boolean;
  reason: string;
}

export interface RouteRequest {
  prompt: string;
  preference?: RouterPreference;
  organization_slug?: string;
  execute?: boolean;
  temperature?: number;
  max_tokens?: number;
}

export interface RouteResponse {
  decision_id: string;
  task_type: TaskType;
  confidence: number;
  preference: RouterPreference;
  recommended_provider: string;
  recommended_model: string;
  rationale: string;
  matched_signals: string[];
  candidates: RouteCandidateItem[];
  executed: boolean;
  completion: CompletionResponse | null;
}

export interface EvaluationScoreItem {
  id: string;
  history_id: string;
  provider: string;
  model: string;
  status: string;
  success_score: string;
  latency_score: string;
  cost_score: string;
  substance_score: string;
  structure_score?: string;
  relevance_score?: string;
  composite_score: string;
  rank: number;
  rationale?: string | null;
}

export interface EvaluationResponse {
  id: string;
  arena_run_id: string;
  strategy: string;
  task_type?: string | null;
  metric_weights?: Record<string, string> | null;
  score_gap?: string | null;
  recommended_history_id: string | null;
  recommended_provider: string | null;
  recommended_model: string | null;
  summary: string | null;
  scores: EvaluationScoreItem[];
  created_at: string;
}

export interface StrategyComparisonResponse {
  arena_run_id: string;
  evaluations: EvaluationResponse[];
}

export interface AnalyticsSummary {
  total_requests: number;
  success_count: number;
  error_count: number;
  success_rate: number;
  total_tokens: number;
  total_estimated_cost_usd: string;
  avg_latency_ms: number | null;
  arena_run_count: number;
  routing_decision_count: number;
  evaluation_count: number;
}

export interface UsageByDayItem {
  day: string;
  requests: number;
  success_count: number;
  error_count: number;
  tokens: number;
  estimated_cost_usd: string;
}

export interface UsageByProviderItem {
  provider: string;
  requests: number;
  success_count: number;
  error_count: number;
  success_rate: number;
  tokens: number;
  estimated_cost_usd: string;
  avg_latency_ms: number | null;
}

export interface UsageByModelItem {
  provider: string;
  model: string;
  requests: number;
  tokens: number;
  estimated_cost_usd: string;
  avg_latency_ms: number | null;
}

export interface StatusBreakdownItem {
  status: string;
  count: number;
}

export interface RoutingByTaskItem {
  task_type: string;
  count: number;
}

export interface AnalyticsOverviewResponse {
  organization_slug: string;
  days: number;
  summary: AnalyticsSummary;
  usage_by_day: UsageByDayItem[];
  usage_by_provider: UsageByProviderItem[];
  usage_by_model: UsageByModelItem[];
  status_breakdown: StatusBreakdownItem[];
  routing_by_task_type: RoutingByTaskItem[];
}

export interface RegisterRequest {
  email: string;
  password: string;
  full_name?: string | null;
  organization_slug?: string;
  invite_token?: string | null;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface AuthUser {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
  is_active: boolean;
  organization_id: string;
  organization_slug: string;
  permissions: string[];
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  refresh_token?: string | null;
  refresh_expires_in?: number | null;
  user: AuthUser;
}

export interface UpdateUserRequest {
  role?: string | null;
  is_active?: boolean | null;
}

export interface RoleCatalogResponse {
  roles: string[];
  permissions: string[];
  matrix: Record<string, string[]>;
}

export interface PolicyRules {
  allowed_providers?: string[] | null;
  blocked_providers?: string[];
  allowed_models?: string[] | null;
  blocked_models?: string[];
  max_tokens_limit?: number | null;
  blocked_prompt_patterns?: string[];
  max_daily_cost_usd?: string | number | null;
  max_monthly_cost_usd?: string | number | null;
  warn_daily_cost_usd?: string | number | null;
  warn_monthly_cost_usd?: string | number | null;
  pii_block_categories?: string[];
  pii_redact_categories?: string[];
}

export interface PolicyCreateRequest {
  name: string;
  description?: string | null;
  is_active?: boolean;
  priority?: number;
  rules: PolicyRules;
  organization_slug?: string;
}

export interface PolicyUpdateRequest {
  name?: string | null;
  description?: string | null;
  is_active?: boolean | null;
  priority?: number | null;
  rules?: PolicyRules | null;
}

export interface PolicyResponse {
  id: string;
  organization_id: string;
  organization_slug: string;
  name: string;
  description: string | null;
  is_active: boolean;
  priority: number;
  rules: PolicyRules;
  created_at: string;
  updated_at: string;
}

export interface PolicyEvaluateRequest {
  provider: string;
  model?: string | null;
  prompt: string;
  max_tokens?: number;
  organization_slug?: string;
}

export interface PolicyViolationItem {
  policy_id: string;
  policy_name: string;
  rule: string;
  message: string;
}

export interface PolicyEvaluateResponse {
  allowed: boolean;
  organization_slug: string;
  violations: PolicyViolationItem[];
  warnings?: PolicyViolationItem[];
  spend_daily_usd?: string | number;
  spend_monthly_usd?: string | number;
  pii_findings?: Array<{ category: string; label: string }>;
  sanitized_prompt?: string | null;
}

export interface AuditEvent {
  id: string;
  organization_id: string | null;
  actor_user_id: string | null;
  actor_email: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  status: string;
  request_id: string | null;
  summary: string | null;
  details: Record<string, unknown> | null;
  created_at: string;
}

export interface AuditEventListResponse {
  items: AuditEvent[];
  total: number;
  page: number;
  page_size: number;
}

export interface AuditActionCatalogResponse {
  actions: string[];
}

export interface RagIngestRequest {
  title: string;
  content: string;
  source?: string | null;
  organization_slug?: string;
}

export interface RagDocumentResponse {
  id: string;
  organization_id: string;
  organization_slug: string;
  title: string;
  source: string | null;
  chunk_count: number;
  embedding_model: string;
  content_preview: string;
  created_at: string;
}

export interface RagSourceItem {
  document_id: string;
  document_title: string;
  chunk_id: string;
  chunk_index: number;
  score: number;
  content: string;
}

export interface RagQueryRequest {
  question: string;
  top_k?: number;
  provider?: string;
  model?: string | null;
  max_tokens?: number;
  organization_slug?: string;
}

export interface RagQueryResponse {
  answer: string;
  provider: string;
  model: string;
  status: string;
  error_message: string | null;
  history_id: string | null;
  sources: RagSourceItem[];
  embedding_model: string;
}

export interface AgentDefinition {
  id: string;
  organization_id: string;
  organization_slug: string;
  name: string;
  description: string | null;
  steps: string[];
  default_provider: string;
  default_model: string | null;
  max_steps: number;
  is_active: boolean;
  created_at: string;
}

export interface AgentRunRequest {
  definition_id: string;
  input_text: string;
  provider?: string | null;
  model?: string | null;
  organization_slug?: string;
}

export interface AgentPlanRunRequest {
  goal: string;
  provider?: string | null;
  model?: string | null;
  organization_slug?: string;
}

export interface AgentPlanPreviewResponse {
  goal: string;
  tools: string[];
  rationale: string;
  planner: string;
}

export interface AgentStepLogItem {
  step: number;
  tool: string;
  status: string;
  summary: string;
  detail?: Record<string, unknown> | null;
}

export interface AgentRunResponse {
  id: string;
  definition_id: string;
  definition_name: string;
  organization_slug: string;
  input_text: string;
  status: string;
  output_text: string | null;
  error_message: string | null;
  steps_log: AgentStepLogItem[];
  created_at: string;
}
