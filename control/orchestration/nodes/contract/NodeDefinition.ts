/**
 * NodeDefinition Contract
 * Sourced from Rivet (packages/core/src/model/NodeDefinition.ts) - MIT License
 *
 * Defines the registration contract binding a node's class implementation,
 * display name, category, and visual properties.
 */

import type { ChartNode } from './NodeBase.js';
import type { NodeImplConstructor, PluginNodeImpl } from './NodeImpl.js';

/**
 * Metadata definition and implementation reference for a built-in node type.
 */
export interface NodeDefinition<T extends ChartNode = ChartNode> {
  /**
   * Class constructor implementing the node's lifecycle and execution methods.
   */
  impl: NodeImplConstructor<T>;

  /**
   * User-facing display name shown in node selectors, menus, and search palettes.
   */
  displayName: string;

  /**
   * Functional category for grouping in the node palette (e.g., 'Flow Control', 'Models', 'Data').
   */
  category?: string;

  /**
   * Short documentation summary of what the node does.
   */
  description?: string;
}

/**
 * Definition for plugin-contributed node types.
 */
export interface PluginNodeDefinition<T extends ChartNode = ChartNode> {
  impl: PluginNodeImpl<T>;
  displayName: string;
  category?: string;
  description?: string;
}

export type UnknownNodeDefinition = NodeDefinition<ChartNode>;

/**
 * Factory helper function to construct a standard NodeDefinition.
 */
export function nodeDefinition<T extends ChartNode>(
  impl: NodeImplConstructor<T>,
  displayName: string,
  category?: string,
  description?: string,
): NodeDefinition<T> {
  return {
    impl,
    displayName,
    category,
    description,
  };
}

/**
 * Factory helper function to construct a PluginNodeDefinition.
 */
export function pluginNodeDefinition<T extends ChartNode>(
  impl: PluginNodeImpl<T>,
  displayName: string,
  category?: string,
  description?: string,
): PluginNodeDefinition<T> {
  return {
    impl,
    displayName,
    category,
    description,
  };
}
