import { describe, expect, it } from 'vitest';
import { A2ARouter } from '../src/agents/a2a.js';

describe('Feature 47: Agent-to-Agent (A2A) Routing Protocol Integration', () => {
  it('registers agents and dispatches tasks matching required capabilities', async () => {
    const router = new A2ARouter();
    router.registerAgent({
      id: 'agent_coder_1',
      name: 'PythonExpert',
      capabilities: ['code_generation', 'python_refactoring'],
      model: 'claude-3-5-sonnet',
      systemPrompt: 'You are a senior python engineer',
      status: 'idle',
    });

    router.registerAgent({
      id: 'agent_sql_1',
      name: 'SqlOptimizer',
      capabilities: ['sql_tuning', 'database_design'],
      model: 'gpt-4o',
      systemPrompt: 'You are a database architect',
      status: 'idle',
    });

    const result = await router.dispatchTask({
      taskId: 'task_001',
      senderAgentId: 'orchestrator_main',
      requiredCapability: 'code_generation',
      input: 'Write a fast sliding-window algorithm',
    });

    expect(result.status).toBe('completed');
    expect(result.assignedAgentId).toBe('agent_coder_1');
    expect(result.hopsTaken).toBe(1);
    expect(result.output).toContain('PythonExpert');
  });

  it('rejects task when no agent possesses the required capability', async () => {
    const router = new A2ARouter();
    const result = await router.dispatchTask({
      taskId: 'task_002',
      senderAgentId: 'orchestrator_main',
      requiredCapability: 'quantum_cryptography',
      input: 'Break RSA-4096',
    });

    expect(result.status).toBe('rejected');
    expect(result.output).toContain('No available agent found');
  });
});
