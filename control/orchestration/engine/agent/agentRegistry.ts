export interface AgentDefinition {
  id: string;
  name: string;
  icon: string;
  description: string;
  systemPrompt: string;
  defaultModel?: string;
  temperature?: number;
  toolsAllowed: string[];
  isBase: boolean;
  createdAt: number;
  updatedAt: number;
}

export type AgentConfigOverrides = Partial<Omit<AgentDefinition, 'id' | 'isBase' | 'createdAt'>>;

export const BASE_AGENTS: AgentDefinition[] = [
  {
    id: 'general-assistant',
    name: 'General Assistant',
    icon: '🌟',
    description: 'Helpful, versatile conversational assistant for writing, reasoning, and daily tasks.',
    systemPrompt: `You are Ra1 Assistant, a versatile, intelligent AI companion built for insightful conversation, problem-solving, and clear communication. Respond directly, articulately, and format output using clean markdown with headers, bullet points, and code blocks where appropriate.`,
    defaultModel: 'openai/gpt-4o',
    temperature: 0.7,
    toolsAllowed: ['web_search'],
    isBase: true,
    createdAt: 1726500000000,
    updatedAt: 1726500000000,
  },
  {
    id: 'research-specialist',
    name: 'Research & RAG Specialist',
    icon: '🔍',
    description: 'Deep literature search, document synthesis, and factual citation extraction.',
    systemPrompt: `You are the Ra1 Research Specialist. Your primary responsibility is deep, evidence-based investigation and synthesis. Always synthesize facts rigorously, contrast differing perspectives, and cite your sources precisely.`,
    defaultModel: 'anthropic/claude-3-5-sonnet',
    temperature: 0.2,
    toolsAllowed: ['web_search', 'rag_retriever'],
    isBase: true,
    createdAt: 1726500000000,
    updatedAt: 1726500000000,
  },
  {
    id: 'coder-specialist',
    name: 'Software Engineer',
    icon: '💻',
    description: 'Expert software engineer for full-stack code, refactoring, debugging, and live sandbox execution.',
    systemPrompt: `You are the Ra1 Software Architect and Senior Engineer. You write clean, type-safe, and production-ready code with concise explanations. Provide runnable code blocks and consider edge cases and performance.`,
    defaultModel: 'anthropic/claude-3-5-sonnet',
    temperature: 0.2,
    toolsAllowed: ['sandbox_runner', 'code_analyzer'],
    isBase: true,
    createdAt: 1726500000000,
    updatedAt: 1726500000000,
  },
  {
    id: 'data-analyst',
    name: 'Data Analyst',
    icon: '📊',
    description: 'Interprets tables, computes statistics, and recommends visual charts.',
    systemPrompt: `You are the Ra1 Data Analyst. You excel at analyzing datasets, detecting trends and anomalies, calculating statistical summaries, and preparing structured data for charts (bar, line, pie).`,
    defaultModel: 'openai/gpt-4o',
    temperature: 0.3,
    toolsAllowed: ['data_table', 'csv_parser'],
    isBase: true,
    createdAt: 1726500000000,
    updatedAt: 1726500000000,
  },
  {
    id: 'task-operator',
    name: 'Autonomous Task Operator',
    icon: '🌐',
    description: 'Autonomous ReAct agent for multi-step tasks, web browsing, emails, calendar, and connectors.',
    systemPrompt: `You are the Ra1 Autonomous Task Operator. You decompose user objectives into clear, step-by-step actions. Use your available tools effectively. When mutative actions are consequential, request human confirmation before execution.`,
    defaultModel: 'openai/gpt-4o',
    temperature: 0.2,
    toolsAllowed: ['web_search', 'browser', 'email', 'calendar', 'mcp:*'],
    isBase: true,
    createdAt: 1726500000000,
    updatedAt: 1726500000000,
  },
];

export class AgentRegistry {
  private customAgents: Map<string, AgentDefinition> = new Map();

  constructor(initialCustom?: AgentDefinition[]) {
    if (initialCustom) {
      for (const a of initialCustom) {
        this.customAgents.set(a.id, a);
      }
    }
  }

  public getBaseAgents(): AgentDefinition[] {
    return [...BASE_AGENTS];
  }

  public getAllAgents(): AgentDefinition[] {
    return [...BASE_AGENTS, ...Array.from(this.customAgents.values())];
  }

  /**
   * Retrieves an agent by id. If tempOverrides are provided, merges them without mutating storage.
   */
  public getAgent(agentId: string, tempOverrides?: AgentConfigOverrides): AgentDefinition {
    const base = BASE_AGENTS.find((a) => a.id === agentId);
    const custom = this.customAgents.get(agentId);
    const target = custom || base || BASE_AGENTS[0];

    if (!tempOverrides || Object.keys(tempOverrides).length === 0) {
      return { ...target };
    }

    return {
      ...target,
      ...tempOverrides,
      id: target.id,
      isBase: target.isBase,
      createdAt: target.createdAt,
      updatedAt: Date.now(),
    };
  }

  /**
   * Persists a custom agent definition (True Config).
   */
  public saveCustomAgent(agent: Omit<AgentDefinition, 'isBase' | 'createdAt' | 'updatedAt'> & { id?: string }): AgentDefinition {
    const id = agent.id || `agent-custom-${Date.now()}`;
    const now = Date.now();
    const existing = this.customAgents.get(id);

    const saved: AgentDefinition = {
      ...agent,
      id,
      isBase: false,
      createdAt: existing ? existing.createdAt : now,
      updatedAt: now,
    };

    this.customAgents.set(id, saved);
    return saved;
  }

  /**
   * Deletes a custom agent. Base agents cannot be deleted.
   */
  public deleteCustomAgent(agentId: string): boolean {
    if (BASE_AGENTS.some((a) => a.id === agentId)) {
      throw new Error(`Cannot delete base agent "${agentId}"`);
    }
    return this.customAgents.delete(agentId);
  }

  /**
   * Builds the effective prompt for the agent incorporating memory context.
   */
  public resolveSystemPrompt(
    agentId: string,
    tempOverrides?: AgentConfigOverrides,
    memoryContext?: string
  ): string {
    const agent = this.getAgent(agentId, tempOverrides);
    let prompt = agent.systemPrompt;
    if (memoryContext && memoryContext.trim()) {
      prompt += `\n${memoryContext.trim()}`;
    }
    return prompt;
  }
}

// Global registry instance
export const globalAgentRegistry = new AgentRegistry();
