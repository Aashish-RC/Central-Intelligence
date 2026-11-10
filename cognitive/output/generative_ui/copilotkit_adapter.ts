/**
 * CopilotKit Generative UI Adapter (AG-UI Protocol)
 * Enables rendering dynamic UI widgets (forms, progress bars, streaming tables)
 * inside conversational chat responses.
 */

export interface FormField {
  id: string;
  label: string;
  type: 'text' | 'number' | 'select' | 'boolean' | 'date';
  required?: boolean;
  options?: Array<{ label: string; value: string | number }>;
  defaultValue?: any;
}

export interface FormConfig {
  id: string;
  title: string;
  fields: FormField[];
  submitLabel?: string;
  submitAction: string;
}

export interface TableColumn {
  key: string;
  header: string;
  type?: 'text' | 'number' | 'badge';
}

export interface GenerativeUIWidget<T = any> {
  id: string;
  type: 'form' | 'progress_bar' | 'streaming_table' | 'canvas' | 'editor';
  props: T;
  version: string;
  createdAt: string;
}

export interface CopilotKitAction {
  name: string;
  description: string;
  parameters: Array<{
    name: string;
    type: string;
    description: string;
    required: boolean;
  }>;
  handler?: (args: Record<string, any>) => Promise<any> | any;
}

export interface ChatResponseEnvelope {
  protocol: 'ag-ui-v1';
  messageId: string;
  content: string;
  widget?: GenerativeUIWidget;
  actions: CopilotKitAction[];
  metadata: Record<string, any>;
}

export class CopilotKitAdapter {
  private actions: Map<string, CopilotKitAction> = new Map();

  constructor() {}

  /**
   * Register a CopilotKit action callable by agent or user UI
   */
  public registerAction(action: CopilotKitAction): void {
    this.actions.set(action.name, action);
  }

  public getAction(name: string): CopilotKitAction | undefined {
    return this.actions.get(name);
  }

  public listActions(): CopilotKitAction[] {
    return Array.from(this.actions.values());
  }

  /**
   * Render an interactive form widget
   */
  public renderForm(config: FormConfig): GenerativeUIWidget<FormConfig> {
    return {
      id: config.id || `form_${Date.now()}`,
      type: 'form',
      props: {
        ...config,
        submitLabel: config.submitLabel || 'Submit',
      },
      version: '1.0.0',
      createdAt: new Date().toISOString(),
    };
  }

  /**
   * Render a live progress bar widget
   */
  public renderProgressBar(progress: number, label: string, status: 'in_progress' | 'completed' | 'failed' = 'in_progress'): GenerativeUIWidget {
    const clampedProgress = Math.max(0, Math.min(100, progress));
    return {
      id: `progress_${Date.now()}`,
      type: 'progress_bar',
      props: {
        progress: clampedProgress,
        label,
        status,
        updatedAt: new Date().toISOString(),
      },
      version: '1.0.0',
      createdAt: new Date().toISOString(),
    };
  }

  /**
   * Render a streaming table widget
   */
  public renderStreamingTable(
    id: string,
    columns: TableColumn[],
    rows: Array<Record<string, any>> = [],
    isStreaming: boolean = false
  ): GenerativeUIWidget {
    return {
      id,
      type: 'streaming_table',
      props: {
        columns,
        rows,
        isStreaming,
        rowCount: rows.length,
      },
      version: '1.0.0',
      createdAt: new Date().toISOString(),
    };
  }

  /**
   * Package generative widget into AG-UI chat response envelope
   */
  public serializeForChat(
    content: string,
    widget?: GenerativeUIWidget,
    metadata: Record<string, any> = {}
  ): ChatResponseEnvelope {
    return {
      protocol: 'ag-ui-v1',
      messageId: `msg_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
      content,
      widget,
      actions: this.listActions(),
      metadata: {
        ...metadata,
        renderedAt: new Date().toISOString(),
      },
    };
  }
}

