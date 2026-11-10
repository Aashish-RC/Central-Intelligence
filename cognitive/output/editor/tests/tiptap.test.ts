import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { TipTapAdapter } from '../tiptap_adapter.js';

describe('TipTap Rich-Text Editor Adapter', () => {
  const adapter = new TipTapAdapter();

  it('can render editable rich-text document with markdown', () => {
    const markdown = `# Architecture Overview

This is the **Central Intelligence** system doc.

* Layer 6 Output
* Layer 7 Learning

\`\`\`typescript
const status = "operational";
\`\`\``;

    const doc = adapter.parseMarkdown(markdown);
    assert.equal(doc.type, 'doc');
    assert.equal(doc.content.length, 4);

    // Check heading
    const heading = doc.content[0];
    assert.equal(heading.type, 'heading');
    assert.equal(heading.attrs?.level, 1);

    // Check paragraph and inline bold mark
    const p = doc.content[1];
    assert.equal(p.type, 'paragraph');
    const boldNode = p.content?.find((n) => n.marks?.some((m) => m.type === 'bold'));
    assert.ok(boldNode);
    assert.equal(boldNode?.text, 'Central Intelligence');

    // Check bullet list
    const list = doc.content[2];
    assert.equal(list.type, 'bulletList');
    assert.equal(list.content?.length, 2);

    // Check code block
    const code = doc.content[3];
    assert.equal(code.type, 'codeBlock');
    assert.equal(code.attrs?.language, 'typescript');
  });

  it('can round-trip document back to markdown and HTML', () => {
    const initialMd = `## Subsystem Status\n\nAll nodes are **synchronized**.\n\n* Alpha\n* Beta`;
    const doc = adapter.parseMarkdown(initialMd);
    const serializedMd = adapter.toMarkdown(doc);
    assert.ok(serializedMd.includes('## Subsystem Status'));
    assert.ok(serializedMd.includes('**synchronized**'));

    const html = adapter.toHtml(doc);
    assert.ok(html.includes('<h2>Subsystem Status</h2>'));
    assert.ok(html.includes('<ul>'));
    assert.ok(html.includes('<li>'));
  });
});

