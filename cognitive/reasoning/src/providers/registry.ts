import type { ProviderAdapter } from '../types/provider.js';
import { AnthropicAdapter } from './anthropic.js';
import { BedrockProviderAdapter } from './bedrock.js';
import { GeminiProviderAdapter } from './gemini.js';
import { OpenAICompatibleLocalAdapter } from './local.js';
import { OllamaAdapter } from './ollama.js';
import { OpenAIAdapter } from './openai.js';

export class ProviderRegistry {
  private static adapters: Map<string, ProviderAdapter> = new Map();

  public static initialize(): void {
    this.register(new OpenAIAdapter());
    this.register(new AnthropicAdapter());
    this.register(new OllamaAdapter());
    this.register(new GeminiProviderAdapter());
    this.register(new BedrockProviderAdapter());
    this.register(new OpenAICompatibleLocalAdapter('localai', 'LocalAI Runtime'));
    this.register(new OpenAICompatibleLocalAdapter('llama.cpp', 'llama.cpp Server'));
  }

  public static register(adapter: ProviderAdapter): void {
    this.adapters.set(adapter.id.toLowerCase(), adapter);
  }

  public static get(providerId: string): ProviderAdapter | undefined {
    return this.adapters.get(providerId.toLowerCase());
  }

  public static has(providerId: string): boolean {
    return this.adapters.has(providerId.toLowerCase());
  }
}

// Auto-initialize standard registry
ProviderRegistry.initialize();
