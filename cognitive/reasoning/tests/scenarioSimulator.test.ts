import { describe, it, expect } from "vitest";
import { ScenarioSimulator } from "../src/simulation/scenarioSimulator";
import { SimulationScenario } from "../src/simulation/models";

describe("ScenarioSimulator (4.06: What-If Failure Testing)", () => {
  const scenario: SimulationScenario = {
    id: "scen_prod_deploy",
    name: "Production Microservice Deployment",
    failureInjections: [
      {
        mode: "api_timeout",
        stepTarget: "step_2",
      },
      {
        mode: "rate_limit_429",
        stepTarget: "step_3",
      },
    ],
    steps: [
      {
        stepId: "step_1",
        tool: "git_checkout",
        description: "Pull latest commit",
        input: { repo: "central-intelligence" },
      },
      {
        stepId: "step_2",
        tool: "cloud_build_api",
        description: "Trigger cloud build image",
        input: { image: "aevum/core:latest" },
      },
      {
        stepId: "step_3",
        tool: "llm_summary_generator",
        description: "Generate release notes",
        input: { commits: ["feat: new engine"] },
      },
    ],
  };

  it("simulates built-in recovery for api_timeout and rate_limit_429", async () => {
    const simulator = new ScenarioSimulator();
    const report = await simulator.simulateScenario(scenario);

    expect(report.scenarioId).toBe("scen_prod_deploy");
    expect(report.totalSteps).toBe(3);
    expect(report.failuresInjected).toBe(2);
    expect(report.failuresRecovered).toBe(2);
    expect(report.resilienceScore).toBe(1.0);

    const step2 = report.stepResults.find((s) => s.stepId === "step_2");
    expect(step2?.injectedFailure).toBe("api_timeout");
    expect(step2?.executionStatus).toBe("recovered");
    expect(step2?.recoveryStrategy).toContain("Exponential backoff retry");
  });

  it("evaluates custom agent runner handling unrecoverable failure", async () => {
    const customRunner = async (step: any, failure: any) => {
      if (failure === "budget_exhausted") {
        return {
          success: false,
          recovered: false,
          fallbackAttempted: false,
          error: "Hard financial ceiling reached",
        };
      }
      return { success: true, recovered: false, fallbackAttempted: false };
    };

    const fatalScenario: SimulationScenario = {
      id: "scen_budget_test",
      name: "Runaway Agent Task",
      failureInjections: [{ mode: "budget_exhausted", stepTarget: 1 }],
      steps: [
        {
          stepId: "s1",
          tool: "heavy_model_inference",
          description: "Run 100K token batch",
          input: {},
        },
      ],
    };

    const simulator = new ScenarioSimulator();
    const report = await simulator.simulateScenario(fatalScenario, customRunner);

    expect(report.failuresInjected).toBe(1);
    expect(report.failuresRecovered).toBe(0);
    expect(report.resilienceScore).toBe(0.0);
    expect(report.unrecoveredFailures).toBe(1);
    expect(report.recommendations.length).toBeGreaterThan(0);
  });
});
