/**
 * Mermaid Diagram Adapter
 * Text-based diagram rendering for Flowcharts, ERDs, Sequence diagrams, and graphs.
 */

export type DiagramType =
  | 'flowchart'
  | 'sequenceDiagram'
  | 'erDiagram'
  | 'classDiagram'
  | 'stateDiagram'
  | 'gitGraph';

export interface DiagramNode {
  id: string;
  label: string;
  shape?: 'box' | 'round' | 'diamond' | 'circle';
}

export interface DiagramLink {
  from: string;
  to: string;
  label?: string;
  arrowType?: 'directed' | 'open' | 'dotted';
}

export interface ParsedDiagram {
  type: DiagramType;
  direction?: 'TD' | 'TB' | 'LR' | 'RL';
  nodes: DiagramNode[];
  links: DiagramLink[];
  rawText: string;
}

export interface MermaidRenderResult {
  svg: string;
  diagramType: DiagramType;
  nodeCount: number;
  ariaLabel: string;
}

export class MermaidAdapter {
  private supportedTypes: DiagramType[] = [
    'flowchart',
    'sequenceDiagram',
    'erDiagram',
    'classDiagram',
    'stateDiagram',
    'gitGraph',
  ];

  /**
   * Validate mermaid syntax
   */
  public validateSyntax(text: string): { valid: boolean; errors: string[] } {
    const trimmed = text.trim();
    const errors: string[] = [];

    if (!trimmed) {
      errors.push('Diagram source text is empty');
      return { valid: false, errors };
    }

    const firstLine = trimmed.split(/\r?\n/)[0].trim();
    const matchedType = this.supportedTypes.find((t) =>
      firstLine.startsWith(t) || firstLine.startsWith(`graph `)
    );

    if (!matchedType) {
      errors.push(`Unrecognized diagram type in: "${firstLine}"`);
    }

    return {
      valid: errors.length === 0,
      errors,
    };
  }

  /**
   * Parse diagram text into structured components
   */
  public parseDiagram(text: string): ParsedDiagram {
    const lines = text
      .trim()
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter((l) => l.length > 0 && !l.startsWith('%%'));

    const header = lines[0] || 'flowchart TD';
    let type: DiagramType = 'flowchart';
    let direction: 'TD' | 'TB' | 'LR' | 'RL' = 'TD';

    if (header.startsWith('flowchart') || header.startsWith('graph')) {
      type = 'flowchart';
      const parts = header.split(/\s+/);
      if (parts[1] && ['TD', 'TB', 'LR', 'RL'].includes(parts[1])) {
        direction = parts[1] as any;
      }
    } else if (header.startsWith('sequenceDiagram')) {
      type = 'sequenceDiagram';
    } else if (header.startsWith('erDiagram')) {
      type = 'erDiagram';
    } else if (header.startsWith('classDiagram')) {
      type = 'classDiagram';
    } else if (header.startsWith('stateDiagram')) {
      type = 'stateDiagram';
    } else if (header.startsWith('gitGraph')) {
      type = 'gitGraph';
    }

    const nodesMap = new Map<string, DiagramNode>();
    const links: DiagramLink[] = [];

    for (let i = 1; i < lines.length; i++) {
      const line = lines[i].trim();

      // Match flowchart links: A[Label A] -->|Text| B(Label B) or A --> B
      const linkMatch = line.match(/^([A-Za-z0-9_\-]+)(?:\[(.*?)\]|\((.*?)\))?\s*(-->|-.->|==>)(?:\|(.*?)\|)?\s*([A-Za-z0-9_\-]+)(?:\[(.*?)\]|\((.*?)\))?/);
      if (linkMatch) {
        const fromId = linkMatch[1];
        const fromLabel = linkMatch[2] || linkMatch[3] || fromId;
        const arrow = linkMatch[4];
        const linkText = linkMatch[5];
        const toId = linkMatch[6];
        const toLabel = linkMatch[7] || linkMatch[8] || toId;

        const updateNode = (id: string, label: string) => {
          const existing = nodesMap.get(id);
          if (!existing || (existing.label === id && label !== id)) {
            nodesMap.set(id, { id, label });
          }
        };

        updateNode(fromId, fromLabel);
        updateNode(toId, toLabel);

        links.push({
          from: fromId,
          to: toId,
          label: linkText,
          arrowType: arrow.includes('.') ? 'dotted' : 'directed',
        });
      } else {
        // Individual node declaration: A[Label]
        const singleMatch = line.match(/^([A-Za-z0-9_\-]+)(?:\[(.*?)\]|\((.*?)\))/);
        if (singleMatch) {
          const id = singleMatch[1];
          const label = singleMatch[2] || singleMatch[3] || id;
          nodesMap.set(id, { id, label });
        }
      }
    }

    return {
      type,
      direction,
      nodes: Array.from(nodesMap.values()),
      links,
      rawText: text,
    };
  }

  /**
   * Render SVG markup from mermaid text syntax
   */
  public renderSvg(text: string, title: string = 'Generated Architecture Diagram'): MermaidRenderResult {
    const validation = this.validateSyntax(text);
    if (!validation.valid) {
      throw new Error(`Invalid mermaid diagram: ${validation.errors.join(', ')}`);
    }

    const parsed = this.parseDiagram(text);
    const width = Math.max(400, parsed.nodes.length * 150);
    const height = Math.max(300, (parsed.links.length + 1) * 90);

    // Generate accessible SVG
    let svgContent = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" role="img" aria-label="${title}">`;
    svgContent += `<title>${title}</title>`;
    svgContent += `<desc>Mermaid ${parsed.type} containing ${parsed.nodes.length} nodes and ${parsed.links.length} connections.</desc>`;
    svgContent += `<defs><marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#3b82f6"/></marker></defs>`;
    svgContent += `<g class="mermaid-diagram" data-type="${parsed.type}">`;

    // Render nodes
    parsed.nodes.forEach((node, index) => {
      const x = 50 + (index % 3) * 140;
      const y = 50 + Math.floor(index / 3) * 90;
      svgContent += `<g class="node" id="node-${node.id}">`;
      svgContent += `<rect x="${x}" y="${y}" width="120" height="45" rx="6" fill="#1e293b" stroke="#3b82f6" stroke-width="2"/>`;
      svgContent += `<text x="${x + 60}" y="${y + 26}" fill="#f8fafc" font-family="sans-serif" font-size="12" text-anchor="middle">${node.label}</text>`;
      svgContent += `</g>`;
    });

    svgContent += `</g></svg>`;

    return {
      svg: svgContent,
      diagramType: parsed.type,
      nodeCount: parsed.nodes.length,
      ariaLabel: title,
    };
  }
}
