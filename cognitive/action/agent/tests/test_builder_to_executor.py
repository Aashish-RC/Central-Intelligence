"""End-to-End Test: Builder graph compile -> Executor run test."""

import pytest
from agent.builder.compiler import ManifestCompiler
from agent.executor.runner import AgentRunner
from agent.core.event_bus import default_event_bus, EventType


@pytest.mark.asyncio
async def test_compile_graph_to_manifest():
    graph = {
        "nodes": [
            {
                "id": "node_1",
                "type": "agent",
                "data": {
                    "agent_id": "compiler-test-agent",
                    "name": "Graph Test Agent",
                    "description": "Compiled from visual nodes",
                }
            },
            {
                "id": "node_2",
                "type": "model",
                "data": {
                    "engine": "agno",
                    "model": "gemini-2.5-flash",
                    "temperature": 0.5,
                }
            },
            {
                "id": "node_3",
                "type": "tool",
                "data": {
                    "name": "calculator",
                    "tool_type": "builtin",
                    "description": "Safe math calculator",
                }
            },
            {
                "id": "node_4",
                "type": "subagent",
                "data": {
                    "subagent_id": "helper-bot",
                    "role": "Assistant Helper",
                }
            }
        ]
    }

    manifest = ManifestCompiler.compile_graph(graph)
    assert manifest.agent_id == "compiler-test-agent"
    assert manifest.metadata.name == "Graph Test Agent"
    assert manifest.runtime.model == "gemini-2.5-flash"
    assert any(t.name == "calculator" for t in manifest.tools)
    assert len(manifest.subagents) == 1


@pytest.mark.asyncio
async def test_end_to_end_executor_run():
    graph = {
        "nodes": [
            {
                "id": "n1",
                "type": "agent",
                "data": {
                    "agent_id": "math-solver-agent",
                    "name": "Math Solver",
                }
            },
            {
                "id": "n2",
                "type": "tool",
                "data": {
                    "name": "calculator",
                    "tool_type": "builtin",
                }
            }
        ]
    }

    manifest = ManifestCompiler.compile_graph(graph)
    runner = AgentRunner(manifest=manifest)

    # Track lifecycle events
    events_captured = []
    async def on_event(ev):
        events_captured.append(ev.event_type)

    default_event_bus.subscribe("*", on_event)

    res = await runner.run(prompt="calculate (25 * 4) + 50")

    assert res["status"] == "completed"
    assert res["agent_id"] == "math-solver-agent"
    assert res["steps_taken"] >= 2
    assert len(res["tool_outputs"]) >= 1
    assert res["tool_outputs"][0]["tool"] == "calculator"
    assert res["tool_outputs"][0]["output"] == 150.0

    # Verify event bus received lifecycle sequence
    assert EventType.AGENT_STARTED in events_captured
    assert EventType.AGENT_COMPLETED in events_captured
