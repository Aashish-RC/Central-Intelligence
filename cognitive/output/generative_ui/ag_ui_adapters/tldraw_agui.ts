/**
 * Tldraw AG-UI Adapter
 * Wraps Tldraw infinite canvas documents into CopilotKit generative UI widgets for chat embedding.
 */

import { GenerativeUIWidget, CopilotKitAdapter } from '../copilotkit_adapter.js';
import { TldrawCanvasDoc, TldrawCanvasAdapter } from '../../canvas/tldraw_adapter.js';

export interface TldrawAGUIProps {
  canvasId: string;
  canvas: TldrawCanvasDoc;
  svgSnapshot: string;
  shapeCount: number;
  interactive: boolean;
  viewBox: { minX: number; minY: number; width: number; height: number };
}

export class TldrawAGUIAdapter {
  private tldraw: TldrawCanvasAdapter;

  constructor(tldraw: TldrawCanvasAdapter = new TldrawCanvasAdapter()) {
    this.tldraw = tldraw;
  }

  /**
   * Wrap a Tldraw canvas into a CopilotKit Generative UI Widget
   */
  public toGenerativeWidget(
    canvas: TldrawCanvasDoc,
    options: { interactive?: boolean } = {}
  ): GenerativeUIWidget<TldrawAGUIProps> {
    const bounds = this.tldraw.getBounds(canvas);
    return {
      id: `widget_canvas_${canvas.id}`,
      type: 'canvas',
      props: {
        canvasId: canvas.id,
        canvas,
        svgSnapshot: this.tldraw.renderSvgSnapshot(canvas),
        shapeCount: canvas.shapes.length,
        interactive: options.interactive ?? true,
        viewBox: {
          minX: bounds.minX,
          minY: bounds.minY,
          width: bounds.width,
          height: bounds.height,
        },
      },
      version: '1.0.0',
      createdAt: new Date().toISOString(),
    };
  }

  /**
   * Register Tldraw manipulation actions on CopilotKit adapter
   */
  public registerCanvasActions(
    copilotAdapter: CopilotKitAdapter,
    handler?: (action: string, params: Record<string, any>) => any
  ): void {
    copilotAdapter.registerAction({
      name: 'add_canvas_element',
      description: 'Add a new shape or box to the infinite canvas',
      parameters: [
        { name: 'canvasId', type: 'string', description: 'Target canvas ID', required: true },
        { name: 'text', type: 'string', description: 'Label text', required: true },
        { name: 'x', type: 'number', description: 'X position', required: true },
        { name: 'y', type: 'number', description: 'Y position', required: true },
      ],
      handler: (args) => {
        if (handler) return handler('add_canvas_element', args);
        return { success: true, shapeId: `shape_${Date.now()}` };
      },
    });
  }
}

