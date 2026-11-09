import { describe, it, expect } from 'vitest';
import {
  SelfKnowledgeBoundaryModule,
  type AgentCapabilityManifest,
} from '../src/selfKnowledge/index.js';

describe('Self-Knowledge Boundary Module (Feature 4.27)', () => {
  const manifest: AgentCapabilityManifest = {
    agentId: 'agent_coder_alpha',
    name: 'Autonomous Code Assistant',
    modelName: 'claude-3-7-sonnet',
    registeredTools: ['read_file', 'write_file', 'run_tests'],
    allowedDomains: ['github.com', 'internal.repo'],
    sandboxEnabled: true,
    internetAccess: false,
    financialAuthorityUSD: 250.0,
    restrictedActions: ['deploy to production', 'drop database', 'delete user accounts'],
  };

  const boundary = new SelfKnowledgeBoundaryModule(manifest);

  it('1. Within-boundary query evaluation succeeds', () => {
    const res = boundary.evaluateQuery('Please read file src/index.ts and run the unit tests');
    expect(res.canHandle).toBe(true);
    expect(res.boundaryType).toBe('within_boundary');
    expect(res.confidence).toBeGreaterThan(0.9);
  });

  it('2. Financial threshold violation is caught', () => {
    const res = boundary.evaluateQuery('Transfer $1,500.00 to cloud provider for additional GPUs');
    expect(res.canHandle).toBe(false);
    expect(res.boundaryType).toBe('financial_limit_exceeded');
    expect(res.reason).toContain('exceeds autonomous financial limit');
  });

  it('3. Explicitly restricted actions are blocked', () => {
    const res = boundary.evaluateQuery('All checks pass, please deploy to production now');
    expect(res.canHandle).toBe(false);
    expect(res.boundaryType).toBe('restricted_action');
    expect(res.reason).toContain('deploy to production');
  });

  it('4. Real-time internet access requirement caught when offline', () => {
    const res = boundary.evaluateQuery('What is the current stock price of Apple right now?');
    expect(res.canHandle).toBe(false);
    expect(res.boundaryType).toBe('missing_tool');
    expect(res.reason).toContain('internet access is disabled');
    expect(res.missingCapabilities).toContain('web_search');
  });

  it('5. Tool invocation validation checks registered tools and parameter limits', () => {
    // Registered tool succeeds
    const validCall = boundary.validateToolCall('read_file', { path: 'package.json' });
    expect(validCall.valid).toBe(true);

    // Unregistered tool fails
    const invalidTool = boundary.validateToolCall('execute_remote_shell');
    expect(invalidTool.valid).toBe(false);
    expect(invalidTool.reason).toContain('not registered');

    // Tool call with parameter exceeding financial authority fails
    const overspend = boundary.validateToolCall('run_tests', { amountUSD: 500.0 });
    expect(overspend.valid).toBe(false);
    expect(overspend.reason).toContain('exceeding financial authority limit');
  });

  it('6. System prompt boundary generation formats all constraints accurately', () => {
    const prompt = boundary.formatBoundarySystemPrompt();
    expect(prompt).toContain('[SELF-KNOWLEDGE & CAPABILITY BOUNDARIES]');
    expect(prompt).toContain('Autonomous Code Assistant');
    expect(prompt).toContain('Internet Access: Disabled');
    expect(prompt).toContain('read_file, write_file, run_tests');
    expect(prompt).toContain('$250.00 USD');
    expect(prompt).toContain('deploy to production');
  });
});
