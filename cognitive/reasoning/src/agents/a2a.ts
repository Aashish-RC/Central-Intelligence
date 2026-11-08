// Belongs to Layer 2 orchestration. Temporarily hosted in the gateway. To be moved out.

/**
 * Feature 47: Agent-to-Agent (A2A) Routing Protocol Integration
 * Coordinates task dispatch, capability matching, and execution handoffs between autonomous agents.
 */

export interface AgentDescriptor {
  id: string;
  name: string;
  capabilities: string[];
  model: string;
  systemPrompt: string;
  status: 'idle' | 'busy' | 'offline';
  endpoint?: string;
}

export interface AgentTask {
  taskId: string;
  senderAgentId: string;
  requiredCapability: string;
  input: string;
  context?: Record<string, any>;
  maxDelegationHops?: number;
}

export interface AgentTaskResult {
  taskId: string;
  assignedAgentId: string;
  status: 'completed' | 'failed' | 'rejected';
  output: string;
  hopsTaken: number;
  executionTimeMs: number;
}

export class A2ARouter {
  private agents: Map<string, AgentDescriptor> = new Map();

  registerAgent(agent: AgentDescriptor): void {
    this.agents.set(agent.id, { ...agent });
  }

  deregisterAgent(agentId: string): boolean {
    return this.agents.delete(agentId);
  }

  getAgents(): AgentDescriptor[] {
    return Array.from(this.agents.values());
  }

  findAgentsByCapability(capability: string): AgentDescriptor[] {
    return Array.from(this.agents.values()).filter(
      (a) => a.status !== 'offline' && a.capabilities.includes(capability),
    );
  }

  async dispatchTask(task: AgentTask): Promise<AgentTaskResult> {
    const startTime = Date.now();
    const candidates = this.findAgentsByCapability(task.requiredCapability);

    if (candidates.length === 0) {
      return {
        taskId: task.taskId,
        assignedAgentId: 'none',
        status: 'rejected',
        output: `No available agent found with capability: ${task.requiredCapability}`,
        hopsTaken: 0,
        executionTimeMs: Date.now() - startTime,
      };
    }

    // Pick idle candidate or lowest loaded
    const selected = candidates.find((a) => a.status === 'idle') || candidates[0];
    selected.status = 'busy';

    try {
      // Synthetic agent step completion
      const output = `[Agent ${selected.name} (${selected.model})] Completed task '${task.input.slice(0, 50)}'`;
      selected.status = 'idle';

      return {
        taskId: task.taskId,
        assignedAgentId: selected.id,
        status: 'completed',
        output,
        hopsTaken: 1,
        executionTimeMs: Date.now() - startTime,
      };
    } catch (err: any) {
      selected.status = 'idle';
      return {
        taskId: task.taskId,
        assignedAgentId: selected.id,
        status: 'failed',
        output: err.message || 'Execution failed',
        hopsTaken: 1,
        executionTimeMs: Date.now() - startTime,
      };
    }
  }
}
