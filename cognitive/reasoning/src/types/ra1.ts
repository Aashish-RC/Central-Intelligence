import type { ChatCompletionRequest, ChatCompletionResponse } from './chat.js';
import type { CalculatedCost, MultiUnitUsage } from './telemetry.js';

export interface RequestContext {
  requestId: string;
  traceId: string;
  actor: string;
  clientIp?: string;
  tenantId?: string;
  metadata?: Record<string, unknown>;
}

// H2: Permission & Identity hook
export type PermissionDecision =
  | { action: 'allow' }
  | { action: 'deny'; reason: string; statusCode?: number }
  | { action: 'ask-human'; reason: string; challengeId: string };

export type IdentityHook = (
  c: any,
) => Promise<string | null | undefined> | (string | null | undefined);

export type PermissionHook = (
  req: ChatCompletionRequest,
  context: RequestContext,
) => Promise<PermissionDecision> | PermissionDecision;

// H3: Vault key hook
export interface ScopedCredential {
  apiKey: string;
  expiresAt?: number;
  provider: string;
  source: 'vault' | 'keychain' | 'kms';
}

export type KeyLookupHook = (
  provider: string,
  model: string,
  context: RequestContext,
) => Promise<ScopedCredential | null> | (ScopedCredential | null);

// H4: Audit and metering hook
export interface AuditRecord {
  requestId: string;
  traceId: string;
  timestamp: string;
  actor: string;
  model: string;
  provider: string;
  targetId: string;
  tokens: MultiUnitUsage & { estimated?: boolean };
  cost: CalculatedCost | null;
  costEstimated?: boolean;
  latencyMs: number;
  outcome: 'success' | 'error' | 'denied' | 'fallback';
  statusCode: number;
  errorMessage?: string;
  warning?: string;
  cached?: boolean;
  metadata?: Record<string, unknown>;
}

export type AuditHook = (record: AuditRecord) => Promise<void> | void;

// H5: Stream chunk hook (for guardrails and redaction)
export type StreamChunkHook = (chunk: string, context: RequestContext) => Promise<string> | string;

// H1: Gateway interface
export interface GatewayRequestOptions {
  context?: Partial<RequestContext>;
  permissionHook?: PermissionHook;
  keyLookupHook?: KeyLookupHook;
  auditHook?: AuditHook;
  streamChunkHook?: StreamChunkHook;
}

export interface IGatewayEngine {
  chatCompletion(
    req: ChatCompletionRequest,
    options?: GatewayRequestOptions,
  ): Promise<ChatCompletionResponse>;

  streamChatCompletion(
    req: ChatCompletionRequest,
    options?: GatewayRequestOptions,
  ): Promise<ReadableStream<Uint8Array>>;
}
