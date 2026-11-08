/**
 * PortDefinition Contract
 * Sourced from Rivet (packages/core/src/model/NodeBase.ts) - MIT License
 *
 * Defines the contract for port definitions, data type specifications, and port matching logic.
 */

import type { PortId, NodeInputDefinition, NodeOutputDefinition } from './NodeBase.js';

/**
 * Standard data type identifiers supported by ports in the node-canvas system.
 */
export type DataType =
  | 'string'
  | 'number'
  | 'boolean'
  | 'chat-message'
  | 'date'
  | 'time'
  | 'datetime'
  | 'object'
  | 'array'
  | 'vector'
  | 'binary'
  | 'image'
  | 'audio'
  | 'document'
  | 'dataset-provider'
  | 'graph-reference'
  | 'any'
  | 'unknown';

/**
 * Common port configuration shared between inputs and outputs.
 */
export interface BasePortDefinition {
  /**
   * Unique port identifier within the node's input or output namespace.
   */
  id: PortId;

  /**
   * Human-readable label displayed in the canvas UI next to the port handle.
   */
  title: string;

  /**
   * Accepted or emitted data type (or array of allowable types).
   */
  dataType: DataType | readonly DataType[] | string | readonly string[];

  /**
   * Explanatory description shown in hover tooltips.
   */
  description?: string;

  /**
   * Default value used when disconnected.
   */
  defaultValue?: unknown;
}

export type PortDefinition = NodeInputDefinition | NodeOutputDefinition;

/**
 * Determines if an output data type can be connected to an input data type.
 * 'any' connects to any other type. Identical types are always compatible.
 */
export function areDataTypesCompatible(outputType: string, inputType: string): boolean {
  if (outputType === 'any' || inputType === 'any') {
    return true;
  }
  return outputType === inputType;
}

/**
 * Standard color mapping for canvas port dots based on their data type.
 */
export const DATA_TYPE_COLORS: Record<string, string> = {
  string: '#10b981',        // emerald
  number: '#3b82f6',        // blue
  boolean: '#f59e0b',       // amber
  'chat-message': '#8b5cf6',// purple
  object: '#ec4899',        // pink
  array: '#06b6d4',         // cyan
  image: '#f97316',         // orange
  audio: '#e11d48',         // rose
  document: '#6366f1',      // indigo
  vector: '#14b8a6',        // teal
  any: '#a1a1aa',           // zinc/gray
  unknown: '#71717a',
};
