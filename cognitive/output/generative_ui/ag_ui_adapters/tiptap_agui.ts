/**
 * TipTap AG-UI Adapter
 * Wraps TipTap editor documents into CopilotKit generative UI widgets for chat embedding.
 */

import { GenerativeUIWidget, CopilotKitAdapter } from '../copilotkit_adapter.js';
import { TipTapDoc, TipTapAdapter } from '../../editor/tiptap_adapter.js';

export interface TipTapAGUIProps {
  documentId: string;
  doc: TipTapDoc;
  htmlPreview: string;
  markdown: string;
  editable: boolean;
  activeUsers: string[];
}

export class TipTapAGUIAdapter {
  private tiptap: TipTapAdapter;

  constructor(tiptap: TipTapAdapter = new TipTapAdapter()) {
    this.tiptap = tiptap;
  }

  /**
   * Wrap a TipTap document into a CopilotKit Generative UI Widget
   */
  public toGenerativeWidget(
    documentId: string,
    doc: TipTapDoc,
    options: { editable?: boolean; activeUsers?: string[] } = {}
  ): GenerativeUIWidget<TipTapAGUIProps> {
    return {
      id: `widget_editor_${documentId}`,
      type: 'editor',
      props: {
        documentId,
        doc,
        htmlPreview: this.tiptap.toHtml(doc),
        markdown: this.tiptap.toMarkdown(doc),
        editable: options.editable ?? true,
        activeUsers: options.activeUsers || ['current_user'],
      },
      version: '1.0.0',
      createdAt: new Date().toISOString(),
    };
  }

  /**
   * Register TipTap manipulation actions on CopilotKit adapter
   */
  public registerEditorActions(
    copilotAdapter: CopilotKitAdapter,
    handler?: (action: string, params: Record<string, any>) => any
  ): void {
    copilotAdapter.registerAction({
      name: 'update_document_markdown',
      description: 'Update the rich-text editor content with new markdown text',
      parameters: [
        { name: 'documentId', type: 'string', description: 'Target document ID', required: true },
        { name: 'markdown', type: 'string', description: 'New markdown content', required: true },
      ],
      handler: (args) => {
        if (handler) return handler('update_document_markdown', args);
        return { success: true, doc: this.tiptap.parseMarkdown(args.markdown) };
      },
    });
  }
}

