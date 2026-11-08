/**
 * NodeImpl Contract
 * Sourced from Rivet (packages/core/src/model/NodeImpl.ts) - MIT License
 *
 * Defines the abstract base class and interfaces for node implementations.
 */

import {
  IF_PORT,
  type ChartNode,
  type NodeId,
  type NodeInputDefinition,
  type NodeOutputDefinition,
} from './NodeBase.js';
import type { NodeConnection } from './NodeConnection.js';

export type Inputs = Record<string, unknown>;
export type Outputs = Record<string, unknown>;

export interface InternalProcessContext {
  [key: string]: unknown;
}

export interface NodeUIData {
  contextMenuTitle?: string;
  infoBoxTitle?: string;
  infoBoxBody?: string;
}

export type NodeBody = string | { type: string; [key: string]: unknown };

export interface EditorDefinition<T extends ChartNode> {
  type: string;
  label: string;
  dataKey: string;
  [key: string]: unknown;
}

export interface RivetUIContext {
  [key: string]: unknown;
}

export interface NodeImplConstructor<T extends ChartNode> {
  new (chartNode: T): NodeImpl<T>;
  create(): T;
}

export interface PluginNodeImpl<T extends ChartNode> {
  getInputDefinitions(
    data: T['data'],
    connections: NodeConnection[],
    nodes: Record<NodeId, ChartNode>,
    project?: unknown,
  ): NodeInputDefinition[];

  getOutputDefinitions(
    data: T['data'],
    connections: NodeConnection[],
    nodes: Record<NodeId, ChartNode>,
    project?: unknown,
  ): NodeOutputDefinition[];

  process(data: T['data'], inputData: Inputs, context: InternalProcessContext): Promise<Outputs>;

  getEditors?(data: T['data'], context?: RivetUIContext): EditorDefinition<T>[] | Promise<EditorDefinition<T>[]>;

  getBody?(data: T['data'], context?: RivetUIContext): NodeBody | Promise<NodeBody>;

  create(): T;

  getUIData?(context?: RivetUIContext): NodeUIData | Promise<NodeUIData>;
}

/**
 * Abstract class that all built-in node implementations extend.
 * Provides default port resolution, conditional handling, and property accessors.
 */
export abstract class NodeImpl<T extends ChartNode, Type extends T['type'] = T['type']> {
  readonly chartNode: T;

  constructor(chartNode: T) {
    this.chartNode = chartNode;
  }

  get id(): string {
    return this.chartNode.id;
  }

  get type(): Type {
    return this.chartNode.type as Type;
  }

  get title(): string {
    return this.chartNode.title;
  }

  get visualData(): { x: number; y: number; width?: number; height?: number } {
    return this.chartNode.visualData;
  }

  get data(): T['data'] {
    return this.chartNode.data;
  }

  /**
   * Computes the dynamically configured input definitions for this node.
   */
  abstract getInputDefinitions(
    connections?: NodeConnection[],
    nodes?: Record<NodeId, ChartNode>,
    project?: unknown,
  ): NodeInputDefinition[];

  /**
   * Retrieves all input ports, automatically including the `$if` port when conditional execution is active.
   */
  getInputDefinitionsIncludingBuiltIn(
    connections?: NodeConnection[],
    nodes?: Record<NodeId, ChartNode>,
    project?: unknown,
  ): NodeInputDefinition[] {
    const ports = [...this.getInputDefinitions(connections, nodes, project)];
    if (this.chartNode.isConditional) {
      ports.push(IF_PORT);
    }
    return ports;
  }

  /**
   * Computes the output definitions emitted by this node.
   */
  abstract getOutputDefinitions(
    connections?: NodeConnection[],
    nodes?: Record<NodeId, ChartNode>,
    project?: unknown,
  ): NodeOutputDefinition[];

  /**
   * Core execution handler invoked during graph processing.
   */
  abstract process(inputData: Inputs, context: InternalProcessContext): Promise<Outputs>;

  /**
   * Returns editor field definitions used to render inspector form controls for this node.
   */
  getEditors(_context?: RivetUIContext): EditorDefinition<T>[] | Promise<EditorDefinition<T>[]> {
    return [];
  }

  /**
   * Returns content rendered inside the visual node's body on the canvas.
   */
  getBody(_context?: RivetUIContext): NodeBody | undefined | Promise<NodeBody | undefined> {
    return undefined;
  }

  getUIData(_context?: RivetUIContext): NodeUIData | undefined | Promise<NodeUIData | undefined> {
    return undefined;
  }
}
