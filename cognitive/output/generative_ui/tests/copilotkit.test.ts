import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { CopilotKitAdapter } from '../copilotkit_adapter.js';

describe('CopilotKit Generative UI Adapter', () => {
  let adapter: CopilotKitAdapter;

  beforeEach(() => {
    adapter = new CopilotKitAdapter();
  });

  it('can render a generative UI form inside a chat response', () => {
    const formWidget = adapter.renderForm({
      id: 'user-feedback-form',
      title: 'Mission Evaluation Form',
      fields: [
        { id: 'rating', label: 'Quality Score', type: 'number', required: true },
        { id: 'feedback', label: 'Comments', type: 'text', required: false },
      ],
      submitAction: 'submit_feedback',
    });

    const envelope = adapter.serializeForChat(
      'Please fill out the post-operation feedback below:',
      formWidget
    );

    assert.equal(envelope.protocol, 'ag-ui-v1');
    assert.ok(envelope.content.includes('post-operation feedback'));
    assert.ok(envelope.widget);
    assert.equal(envelope.widget?.type, 'form');
    assert.equal(envelope.widget?.props.title, 'Mission Evaluation Form');
    assert.equal(envelope.widget?.props.fields.length, 2);
  });

  it('can render progress bar widgets with bounded values', () => {
    const progress = adapter.renderProgressBar(45, 'Synthesizing output payload');
    assert.equal(progress.type, 'progress_bar');
    assert.equal(progress.props.progress, 45);
    assert.equal(progress.props.status, 'in_progress');

    const clamped = adapter.renderProgressBar(120, 'Clamped task');
    assert.equal(clamped.props.progress, 100);
  });

  it('can render streaming tables', () => {
    const table = adapter.renderStreamingTable(
      'logs-stream',
      [
        { key: 'timestamp', header: 'Time' },
        { key: 'event', header: 'Event' },
      ],
      [{ timestamp: '12:00:01', event: 'Initiated' }],
      true
    );

    assert.equal(table.type, 'streaming_table');
    assert.equal(table.props.isStreaming, true);
    assert.equal(table.props.rows.length, 1);
  });

  it('registers and lists CopilotKit actions', () => {
    adapter.registerAction({
      name: 'approve_output',
      description: 'Approve generated document for release',
      parameters: [{ name: 'reason', type: 'string', description: 'Approval note', required: true }],
    });

    const action = adapter.getAction('approve_output');
    assert.ok(action);
    assert.equal(adapter.listActions().length, 1);
  });
});
