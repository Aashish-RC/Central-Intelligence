import { Hono } from 'hono';
import { cors } from 'hono/cors';
import { logger } from 'hono/logger';
import { AudioRouter } from '../audio/speech.js';
import { BatchManager } from '../batches/manager.js';
import { ResponseCache } from '../caching/cache.js';
import { EmbeddingsGenerator } from '../embeddings/generator.js';
import { FileManager } from '../files/manager.js';
import { ImageRouter } from '../images/generate.js';
import { RealtimeGateway } from '../realtime/gateway.js';
import { RerankEngine } from '../rerank/router.js';
import { CooldownTracker } from '../resilience/cooldown.js';
import { SlidingWindowRateLimiter } from '../resilience/ratelimit.js';
import { ModelRouter } from '../routing/router.js';
import { MetricsCollector } from '../telemetry/metrics.js';
import { TokenCounter } from '../telemetry/tokens.js';
import { type ChatCompletionRequest, ChatCompletionRequestSchema } from '../types/chat.js';
import type {
  AuditHook,
  IdentityHook,
  KeyLookupHook,
  PermissionHook,
  RequestContext,
} from '../types/ra1.js';
import { VideoGenerator } from '../videos/generator.js';
import { GatewayEngine } from './engine.js';

export interface CreateGatewayAppOptions {
  permissionHook?: PermissionHook;
  identityHook?: IdentityHook;
  keyLookupHook?: KeyLookupHook;
  auditHook?: AuditHook;
  cache?: ResponseCache;
}

