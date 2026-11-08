/**
 * Model Engine Types & Contracts
 * Inspired by OmniRoute (MIT) & LiteLLM (MIT conceptual patterns)
 */

export type Modality = 'text' | 'image' | 'embedding' | 'audio';
export type Capability = 'reasoning' | 'code' | 'math' | 'creative' | 'multimodal' | 'tools' | 'fast';
export type RoutingPath = 'pooled-enterprise' | 'pooled-aggregator' | 'byok' | 'byoi';
export type SelectionMode = 'dropdown' | 'search' | 'auto';
export type FlagPreference = 'always' | 'cost-impacting' | 'never';

export interface ModelDefinition {
  id: string;
  name: string;
  provider: string;
  modalities: Modality[];
  capabilities: Capability[];
  contextWindow: number;
  costPer1kInputUSD: number;
  costPer1kOutputUSD: number;
  benchmarkScore: number; // 0 to 100 overall intelligence rating
  latencyScoreMs: number;
  tier: 'flagship' | 'mid-tier' | 'economy' | 'local';
  endpointSuffix?: string;
}

export interface MultimodalAttachment {
  type: 'image' | 'file';
  mimeType: string;
  data: string; // base64 or URL
}

export interface EngineMessage {
  role: 'system' | 'user' | 'assistant' | 'tool';
  content: string;
  attachments?: MultimodalAttachment[];
  toolCallId?: string;
  toolCalls?: Array<{
    id: string;
    type: 'function';
    function: { name: string; arguments: string };
  }>;
}

export interface ToolDefinition {
  type: 'function';
  function: {
    name: string;
    description: string;
    parameters: Record<string, unknown>;
  };
}

export interface ExecutionRequest {
  messages: EngineMessage[];
  selectionMode?: SelectionMode;
  model?: string; // Explicit model when in dropdown or search mode
  searchQuery?: string; // Query string when in search mode
  allowList?: string[]; // Priority signal in Auto mode
  denyList?: string[]; // Hard exclusion in all modes & fallbacks
  flagPreference?: FlagPreference;
  temperature?: number;
  maxTokens?: number;
  tools?: ToolDefinition[];
  virtualKey?: string; // Virtual key from governance layer
  userContext?: {
    userId?: string;
    teamId?: string;
  };
  byokKeys?: Record<string, string>; // User-provided provider API keys
  byoiEndpoints?: Record<string, { endpointUrl: string; apiKey?: string; model?: string }>; // User-provided infrastructure
}

export interface ExecutionResponse {
  id: string;
  text: string;
  model: string;
  routeUsed: RoutingPath;
  fallbackTriggered: boolean;
  fallbackChain: string[];
  notifications: Array<{
    type: 'auto_selected_outside_allowlist' | 'fallback_warning' | 'budget_alert';
    message: string;
    model: string;
    costImpactUSD?: number;
  }>;
  usage: {
    promptTokens: number;
    completionTokens: number;
    totalTokens: number;
    costUSD: number;
  };
  latencyMs: number;
}

export interface VirtualKey {
  key: string;
  userId: string;
  teamId?: string;
  name: string;
  createdAt: number;
  expiresAt?: number;
  revoked?: boolean;
  rateLimitRPM?: number;
  rateLimitTPM?: number;
  maxSpendUSD?: number;
  allowedModels?: string[];
  deniedModels?: string[];
}

export interface BudgetRecord {
  entityId: string; // userId or teamId or virtualKey
  entityType: 'user' | 'team' | 'key';
  maxSpendUSD: number;
  currentSpendUSD: number;
  resetPeriod: 'daily' | 'monthly' | 'lifetime';
  periodStart: number;
}

export interface RateLimitStatus {
  requestsThisMinute: number;
  tokensThisMinute: number;
  windowStartMs: number;
}

export interface UsageAuditRecord {
  id: string;
  timestamp: number;
  virtualKey?: string;
  userId?: string;
  teamId?: string;
  model: string;
  routeUsed: RoutingPath;
  promptTokens: number;
  completionTokens: number;
  costUSD: number;
  latencyMs: number;
  status: 'success' | 'failed';
  error?: string;
}
