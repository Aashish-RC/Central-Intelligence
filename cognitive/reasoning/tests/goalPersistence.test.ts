import { describe, it, expect } from "vitest";
import { GoalStore } from "../src/goals/goalStore";

describe("GoalStore Persistence & Long-Horizon Tracking (4.15)", () => {
  it("creates and retrieves a goal with hierarchical subgoals", () => {
    const store = new GoalStore();
    const goal = store.createGoal({
      title: "Refactor Database Schema",
      description: "Migrate legacy facts to relational schema",
      userId: "dev_agent_01",
      subGoals: [
        { title: "Analyze current schema dependencies" },
        { title: "Draft migration script", dependsOn: ["subgoal_1"] },
        { title: "Run migration and verify integrity", dependsOn: ["subgoal_2"] },
      ],
    });

    expect(goal.id).toBeDefined();
    expect(goal.status).toBe("pending");
    expect(goal.subGoals).toHaveLength(3);
    expect(goal.subGoals[0].status).toBe("pending");
    expect(store.calculateProgress(goal)).toBe(0);

    const fetched = store.getGoal(goal.id);
    expect(fetched).toBeDefined();
    expect(fetched?.title).toBe("Refactor Database Schema");
  });

  it("handles lifecycle transitions: pause, resume, complete subgoals and track progress", () => {
    const store = new GoalStore();
    const goal = store.createGoal({
      title: "Deploy Multi-Agent Cluster",
      userId: "user_123",
      subGoals: [
        { id: "sg_1", title: "Provision nodes" },
        { id: "sg_2", title: "Deploy orchestration pods" },
      ],
    });

    // Complete first subgoal
    store.completeSubGoal(goal.id, "sg_1", { nodeId: "node-xyz-101" });
    expect(goal.status).toBe("active");
    expect(goal.subGoals[0].status).toBe("completed");
    expect(goal.subGoals[0].outputArtifacts?.nodeId).toBe("node-xyz-101");
    expect(store.calculateProgress(goal)).toBe(50);

    // Pause goal
    store.pauseGoal(goal.id);
    expect(goal.status).toBe("paused");

    // Resume goal
    store.resumeGoal(goal.id);
    expect(goal.status).toBe("active");

    // Complete second subgoal
    store.completeSubGoal(goal.id, "sg_2");
    expect(goal.status).toBe("completed");
    expect(store.calculateProgress(goal)).toBe(100);
  });

  it("creates and restores checkpoints for long-horizon task resumption", () => {
    const store = new GoalStore();
    const goal = store.createGoal({
      title: "Data Pipeline Ingestion",
      userId: "agent_etl",
      subGoals: [
        { id: "step_1", title: "Fetch API logs" },
        { id: "step_2", title: "Run enrichment transformations" },
        { id: "step_3", title: "Load into Data Lake" },
      ],
    });

    store.completeSubGoal(goal.id, "step_1");
    const cp1 = store.createCheckpoint(goal.id, { cursor: "offset_500" }, "Finished initial fetch");

    expect(cp1.completedSubGoalIds).toEqual(["step_1"]);
    expect(cp1.progressPercentage).toBe(33);

    // Complete step 2
    store.completeSubGoal(goal.id, "step_2");
    expect(store.calculateProgress(goal)).toBe(67);

    // Simulate failure or rollback requirement -> restore to checkpoint 1
    const restored = store.restoreCheckpoint(goal.id, cp1.checkpointId);
    expect(restored.subGoals.find((s) => s.id === "step_1")?.status).toBe("completed");
    expect(restored.subGoals.find((s) => s.id === "step_2")?.status).toBe("pending");
    expect(store.calculateProgress(restored)).toBe(33);
  });

  it("handles subgoal failure gracefully", () => {
    const store = new GoalStore();
    const goal = store.createGoal({
      title: "Payment Processing Run",
      userId: "finance_worker",
      subGoals: [{ id: "tx_1", title: "Charge card" }],
    });

    store.failSubGoal(goal.id, "tx_1", "Card declined by issuing bank");
    expect(goal.status).toBe("failed");
    expect(goal.subGoals[0].status).toBe("failed");
    expect(goal.subGoals[0].outputArtifacts?.failureReason).toBe("Card declined by issuing bank");
  });
});
