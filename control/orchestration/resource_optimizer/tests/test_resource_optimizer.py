"""
Pheonix Resource Optimizer Test Suite
Validates adaptive concurrency, host load thresholds, rate-limit headroom,
deterministic clocking, thread safety, and orchestrator DAG runner integration.
"""

import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
from orchestrator.core.models import TaskStatus
from orchestrator.engine.dag_runner import ParallelDAGRunner
from orchestrator.planner.multi_step_planner import MultiStepPlanner
from resource_optimizer.core.optimizer import ResourceOptimizer
from resource_optimizer.core.signals import FakeSignalSource
from resource_optimizer.models import (
    Decision,
    ResourceOptimizerConfig,
    TaskDescriptor,
)


class TestResourceOptimizerCore:
    """Core unit tests for ResourceOptimizer adaptive logic and safety bounds."""

    def test_cap_grows_when_healthy(self):
        """Cap starts at initial_cap and adds 1 after every N consecutive healthy checks up to max."""
        config = ResourceOptimizerConfig(
            initial_cap=2,
            max_cap=5,
            healthy_checks_threshold=3,
        )
        fake_signals = FakeSignalSource(cpu_percent=20.0, ram_percent=30.0)
        optimizer = ResourceOptimizer(signal_source=fake_signals, config=config)

        assert optimizer.concurrency_cap == 2

        # 1st healthy check
        d = optimizer.acquire("t1")
        assert d.action == "allow"
        assert optimizer.concurrency_cap == 2
        optimizer.release("t1")

        # 2nd healthy check
        d = optimizer.acquire("t2")
        assert d.action == "allow"
        assert optimizer.concurrency_cap == 2
        optimizer.release("t2")

        # 3rd healthy check -> triggers growth (+1)
        d = optimizer.acquire("t3")
        assert d.action == "allow"
        assert optimizer.concurrency_cap == 3
        optimizer.release("t3")

        # 3 more healthy checks -> grows to 4
        for i in range(3):
            d = optimizer.acquire(f"t_growth_{i}")
            optimizer.release(f"t_growth_{i}")

        assert optimizer.concurrency_cap == 4

    def test_cap_halves_under_cpu_pressure(self):
        """Cap halves immediately when CPU usage exceeds 85%."""
        config = ResourceOptimizerConfig(
            initial_cap=4,
            cpu_threshold_percent=85.0,
        )
        fake_signals = FakeSignalSource(cpu_percent=92.0, ram_percent=30.0)
        optimizer = ResourceOptimizer(signal_source=fake_signals, config=config)

        assert optimizer.concurrency_cap == 4

        d = optimizer.acquire("t_cpu")
        # Halves from 4 -> 2
        assert optimizer.concurrency_cap == 2
        optimizer.release("t_cpu")

        # Another high-CPU check halves from 2 -> 1
        d = optimizer.acquire("t_cpu_2")
        assert optimizer.concurrency_cap == 1
        optimizer.release("t_cpu_2")

    def test_cap_halves_under_ram_pressure(self):
        """Cap halves immediately when RAM usage exceeds 85%."""
        config = ResourceOptimizerConfig(
            initial_cap=4,
            ram_threshold_percent=85.0,
        )
        fake_signals = FakeSignalSource(cpu_percent=20.0, ram_percent=88.5)
        optimizer = ResourceOptimizer(signal_source=fake_signals, config=config)

        d = optimizer.acquire("t_ram")
        assert optimizer.concurrency_cap == 2
        optimizer.release("t_ram")

    def test_cap_floors_at_1(self):
        """Repeated load spikes never reduce concurrency cap below 1."""
        config = ResourceOptimizerConfig(
            initial_cap=1,
            cpu_threshold_percent=85.0,
        )
        fake_signals = FakeSignalSource(cpu_percent=99.0, ram_percent=95.0)
        optimizer = ResourceOptimizer(signal_source=fake_signals, config=config)

        for i in range(5):
            d = optimizer.acquire(f"t_floor_{i}")
            assert optimizer.concurrency_cap == 1
            optimizer.release(f"t_floor_{i}")

        assert optimizer.concurrency_cap == 1

    def test_cap_never_exceeds_max(self):
        """Cap growth stops upon reaching max_cap."""
        config = ResourceOptimizerConfig(
            initial_cap=2,
            max_cap=3,
            healthy_checks_threshold=1,
        )
        fake_signals = FakeSignalSource(cpu_percent=10.0, ram_percent=10.0)
        optimizer = ResourceOptimizer(signal_source=fake_signals, config=config)

        # 5 healthy checks with threshold=1
        for i in range(5):
            d = optimizer.acquire(f"t_max_{i}")
            optimizer.release(f"t_max_{i}")

        assert optimizer.concurrency_cap == 3

    def test_device_profile_sets_max_cap(self):
        """Device profile logical_cores bounds max_cap dynamically."""
        mock_profile = MagicMock()
        mock_profile.logical_cores = 6
        config = ResourceOptimizerConfig(initial_cap=2, max_cap=16, healthy_checks_threshold=1)
        fake_signals = FakeSignalSource(cpu_percent=10.0, ram_percent=10.0)
        optimizer = ResourceOptimizer(
            signal_source=fake_signals,
            config=config,
            device_profile=mock_profile,
        )

        assert optimizer.max_cap == 6
        for i in range(10):
            d = optimizer.acquire(f"t_prof_{i}")
            optimizer.release(f"t_prof_{i}")

        assert optimizer.concurrency_cap == 6

    def test_provider_headroom_causes_delay(self):
        """Low provider rate-limit headroom (< 10%) produces delay decision."""
        config = ResourceOptimizerConfig(
            provider_headroom_threshold=0.10,
            default_delay_seconds=0.75,
        )
        fake_signals = FakeSignalSource(
            cpu_percent=20.0,
            ram_percent=20.0,
            provider_headroom={"anthropic": 0.05, "openai": 0.90},
        )
        optimizer = ResourceOptimizer(signal_source=fake_signals, config=config)

        task = TaskDescriptor(task_id="call_claude", provider="anthropic")
        decision = optimizer.acquire(task)

        assert decision.action == "delay"
        assert decision.delay_seconds == 0.75
        assert "anthropic" in decision.reason
        assert "critically low" in decision.reason

    def test_release_frees_a_slot(self):
        """Releasing an active slot allows subsequent task acquisition."""
        config = ResourceOptimizerConfig(initial_cap=2, max_cap=2)
        fake_signals = FakeSignalSource(cpu_percent=20.0, ram_percent=20.0)
        optimizer = ResourceOptimizer(signal_source=fake_signals, config=config)

        d1 = optimizer.acquire("task_1")
        assert d1.action == "allow"

        d2 = optimizer.acquire("task_2")
        assert d2.action == "allow"

        # Cap is 2; 3rd task should delay
        d3 = optimizer.acquire("task_3")
        assert d3.action == "delay"

        # Release task 1
        optimizer.release("task_1")

        # Now task 3 can acquire
        d4 = optimizer.acquire("task_3")
        assert d4.action == "allow"
        optimizer.release("task_2")
        optimizer.release("task_3")

    def test_status_message_text(self):
        """Status message outputs user-facing status string under various conditions."""
        config = ResourceOptimizerConfig(cpu_threshold_percent=85.0)
        fake_signals = FakeSignalSource(cpu_percent=20.0, ram_percent=20.0)
        optimizer = ResourceOptimizer(signal_source=fake_signals, config=config)

        assert "Operating normally" in optimizer.status_message()

        # Under load pressure
        fake_signals.cpu_percent = 95.0
        assert optimizer.status_message() == "Slowing down to protect your device."

        # Under provider headroom pressure
        fake_signals.cpu_percent = 20.0
        fake_signals.provider_headroom = {"google": 0.04}
        assert optimizer.status_message() == "Slowing down to protect provider rate limits."

    def test_config_from_environment(self, monkeypatch):
        """ResourceOptimizerConfig correctly loads overrides from environment variables."""
        monkeypatch.setenv("PHEONIX_RESOURCE_INITIAL_CAP", "6")
        monkeypatch.setenv("PHEONIX_RESOURCE_MAX_CAP", "14")
        monkeypatch.setenv("PHEONIX_RESOURCE_HEALTHY_THRESHOLD", "5")
        monkeypatch.setenv("PHEONIX_RESOURCE_CPU_THRESHOLD", "80.0")
        monkeypatch.setenv("PHEONIX_RESOURCE_RAM_THRESHOLD", "78.0")
        monkeypatch.setenv("PHEONIX_RESOURCE_PROVIDER_HEADROOM_THRESHOLD", "0.15")
        monkeypatch.setenv("PHEONIX_RESOURCE_DEFAULT_DELAY_SECONDS", "1.2")
        monkeypatch.setenv("PHEONIX_RESOURCE_LEASE_TIMEOUT_SECONDS", "8.0")

        cfg = ResourceOptimizerConfig.from_env()
        assert cfg.initial_cap == 6
        assert cfg.max_cap == 14
        assert cfg.healthy_checks_threshold == 5
        assert cfg.cpu_threshold_percent == 80.0
        assert cfg.ram_threshold_percent == 78.0
        assert cfg.provider_headroom_threshold == 0.15
        assert cfg.default_delay_seconds == 1.2
        assert cfg.lease_timeout_seconds == 8.0

    def test_fake_clock_determinism(self):
        """Injected clock governs timeouts without relying on system sleeps."""
        fake_time = [1000.0]

        def fake_clock():
            return fake_time[0]

        config = ResourceOptimizerConfig(initial_cap=2, lease_timeout_seconds=5.0)
        optimizer = ResourceOptimizer(clock=fake_clock, config=config)

        optimizer.acquire("task_1")
        assert optimizer.active_count == 1

        # Advance clock within lease window
        fake_time[0] = 1004.0
        assert optimizer.active_count == 1

        # Advance past lease window
        fake_time[0] = 1006.0
        assert optimizer.active_count == 0

    def test_forgotten_release_does_not_deadlock(self):
        """Stale slot leases are automatically reaped after lease_timeout_seconds."""
        fake_time = [0.0]

        def fake_clock():
            return fake_time[0]

        config = ResourceOptimizerConfig(initial_cap=1, max_cap=1, lease_timeout_seconds=5.0)
        optimizer = ResourceOptimizer(clock=fake_clock, config=config)

        # Task A acquires and forgets to release
        d1 = optimizer.acquire("task_forgotten")
        assert d1.action == "allow"

        # Task B blocked
        d2 = optimizer.acquire("task_b")
        assert d2.action == "delay"

        # Advance clock beyond lease timeout
        fake_time[0] += 6.0

        # Task B re-acquires; stale lease is purged, task B is allowed
        d3 = optimizer.acquire("task_b")
        assert d3.action == "allow"
        optimizer.release("task_b")

    def test_20_threads_no_deadlock(self):
        """20 concurrent threads acquiring and releasing concurrently without deadlock."""
        config = ResourceOptimizerConfig(initial_cap=4, max_cap=8)
        fake_signals = FakeSignalSource(cpu_percent=30.0, ram_percent=40.0)
        optimizer = ResourceOptimizer(signal_source=fake_signals, config=config)

        errors = []

        def worker(worker_id):
            try:
                for i in range(5):
                    decision = optimizer.acquire_blocking(f"worker_{worker_id}_{i}", timeout=2.0)
                    if decision.action != "allow":
                        errors.append(f"Worker {worker_id} got {decision.action}")
                    time.sleep(0.005)
                    optimizer.release(f"worker_{worker_id}_{i}")
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        assert len(errors) == 0
        assert optimizer.active_count == 0


