import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { TldrawCanvasAdapter } from '../tldraw_adapter.js';

describe('Tldraw Infinite Canvas Adapter', () => {
  const adapter = new TldrawCanvasAdapter();

  it('can render an interactive canvas with shapes and text', () => {
    const canvas = adapter.createCanvas('ci-whiteboard', 'Agent Architecture Canvas');
    assert.equal(canvas.name, 'Agent Architecture Canvas');
    assert.equal(canvas.shapes.length, 0);

    const box1 = adapter.addBox(canvas, {
      x: 100,
      y: 100,
      w: 180,
      h: 80,
      geo: 'rectangle',
      text: 'Cognitive Engine',
      color: 'blue',
    });

    const box2 = adapter.addBox(canvas, {
      x: 400,
      y: 100,
      w: 180,
      h: 80,
      geo: 'rectangle',
      text: 'Learning System',
      color: 'green',
    });

    const title = adapter.addText(canvas, {
      x: 100,
      y: 40,
      text: 'Layer 6 & 7 Workspace',
    });

    const arrow = adapter.addArrow(canvas, {
      fromId: box1.id,
      toId: box2.id,
      startX: 280,
      startY: 140,
      endX: 400,
      endY: 140,
      text: 'RL updates',
    });

    assert.equal(canvas.shapes.length, 4);
    assert.equal(canvas.records[box1.id].type, 'geo');
    assert.equal(canvas.records[title.id].type, 'text');
    assert.equal(canvas.records[arrow.id].type, 'arrow');

    const bounds = adapter.getBounds(canvas);
    assert.ok(bounds.width > 300);
    assert.ok(bounds.height > 100);

    const svg = adapter.renderSvgSnapshot(canvas);
    assert.ok(svg.includes('<svg'));
    assert.ok(svg.includes('Cognitive Engine'));
    assert.ok(svg.includes('Layer 6 & 7 Workspace'));

    const json = adapter.serializeToJson(canvas);
    assert.ok(json.includes('ci-whiteboard'));
  });
});

