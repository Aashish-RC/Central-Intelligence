/**
 * NodeBase Contract
 * Sourced from Rivet (packages/core/src/model/NodeBase.ts) - MIT License
 * 
 * This file defines the core contract for graph nodes and ports in the node-canvas system.
 * Every node residing on the canvas implements or extends ChartNode / NodeBase.
 */

/**
 * NodeId: Represents a globally unique identifier for a node within a graph.
 */
export type NodeId = string;

/**
 * PortId: Represents a unique identifier for an input or output port within a single node.
 */
export type PortId = string;

export type { NodeConnection } from './NodeConnection.js';

/**
 * Visual coordinates, dimensions, and styling data for a node on the canvas.
 * Note: visualData does not affect graph execution logic.
 */
export interface VisualData {
  /** X coordinate of the node's top-left position on the canvas. */
  x: number;

  /** Y coordinate of the node's top-left position on the canvas. */
  y: number;

  /** Optional custom width in pixels (defaults to auto/standard node width). */
  width?: number;

  /** Optional custom height in pixels. */
  height?: number;

  /** Optional accent colors for node border and header background. */
  color?: {
    border: string;
    bg: string;
  };

  /** Stacking order on the canvas. The most recently selected or moved node has the highest zIndex. */
  zIndex?: number;
}

/**
 * Variant configuration for nodes supporting data alternatives or A/B test variations.
 */
export interface ChartNodeVariant<Data = unknown> {
  id: string;
  data: Data;
}

/**
 * Test group definition for unit testing a node's logic within the graph.
 */
export interface NodeTestGroup {
  id: string;
  evaluatorGraphId: string;
  tests: Array<{ conditionText: string }>;
}

/**
 * Base interface for all nodes in the canvas system.
 * Every node type instantiated on the canvas contains these core fields.
 */
export interface NodeBase {
  /**
   * The registered type identifier for this node (e.g. 'code', 'chat', 'text', 'match', etc.).
   * Used by the registry to look up the node's implementation and UI definition.
   */
  type: string;

  /**
   * Unique identifier of this node instance within the containing graph.
   */
  id: NodeId;

  /**
   * Human-readable title displayed in the node header on the canvas.
   */
  title: string;

  /**
   * Optional user description or notes for the node.
   */
  description?: string;

  /**
   * Whether this node executes across split inputs in parallel.
   */
  isSplitRun?: boolean;

  /**
   * When splitting, whether executions run sequentially instead of concurrently.
   */
  isSplitSequential?: boolean;

  /**
   * Maximum degree of parallelism when splitting inputs.
   */
  splitRunMax?: number;

  /**
   * Canvas layout coordinates and visual presentation styling.
   */
  visualData: VisualData;

  /**
   * Node-specific configuration and state payload.
   * Specific node types type this field strictly (e.g., CodeNodeData, TextNodeData).
   */
  data: unknown;

  /**
   * Optional alternative data variants for multi-scenario flows.
   */
  variants?: ChartNodeVariant<unknown>[];

  /**
   * Optional inline assertions and test cases attached to this node.
   */
  tests?: NodeTestGroup[];

  /**
   * If true, this node is disabled in the flow and will pass through or be skipped during processing.
   */
  disabled?: boolean;

  /**
   * If true, the node dynamically exposes a special '$if' boolean condition port.
   */
  isConditional?: boolean;

  /**
   * Optional custom TypeScript implementation code for the node (Langflow editable-node-code pattern).
   * When present, represents the editable source code defining this node's logic, inputs, and outputs.
   */
  customCode?: string;
}

/**
 * Strongly typed node contract binding a specific type string literal and data payload structure.
 */
export type ChartNode<Type extends string = string, Data = unknown> = NodeBase & {
  type: Type;
  data: Data;
  variants?: ChartNodeVariant<Data>[];
};

/**
 * Definition of a single input port on a node.
 */
export interface NodeInputDefinition {
  /**
   * Port identifier unique within this node's inputs.
   */
  id: PortId;

  /**
   * Display label shown adjacent to the port handle on the canvas.
   */
  title: string;

  /**
   * Required data type(s) accepted by this port (e.g. 'string', 'number', 'boolean', 'object', 'any').
   */
  dataType: string | readonly string[];

  /**
   * If true, graph execution cannot begin without a valid connection or value supplied to this port.
   */
  required?: boolean;

  /**
   * Default fallback value used when no wire is connected to this port.
   */
  defaultValue?: unknown;

  /**
   * Description shown in port tooltips and documentation popovers.
   */
  description?: string;

  /**
   * Whether the system should attempt automatic type coercion on incoming data values.
   */
  coerced?: boolean;

  /**
   * Arbitrary additional metadata for custom port behaviors.
   */
  data?: unknown;
}

/**
 * Definition of a single output port on a node.
 */
export interface NodeOutputDefinition {
  /**
   * Port identifier unique within this node's outputs.
   */
  id: PortId;

  /**
   * Display label shown adjacent to the port handle on the canvas.
   */
  title: string;

  /**
   * Data type(s) emitted by this port.
   */
  dataType: string | readonly string[];

  /**
   * Static or initial default value of the output.
   */
  defaultValue?: unknown;

  /**
   * Description shown in port tooltips.
   */
  description?: string;

  /**
   * Arbitrary additional metadata for custom port behaviors.
   */
  data?: unknown;
}

/**
 * Standard conditional input port dynamically attached when `isConditional` is true.
 */
export const IF_PORT: NodeInputDefinition = {
  id: '$if',
  title: 'if',
  dataType: 'boolean',
  coerced: true,
  description: 'Only run the node if this condition is true',
  defaultValue: 'false',
};

/**
 * Helper to identify whether an input port is the built-in conditional port.
 */
export function isBuiltInInputDefinition(input: NodeInputDefinition): boolean {
  return input.id === IF_PORT.id;
}
