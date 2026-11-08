import { serve } from '@hono/node-server';
import { createGatewayApp } from './core/server.js';
export * from './types/chat.js';
export * from './types/provider.js';
export * from './types/ra1.js';
export * from './types/resilience.js';
export * from './types/telemetry.js';
export * from './core/engine.js';
export * from './core/server.js';
export * from './core/stream.js';
export * from './core/stream-failover.js';
export * from './routing/router.js';
export * from './telemetry/pricing.js';
export * from './telemetry/usage.js';
export * from './resilience/classifier.js';
export * from './resilience/cooldown.js';

const { app, router, engine } = createGatewayApp();

// Feature 5: Register default routes demonstrating virtual tiers (smart/fast/vision/embedding)
// 1. smart-tier: Primary Claude 3.7 Sonnet -> Fallback GPT-4o -> Escape Route Ollama
router.registerRoute({
  alias: 'smart-tier',
  strategy: 'prompt-cache-affinity',
  targets: [
    {
      id: 'anthropic-primary',
      provider: 'anthropic',
      model: 'claude-3-7-sonnet-20250219',
      config: {
        id: 'anthropic-config',
        name: 'Anthropic Official',
        baseUrl: process.env.ANTHROPIC_BASE_URL || 'https://api.anthropic.com',
        apiKey: process.env.ANTHROPIC_API_KEY || '',
      },
    },
    {
      id: 'openai-fallback',
      provider: 'openai',
      model: 'gpt-4o',
      config: {
        id: 'openai-config',
        name: 'OpenAI Official',
        baseUrl: process.env.OPENAI_BASE_URL || 'https://api.openai.com/v1',
        apiKey: process.env.OPENAI_API_KEY || '',
      },
    },
    {
      id: 'local-escape',
      provider: 'ollama',
      model: 'llama3.2',
      isEscapeRoute: true,
      config: {
        id: 'ollama-config',
        name: 'Local Ollama Escape',
        baseUrl: process.env.OLLAMA_BASE_URL || 'http://127.0.0.1:11434',
      },
    },
  ],
});

// 2. fast-tier: GPT-4o-mini with least-busy routing across two credentials/endpoints
router.registerRoute({
  alias: 'fast-tier',
  strategy: 'least-busy',
  targets: [
    {
      id: 'openai-mini-east',
      provider: 'openai',
      model: 'gpt-4o-mini',
      config: {
        id: 'openai-mini-east-cfg',
        name: 'OpenAI Mini East',
        baseUrl: process.env.OPENAI_BASE_URL || 'https://api.openai.com/v1',
        apiKey: process.env.OPENAI_API_KEY || '',
      },
    },
    {
      id: 'openai-mini-west',
      provider: 'openai',
      model: 'gpt-4o-mini',
      config: {
        id: 'openai-mini-west-cfg',
        name: 'OpenAI Mini West',
        baseUrl: process.env.OPENAI_BASE_URL || 'https://api.openai.com/v1',
        apiKey: process.env.OPENAI_API_KEY || '',
      },
    },
  ],
});

// 3. vision-tier: Multi-modal vision processing
router.registerRoute({
  alias: 'vision-tier',
  strategy: 'prompt-cache-affinity',
  targets: [
    {
      id: 'gemini-vision-primary',
      provider: 'gemini',
      model: 'gemini-1.5-pro',
      config: {
        id: 'gemini-vision-cfg',
        name: 'Google Gemini Pro',
        baseUrl: process.env.GEMINI_BASE_URL || 'https://generativelanguage.googleapis.com',
        apiKey: process.env.GEMINI_API_KEY || '',
      },
    },
    {
      id: 'gpt4o-vision-fallback',
      provider: 'openai',
      model: 'gpt-4o',
      config: {
        id: 'gpt4o-vision-cfg',
        name: 'OpenAI GPT-4o Vision',
        baseUrl: process.env.OPENAI_BASE_URL || 'https://api.openai.com/v1',
        apiKey: process.env.OPENAI_API_KEY || '',
      },
    },
  ],
});

// 4. embedding-tier: Vector embeddings tier
router.registerRoute({
  alias: 'embedding-tier',
  strategy: 'least-busy',
  targets: [
    {
      id: 'openai-text-embed-3-small',
      provider: 'openai',
      model: 'text-embedding-3-small',
      config: {
        id: 'embed-cfg',
        name: 'OpenAI Embeddings',
        baseUrl: process.env.OPENAI_BASE_URL || 'https://api.openai.com/v1',
        apiKey: process.env.OPENAI_API_KEY || '',
      },
    },
  ],
});

// Direct model aliases
router.registerRoute({
  alias: 'gpt-4o',
  targets: [
    {
      id: 'openai-gpt4o',
      provider: 'openai',
      model: 'gpt-4o',
      config: {
        id: 'openai-gpt4o-cfg',
        name: 'OpenAI GPT-4o',
        baseUrl: process.env.OPENAI_BASE_URL || 'https://api.openai.com/v1',
        apiKey: process.env.OPENAI_API_KEY || '',
      },
    },
  ],
});

// Local runtimes (llama.cpp and localai)
router.registerRoute({
  alias: 'llama.cpp',
  targets: [
    {
      id: 'llama-cpp-local',
      provider: 'llama.cpp',
      model: 'default',
      config: {
        id: 'llamacpp-cfg',
        name: 'llama.cpp Local Server',
        baseUrl: process.env.LLAMA_CPP_BASE_URL || 'http://127.0.0.1:8080',
      },
    },
  ],
});

export { app, router, engine };

const PORT = Number.parseInt(process.env.PORT || '4000', 10);

if (process.env.NODE_ENV !== 'test') {
  console.log(`[Model Gateway] Initializing high-performance gateway engine...`);
  console.log(
    `[Model Gateway] Active virtual tiers: smart-tier, fast-tier, vision-tier, embedding-tier`,
  );
  console.log(`[Model Gateway] Listening on http://localhost:${PORT}`);

  serve({
    fetch: app.fetch,
    port: PORT,
  });
}
