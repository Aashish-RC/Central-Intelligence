import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { OpenCodeAdapter } from '../opencode_adapter.js';

describe('OpenCode Terminal Adapter (Task 18.3)', () => {
  it('should interact with AI agent from terminal surface', () => {
    const adapter = new OpenCodeAdapter('claude-3-7-sonnet');
    assert.equal(adapter.getModel(), 'claude-3-7-sonnet');

    // Send user prompt from terminal
    const reply = adapter.sendPrompt('Refactor the database connection pool');
    assert.equal(reply.role, 'assistant');
    assert.ok(reply.content.includes('OpenCode Terminal Agent'));
    assert.ok(reply.ansiFormatted?.includes('\x1b[32m')); // Green ANSI bullet

    // History should reflect both turns
    const history = adapter.getHistory();
    assert.equal(history.length, 2);
    assert.equal(history[0].role, 'user');
    assert.equal(history[1].role, 'assistant');
  });

  it('should format code diffs with ANSI color syntax', () => {
    const adapter = new OpenCodeAdapter();
    const diff = '@@ -1,2 +1,2 @@\n-const oldDb = connect();\n+const pool = createPool();';
    const formatted = adapter.formatDiff(diff);

    assert.ok(formatted.includes('\x1b[31m-const oldDb')); // Red removal
    assert.ok(formatted.includes('\x1b[32m+const pool'));  // Green addition
  });

  it('should execute tool commands from terminal surface', () => {
    const adapter = new OpenCodeAdapter();
    const res = adapter.executeToolCommand('git status');
    assert.equal(res.exitCode, 0);
    assert.ok(res.output.includes('On branch main'));
  });
});
