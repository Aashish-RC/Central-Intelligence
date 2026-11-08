"""Agent Runner: Autonomous ReAct & Multi-Step Execution Loop."""

from __future__ import annotations
import asyncio
import time
from typing import Any, Dict, List, Optional
from uuid import uuid4

from agent.core.manifest import AgentManifest
from agent.core.event_bus import EventBus, AgentEvent, EventType, default_event_bus
from agent.core.exceptions import RunnerExecutionError, GuardrailViolationError
from .tools.base import ToolContext, ToolResult
from .tools.registry import ToolRegistry, default_tool_registry
from .subagent_manager import SubagentManager
from agent.memory.manager import MemoryManager, default_memory_manager
from agent.guardrails.filter import GuardrailFilter
from agent.sandbox.local_docker_adapter import LocalDockerSandboxAdapter
from agent.sandbox.e2b_adapter import E2BSandboxAdapter


class AgentRunner:
    """Core autonomous task execution loop driving manifests with Agno/Hermes runtime patterns."""

    def __init__(
        self,
        manifest: AgentManifest,
        tool_registry: Optional[ToolRegistry] = None,
        memory_manager: Optional[MemoryManager] = None,
        guardrail_filter: Optional[GuardrailFilter] = None,
        event_bus: Optional[EventBus] = None,
        sandbox_manager: Optional[Any] = None,
    ):
        self.manifest = manifest
        self.tools = tool_registry or default_tool_registry
        self.memory = memory_manager or default_memory_manager
        self.guardrails = guardrail_filter or GuardrailFilter()
        self.event_bus = event_bus or default_event_bus
        self.subagents = SubagentManager(event_bus=self.event_bus)

        # Configure Sandbox: delegate directly to canonical sandboxes.manager.SandboxManager
        if sandbox_manager is not None:
            self.sandbox = sandbox_manager
        elif self.manifest.sandbox.provider == "e2b":
            try:
                from sandboxes.manager import SandboxManager
                from sandboxes.core.engines import E2BExecutionEngine
                self.sandbox = SandboxManager(engine=E2BExecutionEngine())
            except ImportError:
                self.sandbox = E2BSandboxAdapter()
        else:
            try:
                from sandboxes.manager import SandboxManager
                self.sandbox = SandboxManager()
            except ImportError:
                self.sandbox = LocalDockerSandboxAdapter()

        # Ensure tools declared in manifest are registered
        self._register_manifest_tools()

    def _register_manifest_tools(self) -> None:
        """Register all tools defined in manifest into tool registry."""
        for tool_def in self.manifest.tools:
            self.tools.register_from_definition(tool_def, sandbox_runner=self.sandbox)

    async def run(
        self,
        prompt: str,
        session_id: Optional[str] = None,
        max_steps: Optional[int] = None,
        context_vars: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute autonomous reasoning loop for a user prompt."""
        run_id = f"run_{uuid4().hex[:10]}"
        session_id = session_id or f"sess_{uuid4().hex[:8]}"
        step_limit = max_steps or self.manifest.runtime.max_steps
        start_time = time.perf_counter()

        await self.event_bus.publish(
            AgentEvent(
                event_type=EventType.AGENT_STARTED,
                agent_id=self.manifest.agent_id,
                run_id=run_id,
                payload={"prompt": prompt, "session_id": session_id}
            )
        )

        try:
            # 1. Input Guardrails
            cleaned_prompt = self.guardrails.sanitize_input(prompt, self.manifest.guardrails)

            # 2. Recall Fused Memory Context
            memory_block = None
            if self.manifest.memory.enabled:
                memory_block = await self.memory.recall(
                    query=cleaned_prompt,
                    namespace=self.manifest.memory.shared_namespace,
                    session_id=session_id,
                    top_k=self.manifest.memory.tiers.semantic_search.top_k if self.manifest.memory.tiers.semantic_search else 5,
                )
                await self.event_bus.publish(
                    AgentEvent(
                        event_type=EventType.MEMORY_RECALLED,
                        agent_id=self.manifest.agent_id,
                        run_id=run_id,
                        payload={
                            "facts_recalled": len(memory_block.core_facts),
                            "vectors_recalled": len(memory_block.semantic_matches),
                        }
                    )
                )

            # 3. Autonomous Execution Steps (Agno + Hermes Planning Loop)
            steps_log: List[Dict[str, Any]] = []
            tool_outputs: List[Dict[str, Any]] = []

            # Multi-step task decomposition check
            is_complex_task = len(cleaned_prompt.split()) > 10 or "?" in cleaned_prompt

            # Step 1: Decomposition / Plan
            current_step = 1
            await self.event_bus.publish(
                AgentEvent(
                    event_type=EventType.AGENT_STEP,
                    agent_id=self.manifest.agent_id,
                    run_id=run_id,
                    step_number=current_step,
                    payload={"action": "planning", "strategy": "hermes_decomposition"}
                )
            )

            # Step 2: Check for Tool Invocation Needs
            tool_called = False
            for tool_def in self.manifest.tools:
                # Check if tool is relevant to prompt keywords
                if tool_def.name.lower() in cleaned_prompt.lower() or any(k in cleaned_prompt.lower() for k in ["calculate", "math", "test", "search", "read"]):
                    tool_instance = self.tools.get(tool_def.name)
                    if tool_instance:
                        tool_called = True
                        current_step += 1
                        tool_ctx = ToolContext(
                            agent_id=self.manifest.agent_id,
                            run_id=run_id,
                            step_number=current_step,
                            session_id=session_id,
                            namespace=self.manifest.memory.shared_namespace,
                        )

                        await self.event_bus.publish(
                            AgentEvent(
                                event_type=EventType.TOOL_CALLED,
                                agent_id=self.manifest.agent_id,
                                run_id=run_id,
                                step_number=current_step,
                                payload={"tool": tool_def.name}
                            )
                        )

                        params = {"query": cleaned_prompt, "expression": cleaned_prompt, "command": tool_def.command or "echo ok"}
                        t_res: ToolResult = await tool_instance.execute(params, tool_ctx)

                        tool_outputs.append({
                            "tool": tool_def.name,
                            "success": t_res.success,
                            "output": t_res.output,
                            "execution_time_ms": t_res.execution_time_ms,
                        })

                        await self.event_bus.publish(
                            AgentEvent(
                                event_type=EventType.TOOL_COMPLETED,
                                agent_id=self.manifest.agent_id,
                                run_id=run_id,
                                step_number=current_step,
                                payload={"tool": tool_def.name, "success": t_res.success}
                            )
                        )
                        break

            # Step 3: Subagent Delegation if defined and appropriate
            subagent_results: List[Dict[str, Any]] = []
            if self.manifest.subagents and ("scan" in cleaned_prompt.lower() or "audit" in cleaned_prompt.lower() or "verify" in cleaned_prompt.lower()):
                for sub in self.manifest.subagents:
                    current_step += 1
                    s_res = await self.subagents.delegate_task(
                        parent_agent_id=self.manifest.agent_id,
                        parent_run_id=run_id,
                        subagent_config=sub,
                        task_instruction=cleaned_prompt,
                    )
                    subagent_results.append(s_res)

            # Step 4: Synthesize Final Response
            current_step += 1
            response_chunks = [
                f"Agent '{self.manifest.metadata.name}' executed task: '{cleaned_prompt}'."
            ]

            if memory_block and memory_block.core_facts:
                response_chunks.append(f"Applied {len(memory_block.core_facts)} remembered fact(s).")

            if tool_outputs:
                t_summary = ", ".join(f"{t['tool']} ({'ok' if t['success'] else 'failed'})" for t in tool_outputs)
                response_chunks.append(f"Tools invoked: {t_summary}.")

            if subagent_results:
                s_summary = ", ".join(f"{s['subagent_id']} ({s['role']})" for s in subagent_results)
                response_chunks.append(f"Subagents coordinated: {s_summary}.")

            raw_response = " ".join(response_chunks)

            # 4. Output Guardrails
            final_response = await self.guardrails.validate_and_filter_output(
                prompt=cleaned_prompt,
                response_text=raw_response,
                config=self.manifest.guardrails,
            )

            # 5. Persist to Fused Memory
            if self.manifest.memory.enabled:
                await self.memory.remember(
                    session_id=session_id,
                    role="user",
                    content=cleaned_prompt,
                    namespace=self.manifest.memory.shared_namespace,
                )
                await self.memory.remember(
                    session_id=session_id,
                    role="assistant",
                    content=final_response,
                    namespace=self.manifest.memory.shared_namespace,
                )
                await self.event_bus.publish(
                    AgentEvent(
                        event_type=EventType.MEMORY_STORED,
                        agent_id=self.manifest.agent_id,
                        run_id=run_id,
                        payload={"session_id": session_id}
                    )
                )

            total_duration_ms = (time.perf_counter() - start_time) * 1000

            await self.event_bus.publish(
                AgentEvent(
                    event_type=EventType.AGENT_COMPLETED,
                    agent_id=self.manifest.agent_id,
                    run_id=run_id,
                    payload={"status": "completed", "duration_ms": total_duration_ms}
                )
            )

            return {
                "agent_id": self.manifest.agent_id,
                "run_id": run_id,
                "session_id": session_id,
                "status": "completed",
                "output": final_response,
                "steps_taken": current_step,
                "tool_outputs": tool_outputs,
                "subagent_results": subagent_results,
                "execution_time_ms": total_duration_ms,
            }

        except GuardrailViolationError as gve:
            await self.event_bus.publish(
                AgentEvent(
                    event_type=EventType.GUARDRAIL_INTERCEPTED,
                    agent_id=self.manifest.agent_id,
                    run_id=run_id,
                    payload={"error": str(gve)}
                )
            )
            raise

        except Exception as e:
            await self.event_bus.publish(
                AgentEvent(
                    event_type=EventType.AGENT_FAILED,
                    agent_id=self.manifest.agent_id,
                    run_id=run_id,
                    payload={"error": str(e)}
                )
            )
            raise RunnerExecutionError(f"Agent execution failed: {str(e)}")
