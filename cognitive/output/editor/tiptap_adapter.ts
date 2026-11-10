/**
 * TipTap Headless Rich-Text Editor Adapter
 * Supports ProseMirror JSON document model, Markdown parsing/serialization,
 * code blocks, and real-time document manipulation.
 */

export interface TipTapMark {
  type: 'bold' | 'italic' | 'code' | 'link';
  attrs?: Record<string, any>;
}

export interface TipTapNode {
  type: 'paragraph' | 'heading' | 'codeBlock' | 'bulletList' | 'listItem' | 'text';
  text?: string;
  attrs?: {
    level?: number;
    language?: string;
    [key: string]: any;
  };
  marks?: TipTapMark[];
  content?: TipTapNode[];
}

export interface TipTapDoc {
  type: 'doc';
  content: TipTapNode[];
}

export interface TipTapEditorOptions {
  editable?: boolean;
  autofocus?: boolean;
  extensions?: string[];
}

export class TipTapAdapter {
  private options: TipTapEditorOptions;

  constructor(options: TipTapEditorOptions = { editable: true }) {
    this.options = options;
  }

  /**
   * Parse markdown text into a TipTap / ProseMirror JSON document tree
   */
  public parseMarkdown(markdown: string): TipTapDoc {
    const lines = markdown.split(/\r?\n/);
    const contentNodes: TipTapNode[] = [];
    let i = 0;

    while (i < lines.length) {
      const line = lines[i];

      // Code block
      if (line.startsWith('```')) {
        const lang = line.slice(3).trim();
        const codeLines: string[] = [];
        i++;
        while (i < lines.length && !lines[i].startsWith('```')) {
          codeLines.push(lines[i]);
          i++;
        }
        contentNodes.push({
          type: 'codeBlock',
          attrs: { language: lang || 'plaintext' },
          content: [{ type: 'text', text: codeLines.join('\n') }],
        });
        i++;
        continue;
      }

      // Heading
      const headingMatch = line.match(/^(#{1,6})\s+(.*)$/);
      if (headingMatch) {
        const level = headingMatch[1].length;
        const text = headingMatch[2];
        contentNodes.push({
          type: 'heading',
          attrs: { level },
          content: this.parseInlineMarks(text),
        });
        i++;
        continue;
      }

      // Bullet list item
      if (line.match(/^[\*\-]\s+(.*)$/)) {
        const listItems: TipTapNode[] = [];
        while (i < lines.length && lines[i].match(/^[\*\-]\s+(.*)$/)) {
          const itemText = lines[i].replace(/^[\*\-]\s+/, '');
          listItems.push({
            type: 'listItem',
            content: [{ type: 'paragraph', content: this.parseInlineMarks(itemText) }],
          });
          i++;
        }
        contentNodes.push({
          type: 'bulletList',
          content: listItems,
        });
        continue;
      }

      // Paragraph (skip completely empty lines if we have content)
      if (line.trim().length > 0) {
        contentNodes.push({
          type: 'paragraph',
          content: this.parseInlineMarks(line),
        });
      }

      i++;
    }

    return {
      type: 'doc',
      content: contentNodes.length > 0 ? contentNodes : [{ type: 'paragraph', content: [] }],
    };
  }

  /**
   * Parse inline formatting (bold, italic, inline code)
   */
  private parseInlineMarks(text: string): TipTapNode[] {
    if (!text) return [];
    
    // Simple inline parser for **bold** and `code`
    const nodes: TipTapNode[] = [];
    const regex = /(\*\*[^*]+\*\*|`[^`]+`|[^*`]+)/g;
    let match;

    while ((match = regex.exec(text)) !== null) {
      const part = match[0];
      if (part.startsWith('**') && part.endsWith('**')) {
        nodes.push({
          type: 'text',
          text: part.slice(2, -2),
          marks: [{ type: 'bold' }],
        });
      } else if (part.startsWith('`') && part.endsWith('`')) {
        nodes.push({
          type: 'text',
          text: part.slice(1, -1),
          marks: [{ type: 'code' }],
        });
      } else if (part.length > 0) {
        nodes.push({
          type: 'text',
          text: part,
        });
      }
    }

    return nodes.length > 0 ? nodes : [{ type: 'text', text }];
  }

  /**
   * Convert TipTap doc back into markdown format
   */
  public toMarkdown(doc: TipTapDoc): string {
    const parts: string[] = [];

    for (const node of doc.content) {
      if (node.type === 'heading') {
        const prefix = '#'.repeat(node.attrs?.level || 1);
        const text = this.inlineNodesToText(node.content);
        parts.push(`${prefix} ${text}`);
      } else if (node.type === 'paragraph') {
        parts.push(this.inlineNodesToText(node.content));
      } else if (node.type === 'codeBlock') {
        const lang = node.attrs?.language || '';
        const code = node.content?.map((n) => n.text).join('') || '';
        parts.push(`\`\`\`${lang}\n${code}\n\`\`\``);
      } else if (node.type === 'bulletList') {
        for (const item of node.content || []) {
          const itemText = item.content?.map((p) => this.inlineNodesToText(p.content)).join(' ') || '';
          parts.push(`* ${itemText}`);
        }
      }
    }

    return parts.join('\n\n');
  }

  private inlineNodesToText(nodes?: TipTapNode[]): string {
    if (!nodes) return '';
    return nodes
      .map((node) => {
        let t = node.text || '';
        if (node.marks?.some((m) => m.type === 'bold')) {
          t = `**${t}**`;
        }
        if (node.marks?.some((m) => m.type === 'code')) {
          t = `\`${t}\``;
        }
        return t;
      })
      .join('');
  }

  /**
   * Render TipTap document as HTML
   */
  public toHtml(doc: TipTapDoc): string {
    const htmlParts: string[] = [];
    for (const node of doc.content) {
      if (node.type === 'heading') {
        const level = node.attrs?.level || 1;
        htmlParts.push(`<h${level}>${this.inlineNodesToText(node.content)}</h${level}>`);
      } else if (node.type === 'paragraph') {
        htmlParts.push(`<p>${this.inlineNodesToText(node.content)}</p>`);
      } else if (node.type === 'codeBlock') {
        const lang = node.attrs?.language || 'plaintext';
        const code = node.content?.map((n) => n.text).join('') || '';
        htmlParts.push(`<pre><code class="language-${lang}">${code}</code></pre>`);
      } else if (node.type === 'bulletList') {
        const items = (node.content || [])
          .map((item) => `<li>${item.content?.map((p) => this.inlineNodesToText(p.content)).join(' ')}</li>`)
          .join('');
        htmlParts.push(`<ul>${items}</ul>`);
      }
    }
    return htmlParts.join('\n');
  }
}
