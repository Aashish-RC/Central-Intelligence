/**
 * Tldraw Infinite Canvas Adapter
 * Supports shapes, whiteboard elements, annotations, and real-time canvas document state.
 */

export interface TLShapeProps {
  w?: number;
  h?: number;
  geo?: 'rectangle' | 'ellipse' | 'diamond' | 'triangle';
  color?: string;
  fill?: 'none' | 'semi' | 'solid';
  dash?: 'draw' | 'solid' | 'dashed';
  size?: 's' | 'm' | 'l' | 'xl';
  text?: string;
  start?: { x: number; y: number; binding?: string };
  end?: { x: number; y: number; binding?: string };
  [key: string]: any;
}

export interface TLShape {
  id: string;
  typeName: 'shape';
  type: 'geo' | 'text' | 'arrow' | 'draw' | 'frame';
  x: number;
  y: number;
  rotation?: number;
  index: string;
  parentId: string;
  props: TLShapeProps;
}

export interface TldrawCanvasDoc {
  schemaVersion: number;
  id: string;
  name: string;
  records: Record<string, any>;
  shapes: TLShape[];
  createdAt: string;
}

export class TldrawCanvasAdapter {
  /**
   * Create a new infinite canvas document
   */
  public createCanvas(id: string = `canvas_${Date.now()}`, name: string = 'Untitled Canvas'): TldrawCanvasDoc {
    return {
      schemaVersion: 2,
      id,
      name,
      records: {
        'page:page': { id: 'page:page', typeName: 'page', name: 'Page 1', index: 'a1' },
      },
      shapes: [],
      createdAt: new Date().toISOString(),
    };
  }

  /**
   * Add a geometric shape (rectangle, ellipse, diamond) to canvas
   */
  public addBox(
    canvas: TldrawCanvasDoc,
    options: {
      id?: string;
      x: number;
      y: number;
      w: number;
      h: number;
      geo?: 'rectangle' | 'ellipse' | 'diamond';
      text?: string;
      color?: string;
    }
  ): TLShape {
    const shapeId = options.id || `shape_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`;
    const shape: TLShape = {
      id: shapeId,
      typeName: 'shape',
      type: 'geo',
      x: options.x,
      y: options.y,
      index: `a${canvas.shapes.length + 1}`,
      parentId: 'page:page',
      props: {
        w: options.w,
        h: options.h,
        geo: options.geo || 'rectangle',
        color: options.color || 'black',
        fill: 'semi',
        text: options.text || '',
        size: 'm',
      },
    };

    canvas.shapes.push(shape);
    canvas.records[shapeId] = shape;
    return shape;
  }

  /**
   * Add a text label to canvas
   */
  public addText(
    canvas: TldrawCanvasDoc,
    options: {
      id?: string;
      x: number;
      y: number;
      text: string;
      color?: string;
      size?: 's' | 'm' | 'l' | 'xl';
    }
  ): TLShape {
    const shapeId = options.id || `shape_text_${Date.now()}`;
    const shape: TLShape = {
      id: shapeId,
      typeName: 'shape',
      type: 'text',
      x: options.x,
      y: options.y,
      index: `a${canvas.shapes.length + 1}`,
      parentId: 'page:page',
      props: {
        text: options.text,
        color: options.color || 'black',
        size: options.size || 'm',
      },
    };

    canvas.shapes.push(shape);
    canvas.records[shapeId] = shape;
    return shape;
  }

  /**
   * Add an arrow connector between shapes or coordinates
   */
  public addArrow(
    canvas: TldrawCanvasDoc,
    options: {
      id?: string;
      fromId?: string;
      toId?: string;
      startX: number;
      startY: number;
      endX: number;
      endY: number;
      text?: string;
    }
  ): TLShape {
    const shapeId = options.id || `shape_arrow_${Date.now()}`;
    const shape: TLShape = {
      id: shapeId,
      typeName: 'shape',
      type: 'arrow',
      x: options.startX,
      y: options.startY,
      index: `a${canvas.shapes.length + 1}`,
      parentId: 'page:page',
      props: {
        start: { x: 0, y: 0, binding: options.fromId },
        end: { x: options.endX - options.startX, y: options.endY - options.startY, binding: options.toId },
        text: options.text || '',
      },
    };

    canvas.shapes.push(shape);
    canvas.records[shapeId] = shape;
    return shape;
  }

  /**
   * Compute bounding box across all canvas shapes
   */
  public getBounds(canvas: TldrawCanvasDoc): { minX: number; minY: number; maxX: number; maxY: number; width: number; height: number } {
    if (canvas.shapes.length === 0) {
      return { minX: 0, minY: 0, maxX: 800, maxY: 600, width: 800, height: 600 };
    }

    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;

    for (const shape of canvas.shapes) {
      minX = Math.min(minX, shape.x);
      minY = Math.min(minY, shape.y);
      const w = shape.props.w || 100;
      const h = shape.props.h || 50;
      maxX = Math.max(maxX, shape.x + w);
      maxY = Math.max(maxY, shape.y + h);
    }

    return {
      minX,
      minY,
      maxX,
      maxY,
      width: Math.max(100, maxX - minX + 80),
      height: Math.max(100, maxY - minY + 80),
    };
  }

  /**
   * Render SVG snapshot of interactive canvas
   */
  public renderSvgSnapshot(canvas: TldrawCanvasDoc): string {
    const bounds = this.getBounds(canvas);
    let svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${bounds.minX - 40} ${bounds.minY - 40} ${bounds.width} ${bounds.height}" width="${bounds.width}" height="${bounds.height}">`;
    svg += `<rect x="${bounds.minX - 40}" y="${bounds.minY - 40}" width="${bounds.width}" height="${bounds.height}" fill="#fafafa"/>`;

    for (const shape of canvas.shapes) {
      if (shape.type === 'geo') {
        const fill = shape.props.color === 'blue' ? '#3b82f6' : '#22c55e';
        svg += `<rect x="${shape.x}" y="${shape.y}" width="${shape.props.w}" height="${shape.props.h}" rx="8" fill="${fill}" opacity="0.8" stroke="#0f172a" stroke-width="2"/>`;
        if (shape.props.text) {
          svg += `<text x="${shape.x + (shape.props.w || 100) / 2}" y="${shape.y + (shape.props.h || 50) / 2 + 5}" font-family="sans-serif" font-size="14" fill="#ffffff" text-anchor="middle">${shape.props.text}</text>`;
        }
      } else if (shape.type === 'text') {
        svg += `<text x="${shape.x}" y="${shape.y + 15}" font-family="sans-serif" font-size="16" fill="#0f172a" font-weight="bold">${shape.props.text}</text>`;
      }
    }

    svg += `</svg>`;
    return svg;
  }

  /**
   * Serialize canvas to JSON
   */
  public serializeToJson(canvas: TldrawCanvasDoc): string {
    return JSON.stringify(canvas, null, 2);
  }
}
