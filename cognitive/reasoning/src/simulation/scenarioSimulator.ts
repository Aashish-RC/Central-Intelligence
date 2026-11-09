import {
  FailureMode,
  PlanStep,
  SimulationReport,
  SimulationScenario,
  SimulationStepResult,
} from "./models";

export type AgentStepRunner = (
  step: PlanStep,
  injectedFailure?: FailureMode
) => Promise<{
  success: boolean;
  recovered: boolean;
  fallbackAttempted: boolean;
  recoveryStrategy?: string;
  error?: string;
}>;

export class ScenarioSimulator {
  /**
   * Run a what-if simulation scenario across a planned multi-step reasoning workflow.
   */
  public async simulateScenario(
    scenario: SimulationScenario,
    customRunner?: AgentStepRunner
  ): Promise<SimulationReport> {
    const stepResults: SimulationStepResult[] = [];
    let failuresInjected = 0;
    let failuresRecovered = 0;

    for (let i = 0; i < scenario.steps.length; i++) {
      const step = scenario.steps[i];
      const stepIndex = i + 1;

      // Find any failure injection targeted at this step
      const injection = scenario.failureInjections.find(
        (fi) =>
          fi.stepTarget === step.stepId ||
          fi.stepTarget === stepIndex ||
          fi.stepTarget === undefined
      );

      const hasInjection =
        injection &&
        (injection.probability === undefined || Math.random() <= injection.probability);

      const activeFailure = hasInjection ? injection.mode : undefined;
      if (activeFailure) failuresInjected++;

      const start = Date.now();
      let stepResult: SimulationStepResult;

      if (customRunner) {
        const runRes = await customRunner(step, activeFailure);
        const durationMs = Date.now() - start;

        if (activeFailure && runRes.recovered) {
          failuresRecovered++;
        }

        stepResult = {
          stepId: step.stepId,
          tool: step.tool,
          injectedFailure: activeFailure,
          executionStatus: runRes.success ? "success" : runRes.recovered ? "recovered" : "failed",
          fallbackAttempted: runRes.fallbackAttempted,
          recoveryStrategy: runRes.recoveryStrategy,
          error: runRes.error,
          durationMs,
        };
      } else {
        // Default built-in recovery simulator
        const res = this.evaluateBuiltinStepRecovery(step, activeFailure);
        const durationMs = Date.now() - start;

        if (activeFailure && res.recovered) {
          failuresRecovered++;
        }

        stepResult = {
          stepId: step.stepId,
          tool: step.tool,
          injectedFailure: activeFailure,
          executionStatus: res.success ? "success" : res.recovered ? "recovered" : "failed",
          fallbackAttempted: res.fallbackAttempted,
          recoveryStrategy: res.recoveryStrategy,
          error: res.error,
          durationMs,
        };
      }

      stepResults.push(stepResult);
    }

    const unrecovered = failuresInjected - failuresRecovered;
    const resilienceScore =
      failuresInjected === 0
        ? 1.0
        : Number((failuresRecovered / failuresInjected).toFixed(2));

    const recommendations = this.generateRecommendations(stepResults, resilienceScore);

    return {
      scenarioId: scenario.id,
      scenarioName: scenario.name,
      totalSteps: scenario.steps.length,
      failuresInjected,
      failuresRecovered,
      unrecoveredFailures: unrecovered,
      resilienceScore,
      stepResults,
      recommendations,
    };
  }

  private evaluateBuiltinStepRecovery(
    step: PlanStep,
    failure?: FailureMode
  ): {
    success: boolean;
    recovered: boolean;
    fallbackAttempted: boolean;
    recoveryStrategy?: string;
    error?: string;
  } {
    if (!failure) {
      return { success: true, recovered: false, fallbackAttempted: false };
    }

    switch (failure) {
      case "api_timeout":
        return {
          success: false,
          recovered: true,
          fallbackAttempted: true,
          recoveryStrategy: "Exponential backoff retry with secondary provider fallback",
          error: "Upstream HTTP timeout 504",
        };
      case "rate_limit_429":
        return {
          success: false,
          recovered: true,
          fallbackAttempted: true,
          recoveryStrategy: "Sliding-window backoff delay with quota switching",
          error: "Rate limit exceeded HTTP 429",
        };
      case "corrupt_json_output":
        return {
          success: false,
          recovered: true,
          fallbackAttempted: true,
          recoveryStrategy: "Strict schema repair and JSON extraction parser pass",
          error: "SyntaxError: Unexpected token in JSON",
        };
      case "tool_execution_error":
        return {
          success: false,
          recovered: false,
          fallbackAttempted: true,
          recoveryStrategy: "Alternative tool fallback unavailable",
          error: "Tool execution exited with non-zero exit code",
        };
      case "budget_exhausted":
        return {
          success: false,
          recovered: false,
          fallbackAttempted: false,
          recoveryStrategy: "Halt execution pending operator credit replenishment",
          error: "Financial cap breached",
        };
      default:
        return {
          success: false,
          recovered: false,
          fallbackAttempted: false,
          error: `Unhandled failure mode: ${failure}`,
        };
    }
  }

  private generateRecommendations(
    stepResults: SimulationStepResult[],
    resilienceScore: number
  ): string[] {
    const recs: string[] = [];

    if (resilienceScore < 0.7) {
      recs.push("Resilience score is below threshold (0.7). Implement automated provider failovers.");
    }

    const unrecoveredTools = stepResults
      .filter((r) => r.executionStatus === "failed")
      .map((r) => r.tool);

    if (unrecoveredTools.length > 0) {
      recs.push(
        `Provide fallback alternatives or retry circuits for vulnerable tools: ${[...new Set(unrecoveredTools)].join(", ")}`
      );
    }

    const timeouts = stepResults.filter((r) => r.injectedFailure === "api_timeout");
    if (timeouts.length > 0) {
      recs.push("Configure pre-first-byte streaming timeouts and secondary route failover.");
    }

    return recs;
  }
}
