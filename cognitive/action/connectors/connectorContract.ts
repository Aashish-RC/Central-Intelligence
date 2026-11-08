/**
 * Connector Contract — TypeScript types for the Phase 4 connector node system.
 * Adaptation guide: docs/ARCHITECTURE.md Section 4.8 (Design Blueprint for Phase 4 Connector Layer).
 * Source reference: ActivePieces MIT community pieces framework (pattern reference only).
 */

export type AuthType = 'secret_text' | 'oauth2' | 'basic_auth' | 'none';

export interface AuthField {
  key: string;
  displayName: string;
  required: boolean;
  type: 'password' | 'text';
}

export interface ConnectorProp {
  key: string;
  displayName: string;
  description?: string;
  type: 'short_text' | 'long_text' | 'number' | 'boolean' | 'dropdown' | 'object';
  required: boolean;
  defaultValue?: unknown;
  options?: Array<{ label: string; value: string }>;
}

export interface ConnectorContext {
  /** Resolved auth credentials (key-value map) */
  auth?: Record<string, string>;
  /** Fully resolved input values keyed by ConnectorProp.key */
  propsValue: Record<string, unknown>;
  userId?: string;
  spaceId?: string;
}

export interface ConnectorAction {
  actionId: string;       // e.g. "send_message"
  displayName: string;
  description: string;
  props: ConnectorProp[];
  /** Flag indicating whether this action causes irreversible, external, or financial mutations */
  consequential?: boolean;
  consequentialReason?: string;
  /** Execute the action with resolved context */
  run(context: ConnectorContext): Promise<unknown>;
}

export interface ConnectorPiece {
  pieceId: string;        // e.g. "slack"
  displayName: string;
  description: string;
  logoEmoji?: string;     // fallback when no SVG/PNG logo
  authType: AuthType;
  authFields?: AuthField[];
  actions: ConnectorAction[];
  category: string;
  licenseNote: string;    // attribution for MIT community pieces
}
