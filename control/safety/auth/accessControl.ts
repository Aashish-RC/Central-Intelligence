/**
 * Access Control & Multi-Tenant Authorization Engine
 *
 * Implements:
 * 1. Space-scoping rules:
 *    - Agents built inside a Space are locked to that Space.
 *    - Globally-built agents are cross-Space only if the creator explicitly grants it.
 *    - Space owners control which users within that Space can invoke an agent.
 * 2. Resource ownership (chats, documents, credentials, approvals):
 *    - Chats, documents, and credentials scoped to owner.
 *    - Approval cards can ONLY be resolved by the thread's owning user.
 */

import { nanoid } from 'nanoid';
import type { Space, SpaceMember, AgentScopedDefinition } from './types.js';

export interface CanInvokeResult {
  allowed: boolean;
  reason?: string;
}

export class AccessControlEngine {
  private spaces = new Map<string, Space>(); // spaceId -> Space
  private agents = new Map<string, AgentScopedDefinition>(); // agentId -> Agent
  private userCredentials = new Map<string, Map<string, any>>(); // userId -> credentialKey -> creds

  // --- Space Management ---

  createSpace(ownerId: string, name: string): Space {
    const spaceId = `space-${nanoid(8)}`;
    const space: Space = {
      id: spaceId,
      name,
      ownerId,
      members: [
        {
          userId: ownerId,
          role: 'owner',
          canInvokeAgents: true,
          addedAt: Date.now(),
        },
      ],
      createdAt: Date.now(),
    };
    this.spaces.set(spaceId, space);
    return space;
  }

  getSpace(spaceId: string): Space | undefined {
    return this.spaces.get(spaceId);
  }

  addSpaceMember(
    spaceId: string,
    actorUserId: string,
    targetUserId: string,
    role: 'member' | 'viewer' = 'member',
    canInvokeAgents = false
  ): Space {
    const space = this.spaces.get(spaceId);
    if (!space) {
      throw new Error(`Space "${spaceId}" not found`);
    }

    if (space.ownerId !== actorUserId) {
      throw new Error('Forbidden: Only Space owners can manage members');
    }

    const existingIndex = space.members.findIndex((m) => m.userId === targetUserId);
    const memberRecord: SpaceMember = {
      userId: targetUserId,
      role,
      canInvokeAgents,
      addedAt: Date.now(),
    };

    if (existingIndex >= 0) {
      space.members[existingIndex] = memberRecord;
    } else {
      space.members.push(memberRecord);
    }

    return space;
  }

  setMemberAgentInvocation(
    spaceId: string,
    actorUserId: string,
    targetUserId: string,
    canInvokeAgents: boolean
  ): Space {
    const space = this.spaces.get(spaceId);
    if (!space) {
      throw new Error(`Space "${spaceId}" not found`);
    }

    if (space.ownerId !== actorUserId) {
      throw new Error('Forbidden: Only Space owners can modify agent invocation permissions');
    }

    const member = space.members.find((m) => m.userId === targetUserId);
    if (!member) {
      throw new Error(`User "${targetUserId}" is not a member of Space "${spaceId}"`);
    }

    member.canInvokeAgents = canInvokeAgents;
    return space;
  }

  isMemberOfSpace(userId: string, spaceId: string): boolean {
    const space = this.spaces.get(spaceId);
    if (!space) return false;
    return space.members.some((m) => m.userId === userId);
  }

  // --- Agent Scoping Rules ---

  registerAgent(agent: AgentScopedDefinition): AgentScopedDefinition {
    this.agents.set(agent.id, agent);
    return agent;
  }

  getAgent(agentId: string): AgentScopedDefinition | undefined {
    return this.agents.get(agentId);
  }

