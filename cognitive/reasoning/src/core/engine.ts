import { ResponseCache } from '../caching/cache.js';
import { ProviderRegistry } from '../providers/registry.js';
import { ErrorClassifier } from '../resilience/classifier.js';
import type { CooldownTracker } from '../resilience/cooldown.js';
import type { ModelRouter } from '../routing/router.js';
import { SSRFGuard } from '../security/ssrf.js';
import { PricingEngine } from '../telemetry/pricing.js';
import { TokenUsageAccounting } from '../telemetry/usage.js';
import {
  type ChatCompletionRequest,
  ChatCompletionRequestSchema,
  type ChatCompletionResponse,
} from '../types/chat.js';
import type { StreamTransformState } from '../types/provider.js';
import {
  type AuditHook,
  AuditRecord,
  type GatewayRequestOptions,
  type IGatewayEngine,
  type KeyLookupHook,
  type PermissionHook,
  type RequestContext,
  type StreamChunkHook,
} from '../types/ra1.js';
import { StreamFailoverManager } from './stream-failover.js';

export interface GatewayEngineConfig {
  router: ModelRouter;
  cooldownTracker: CooldownTracker;
  cache?: ResponseCache;
  defaultPermissionHook?: PermissionHook;
  defaultKeyLookupHook?: KeyLookupHook;
  defaultAuditHook?: AuditHook;
  defaultStreamChunkHook?: StreamChunkHook;
}

/**
 * High-performance ra1-native Model Gateway Engine implementing the IGatewayEngine contract.
 */
export class GatewayEngine implements IGatewayEngine {
  private router: ModelRouter;
  private cooldownTracker: CooldownTracker;
  private cache?: ResponseCache;
  private permissionHook?: PermissionHook;
  private keyLookupHook?: KeyLookupHook;
  private auditHook?: AuditHook;
  private streamChunkHook?: StreamChunkHook;

  constructor(config: GatewayEngineConfig) {
    this.router = config.router;
    this.cooldownTracker = config.cooldownTracker;
    this.cache = config.cache;
    this.permissionHook = config.defaultPermissionHook;
    this.keyLookupHook = config.defaultKeyLookupHook;
    this.auditHook = config.defaultAuditHook;
    this.streamChunkHook = config.defaultStreamChunkHook;
  }

  public setPermissionHook(hook: PermissionHook): void {
    this.permissionHook = hook;
  }

  public setKeyLookupHook(hook: KeyLookupHook): void {
    this.keyLookupHook = hook;
  }

  public setAuditHook(hook: AuditHook): void {
    this.auditHook = hook;
  }

  public setStreamChunkHook(hook: StreamChunkHook): void {
    this.streamChunkHook = hook;
  }

  public setCache(cache: ResponseCache): void {
    this.cache = cache;
  }