class TestResourceOptimizerDAGIntegration:
    """Integration tests connecting ResourceOptimizer with orchestrator ParallelDAGRunner."""

    def test_dag_runner_integration(self):
        """ParallelDAGRunner executes tasks while respecting ResourceOptimizer acquire/release."""
        config = ResourceOptimizerConfig(initial_cap=2, max_cap=2)
        fake_signals = FakeSignalSource(cpu_percent=15.0, ram_percent=25.0)
        optimizer = ResourceOptimizer(signal_source=fake_signals, config=config)

        planner = MultiStepPlanner()
        runner = ParallelDAGRunner(resource_optimizer=optimizer)

        executed_nodes = []
        runner.register_handler(
            "test_action",
            lambda node, ctx: executed_nodes.append(node.id) or f"Result of {node.id}",
        )

        specs = [
            {"id": f"node_{i}", "action": "test_action", "depends_on": []}
            for i in range(4)
        ]

        plan = planner.create_plan("Optimizer DAG Plan", specs, max_concurrency=4)
        report = runner.run_plan(plan)

        assert report.status == TaskStatus.COMPLETED
        assert report.completed_nodes == 4
        assert len(executed_nodes) == 4
        assert optimizer.active_count == 0

    def test_burst_of_10_steps_with_cap_3(self):
        """
        Critical spec test: A burst of 10 independent steps with concurrency cap 3
        never executes more than 3 tasks concurrently.
        """
        config = ResourceOptimizerConfig(
            initial_cap=3,
            max_cap=3,
            default_delay_seconds=0.02,
        )
        fake_signals = FakeSignalSource(cpu_percent=20.0, ram_percent=30.0)
        optimizer = ResourceOptimizer(signal_source=fake_signals, config=config)

        planner = MultiStepPlanner()
        runner = ParallelDAGRunner(resource_optimizer=optimizer)

        active_concurrent = 0
        max_concurrent_observed = 0
        counter_lock = threading.Lock()

        def throttled_step(node, ctx):
            nonlocal active_concurrent, max_concurrent_observed
            with counter_lock:
                active_concurrent += 1
                if active_concurrent > max_concurrent_observed:
                    max_concurrent_observed = active_concurrent
            # Simulate work
            time.sleep(0.04)
            with counter_lock:
                active_concurrent -= 1
            return f"output_{node.id}"

        runner.register_handler("burst_step", throttled_step)

        specs = [
            {"id": f"burst_node_{i}", "action": "burst_step", "depends_on": []}
            for i in range(10)
        ]

        plan = planner.create_plan("Burst 10 Plan", specs, max_concurrency=10)
        start = time.perf_counter()
        report = runner.run_plan(plan)
        duration = time.perf_counter() - start

        assert report.status == TaskStatus.COMPLETED
        assert report.completed_nodes == 10
        assert report.failed_nodes == 0
        assert optimizer.active_count == 0

        # Concurrency must NEVER exceed the cap of 3
        assert max_concurrent_observed <= 3
        # Must have achieved concurrency (at least 2 simultaneously)
        assert max_concurrent_observed >= 2
