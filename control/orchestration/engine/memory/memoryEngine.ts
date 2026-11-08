import { nanoid } from 'nanoid';

export interface MemoryItem {
  id: string;
  fact: string;
  category: 'preference' | 'persona' | 'project' | 'fact' | 'instruction';
  timestamp: number;
  userId?: string;
  spaceId?: string;
  confidence?: number;
  tags?: string[];
}

export interface MemorySearchOptions {
  category?: MemoryItem['category'];
  userId?: string;
  spaceId?: string;
  limit?: number;
}

/**
 * MemoryEngine handles short-term context and long-term persistent facts
 * for the conversational agent.
 */
export class MemoryEngine {
  private memories: Map<string, MemoryItem> = new Map();
  private enabled: boolean = true;

  constructor(initialMemories?: MemoryItem[]) {
    if (initialMemories) {
      for (const item of initialMemories) {
        this.memories.set(item.id, item);
      }
    }
  }

  public setEnabled(enabled: boolean): void {
    this.enabled = enabled;
  }

  public isEnabled(): boolean {
    return this.enabled;
  }

  /**
   * Add a new fact to memory.
   */
  public remember(
    fact: string,
    category: MemoryItem['category'] = 'fact',
    metadata?: {
      userId?: string;
      spaceId?: string;
      tags?: string[];
      confidence?: number;
    }
  ): MemoryItem {
    const cleanFact = fact.trim();
    if (!cleanFact) {
      throw new Error('Memory fact cannot be empty');
    }

    // Check if similar fact exists in same category to prevent duplicates
    for (const existing of this.memories.values()) {
      if (
        existing.category === category &&
        existing.fact.toLowerCase() === cleanFact.toLowerCase() &&
        existing.userId === metadata?.userId
      ) {
        // Refresh timestamp
        existing.timestamp = Date.now();
        return existing;
      }
    }

    const item: MemoryItem = {
      id: `mem-${nanoid(8)}`,
      fact: cleanFact,
      category,
      timestamp: Date.now(),
      userId: metadata?.userId,
      spaceId: metadata?.spaceId,
      tags: metadata?.tags || [],
      confidence: metadata?.confidence ?? 1.0,
    };

    this.memories.set(item.id, item);
    return item;
  }

  /**
   * Remove a memory item by ID.
   */
  public forget(id: string): boolean {
    return this.memories.delete(id);
  }

  /**
   * Clear all memories, optionally filtered by userId or spaceId.
   */
  public clear(filter?: { userId?: string; spaceId?: string }): void {
    if (!filter) {
      this.memories.clear();
      return;
    }

    for (const [id, item] of this.memories.entries()) {
      const matchUser = filter.userId ? item.userId === filter.userId : true;
      const matchSpace = filter.spaceId ? item.spaceId === filter.spaceId : true;
      if (matchUser && matchSpace) {
        this.memories.delete(id);
      }
    }
  }

  /**
   * List all stored memories matching optional filters.
   */
  public list(options?: MemorySearchOptions): MemoryItem[] {
    let items = Array.from(this.memories.values());

    if (options?.category) {
      items = items.filter((m) => m.category === options.category);
    }
    if (options?.userId) {
      items = items.filter((m) => !m.userId || m.userId === options.userId);
    }
    if (options?.spaceId) {
      items = items.filter((m) => !m.spaceId || m.spaceId === options.spaceId);
    }

    items.sort((a, b) => b.timestamp - a.timestamp);

    if (options?.limit && options.limit > 0) {
      items = items.slice(0, options.limit);
    }

    return items;
  }

  /**
   * Recall relevant memories based on conversational query.
   */
  public recall(query: string, options?: MemorySearchOptions): MemoryItem[] {
    if (!this.enabled) return [];

    const candidates = this.list(options);
    if (!query || !query.trim()) {
      return candidates.slice(0, options?.limit || 10);
    }

    const queryTokens = query.toLowerCase().split(/\W+/).filter(Boolean);
    if (queryTokens.length === 0) {
      return candidates.slice(0, options?.limit || 10);
    }

    // Keyword relevance score
    const scored = candidates.map((item) => {
      const text = `${item.fact} ${(item.tags || []).join(' ')} ${item.category}`.toLowerCase();
      let matchCount = 0;
      for (const token of queryTokens) {
        if (text.includes(token)) {
          matchCount++;
        }
      }
      return { item, score: matchCount };
    });

    // Sort by matches desc, then timestamp desc
    scored.sort((a, b) => {
      if (b.score !== a.score) return b.score - a.score;
      return b.item.timestamp - a.item.timestamp;
    });

    const limit = options?.limit || 5;
    return scored
      .filter((s) => s.score > 0 || scored.length <= limit)
      .slice(0, limit)
      .map((s) => s.item);
  }

  /**
   * Formats active memories into a prompt block for system prompt injection.
   */
  public buildMemoryPromptContext(query: string, options?: MemorySearchOptions): string {
    if (!this.enabled) return '';

    const relevant = this.recall(query, options);
    if (relevant.length === 0) return '';

    const lines = relevant.map((item, idx) => {
      const categoryTag = item.category ? `[${item.category.toUpperCase()}]` : '';
      return `${idx + 1}. ${categoryTag} ${item.fact}`;
    });

    return `\n\n[Persistent Memory Context — Remembered facts about the user and project]:\n${lines.join('\n')}\nUse these memories naturally without explicitly quoting this header unless asked.`;
  }

  /**
   * Heuristic extraction of facts from a user turn (e.g. "I prefer TypeScript", "My name is Bob").
   */
  public extractFactsFromTurn(userText: string, metadata?: { userId?: string; spaceId?: string }): MemoryItem[] {
    if (!this.enabled || !userText) return [];

    const extracted: MemoryItem[] = [];
    const lower = userText.trim();

    // Pattern 1: Preferences ("I prefer X", "I always use X", "I like X", "My favorite X is Y")
    const prefRegex = /(?:i prefer|i always use|my preferred|i like using)\s+([^.,;\n]+)/gi;
    let match: RegExpExecArray | null;
    while ((match = prefRegex.exec(lower)) !== null) {
      const captured = match[1]?.trim();
      if (captured && captured.length > 2 && captured.length < 80) {
        extracted.push(this.remember(`User prefers: ${captured}`, 'preference', metadata));
      }
    }

    // Pattern 2: Identity / Persona ("My name is X", "I am a Y", "I work as a Y")
    const personaRegex = /(?:my name is|i am a|i work as a)\s+([^.,;\n]+)/gi;
    while ((match = personaRegex.exec(lower)) !== null) {
      const captured = match[1]?.trim();
      if (captured && captured.length > 2 && captured.length < 80) {
        extracted.push(this.remember(`User identity/role: ${captured}`, 'persona', metadata));
      }
    }

    // Pattern 3: Explicit memory request ("Remember that X", "Please remember X")
    const explicitRegex = /(?:please remember that|remember that|remember:)\s+([^.,;\n]+)/gi;
    while ((match = explicitRegex.exec(lower)) !== null) {
      const captured = match[1]?.trim();
      if (captured && captured.length > 3) {
        extracted.push(this.remember(captured, 'instruction', metadata));
      }
    }

    return extracted;
  }
}

// Global shared memory engine instance
export const globalMemoryEngine = new MemoryEngine();