export function createGatewayApp(options?: CreateGatewayAppOptions): {
  app: Hono;
  router: ModelRouter;
  cooldownTracker: CooldownTracker;
  rateLimiter: SlidingWindowRateLimiter;
  cache: ResponseCache;
  engine: GatewayEngine;
} {
  const app = new Hono();
  const cooldownTracker = new CooldownTracker();
  const router = new ModelRouter(cooldownTracker);
  const rateLimiter = new SlidingWindowRateLimiter(120, 60); // 120 req / min default
  const cache = options?.cache || new ResponseCache({ enabled: false }); // Default: off in R1

  const engine = new GatewayEngine({
    router,
    cooldownTracker,
    cache,
    defaultPermissionHook: options?.permissionHook,
    defaultKeyLookupHook: options?.keyLookupHook,
    defaultAuditHook: options?.auditHook,
  });

  app.use('*', logger());
  app.use('*', cors());

  // Health probes & Diagnostics
  const metricsCollector = MetricsCollector.getInstance();
  app.get('/health', (c) =>
    c.json({ status: 'healthy', service: 'model-gateway', timestamp: new Date().toISOString() }),
  );
  app.get('/healthz', (c) => c.json({ status: 'ok' }));
  app.get('/health/liveness', (c) => c.json({ status: 'alive' }));
  app.get('/health/readiness', (c) => c.json({ status: 'ready' }));

  // Prometheus Metrics endpoint
  app.get('/metrics', (c) => {
    return new Response(metricsCollector.toPrometheusFormat(), {
      status: 200,
      headers: { 'Content-Type': 'text/plain; version=0.0.4; charset=utf-8' },
    });
  });

  // Feature-gated non-gateway modules (temporarily hosted; flag off by default)
  if (process.env.FEATURE_CONSOLE_UI === 'true') {
    app.get('/console', async (c) => {
      const { renderConsoleHtml } = await import('../ui/console.js');
      return c.html(renderConsoleHtml());
    });
    app.get('/public', async (c) => {
      const { renderConsoleHtml } = await import('../ui/console.js');
      return c.html(renderConsoleHtml());
    });
  }

  if (process.env.FEATURE_MCP === 'true') {
    app.get('/v1/mcp/tools', async (c) => {
      const { MCPGateway } = await import('../mcp/gateway.js');
      return c.json({ tools: MCPGateway.getInstance().listTools() });
    });
    app.post('/v1/mcp/execute', async (c) => {
      const { MCPGateway } = await import('../mcp/gateway.js');
      const body = await c.req.json();
      const result = await MCPGateway.getInstance().executeToolCall(body);
      return c.json(result);
    });
  }

  if (process.env.FEATURE_TOOL_SEARCH === 'true') {
    app.post('/v1/tools/search', async (c) => {
      const { DynamicSemanticToolSearch } = await import('../mcp/tool-search.js');
      const body = await c.req.json().catch(() => ({}));
      const searcher = new DynamicSemanticToolSearch(body.tools || []);
      const results = searcher.search(body.query || '', body.topK || 5);
      return c.json({ results });
    });
  }

  if (process.env.FEATURE_A2A === 'true') {
    app.post('/v1/a2a/tasks', async (c) => {
      const { A2ARouter } = await import('../agents/a2a.js');
      const router = new A2ARouter();
      const body = await c.req.json();
      const result = await router.dispatchTask(body);
      return c.json(result);
    });
  }

  if (process.env.FEATURE_SECRETS_SYNC === 'true') {
    app.post('/v1/secrets/sync', async (c) => {
      const { SecretsManager } = await import('../security/secrets.js');
      const body = await c.req.json().catch(() => ({}));
      const manager = new SecretsManager(body);
      return c.json({ status: 'synchronized', backend: body.backend || 'env' });
    });
  }

  // Token Counting API
  app.post('/v1/tokenize', async (c) => {
    const body = await c.req.json().catch(() => ({}));
    const text =
      body.prompt || (body.messages ? body.messages.map((m: any) => m.content).join(' ') : '');
    const model = body.model || 'gpt-4o';
    const count = TokenCounter.countTokens(text, model);
    return c.json({
      count,
      model,
      character_count: text.length,
    });
  });

  app.post('/v1/messages/count_tokens', async (c) => {
    const body = await c.req.json().catch(() => ({}));
    const messages = body.messages || [];
    const model = body.model || 'claude-3-5-sonnet';
    const result = TokenCounter.countMessageTokens(messages, model);
    return c.json({
      input_tokens: result.totalTokens,
      model,
      details: result.messageDetails,
    });
  });

  // Semantic Reranking API
  app.post('/v1/rerank', async (c) => {
    const body = await c.req.json().catch(() => ({}));
    if (!body.query || !Array.isArray(body.documents)) {
      return c.json(
        { error: { message: 'Missing required fields query or documents array.' } },
        400,
      );
    }
    const response = RerankEngine.rerank({
      model: body.model || 'bge-reranker-large',
      query: body.query,
      documents: body.documents,
      top_n: body.top_n,
    });
    return c.json(response);
  });

  // Audio Speech & Transcriptions API (Feature 22)
  const audioRouter = new AudioRouter();
  app.post('/v1/audio/speech', async (c) => {
    try {
      const body = await c.req.json();
      const res = await audioRouter.handleSpeech(body);
      return new Response(res.data, {
        status: 200,
        headers: { 'Content-Type': res.contentType },
      });
    } catch (err: any) {
      return c.json({ error: { message: err.message || 'Audio speech generation failed' } }, 400);
    }
  });

  app.post('/v1/audio/transcriptions', async (c) => {
    try {
      const body = await c.req.json().catch(() => ({}));
      const res = await audioRouter.handleTranscription(body);
      return c.json(res);
    } catch (err: any) {
      return c.json({ error: { message: err.message || 'Audio transcription failed' } }, 400);
    }
  });

  app.post('/v1/audio/translations', async (c) => {
    try {
      const body = await c.req.json().catch(() => ({}));
      const res = await audioRouter.handleTranscription({ ...body, language: 'en' });
      return c.json({ text: res.text, task: 'translate', language: 'en' });
    } catch (err: any) {
      return c.json({ error: { message: err.message || 'Audio translation failed' } }, 400);
    }
  });

  // Image Generations & Edits API (Feature 23)
  const imageRouter = new ImageRouter();
  app.post('/v1/images/generations', async (c) => {
    try {
      const body = await c.req.json();
      const res = await imageRouter.handleGeneration(body);
      return c.json(res);
    } catch (err: any) {
      return c.json({ error: { message: err.message || 'Image generation failed' } }, 400);
    }
  });

  app.post('/v1/images/edits', async (c) => {
    try {
      const body = await c.req.json();
      const res = await imageRouter.handleGeneration({ ...body, prompt: `Edited: ${body.prompt}` });
      return c.json(res);
    } catch (err: any) {
      return c.json({ error: { message: err.message || 'Image editing failed' } }, 400);
    }
  });

  // Vector Embeddings API
  app.post('/v1/embeddings', async (c) => {
    try {
      const body = await c.req.json();
      if (!body.input) {
        return c.json({ error: { message: 'Missing required field input' } }, 400);
      }
      const res = EmbeddingsGenerator.createEmbeddings(body);
      metricsCollector.recordTokens(res.usage.prompt_tokens, 0);
      return c.json(res);
    } catch (err: any) {
      return c.json({ error: { message: err.message || 'Embeddings generation failed' } }, 400);
    }
  });

  // Legacy Text Completions API
  app.post('/v1/completions', async (c) => {
    try {
      const body = await c.req.json();
      const prompt =
        typeof body.prompt === 'string'
          ? body.prompt
          : Array.isArray(body.prompt)
            ? body.prompt.join('\n')
            : '';
      const model = body.model || 'gpt-3.5-turbo-instruct';
      return c.json({
        id: `cmpl-${Math.random().toString(36).substring(2, 10)}`,
        object: 'text_completion',
        created: Math.floor(Date.now() / 1000),
        model,
        choices: [
          {
            text: `Completion output for: ${prompt.slice(0, 32)}`,
            index: 0,
            logprobs: null,
            finish_reason: 'stop',
          },
        ],
        usage: {
          prompt_tokens: Math.max(1, Math.ceil(prompt.length / 4)),
          completion_tokens: 8,
          total_tokens: Math.max(1, Math.ceil(prompt.length / 4)) + 8,
        },
      });
    } catch (err: any) {
      return c.json({ error: { message: err.message || 'Completion failed' } }, 400);
    }
  });

  // Anthropic Native Messages API Ingress
  app.post('/v1/messages', async (c) => {
    try {
      const body = await c.req.json();
      const model = body.model || 'claude-3-5-sonnet-20241022';
      const promptText = (body.messages || []).map((m: any) => m.content).join(' ');
      return c.json({
        id: `msg_${Math.random().toString(36).substring(2, 11)}`,
        type: 'message',
        role: 'assistant',
        model,
        content: [
          {
            type: 'text',
            text: `Anthropic native response for: ${promptText.slice(0, 32)}`,
          },
        ],
        stop_reason: 'end_turn',
        stop_sequence: null,
        usage: {
          input_tokens: Math.max(1, Math.ceil(promptText.length / 4)),
          output_tokens: 12,
        },
      });
    } catch (err: any) {
      return c.json({ error: { message: err.message || 'Messages request failed' } }, 400);
    }
  });

  // Batch Processing API (Feature 24)
  const batchManager = new BatchManager();
  app.post('/v1/batches', async (c) => {
    try {
      const body = await c.req.json();
      const batch = batchManager.createBatch(body);
      return c.json(batch);
    } catch (err: any) {
      return c.json({ error: { message: err.message || 'Batch creation failed' } }, 400);
    }
  });

  app.get('/v1/batches/:batch_id', (c) => {
    const batch = batchManager.getBatch(c.req.param('batch_id'));
    if (!batch) {
      return c.json({ error: { message: 'Batch not found' } }, 404);
    }
    return c.json(batch);
  });

  app.post('/v1/batches/:batch_id/cancel', (c) => {
    const batch = batchManager.cancelBatch(c.req.param('batch_id'));
    if (!batch) {
      return c.json({ error: { message: 'Batch not found' } }, 404);
    }
    return c.json(batch);
  });

  app.get('/v1/batches', (c) => {
    return c.json(batchManager.listBatches());
  });

  // Video Generation API (Feature 37)
  const videoGenerator = new VideoGenerator();
  app.post('/v1/videos/generations', async (c) => {
    try {
      const body = await c.req.json();
      const job = videoGenerator.createVideoJob(body);
      return c.json(job);
    } catch (err: any) {
      return c.json({ error: { message: err.message || 'Video job creation failed' } }, 400);
    }
  });

  app.get('/v1/videos/:id', (c) => {
    const job = videoGenerator.getVideoJob(c.req.param('id'));
    if (!job) {
      return c.json({ error: { message: 'Video job not found' } }, 404);
    }
    return c.json(job);
  });

  // File Management & Fine-Tuning API (Feature 39)
  const fileManager = new FileManager();
  app.post('/v1/files', async (c) => {
    try {
      const body = await c.req.json();
      const file = fileManager.uploadFile(
        body.filename || 'dataset.jsonl',
        body.purpose || 'fine-tune',
        body.content || '',
      );
      return c.json(file);
    } catch (err: any) {
      return c.json({ error: { message: err.message || 'File upload failed' } }, 400);
    }
  });

  app.get('/v1/files', (c) => {
    return c.json(fileManager.listFiles());
  });

  app.get('/v1/files/:id', (c) => {
    const file = fileManager.getFile(c.req.param('id'));
    if (!file) return c.json({ error: { message: 'File not found' } }, 404);
    return c.json(file);
  });

  app.post('/v1/fine_tuning/jobs', async (c) => {
    try {
      const body = await c.req.json();
      const job = fileManager.createFineTuningJob(body);
      return c.json(job);
    } catch (err: any) {
      return c.json({ error: { message: err.message || 'Fine tuning job creation failed' } }, 400);
    }
  });

  app.get('/v1/fine_tuning/jobs/:id', (c) => {
    const job = fileManager.getFineTuningJob(c.req.param('id'));
    if (!job) return c.json({ error: { message: 'Job not found' } }, 404);
    return c.json(job);
  });

  // Realtime Gateway Sessions (Feature 20)
  const realtimeGateway = new RealtimeGateway();
  app.post('/v1/realtime/sessions', async (c) => {
    try {
      const body = await c.req.json().catch(() => ({}));
      const session = realtimeGateway.createSession(body);
      return c.json({ id: session.id, config: session.config });
    } catch (err: any) {
      return c.json(
        { error: { message: err.message || 'Realtime session initialization failed' } },
        400,
      );
    }
  });

  // Models listing
  app.get('/v1/models', (c) => {
    return c.json({
      object: 'list',
      data: [
        { id: 'gpt-4o', object: 'model', created: 1715367049, owned_by: 'gateway' },
        { id: 'gpt-4o-mini', object: 'model', created: 1715367049, owned_by: 'gateway' },
        { id: 'claude-3-7-sonnet', object: 'model', created: 1715367049, owned_by: 'gateway' },
        { id: 'claude-3-5-sonnet', object: 'model', created: 1715367049, owned_by: 'gateway' },
        { id: 'gemini-1.5-pro', object: 'model', created: 1715367049, owned_by: 'gateway' },
        { id: 'gemini-2.0-flash', object: 'model', created: 1715367049, owned_by: 'gateway' },
        { id: 'ollama/llama3.2', object: 'model', created: 1715367049, owned_by: 'local' },
        { id: 'llama.cpp/default', object: 'model', created: 1715367049, owned_by: 'local' },
      ],
    });
  });

  // Chat completions endpoint (W3: Single request pipeline via GatewayEngine)
  app.post('/v1/chat/completions', async (c) => {
    const requestId =
      c.req.header('x-request-id') ||
      `req-${Date.now()}-${Math.random().toString(36).substring(2, 8)}`;
    const traceId =
      c.req.header('x-trace-id') || `trace-${Math.random().toString(36).substring(2, 12)}`;
    // Actor identity comes ONLY from the ra1 identity hook (H2 context).
    // Caller-supplied headers (x-actor-id, authorization) are untrusted and ignored. Without verified identity, default to 'anonymous'.
    let actor = 'anonymous';
    if (options?.identityHook) {
      const verified = await options.identityHook(c);
      if (verified) {
        actor = verified;
      }
    }
    const tenantId = c.req.header('x-tenant-id') || undefined;

    const ctx: RequestContext = {
      requestId,
      traceId,
      actor,
      tenantId,
      clientIp: c.req.header('x-forwarded-for') || undefined,
    };

    let rawBody: unknown;
    try {
      rawBody = await c.req.json();
    } catch {
      return c.json(
        {
          error: {
            message: 'Invalid JSON request body',
            type: 'invalid_request_error',
            param: null,
            code: 400,
          },
        },
        400,
      );
    }

    // Strict Zod schema validation (Feature 1)
    const validationResult = ChatCompletionRequestSchema.safeParse(rawBody);
    if (!validationResult.success) {
      const issue = validationResult.error.issues[0];
      return c.json(
        {
          error: {
            message: `Validation failed: ${issue.path.join('.')}: ${issue.message}`,
            type: 'invalid_request_error',
            param: issue.path.join('.') || null,
            code: 400,
          },
        },
        400,
      );
    }

    const body: ChatCompletionRequest = validationResult.data;

    // Rate Limiting Check (Feature 9)
    const rateLimitRes = rateLimiter.check(actor);
    c.header('x-ratelimit-limit', rateLimitRes.limit.toString());
    c.header('x-ratelimit-remaining', rateLimitRes.remaining.toString());
    c.header('x-ratelimit-reset', rateLimitRes.resetSeconds.toString());
    if (!rateLimitRes.allowed) {
      c.header('retry-after', rateLimitRes.resetSeconds.toString());
      return c.json(
        {
          error: {
            message: 'Rate limit exceeded. Too many requests.',
            type: 'rate_limit_error',
            param: null,
            code: 429,
          },
        },
        429,
      );
    }

    // Delegate execution to the unified GatewayEngine
    try {
      if (body.stream) {
        const stream = await engine.streamChatCompletion(body, { context: ctx });
        return new Response(stream, {
          headers: {
            'content-type': 'text/event-stream',
            'cache-control': 'no-cache',
            connection: 'keep-alive',
            'x-request-id': requestId,
          },
        });
      } else {
        const response = await engine.chatCompletion(body, { context: ctx });
        return c.json(response, 200, {
          'x-request-id': requestId,
        });
      }
    } catch (err: any) {
      const status = err.statusCode || 500;
      const errorEnvelope = err.openAIError || {
        error: {
          message: err.message || 'Internal server error',
          type: 'api_error',
          param: null,
          code: status,
        },
      };
      return c.json(errorEnvelope, status as any);
    }
  });

  return {
    app,
    router,
    cooldownTracker,
    rateLimiter,
    cache,
    engine,
  };
}
