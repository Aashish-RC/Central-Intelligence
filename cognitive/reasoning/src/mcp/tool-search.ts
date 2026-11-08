// Belongs to Layer 1 tool registry. Temporarily hosted in the gateway. To be moved out.

import type { McpToolDefinition } from './gateway.js';

export interface ScoredTool {
  tool: McpToolDefinition;
  score: number;
}

export class DynamicSemanticToolSearch {
  private tools: Map<string, McpToolDefinition> = new Map();
  private toolTokens: Map<string, Set<string>> = new Map();

  constructor(initialTools: McpToolDefinition[] = []) {
    for (const tool of initialTools) {
      this.registerTool(tool);
    }
  }

  registerTool(tool: McpToolDefinition): void {
    this.tools.set(tool.name, tool);
    const text =
      `${tool.name} ${tool.name.replace(/_/g, ' ')} ${tool.description} ${JSON.stringify(tool.inputSchema)}`.toLowerCase();
    const tokens = new Set(text.match(/[a-z0-9]+/g) || []);
    this.toolTokens.set(tool.name, tokens);
  }

  removeTool(name: string): boolean {
    this.toolTokens.delete(name);
    return this.tools.delete(name);
  }

  search(query: string, topK = 3): McpToolDefinition[] {
    if (this.tools.size === 0) return [];
    if (this.tools.size <= topK) {
      return Array.from(this.tools.values());
    }

    const queryTokens = query.toLowerCase().match(/[a-z0-9]+/g) || [];
    const scored: ScoredTool[] = [];

    for (const [name, tool] of this.tools.entries()) {
      const toolToks = this.toolTokens.get(name)!;
      let matches = 0;
      for (const q of queryTokens) {
        if (toolToks.has(q)) {
          matches += 2.0;
        } else {
          for (const t of toolToks) {
            if (t.length > 3 && (t.includes(q) || q.includes(t))) {
              matches += 0.5;
              break;
            }
          }
        }
      }
      scored.push({ tool, score: matches });
    }

    scored.sort((a, b) => b.score - a.score);
    return scored.slice(0, topK).map((s) => s.tool);
  }
}