  public async chatCompletion(
    req: ChatCompletionRequest,
    options?: GatewayRequestOptions,
  ): Promise<ChatCompletionResponse> {
    const validated = ChatCompletionRequestSchema.parse(req);
    const ctx = this.buildContext(options?.context);
    const requestStartTime = Date.now();

    // H2: Permission Hook
    const permHook = options?.permissionHook || this.permissionHook;
    if (permHook) {
      const decision = await permHook(validated, ctx);
      if (decision.action === 'deny') {
        const statusCode = decision.statusCode || 403;
        const errMsg = `Permission denied: ${decision.reason}`;
        await this.emitAuditRecord({
          ctx,
          model: validated.model,
          provider: 'ra1-permission',
          targetId: 'permission-engine',
          latencyMs: Date.now() - requestStartTime,
          outcome: 'denied',
          statusCode,
          errorMessage: errMsg,
        });
        const error = new Error(errMsg) as any;
        error.statusCode = statusCode;
        error.openAIError = {
          error: { message: errMsg, type: 'permission_denied', param: null, code: statusCode },
        };
        throw error;
      }
      if (decision.action === 'ask-human') {
        const errMsg = `Human-in-the-loop approval required for challenge: ${decision.challengeId}`;
        await this.emitAuditRecord({
          ctx,
          model: validated.model,
          provider: 'ra1-permission',
          targetId: 'permission-engine',
          latencyMs: Date.now() - requestStartTime,
          outcome: 'denied',
          statusCode: 428,
          errorMessage: errMsg,
          metadata: { challengeId: decision.challengeId },
        });
        const error = new Error(errMsg) as any;
        error.statusCode = 428;
        error.challengeId = decision.challengeId;
        error.openAIError = {
          error: { message: errMsg, type: 'approval_required', param: null, code: 428 },
        };
        throw error;
      }
    }

    // Response Cache Check (Feature 14 - W4)
    if (this.cache && this.cache.enabled && !req.stream) {
      const cacheKey = ResponseCache.computeKey(validated, {
        actor: ctx.actor,
        tenantId: ctx.tenantId,
      });
      const cached = this.cache.get(cacheKey);
      if (cached) {
        await this.emitAuditRecord({
          ctx,
          model: validated.model,
          provider: 'cache',
          targetId: 'response-cache',
          latencyMs: Date.now() - requestStartTime,
          outcome: 'success',
          statusCode: 200,
          cached: true,
          usage: cached.usage
            ? {
                promptTokens: cached.usage.prompt_tokens,
                completionTokens: cached.usage.completion_tokens,
                reasoningTokens: cached.usage.completion_tokens_details?.reasoning_tokens || 0,
                cachedPromptTokens: cached.usage.prompt_tokens_details?.cached_tokens || 0,
                totalTokens: cached.usage.total_tokens,
              }
            : undefined,
        });
        return cached;
      }
    }

    const systemPrompt = validated.messages.find((m) => m.role === 'system')?.content || '';
    const targets = this.router.resolveTargets(validated.model, systemPrompt);

    if (targets.length === 0) {
      const errMsg = `No available target found for model '${validated.model}'`;
      await this.emitAuditRecord({
        ctx,
        model: validated.model,
        provider: 'router',
        targetId: 'none',
        latencyMs: Date.now() - requestStartTime,
        outcome: 'error',
        statusCode: 404,
        errorMessage: errMsg,
      });
      const error = new Error(errMsg) as any;
      error.statusCode = 404;
      error.openAIError = {
        error: { message: errMsg, type: 'invalid_request_error', param: 'model', code: 404 },
      };
      throw error;
    }

    let lastRetryableError: any = null;

    for (const target of targets) {
      const adapter = ProviderRegistry.get(target.provider);
      if (!adapter) continue;

      // H3: Vault Key Lookup
      const config = { ...target.config };
      const keyHook = options?.keyLookupHook || this.keyLookupHook;
      if (keyHook) {
        try {
          const scopedCred = await keyHook(target.provider, target.model, ctx);
          if (scopedCred?.apiKey) {
            config.apiKey = scopedCred.apiKey;
          }
        } catch (keyErr: any) {
          const errMsg = `Key lookup failed for provider '${target.provider}': ${keyErr.message}`;
          await this.emitAuditRecord({
            ctx,
            model: validated.model,
            provider: target.provider,
            targetId: target.id,
            latencyMs: Date.now() - requestStartTime,
            outcome: 'error',
            statusCode: 500,
            errorMessage: errMsg,
          });
          const error = new Error(errMsg) as any;
          error.statusCode = 500;
          error.openAIError = {
            error: { message: errMsg, type: 'api_error', param: null, code: 500 },
          };
          throw error;
        }
      }

      const upstreamReq = adapter.transformRequest({ ...validated, model: target.model }, config);

      // Validate URL against SSRF (W6)
      try {
        const isLocal =
          target.provider === 'ollama' ||
          target.provider === 'localai' ||
          target.provider === 'llama.cpp';
        await SSRFGuard.validateUrl(upstreamReq.url, isLocal);
      } catch (ssrfErr: any) {
        await this.emitAuditRecord({
          ctx,
          model: validated.model,
          provider: target.provider,
          targetId: target.id,
          latencyMs: Date.now() - requestStartTime,
          outcome: 'error',
          statusCode: 403,
          errorMessage: ssrfErr.message,
        });
        const error = new Error(ssrfErr.message) as any;
        error.statusCode = 403;
        error.openAIError = {
          error: { message: ssrfErr.message, type: 'security_violation', param: null, code: 403 },
        };
        throw error;
      }

      // In-flight counter incremented and decremented exactly once per attempt (W2)
      this.cooldownTracker.incrementInFlight(target.id);
      const targetStartTime = Date.now();

      try {
        const timeoutMs = config.timeoutMs || 30000;
        const response = await fetch(upstreamReq.url, {
          method: upstreamReq.method,
          headers: upstreamReq.headers,
          body: upstreamReq.body,
          redirect: 'manual',
          signal: AbortSignal.timeout(timeoutMs),
        });

        const latency = Date.now() - targetStartTime;

        if (!response.ok) {
          const errorBody = await response.text();
          let parsedError: unknown = errorBody;
          try {
            parsedError = JSON.parse(errorBody);
          } catch {}

          const classified = ErrorClassifier.classify(
            response.status,
            parsedError,
            response.headers,
          );

          if (classified.isRetryable) {
            // Server error / overloaded / 429: Record failure and cooldown, then fail over to next target
            this.cooldownTracker.recordFailure(target.id, classified.retryAfterSeconds);
            lastRetryableError = classified;
            continue;
          } else {
            // Client error (4xx other than 429 and 408):
            // 1. MUST NOT count against target health or cooldown!
            // 2. MUST NOT fail over to next target!
            // 3. Emit exactly ONE audit record with final outcome.
            const openAIError = ErrorClassifier.toOpenAIError(classified);
            await this.emitAuditRecord({
              ctx,
              model: validated.model,
              provider: target.provider,
              targetId: target.id,
              latencyMs: Date.now() - requestStartTime,
              outcome: 'error',
              statusCode: response.status,
              errorMessage: classified.message,
            });

            const err = new Error(classified.message) as any;
            err.statusCode = response.status;
            err.openAIError = openAIError;
            err.classified = classified;
            throw err;
          }
        }

        // Success!
        this.cooldownTracker.recordSuccess(target.id, latency);

        const rawJson = await response.json();
        const normalized = adapter.transformResponse(rawJson, response.status, config);

        // Feature 7: Unified Token Usage Accounting
        const usage = TokenUsageAccounting.extractUsage(
          rawJson,
          target.provider,
          validated,
          normalized.choices[0]?.message?.content || '',
        );

        // Feature 8: Cost calculation (W7)
        const cost = PricingEngine.calculateCost(validated.model, usage);
        (normalized as any).cost = cost;

        // Cache store if enabled
        if (this.cache && this.cache.enabled) {
          const cacheKey = ResponseCache.computeKey(validated, {
            actor: ctx.actor,
            tenantId: ctx.tenantId,
          });
          this.cache.set(cacheKey, normalized, undefined, {
            actor: ctx.actor,
            tenantId: ctx.tenantId,
          });
        }

        // H4: Exactly ONE audit record on success
        await this.emitAuditRecord({
          ctx,
          model: validated.model,
          provider: target.provider,
          targetId: target.id,
          latencyMs: Date.now() - requestStartTime,
          outcome: 'success',
          statusCode: 200,
          usage,
          cost,
          warning:
            cost === null
              ? `Unknown model pricing for '${validated.model}'; cost cannot be computed`
              : undefined,
        });

        return normalized;
      } catch (err: any) {
        // If it's already a non-retryable client error or SSRF error, rethrow immediately
        if (err.statusCode && ErrorClassifier.isClientNonRetryable(err.statusCode)) {
          throw err;
        }

        // Network error / timeout / 5xx
        const isTimeout =
          err.name === 'TimeoutError' || err.message?.toLowerCase().includes('timeout');
        const classified = isTimeout
          ? ErrorClassifier.classify(408, 'Request timed out')
          : ErrorClassifier.classify(500, err.message || 'Network error');

        this.cooldownTracker.recordFailure(target.id, classified.retryAfterSeconds || 10);
        lastRetryableError = err;
      } finally {
        this.cooldownTracker.decrementInFlight(target.id);
      }
    }

    // All targets failed with retryable errors: emit exactly ONE audit record
    const totalLatency = Date.now() - requestStartTime;
    const finalMsg = `All upstream targets failed for model '${validated.model}'. Last error: ${lastRetryableError?.message || lastRetryableError}`;
    await this.emitAuditRecord({
      ctx,
      model: validated.model,
      provider: 'gateway',
      targetId: 'all-failed',
      latencyMs: totalLatency,
      outcome: 'error',
      statusCode: 502,
      errorMessage: finalMsg,
    });

    const finalErr = new Error(finalMsg) as any;
    finalErr.statusCode = 502;
    finalErr.openAIError = {
      error: { message: finalMsg, type: 'gateway_upstream_error', param: null, code: 502 },
    };
    throw finalErr;
  }