  /**
   * Evaluates if a given user can invoke an agent in a specified execution context.
   *
   * Rules:
   * 1. Space-locked agent: must be invoked in agent.spaceId, and user must have canInvokeAgents permission.
   * 2. Global agent: cross-Space ONLY if creator explicitly granted the target space (or user is creator).
   * 3. Within any Space: user must have canInvokeAgents granted by the Space owner (or be Space owner).
   */
  canInvokeAgent(
    userId: string,
    agentId: string,
    targetSpaceId?: string
  ): CanInvokeResult {
    const agent = this.agents.get(agentId);
    if (!agent) {
      return { allowed: false, reason: `Agent "${agentId}" not found` };
    }

    // 1. Agent built inside a Space is locked to that Space
    if (agent.spaceId) {
      if (!targetSpaceId || targetSpaceId !== agent.spaceId) {
        return {
          allowed: false,
          reason: `Agent is locked to Space "${agent.spaceId}" and cannot be invoked from Space "${targetSpaceId || 'global'}"`,
        };
      }

      const space = this.spaces.get(agent.spaceId);
      if (!space) {
        return { allowed: false, reason: `Space "${agent.spaceId}" not found` };
      }

      const member = space.members.find((m) => m.userId === userId);
      if (!member) {
        return {
          allowed: false,
          reason: `User "${userId}" is not a member of Space "${agent.spaceId}"`,
        };
      }

      // Space owner controls which users within that Space can invoke an agent
      if (space.ownerId !== userId && !member.canInvokeAgents) {
        return {
          allowed: false,
          reason: `User does not have agent invocation permissions in Space "${agent.spaceId}"`,
        };
      }

      return { allowed: true };
    }

    // 2. Agent built globally
    if (agent.isGlobal) {
      // Creator can always run their own global agent anywhere
      if (agent.creatorId === userId && !targetSpaceId) {
        return { allowed: true };
      }

      // If invoking inside a target Space
      if (targetSpaceId) {
        const space = this.spaces.get(targetSpaceId);
        if (!space) {
          return { allowed: false, reason: `Target Space "${targetSpaceId}" not found` };
        }

        // An agent built globally is cross-Space only if the creator explicitly grants it
        const isGranted = agent.grantedSpaceIds && agent.grantedSpaceIds.includes(targetSpaceId);
        if (!isGranted && agent.creatorId !== userId) {
          return {
            allowed: false,
            reason: `Global agent creator has not granted access to Space "${targetSpaceId}"`,
          };
        }

        // Space owner controls member execution permissions inside the Space
        const member = space.members.find((m) => m.userId === userId);
        if (!member) {
          return {
            allowed: false,
            reason: `User "${userId}" is not a member of Space "${targetSpaceId}"`,
          };
        }

        if (space.ownerId !== userId && !member.canInvokeAgents) {
          return {
            allowed: false,
            reason: `User does not have agent invocation permissions in Space "${targetSpaceId}"`,
          };
        }
      }

      return { allowed: true };
    }

    return { allowed: false, reason: 'Agent is neither global nor assigned to a valid Space' };
  }

  // --- Resource Ownership: Connectors, Credentials & Documents ---

  setConnectorCredential(userId: string, credentialKey: string, secretValue: any): void {
    if (!this.userCredentials.has(userId)) {
      this.userCredentials.set(userId, new Map());
    }
    this.userCredentials.get(userId)!.set(credentialKey, secretValue);
  }

  getConnectorCredential(userId: string, credentialKey: string, actorUserId: string): any {
    // Only the owning user can access their connector credentials
    if (actorUserId !== userId) {
      throw new Error(`Forbidden: User "${actorUserId}" cannot access credentials owned by "${userId}"`);
    }
    return this.userCredentials.get(userId)?.get(credentialKey);
  }

  canAccessChat(actorUserId: string, threadOwnerUserId?: string): boolean {
    if (!threadOwnerUserId) return true; // unauthenticated legacy thread
    return actorUserId === threadOwnerUserId;
  }

  canResolveApproval(actorUserId: string, threadOwnerUserId?: string): boolean {
    if (!threadOwnerUserId) return true; // legacy thread
    return actorUserId === threadOwnerUserId;
  }

  reset(): void {
    this.spaces.clear();
    this.agents.clear();
    this.userCredentials.clear();
  }
}

export const accessControl = new AccessControlEngine();
