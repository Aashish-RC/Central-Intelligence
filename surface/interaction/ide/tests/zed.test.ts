import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { ZedIdeAdapter } from '../zed_adapter.js';

describe('Zed IDE Adapter (Task 18.4)', () => {
  it('should interact with AI assistant from Zed IDE panel', () => {
    const adapter = new ZedIdeAdapter();

    const reply = adapter.sendAssistantMessage(
      'How to optimize this Rust iterator?',
      ['src/main.rs', 'src/lib.rs']
    );

    assert.equal(reply.role, 'assistant');
    assert.ok(reply.content.includes('[Zed Assistant Panel]'));
    assert.deepEqual(reply.contextFiles, ['src/main.rs', 'src/lib.rs']);

    const history = adapter.getAssistantHistory();
    assert.equal(history.length, 2);
  });

  it('should execute inline code edit on editor selection', () => {
    const adapter = new ZedIdeAdapter();
    adapter.setFileBuffer('src/service.ts', 'function fetchData() { return null; }');

    const edit = adapter.requestInlineEdit(
      {
        filePath: 'src/service.ts',
        startLine: 1,
        endLine: 1,
        selectedText: 'function fetchData() { return null; }',
      },
      'Make this function async'
    );

    assert.equal(edit.applied, true);
    assert.equal(edit.newText, 'async function fetchData() { return null; }');
  });
});
