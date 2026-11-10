import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { MermaidAdapter } from '../mermaid_adapter.js';

describe('Mermaid Diagram Adapter', () => {
  const adapter = new MermaidAdapter();

  it('can render a flowchart from mermaid text syntax', () => {
    const flowchartCode = `flowchart TD
      L1[Perception] --> L4[Reasoning]
      L4 --> L6[Output Generation]
      L6 --> L7[Learning Feedback]`;

    const validation = adapter.validateSyntax(flowchartCode);
    assert.equal(validation.valid, true);

    const parsed = adapter.parseDiagram(flowchartCode);
    assert.equal(parsed.type, 'flowchart');
    assert.equal(parsed.direction, 'TD');
    assert.equal(parsed.nodes.length, 4);
    assert.equal(parsed.links.length, 3);

    const result = adapter.renderSvg(flowchartCode, 'Central Intelligence Flow');
    assert.equal(result.diagramType, 'flowchart');
    assert.equal(result.nodeCount, 4);
    assert.ok(result.svg.startsWith('<svg'));
    assert.ok(result.svg.includes('aria-label="Central Intelligence Flow"'));
    assert.ok(result.svg.includes('Perception'));
    assert.ok(result.svg.includes('Output Generation'));
  });

  it('validates syntax and detects unsupported or empty diagrams', () => {
    const invalid = adapter.validateSyntax('invalidFormat xyz');
    assert.equal(invalid.valid, false);
    assert.ok(invalid.errors.length > 0);

    const empty = adapter.validateSyntax('   ');
    assert.equal(empty.valid, false);
  });
});

