import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { CopilotKitAdapter } from '../../copilotkit_adapter.js';
import { TipTapAdapter } from '../../../editor/tiptap_adapter.js';
import { TldrawCanvasAdapter } from '../../../canvas/tldraw_adapter.js';
import { TipTapAGUIAdapter } from '../tiptap_agui.js';
import { TldrawAGUIAdapter } from '../tldraw_agui.js';

describe('AG-UI Adapters for TipTap & Tldraw', () => {
  const copilot = new CopilotKitAdapter();
  const tiptap = new TipTapAdapter();
  const tldraw = new TldrawCanvasAdapter();
  const tiptapAGUI = new TipTapAGUIAdapter(tiptap);
  const tldrawAGUI = new TldrawAGUIAdapter(tldraw);

  it('TipTap editor renders inside CopilotKit chat surface', () => {
    const doc = tiptap.parseMarkdown('# Mission Debrief\n\nAll objectives achieved with zero casualties.');
    const widget = tiptapAGUI.toGenerativeWidget('debrief-001', doc);

    assert.equal(widget.type, 'editor');
    assert.equal(widget.props.documentId, 'debrief-001');
    assert.ok(widget.props.htmlPreview.includes('<h1>Mission Debrief</h1>'));

    tiptapAGUI.registerEditorActions(copilot);
    assert.ok(copilot.getAction('update_document_markdown'));

    const chatResponse = copilot.serializeForChat(
      'Here is the requested document draft. You can edit it directly:',
      widget
    );

    assert.equal(chatResponse.protocol, 'ag-ui-v1');
    assert.ok(chatResponse.widget);
    assert.equal(chatResponse.widget?.type, 'editor');
    assert.ok(chatResponse.actions.some((a) => a.name === 'update_document_markdown'));
  });

  it('Tldraw canvas renders inside CopilotKit chat surface', () => {
    const canvas = tldraw.createCanvas('infra-diagram', 'Infrastructure Map');
    tldraw.addBox(canvas, { x: 50, y: 50, w: 120, h: 60, text: 'Gateway' });
    tldraw.addBox(canvas, { x: 250, y: 50, w: 120, h: 60, text: 'Cluster' });

    const widget = tldrawAGUI.toGenerativeWidget(canvas);

    assert.equal(widget.type, 'canvas');
    assert.equal(widget.props.canvasId, 'infra-diagram');
    assert.equal(widget.props.shapeCount, 2);
    assert.ok(widget.props.svgSnapshot.includes('Gateway'));

    tldrawAGUI.registerCanvasActions(copilot);
    assert.ok(copilot.getAction('add_canvas_element'));

    const chatResponse = copilot.serializeForChat(
      'Here is the current canvas layout:',
      widget
    );

    assert.equal(chatResponse.protocol, 'ag-ui-v1');
    assert.ok(chatResponse.widget);
    assert.equal(chatResponse.widget?.type, 'canvas');
    assert.ok(chatResponse.actions.some((a) => a.name === 'add_canvas_element'));
  });
});