  public async streamChatCompletion(
    req: ChatCompletionRequest,
    options?: GatewayRequestOptions,
  ): Promise<ReadableStream<Uint8Array>> {
    const validated = ChatCompletionRequestSchema.parse({ ...req, stream: true });
    const ctx = this.buildContext(options?.context);
    const requestStartTime = Date.now();

    // H2: Permission Hook
    const permHook = options?.permissionHook || this.permissionHook;
    if (permHook) {
      const decision = await permHook(validated, ctx);
      if (decision.action === 'deny') {
        const statusCode = decision.statusCode || 403;
        const errMsg = `Permission denied: ${decision.reason}`;
        await this.emitAuditRecord({
          ctx,
          model: validated.model,
          provider: 'ra1-permission',
          targetId: 'permission-engine',
          latencyMs: Date.now() - requestStartTime,
          outcome: 'denied',
          statusCode,
          errorMessage: errMsg,
        });
        const error = new Error(errMsg) as any;
        error.statusCode = statusCode;
        error.openAIError = {
          error: { message: errMsg, type: 'permission_denied', param: null, code: statusCode },
        };
        throw error;
      }
      if (decision.action === 'ask-human') {
        const errMsg = `Human-in-the-loop approval required for challenge: ${decision.challengeId}`;
        await this.emitAuditRecord({
          ctx,
          model: validated.model,
          provider: 'ra1-permission',
          targetId: 'permission-engine',
          latencyMs: Date.now() - requestStartTime,
          outcome: 'denied',
          statusCode: 428,
          errorMessage: errMsg,
          metadata: { challengeId: decision.challengeId },
        });
        const error = new Error(errMsg) as any;
        error.statusCode = 428;
        error.challengeId = decision.challengeId;
        error.openAIError = {
          error: { message: errMsg, type: 'approval_required', param: null, code: 428 },
        };
        throw error;
      }
    }

    const systemPrompt = validated.messages.find((m) => m.role === 'system')?.content || '';
    const targets = this.router.resolveTargets(validated.model, systemPrompt);

    if (targets.length === 0) {
      const errMsg = `No available target found for model '${validated.model}'`;
      await this.emitAuditRecord({
        ctx,
        model: validated.model,
        provider: 'router',
        targetId: 'none',
        latencyMs: Date.now() - requestStartTime,
        outcome: 'error',
        statusCode: 404,
        errorMessage: errMsg,
      });
      const error = new Error(errMsg) as any;
      error.statusCode = 404;
      error.openAIError = {
        error: { message: errMsg, type: 'invalid_request_error', param: 'model', code: 404 },
      };
      throw error;
    }

    let lastRetryableError: any = null;

    for (const target of targets) {
      const adapter = ProviderRegistry.get(target.provider);
      if (!adapter) continue;

      // H3: Vault Key Lookup
      const config = { ...target.config };
      const keyHook = options?.keyLookupHook || this.keyLookupHook;
      if (keyHook) {
        try {
          const scopedCred = await keyHook(target.provider, target.model, ctx);
          if (scopedCred?.apiKey) {
            config.apiKey = scopedCred.apiKey;
          }
        } catch (keyErr: any) {
          const errMsg = `Key lookup failed for provider '${target.provider}': ${keyErr.message}`;
          await this.emitAuditRecord({
            ctx,
            model: validated.model,
            provider: target.provider,
            targetId: target.id,
            latencyMs: Date.now() - requestStartTime,
            outcome: 'error',
            statusCode: 500,
            errorMessage: errMsg,
          });
          const error = new Error(errMsg) as any;
          error.statusCode = 500;
          error.openAIError = {
            error: { message: errMsg, type: 'api_error', param: null, code: 500 },
          };
          throw error;
        }
      }

      const upstreamReq = adapter.transformRequest({ ...validated, model: target.model }, config);

      try {
        const isLocal =
          target.provider === 'ollama' ||
          target.provider === 'localai' ||
          target.provider === 'llama.cpp';
        await SSRFGuard.validateUrl(upstreamReq.url, isLocal);
      } catch (ssrfErr: any) {
        await this.emitAuditRecord({
          ctx,
          model: validated.model,
          provider: target.provider,
          targetId: target.id,
          latencyMs: Date.now() - requestStartTime,
          outcome: 'error',
          statusCode: 403,
          errorMessage: ssrfErr.message,
        });
        const error = new Error(ssrfErr.message) as any;
        error.statusCode = 403;
        error.openAIError = {
          error: { message: ssrfErr.message, type: 'security_violation', param: null, code: 403 },
        };
        throw error;
      }

      this.cooldownTracker.incrementInFlight(target.id);
      const targetStartTime = Date.now();

      try {
        const timeoutMs = config.timeoutMs || 30000;
        const response = await fetch(upstreamReq.url, {
          method: upstreamReq.method,
          headers: upstreamReq.headers,
          body: upstreamReq.body,
          redirect: 'manual',
          signal: AbortSignal.timeout(timeoutMs),
        });

        if (!response.ok || !response.body) {
          const errorBody = await response.text();
          let parsedError: unknown = errorBody;
          try {
            parsedError = JSON.parse(errorBody);
          } catch {}

          const classified = ErrorClassifier.classify(
            response.status,
            parsedError,
            response.headers,
          );

          if (classified.isRetryable) {
            this.cooldownTracker.recordFailure(target.id, classified.retryAfterSeconds);
            lastRetryableError = classified;
            continue; // Failover pre-first-byte
          } else {
            // Client-side non-retryable error
            const openAIError = ErrorClassifier.toOpenAIError(classified);
            await this.emitAuditRecord({
              ctx,
              model: validated.model,
              provider: target.provider,
              targetId: target.id,
              latencyMs: Date.now() - requestStartTime,
              outcome: 'error',
              statusCode: response.status,
              errorMessage: classified.message,
            });

            const err = new Error(classified.message) as any;
            err.statusCode = response.status;
            err.openAIError = openAIError;
            throw err;
          }
        }

        // Feature 34: Guarded stream with pre-first-byte failover & post-first-byte SSE error
        const state: StreamTransformState = {
          id: `chatcmpl-${Date.now()}`,
          model: validated.model,
          created: Math.floor(Date.now() / 1000),
          buffer: '',
        };

        let stream: ReadableStream<Uint8Array>;
        try {
          const guarded = await StreamFailoverManager.createGuardedStream(
            response.body,
            adapter,
            state,
            { preflightTimeoutMs: Math.min(timeoutMs, 15000) },
          );
          stream = guarded.stream;
        } catch (preflightErr: any) {
          this.cooldownTracker.recordFailure(target.id, 10);
          lastRetryableError = preflightErr;
          continue; // pre-first-byte failure -> failover to next target!
        }

        const latency = Date.now() - targetStartTime;
        this.cooldownTracker.recordSuccess(target.id, latency);

        // H4: Emit audit record for streaming initiation
        const promptTokens = TokenUsageAccounting.estimatePromptTokens(validated);
        const estimatedUsage = {
          promptTokens,
          completionTokens: 0,
          reasoningTokens: 0,
          cachedPromptTokens: 0,
          totalTokens: promptTokens,
          estimated: true,
        };
        const estimatedCost = PricingEngine.calculateCost(validated.model, estimatedUsage);

        await this.emitAuditRecord({
          ctx,
          model: validated.model,
          provider: target.provider,
          targetId: target.id,
          latencyMs: Date.now() - requestStartTime,
          outcome: 'success',
          statusCode: 200,
          usage: estimatedUsage,
          cost: estimatedCost,
          warning:
            estimatedCost === null
              ? `Unknown model pricing for '${validated.model}'; cost cannot be computed`
              : undefined,
        });

        return stream;
      } catch (err: any) {
        if (err.statusCode && ErrorClassifier.isClientNonRetryable(err.statusCode)) {
          throw err;
        }
        this.cooldownTracker.recordFailure(target.id, 10);
        lastRetryableError = err;
      } finally {
        this.cooldownTracker.decrementInFlight(target.id);
      }
    }

    const totalLatency = Date.now() - requestStartTime;
    const finalMsg = `All streaming targets failed for model '${validated.model}'. Last error: ${lastRetryableError?.message || lastRetryableError}`;
    await this.emitAuditRecord({
      ctx,
      model: validated.model,
      provider: 'gateway',
      targetId: 'all-failed',
      latencyMs: totalLatency,
      outcome: 'error',
      statusCode: 502,
      errorMessage: finalMsg,
    });

    const finalErr = new Error(finalMsg) as any;
    finalErr.statusCode = 502;
    finalErr.openAIError = {
      error: { message: finalMsg, type: 'gateway_upstream_error', param: null, code: 502 },
    };
    throw finalErr;
  }

