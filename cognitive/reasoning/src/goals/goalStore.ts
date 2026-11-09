import { Goal, GoalCheckpoint, GoalStatus, SubGoal } from "./models";

export interface CreateGoalParams {
  id?: string;
  title: string;
  description?: string;
  userId: string;
  subGoals?: Array<{
    id?: string;
    title: string;
    description?: string;
    dependsOn?: string[];
  }>;
  metadata?: Record<string, unknown>;
}

export class GoalStore {
  private goals: Map<string, Goal> = new Map();

  /**
   * Create a new long-horizon goal.
   */
  public createGoal(params: CreateGoalParams): Goal {
    const goalId = params.id || `goal_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
    const now = Date.now();

    const subGoals: SubGoal[] = (params.subGoals || []).map((sg, idx) => ({
      id: sg.id || `subgoal_${idx + 1}`,
      title: sg.title,
      description: sg.description,
      status: "pending",
      order: idx + 1,
      dependsOn: sg.dependsOn || [],
    }));

    const goal: Goal = {
      id: goalId,
      title: params.title,
      description: params.description || "",
      userId: params.userId,
      status: "pending",
      subGoals,
      createdAt: now,
      updatedAt: now,
      checkpoints: [],
      metadata: params.metadata || {},
    };

    this.goals.set(goalId, goal);
    return goal;
  }

  /**
   * Retrieve a goal by ID.
   */
  public getGoal(id: string): Goal | undefined {
    return this.goals.get(id);
  }

  /**
   * List goals with optional filtering.
   */
  public listGoals(filter?: { userId?: string; status?: GoalStatus }): Goal[] {
    let list = Array.from(this.goals.values());
    if (filter?.userId) {
      list = list.filter((g) => g.userId === filter.userId);
    }
    if (filter?.status) {
      list = list.filter((g) => g.status === filter.status);
    }
    return list;
  }

  /**
   * Update the overall status of a goal.
   */
  public updateGoalStatus(id: string, status: GoalStatus): Goal {
    const goal = this.goals.get(id);
    if (!goal) {
      throw new Error(`Goal with ID ${id} not found`);
    }
    goal.status = status;
    goal.updatedAt = Date.now();
    return goal;
  }

  /**
   * Add a subgoal to an existing goal.
   */
  public addSubGoal(
    goalId: string,
    subGoal: { id?: string; title: string; description?: string; dependsOn?: string[] }
  ): SubGoal {
    const goal = this.goals.get(goalId);
    if (!goal) {
      throw new Error(`Goal with ID ${goalId} not found`);
    }

    const newSubGoal: SubGoal = {
      id: subGoal.id || `subgoal_${goal.subGoals.length + 1}`,
      title: subGoal.title,
      description: subGoal.description,
      status: "pending",
      order: goal.subGoals.length + 1,
      dependsOn: subGoal.dependsOn || [],
    };

    goal.subGoals.push(newSubGoal);
    goal.updatedAt = Date.now();
    return newSubGoal;
  }

  /**
   * Mark a subgoal as completed and update overall goal progress.
   */
  public completeSubGoal(
    goalId: string,
    subGoalId: string,
    outputArtifacts?: Record<string, unknown>
  ): Goal {
    const goal = this.goals.get(goalId);
    if (!goal) {
      throw new Error(`Goal with ID ${goalId} not found`);
    }

    const sg = goal.subGoals.find((s) => s.id === subGoalId);
    if (!sg) {
      throw new Error(`SubGoal with ID ${subGoalId} not found in goal ${goalId}`);
    }

    sg.status = "completed";
    sg.completedAt = Date.now();
    if (outputArtifacts) {
      sg.outputArtifacts = outputArtifacts;
    }

    // Auto-advance goal status to active if pending
    if (goal.status === "pending") {
      goal.status = "active";
    }

    // Check if all subgoals are completed
    const allDone = goal.subGoals.length > 0 && goal.subGoals.every((s) => s.status === "completed");
    if (allDone) {
      goal.status = "completed";
    }

    goal.updatedAt = Date.now();
    return goal;
  }

  /**
   * Mark a subgoal as failed.
   */
  public failSubGoal(goalId: string, subGoalId: string, reason?: string): Goal {
    const goal = this.goals.get(goalId);
    if (!goal) {
      throw new Error(`Goal with ID ${goalId} not found`);
    }

    const sg = goal.subGoals.find((s) => s.id === subGoalId);
    if (!sg) {
      throw new Error(`SubGoal with ID ${subGoalId} not found in goal ${goalId}`);
    }

    sg.status = "failed";
    if (reason) {
      sg.outputArtifacts = { ...(sg.outputArtifacts || {}), failureReason: reason };
    }
    goal.status = "failed";
    goal.updatedAt = Date.now();
    return goal;
  }

  /**
   * Calculate progress percentage for a goal (0 - 100).
   */
  public calculateProgress(goal: Goal): number {
    if (goal.subGoals.length === 0) {
      return goal.status === "completed" ? 100 : 0;
    }
    const completedCount = goal.subGoals.filter((sg) => sg.status === "completed").length;
    return Math.round((completedCount / goal.subGoals.length) * 100);
  }

  /**
   * Save a snapshot/checkpoint of current progress.
   */
  public createCheckpoint(
    goalId: string,
    contextSnapshot: Record<string, unknown> = {},
    notes?: string
  ): GoalCheckpoint {
    const goal = this.goals.get(goalId);
    if (!goal) {
      throw new Error(`Goal with ID ${goalId} not found`);
    }

    const completed = goal.subGoals.filter((s) => s.status === "completed").map((s) => s.id);
    const active = goal.subGoals.find((s) => s.status === "active")?.id;
    const progress = this.calculateProgress(goal);

    const checkpoint: GoalCheckpoint = {
      checkpointId: `chk_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
      timestamp: Date.now(),
      completedSubGoalIds: completed,
      activeSubGoalId: active,
      contextSnapshot,
      progressPercentage: progress,
      notes,
    };

    goal.checkpoints.push(checkpoint);
    goal.updatedAt = Date.now();
    return checkpoint;
  }

  /**
   * Restore a goal to the state captured in a checkpoint.
   */
  public restoreCheckpoint(goalId: string, checkpointId: string): Goal {
    const goal = this.goals.get(goalId);
    if (!goal) {
      throw new Error(`Goal with ID ${goalId} not found`);
    }

    const chk = goal.checkpoints.find((c) => c.checkpointId === checkpointId);
    if (!chk) {
      throw new Error(`Checkpoint ${checkpointId} not found for goal ${goalId}`);
    }

    // Restore subgoal statuses
    for (const sg of goal.subGoals) {
      if (chk.completedSubGoalIds.includes(sg.id)) {
        sg.status = "completed";
      } else if (sg.id === chk.activeSubGoalId) {
        sg.status = "active";
      } else {
        sg.status = "pending";
      }
    }

    goal.status = chk.progressPercentage === 100 ? "completed" : "active";
    goal.updatedAt = Date.now();
    return goal;
  }

  /**
   * Pause a goal.
   */
  public pauseGoal(id: string): Goal {
    return this.updateGoalStatus(id, "paused");
  }

  /**
   * Resume a goal.
   */
  public resumeGoal(id: string): Goal {
    return this.updateGoalStatus(id, "active");
  }
}
