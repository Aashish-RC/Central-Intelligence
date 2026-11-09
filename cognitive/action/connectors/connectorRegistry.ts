/**
 * Connector Registry — aggregates all connector pieces and provides lookup helpers.
 * License: MIT (ActivePieces community piece pattern reference)
 */

import type { ConnectorPiece, ConnectorAction } from './connectorContract.js';
import { slackPiece } from './pieces/slack.js';
import { httpPiece } from './pieces/http.js';
import { openaiChatPiece } from './pieces/openaiChat.js';
import { emailPiece } from './pieces/email.js';
import { calendarPiece } from './pieces/calendar.js';
import { searchPiece } from './pieces/search.js';
import { browserPiece } from './pieces/browser.js';
import { openclawPiece } from './pieces/openclaw.js';

/** All registered connector pieces */
export const CONNECTOR_REGISTRY: ConnectorPiece[] = [
  slackPiece,
  httpPiece,
  openaiChatPiece,
  emailPiece,
  calendarPiece,
  searchPiece,
  browserPiece,
  openclawPiece,
];

/**
 * Look up a specific action by pieceId + actionId.
 * e.g. getConnectorAction('slack', 'send_message')
 */
export function getConnectorAction(
  pieceId: string,
  actionId: string
): ConnectorAction | undefined {
  const piece = CONNECTOR_REGISTRY.find((p) => p.pieceId === pieceId);
  return piece?.actions.find((a) => a.actionId === actionId);
}

/**
 * Get a piece by its ID.
 */
export function getConnectorPiece(pieceId: string): ConnectorPiece | undefined {
  return CONNECTOR_REGISTRY.find((p) => p.pieceId === pieceId);
}

/**
 * Build a canvas node type string from a piece + action.
 * Format: "piece:{pieceId}:{actionId}" — matches ARCHITECTURE.md §4.8 design.
 */
export function connectorNodeType(pieceId: string, actionId: string): string {
  return `piece:${pieceId}:${actionId}`;
}

/**
 * Parse a connector node type string back to pieceId + actionId.
 * Returns null if the string is not a valid connector node type.
 */
export function parseConnectorNodeType(
  nodeType: string
): { pieceId: string; actionId: string } | null {
  const parts = nodeType.split(':');
  if (parts.length !== 3 || parts[0] !== 'piece') return null;
  return { pieceId: parts[1], actionId: parts[2] };
}