  private buildContext(ctx?: Partial<RequestContext>): RequestContext {
    return {
      requestId:
        ctx?.requestId || `req-${Date.now()}-${Math.random().toString(36).substring(2, 8)}`,
      traceId: ctx?.traceId || `trace-${Math.random().toString(36).substring(2, 12)}`,
      actor: ctx?.actor || 'anonymous-actor',
      clientIp: ctx?.clientIp,
      tenantId: ctx?.tenantId,
      metadata: ctx?.metadata,
    };
  }

  private async emitAuditRecord(params: {
    ctx: RequestContext;
    model: string;
    provider: string;
    targetId: string;
    latencyMs: number;
    outcome: 'success' | 'error' | 'denied' | 'fallback';
    statusCode: number;
    errorMessage?: string;
    warning?: string;
    cached?: boolean;
    usage?: any;
    cost?: any;
    metadata?: Record<string, unknown>;
  }): Promise<void> {
    if (!this.auditHook) return;

    const defaultUsage = params.usage || {
      promptTokens: 0,
      completionTokens: 0,
      reasoningTokens: 0,
      cachedPromptTokens: 0,
      totalTokens: 0,
      estimated: false,
    };

    const cost =
      params.cost !== undefined
        ? params.cost
        : PricingEngine.calculateCost(params.model, defaultUsage);
    const isUnknownModelCost = cost === null;
    const costEstimated = isUnknownModelCost ? true : (params.usage?.estimated ?? false);
    const warning =
      params.warning ||
      (isUnknownModelCost
        ? `Unknown model pricing for '${params.model}'; cost cannot be computed`
        : undefined);

    try {
      await this.auditHook({
        requestId: params.ctx.requestId,
        traceId: params.ctx.traceId,
        timestamp: new Date().toISOString(),
        actor: params.ctx.actor,
        model: params.model,
        provider: params.provider,
        targetId: params.targetId,
        tokens: defaultUsage,
        cost,
        costEstimated,
        latencyMs: params.latencyMs,
        outcome: params.outcome,
        statusCode: params.statusCode,
        errorMessage: params.errorMessage,
        warning,
        cached: params.cached,
        metadata: { ...(params.ctx.metadata || {}), ...(params.metadata || {}) },
      });
    } catch (auditErr) {
      console.error(`[GatewayEngine] Audit hook failed:`, auditErr);
    }
  }
}
