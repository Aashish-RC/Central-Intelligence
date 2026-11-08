/**
 * NodeConnection Contract
 * Sourced from Rivet (packages/core/src/model/NodeBase.ts) - MIT License
 *
 * Defines the contract for wires/connections between nodes in the graph canvas.
 */

import type { NodeId, PortId } from './NodeBase.js';

/**
 * Represents a directional wire connecting an output port of one node
 * to an input port of another node.
 */
export interface NodeConnection {
  /**
   * NodeId of the upstream source node emitting the data.
   */
  outputNodeId: NodeId;

  /**
   * PortId of the specific output port on the source node.
   */
  outputId: PortId;

  /**
   * NodeId of the downstream target node receiving the data.
   */
  inputNodeId: NodeId;

  /**
   * PortId of the specific input port on the target node.
   */
  inputId: PortId;
}

/**
 * Creates a unique string key for a connection to easily test set membership.
 */
export function connectionKey(conn: NodeConnection): string {
  return `${conn.outputNodeId}:${conn.outputId}->${conn.inputNodeId}:${conn.inputId}`;
}

/**
 * Checks whether two NodeConnection objects reference the same wire.
 */
export function areConnectionsEqual(a: NodeConnection, b: NodeConnection): boolean {
  return (
    a.outputNodeId === b.outputNodeId &&
    a.outputId === b.outputId &&
    a.inputNodeId === b.inputNodeId &&
    a.inputId === b.inputId
  );
}

/**
 * Validates whether a proposed connection is logically sound:
 * - Cannot connect a node directly to itself on the same port
 * - Output and Input IDs must be specified
 */
export function isValidConnection(conn: NodeConnection): boolean {
  if (!conn.outputNodeId || !conn.inputNodeId || !conn.outputId || !conn.inputId) {
    return false;
  }
  // Disallow direct cycle to same port
  if (conn.outputNodeId === conn.inputNodeId && conn.outputId === conn.inputId) {
    return false;
  }
  return true;
}
