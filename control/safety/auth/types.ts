/**
 * Authentication & Access Control Types
 * Reference pattern: LibreChat auth architecture (MIT) & Multi-Tenant Governance.
 */

export type AuthProvider = 'local' | 'google' | 'github' | 'ldap' | 'saml';

export interface User {
  id: string;
  email: string;
  name: string;
  passwordHash?: string;
  salt?: string;
  teamId?: string;
  avatarUrl?: string;
  provider: AuthProvider;
  providerId?: string;
  virtualKeyString?: string;
  createdAt: number;
}

export interface UserSession {
  token: string;
  userId: string;
  createdAt: number;
  expiresAt: number;
}

export interface AuthResult {
  user: Omit<User, 'passwordHash' | 'salt'>;
  token: string;
  virtualKey: string;
  expiresAt: number;
}

export interface SpaceMember {
  userId: string;
  role: 'owner' | 'member' | 'viewer';
  canInvokeAgents: boolean;
  addedAt: number;
}

export interface Space {
  id: string;
  name: string;
  ownerId: string;
  members: SpaceMember[];
  createdAt: number;
}

export interface AgentScopedDefinition {
  id: string;
  name: string;
  creatorId: string;
  spaceId?: string;           // If set, agent is locked to this Space
  isGlobal?: boolean;         // If true, built globally
  grantedSpaceIds?: string[]; // If global, list of Spaces where creator granted execution
  description?: string;
}

export interface OAuthProfile {
  provider: AuthProvider;
  id: string;
  email: string;
  name: string;
  avatarUrl?: string;
}

export interface UserContext {
  userId: string;
  teamId?: string;
  spaceId?: string;
}
