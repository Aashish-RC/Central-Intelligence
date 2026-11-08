/**
 * Connector Node — bridges the connector contract to the Rivet canvas node catalog.
 *
 * Each ConnectorPiece action is surfaced as a node in NODES_BY_TYPE:
 *   type: "piece:{pieceId}:{actionId}"
 *
 * Design: maps ConnectorProp[] to NodeInputDefinition[] and creates a single
 *   output port 'result' of dataType 'object'.
 *
 * Reference: docs/ARCHITECTURE.md §4.8 — Design Blueprint for Phase 4 Connector Layer.
 */

import type { ConnectorPiece, ConnectorProp } from './connectorContract.js';
import { connectorNodeType } from './connectorRegistry.js';

export interface ConnectorNodeCatalogEntry {
  title: string;
  category: string;
  description: string;
  defaultInputs: Array<{ id: string; title: string; dataType: string }>;
  defaultOutputs: Array<{ id: string; title: string; dataType: string }>;
  defaultData: Record<string, unknown>;
  /** The connector action runner — called during canvas graph execution */
  execute?: (inputs: Record<string, unknown>, authMap?: Record<string, string>) => Promise<unknown>;
}

function propToDataType(prop: ConnectorProp): string {
  switch (prop.type) {
    case 'number': return 'number';
    case 'boolean': return 'boolean';
    case 'object': return 'object';
    default: return 'string';
  }
}

/**
 * Generate canvas node catalog entries for all actions in a ConnectorPiece.
 * Returns a map of nodeType → ConnectorNodeCatalogEntry.
 */
export function buildConnectorNodes(
  piece: ConnectorPiece
): Record<string, ConnectorNodeCatalogEntry> {
  const entries: Record<string, ConnectorNodeCatalogEntry> = {};

  for (const action of piece.actions) {
    const nodeType = connectorNodeType(piece.pieceId, action.actionId);

    // Auth fields become special 'auth.*' inputs
    const authInputs = (piece.authFields ?? []).map((f) => ({
      id: `auth.${f.key}`,
      title: f.displayName,
      dataType: 'string',
    }));

    // Action props become regular inputs
    const propInputs = action.props.map((p) => ({
      id: p.key,
      title: p.displayName,
      dataType: propToDataType(p),
    }));

    const defaultData: Record<string, unknown> = {};
    for (const prop of action.props) {
      if (prop.defaultValue !== undefined) {
        defaultData[prop.key] = prop.defaultValue;
      }
    }

    entries[nodeType] = {
      title: `${piece.displayName}: ${action.displayName}`,
      category: 'Connectors',
      description: action.description,
      defaultInputs: [...authInputs, ...propInputs],
      defaultOutputs: [
        { id: 'result', title: 'Result', dataType: 'object' },
        { id: 'error', title: 'Error', dataType: 'string' },
      ],
      defaultData,
      async execute(inputs, authMap) {
        const propsValue: Record<string, unknown> = {};
        for (const prop of action.props) {
          propsValue[prop.key] = inputs[prop.key] ?? prop.defaultValue;
        }
        const auth: Record<string, string> = authMap ?? {};
        // Also pick auth fields from inputs
        for (const f of piece.authFields ?? []) {
          const val = inputs[`auth.${f.key}`];
          if (val !== undefined) auth[f.key] = String(val);
        }
        return action.run({ auth, propsValue });
      },
    };
  }

  return entries;
}
