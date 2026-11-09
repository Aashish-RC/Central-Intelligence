import { z } from "zod";

export type FailureMode =
  | "api_timeout"
  | "rate_limit_429"
  | "tool_execution_error"
  | "corrupt_json_output"
  | "context_length_exceeded"
  | "budget_exhausted"
  | "network_partition";

export interface ScenarioFailureInjection {
  mode: FailureMode;
  stepTarget?: string | number;
  probability?: number;
  customError?: string;
  metadata?: Record<string, unknown>;
}

export interface PlanStep {
  stepId: string;
  tool: string;
  description: string;
  input: Record<string, unknown>;
}

export interface SimulationScenario {
  id: string;
  name: string;
  description?: string;
  failureInjections: ScenarioFailureInjection[];
  steps: PlanStep[];
}

export interface SimulationStepResult {
  stepId: string;
  tool: string;
  injectedFailure?: FailureMode;
  executionStatus: "success" | "recovered" | "failed";
  fallbackAttempted: boolean;
  recoveryStrategy?: string;
  error?: string;
  durationMs: number;
}

export interface SimulationReport {
  scenarioId: string;
  scenarioName: string;
  totalSteps: number;
  failuresInjected: number;
  failuresRecovered: number;
  unrecoveredFailures: number;
  resilienceScore: number; // 0.0 to 1.0
  stepResults: SimulationStepResult[];
  recommendations: string[];
}

export const SimulationScenarioSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string().optional(),
  failureInjections: z.array(
    z.object({
      mode: z.enum([
        "api_timeout",
        "rate_limit_429",
        "tool_execution_error",
        "corrupt_json_output",
        "context_length_exceeded",
        "budget_exhausted",
        "network_partition",
      ]),
      stepTarget: z.union([z.string(), z.number()]).optional(),
      probability: z.number().min(0).max(1).optional(),
      customError: z.string().optional(),
      metadata: z.record(z.unknown()).optional(),
    })
  ),
  steps: z.array(
    z.object({
      stepId: z.string(),
      tool: z.string(),
      description: z.string(),
      input: z.record(z.unknown()),
    })
  ),
});
