/**
 * Authentication Service
 * Reference pattern: LibreChat localStrategy & session management (MIT).
 *
 * Provides signup, login, logout, session token management, OAuth2 integration,
 * and ties directly into the Phase 2 VirtualKey and Budget governance layer.
 */

import { randomBytes, pbkdf2Sync } from 'node:crypto';
import { nanoid } from 'nanoid';
import type { User, UserSession, AuthResult, OAuthProfile, AuthProvider } from './types.js';
import { strategyRegistry } from './oauthStrategies.js';
import { engine } from '../chat/chatService.js';

export interface SignupParams {
  email: string;
  password?: string;
  name: string;
  teamId?: string;
  rateLimitRPM?: number;
  maxSpendUSD?: number;
}

export interface LoginParams {
  email: string;
  password?: string;
}

export class AuthService {
  private users = new Map<string, User>(); // userId -> User
  private usersByEmail = new Map<string, string>(); // email -> userId
  private sessions = new Map<string, UserSession>(); // token -> UserSession
  private tokenExpiryMs = 24 * 60 * 60 * 1000; // 24 hours

  constructor() {}

  /**
   * Register a new user account with email/password or initial profile.
   * Directly provisions a dedicated VirtualKey and sets up initial budget in ModelEngine.
   */
  async signup(params: SignupParams): Promise<AuthResult> {
    const normalizedEmail = params.email.trim().toLowerCase();
    if (this.usersByEmail.has(normalizedEmail)) {
      throw new Error(`User with email "${normalizedEmail}" already exists`);
    }

    if (!params.password || params.password.length < 6) {
      throw new Error('Password must be at least 6 characters');
    }

    const salt = randomBytes(16).toString('hex');
    const passwordHash = pbkdf2Sync(params.password, salt, 10000, 64, 'sha512').toString('hex');

    const userId = `usr-${nanoid(8)}`;
    const teamId = params.teamId || 'default-team';

    // 1. Tie to Phase 2 Governance: Provision real Virtual Key
    const vk = engine.issueVirtualKey({
      userId,
      teamId,
      name: `${params.name} Account Key`,
      rateLimitRPM: params.rateLimitRPM || 60,
      rateLimitTPM: 100000,
      maxSpendUSD: params.maxSpendUSD || 10.0,
    });

    // 2. Tie to Phase 2 Governance: Set isolated User Budget
    engine.setUserBudget(userId, params.maxSpendUSD || 10.0, 'monthly');

    const user: User = {
      id: userId,
      email: normalizedEmail,
      name: params.name,
      passwordHash,
      salt,
      teamId,
      provider: 'local',
      virtualKeyString: vk.key,
      createdAt: Date.now(),
    };

    this.users.set(userId, user);
    this.usersByEmail.set(normalizedEmail, userId);

    // Create active session
    return this.createSession(user);
  }

  /**
   * Authenticate via email & password
   */
  async login(params: LoginParams): Promise<AuthResult> {
    const normalizedEmail = params.email.trim().toLowerCase();
    const userId = this.usersByEmail.get(normalizedEmail);
    if (!userId) {
      throw new Error('Invalid email or password');
    }

    const user = this.users.get(userId);
    if (!user || !user.passwordHash || !user.salt) {
      throw new Error('Invalid email or password');
    }

    const testHash = pbkdf2Sync(params.password || '', user.salt, 10000, 64, 'sha512').toString('hex');
    if (testHash !== user.passwordHash) {
      throw new Error('Invalid email or password');
    }

    return this.createSession(user);
  }

  /**
   * Social / OAuth2 login (Google, GitHub, etc.)
   */
  async loginWithOAuth(
    provider: AuthProvider,
    codeOrToken: string,
    clientProfile?: Partial<OAuthProfile>
  ): Promise<AuthResult> {
    const strategy = strategyRegistry.get(provider);
    if (!strategy) {
      throw new Error(`OAuth provider "${provider}" is not configured`);
    }

    const profile = await strategy.authenticate({ codeOrToken, clientProfile });
    const normalizedEmail = profile.email.trim().toLowerCase();

    let userId = this.usersByEmail.get(normalizedEmail);
    let user: User;

    if (!userId) {
      // Create new social user
      userId = `usr-${nanoid(8)}`;
      const vk = engine.issueVirtualKey({
        userId,
        name: `${profile.name} Social Key`,
        rateLimitRPM: 60,
        rateLimitTPM: 100000,
        maxSpendUSD: 10.0,
      });
      engine.setUserBudget(userId, 10.0, 'monthly');

      user = {
        id: userId,
        email: normalizedEmail,
        name: profile.name,
        avatarUrl: profile.avatarUrl,
        provider,
        providerId: profile.id,
        virtualKeyString: vk.key,
        createdAt: Date.now(),
      };

      this.users.set(userId, user);
      this.usersByEmail.set(normalizedEmail, userId);
    } else {
      user = this.users.get(userId)!;
    }

    return this.createSession(user);
  }

  /**
   * Log out and terminate session token
   */
  logout(token: string): boolean {
    if (this.sessions.has(token)) {
      this.sessions.delete(token);
      return true;
    }
    return false;
  }

  /**
   * Validate session token; returns user or throws 401 Unauthorized
   */
  validateSession(token: string): { session: UserSession; user: User } {
    if (!token) {
      throw new Error('Unauthorized: Missing session token');
    }

    const session = this.sessions.get(token);
    if (!session) {
      throw new Error('Unauthorized: Invalid or expired session token');
    }

    if (Date.now() > session.expiresAt) {
      this.sessions.delete(token);
      throw new Error('Unauthorized: Session token has expired');
    }

    const user = this.users.get(session.userId);
    if (!user) {
      throw new Error('Unauthorized: User account not found');
    }

    return { session, user };
  }

  getUser(userId: string): User | undefined {
    return this.users.get(userId);
  }

  getUserByEmail(email: string): User | undefined {
    const userId = this.usersByEmail.get(email.trim().toLowerCase());
    return userId ? this.users.get(userId) : undefined;
  }

  private createSession(user: User): AuthResult {
    const token = `sess_${nanoid(32)}`;
    const expiresAt = Date.now() + this.tokenExpiryMs;

    const session: UserSession = {
      token,
      userId: user.id,
      createdAt: Date.now(),
      expiresAt,
    };

    this.sessions.set(token, session);

    const { passwordHash, salt, ...safeUser } = user;

    return {
      user: safeUser,
      token,
      virtualKey: user.virtualKeyString || '',
      expiresAt,
    };
  }

  /** Clear all data for clean test execution */
  reset(): void {
    this.users.clear();
    this.usersByEmail.clear();
    this.sessions.clear();
  }
}

export const authService = new AuthService();
