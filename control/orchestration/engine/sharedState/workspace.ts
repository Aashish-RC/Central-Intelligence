/**
 * Shared Working State Workspace
 *
 * Provides shared blackboard state, multi-agent artifact collaboration,
 * speculative branching, atomic merges, and conflict resolution across executing agents.
 *
 * Feature ID: 8.49
 */

export interface WorkspaceArtifact {
  id: string;
  name: string;
  type: string;
  content: unknown;
  version: number;
  author: string;
  updatedAt: number;
}

export interface WorkspaceBranch {
  branchName: string;
  artifacts: Map<string, WorkspaceArtifact>;
  createdAt: number;
}

export interface MergeConflict {
  artifactId: string;
  mainVersion: number;
  branchVersion: number;
  mainAuthor: string;
  branchAuthor: string;
}

export class SharedWorkspace {
  readonly workspaceId: string;
  private artifacts: Map<string, WorkspaceArtifact> = new Map();
  private branches: Map<string, WorkspaceBranch> = new Map();
  private revisionLog: Array<{ action: string; author: string; timestamp: number; details: string }> = [];

  constructor(workspaceId: string, initialData?: Record<string, unknown>) {
    this.workspaceId = workspaceId;
    if (initialData) {
      for (const [k, v] of Object.entries(initialData)) {
        this.setArtifact(k, k, v, 'system', 'variable');
      }
    }
  }

  /**
   * Set or update an artifact on the main workspace.
   */
  setArtifact(
    id: string,
    name: string,
    content: unknown,
    author: string,
    type: string = 'text'
  ): WorkspaceArtifact {
    const existing = this.artifacts.get(id);
    const version = existing ? existing.version + 1 : 1;

    const artifact: WorkspaceArtifact = {
      id,
      name,
      type,
      content,
      version,
      author,
      updatedAt: Date.now(),
    };

    this.artifacts.set(id, artifact);
    this.revisionLog.push({
      action: 'set_artifact',
      author,
      timestamp: Date.now(),
      details: `Updated '${id}' (v${version})`,
    });

    return artifact;
  }

  /**
   * Retrieve an artifact from the main workspace.
   */
  getArtifact(id: string): WorkspaceArtifact | undefined {
    return this.artifacts.get(id);
  }

  /**
   * List all current artifacts in the workspace.
   */
  listArtifacts(): WorkspaceArtifact[] {
    return Array.from(this.artifacts.values());
  }

  /**
   * Create an isolated branch of the workspace for speculative agent exploration.
   */
  createBranch(branchName: string): WorkspaceBranch {
    if (this.branches.has(branchName)) {
      throw new Error(`Branch '${branchName}' already exists in workspace '${this.workspaceId}'.`);
    }

    const clonedArtifacts = new Map<string, WorkspaceArtifact>();
    for (const [k, v] of this.artifacts.entries()) {
      clonedArtifacts.set(k, { ...v });
    }

    const branch: WorkspaceBranch = {
      branchName,
      artifacts: clonedArtifacts,
      createdAt: Date.now(),
    };

    this.branches.set(branchName, branch);
    return branch;
  }

  /**
   * Modify an artifact in a specific branch without affecting the main workspace.
   */
  setBranchArtifact(
    branchName: string,
    id: string,
    name: string,
    content: unknown,
    author: string,
    type: string = 'text'
  ): WorkspaceArtifact {
    const branch = this.branches.get(branchName);
    if (!branch) {
      throw new Error(`Branch '${branchName}' not found.`);
    }

    const existing = branch.artifacts.get(id);
    const version = existing ? existing.version + 1 : 1;

    const artifact: WorkspaceArtifact = {
      id,
      name,
      type,
      content,
      version,
      author,
      updatedAt: Date.now(),
    };

    branch.artifacts.set(id, artifact);
    return artifact;
  }

  /**
   * Merge a branch back into the main workspace.
   */
  mergeBranch(
    branchName: string,
    strategy: 'auto_prefer_branch' | 'strict_reject_conflicts' = 'auto_prefer_branch'
  ): { merged: string[]; conflicts: MergeConflict[] } {
    const branch = this.branches.get(branchName);
    if (!branch) {
      throw new Error(`Branch '${branchName}' not found.`);
    }

    const merged: string[] = [];
    const conflicts: MergeConflict[] = [];

    for (const [id, branchArt] of branch.artifacts.entries()) {
      const mainArt = this.artifacts.get(id);

      if (mainArt && (mainArt.author !== branchArt.author || mainArt.content !== branchArt.content)) {
        // Potential conflict
        conflicts.push({
          artifactId: id,
          mainVersion: mainArt.version,
          branchVersion: branchArt.version,
          mainAuthor: mainArt.author,
          branchAuthor: branchArt.author,
        });

        if (strategy === 'strict_reject_conflicts') {
          continue; // Skip merging this item
        }
      }

      // Merge item into main
      this.artifacts.set(id, {
        ...branchArt,
        version: (mainArt ? mainArt.version : 0) + 1,
        updatedAt: Date.now(),
      });
      merged.push(id);
    }

    this.branches.delete(branchName);
    return { merged, conflicts };
  }

  /**
   * Export complete workspace snapshot.
   */
  snapshot(): Record<string, unknown> {
    const data: Record<string, unknown> = {};
    for (const [k, v] of this.artifacts.entries()) {
      data[k] = v.content;
    }
    return data;
  }

  /**
   * Restore workspace to a previous snapshot state.
   */
  restoreSnapshot(snapshot: Record<string, unknown>, author: string = 'system'): void {
    this.artifacts.clear();
    for (const [k, v] of Object.entries(snapshot)) {
      this.setArtifact(k, k, v, author, 'snapshot_restored');
    }
  }
}
