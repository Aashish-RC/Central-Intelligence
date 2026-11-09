import { z } from "zod";

export type GoalStatus = "pending" | "active" | "paused" | "completed" | "failed";

export interface GoalCheckpoint {
  checkpointId: string;
  timestamp: number;
  completedSubGoalIds: string[];
  activeSubGoalId?: string;
  contextSnapshot: Record<string, unknown>;
  progressPercentage: number;
  notes?: string;
}

export interface SubGoal {
  id: string;
  title: string;
  description?: string;
  status: GoalStatus;
  order: number;
  dependsOn?: string[];
  completedAt?: number;
  outputArtifacts?: Record<string, unknown>;
}

export interface Goal {
  id: string;
  title: string;
  description: string;
  userId: string;
  status: GoalStatus;
  subGoals: SubGoal[];
  createdAt: number;
  updatedAt: number;
  checkpoints: GoalCheckpoint[];
  metadata?: Record<string, unknown>;
}

export const GoalSchema = z.object({
  id: z.string(),
  title: z.string(),
  description: z.string().default(""),
  userId: z.string(),
  status: z.enum(["pending", "active", "paused", "completed", "failed"]),
  subGoals: z.array(
    z.object({
      id: z.string(),
      title: z.string(),
      description: z.string().optional(),
      status: z.enum(["pending", "active", "paused", "completed", "failed"]),
      order: z.number(),
      dependsOn: z.array(z.string()).optional(),
      completedAt: z.number().optional(),
      outputArtifacts: z.record(z.unknown()).optional(),
    })
  ),
  createdAt: z.number(),
  updatedAt: z.number(),
  checkpoints: z.array(
    z.object({
      checkpointId: z.string(),
      timestamp: z.number(),
      completedSubGoalIds: z.array(z.string()),
      activeSubGoalId: z.string().optional(),
      contextSnapshot: z.record(z.unknown()),
      progressPercentage: z.number(),
      notes: z.string().optional(),
    })
  ),
  metadata: z.record(z.unknown()).optional(),
});
