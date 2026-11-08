/**
 * NodeRegistration Contract
 * Sourced from Rivet (packages/core/src/model/NodeRegistration.ts) - MIT License
 *
 * Implements the registry to register, discover, and instantiate node definitions.
 */

import type { ChartNode } from './NodeBase.js';
import type { NodeDefinition, PluginNodeDefinition } from './NodeDefinition.js';
import type { NodeImplConstructor } from './NodeImpl.js';

export interface RegisteredNodeInfo {
  type: string;
  displayName: string;
  category?: string;
  description?: string;
  impl: NodeImplConstructor<ChartNode>;
}

export class NodeRegistration {
  private readonly nodesByType = new Map<string, RegisteredNodeInfo>();

  /**
   * Registers a node definition into the registry.
   */
  register<T extends ChartNode>(definition: NodeDefinition<T>): this {
    const dummyNode = definition.impl.create();
    const typeStr = dummyNode.type;

    if (this.nodesByType.has(typeStr)) {
      console.warn(`Overriding node registration for type: ${typeStr}`);
    }

    this.nodesByType.set(typeStr, {
      type: typeStr,
      displayName: definition.displayName,
      category: definition.category,
      description: definition.description,
      impl: definition.impl as any,
    });

    return this;
  }

  /**
   * Registers a plugin-contributed node definition.
   */
  registerPluginNode<T extends ChartNode>(definition: PluginNodeDefinition<T>): this {
    const dummyNode = definition.impl.create();
    const typeStr = dummyNode.type;

    this.nodesByType.set(typeStr, {
      type: typeStr,
      displayName: definition.displayName,
      category: definition.category,
      description: definition.description,
      impl: {
        create: () => definition.impl.create(),
      } as any,
    });

    return this;
  }

  /**
   * Retrieves info for a registered node type.
   */
  get(type: string): RegisteredNodeInfo | undefined {
    return this.nodesByType.get(type);
  }

  /**
   * Checks whether a node type is registered.
   */
  has(type: string): boolean {
    return this.nodesByType.has(type);
  }

  /**
   * Returns all registered node definitions.
   */
  getAll(): RegisteredNodeInfo[] {
    return Array.from(this.nodesByType.values());
  }

  /**
   * Returns all registered type names.
   */
  getNodeTypes(): string[] {
    return Array.from(this.nodesByType.keys());
  }

  /**
   * Instantiates a new default node instance of a given type.
   */
  createNode(type: string): ChartNode {
    const info = this.nodesByType.get(type);
    if (!info) {
      throw new Error(`Unregistered node type: ${type}`);
    }
    return info.impl.create();
  }
}
