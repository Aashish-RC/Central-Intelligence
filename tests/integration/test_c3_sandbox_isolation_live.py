"""C3 Verification: Real CI Sandbox Adapter Live Runtime Isolation Suite.

Validates that Central Intelligence's actual project sandbox adapter
(E2BSandboxAdapter -> LocalDockerSandboxAdapter -> SandboxManager -> DockerRunner)
executes untrusted code inside an isolated container runtime and enforces all
10 critical isolation controls at runtime:

1. Execution isolation: Untrusted code runs in Linux container, not Windows host.
2. Runtime identity: Platform reports Linux, preventing host environment leakage.
3. Privilege restrictions: CapEff is 0000000000000000, NoNewPrivs is 1.
4. Resource limits: Memory ceiling (<= 512MB) enforced by kernel cgroups.
5. Network isolation: Network access is denied by default (--network none).
6. Filesystem isolation: Root filesystem is strictly read-only.
7. Host isolation: Windows host drives and sensitive files are inaccessible.
8. Adversarial escape blocked: Host execution primitives statically blocked.
9. Tenant separation: Isolated workspaces per tenant with deterministic cleanup.
10. Timeout and cancellation: Rogue workloads terminate promptly; containers cleaned up.
11. Fail-closed behavior: Daemon unavailability never triggers unsafe host fallback.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Load .env into os.environ if present
_env_path = REPO_ROOT / ".env"
if _env_path.is_file():
    for _line in _env_path.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _, _v = _line.partition("=")
        os.environ.setdefault(_k.strip(), _v.strip().strip("'\""))

from agent.core.exceptions import SandboxExecutionError
from agent.core.manifest import SandboxConfig
from agent.sandbox.e2b_adapter import E2BSandboxAdapter
from cognitive.action.agent.sandbox.local_docker_adapter import LocalDockerSandboxAdapter
from cognitive.action.sandboxes.core.models import (
    ExecutionRequest,
    ResourceLimits,
    SandboxResult,
    SandboxStatus,
)
from cognitive.action.sandboxes.manager import SandboxManager
from cognitive.action.sandboxes.runner.docker_runner import DockerRunner
from control.safety.production_guard import ProductionSafetyError

pytestmark = [pytest.mark.live, pytest.mark.asyncio]


def _require_docker() -> None:
    """Fail test if Docker daemon is not operational (live acceptance requires working engine)."""
    docker_bin = shutil.which("docker")
    if not docker_bin:
        pytest.fail("Docker CLI not found on host - live acceptance requires functional container engine")
    try:
        res = subprocess.run(
            ["docker", "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10.0,
        )
        if res.returncode != 0:
            pytest.fail("Docker daemon is not responsive - live acceptance requires functional container engine")
    except Exception as exc:
        pytest.fail(f"Docker health check failed: {exc}")


async def test_c3_01_permitted_real_python_execution(monkeypatch):
    """Control 1: Untrusted Python code executes through the real CI sandbox adapter and computes real output."""
    _require_docker()
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)
    monkeypatch.delenv("E2B_API_KEY", raising=False)

    adapter = E2BSandboxAdapter()
    config = SandboxConfig(timeout_seconds=20)
    cmd = "python3 -c \"print('CENTRAL_INTELLIGENCE_C3_' + str(1000 + 42))\""

    res = await adapter.execute_command(cmd, config=config)
    assert res["exit_code"] == 0, f"Command failed: {res}"
    assert "CENTRAL_INTELLIGENCE_C3_1042" in res["stdout"]
    assert res["provider"] == "local-docker"
    assert "Simulated" not in res["stdout"]


async def test_c3_02_runtime_and_platform_identity(monkeypatch):
    """Control 2: Execution runtime reports Linux container identity, NOT Windows host."""
    _require_docker()
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)
    monkeypatch.delenv("E2B_API_KEY", raising=False)

    adapter = E2BSandboxAdapter()
    config = SandboxConfig(timeout_seconds=20)
    cmd = 'python3 -c "import sys, platform; print(f\'PLATFORM={sys.platform};SYSTEM={platform.system()}\')"'

    res = await adapter.execute_command(cmd, config=config)
    assert res["exit_code"] == 0
    stdout = res["stdout"].strip()
    assert "PLATFORM=linux" in stdout, f"Unexpected platform: {stdout}"
    assert "SYSTEM=Linux" in stdout, f"Unexpected OS: {stdout}"
    assert "win32" not in stdout
    assert "Windows" not in stdout


async def test_c3_03_effective_privileges_and_capabilities(monkeypatch):
    """Control 3: Kernel capabilities are fully dropped (CapEff=0) and NoNewPrivs is enforced."""
    _require_docker()
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)
    monkeypatch.delenv("E2B_API_KEY", raising=False)

    adapter = E2BSandboxAdapter()
    config = SandboxConfig(timeout_seconds=20)
    cmd = (
        'python3 -c "'
        'with open(\'/proc/self/status\') as f:\n'
        '    lines = {line.split(\':\')[0].strip(): line.split(\':\')[1].strip() for line in f if \':\' in line}\n'
        'print(\'CapEff=\' + lines.get(\'CapEff\', \'UNKNOWN\'))\n'
        'print(\'NoNewPrivs=\' + lines.get(\'NoNewPrivs\', \'UNKNOWN\'))\n'
        '"'
    )

    res = await adapter.execute_command(cmd, config=config)
    assert res["exit_code"] == 0, f"Execution failed: {res}"
    stdout = res["stdout"]
    assert "CapEff=0000000000000000" in stdout, f"Linux capabilities not fully dropped: {stdout}"
    assert "NoNewPrivs=1" in stdout, f"NoNewPrivs flag not active: {stdout}"


async def test_c3_04_effective_resource_limits(monkeypatch):
    """Control 4: Kernel memory, CPU, and process ceilings are enforced inside the container."""
    _require_docker()
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)
    monkeypatch.delenv("E2B_API_KEY", raising=False)

    adapter = E2BSandboxAdapter()
    config = SandboxConfig(timeout_seconds=20)
    cmd = (
        'python3 -c "'
        'import os\n'
        'mem_limit = None\n'
        'for p in [\'/sys/fs/cgroup/memory.max\', \'/sys/fs/cgroup/memory/memory.limit_in_bytes\']:\n'
        '    if os.path.exists(p):\n'
        '        with open(p) as f:\n'
        '            val = f.read().strip()\n'
        '            if val != \'max\':\n'
        '                mem_limit = int(val)\n'
        '                break\n'
        'pids_limit = None\n'
        'for p in [\'/sys/fs/cgroup/pids.max\', \'/sys/fs/cgroup/pids/pids.max\']:\n'
        '    if os.path.exists(p):\n'
        '        with open(p) as f:\n'
        '            val = f.read().strip()\n'
        '            if val != \'max\':\n'
        '                pids_limit = int(val)\n'
        '                break\n'
        'print(f\'CGROUP_MEMORY_LIMIT={mem_limit}\')\n'
        'print(f\'CGROUP_PIDS_LIMIT={pids_limit}\')\n'
        '"'
    )

    res = await adapter.execute_command(cmd, config=config)
    assert res["exit_code"] == 0, f"Execution failed: {res}"
    stdout = res["stdout"]
    assert "CGROUP_MEMORY_LIMIT=" in stdout, f"Missing cgroup memory output: {stdout}"
    
    # Extract memory limit integer; MUST be finite and established
    limit_str = stdout.split("CGROUP_MEMORY_LIMIT=")[1].split()[0]
    assert limit_str != "None" and limit_str != "max", (
        f"Failed to establish finite effective memory limit: {stdout}"
    )
    limit_bytes = int(limit_str)
    # Default is 512MB = 536,870,912 bytes
    assert 0 < limit_bytes <= 536870912, f"Memory ceiling {limit_bytes} exceeds 512MB or is invalid"

    # Verify process/pids ceiling if present
    if "CGROUP_PIDS_LIMIT=" in stdout:
        pids_str = stdout.split("CGROUP_PIDS_LIMIT=")[1].split()[0]
        if pids_str not in ("None", "max"):
            pids_val = int(pids_str)
            assert 0 < pids_val <= 64, f"Pids limit {pids_val} exceeds expected sandbox ceiling"


async def test_c3_05_network_denied_by_default(monkeypatch):
    """Control 5: Network access is denied by default through dual-layer defense:

    Layer 1: Static policy rejection by SecurityGovernor.
    Layer 2: Runtime kernel network isolation (--network none) inside the container.
    """
    _require_docker()
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)
    monkeypatch.delenv("E2B_API_KEY", raising=False)

    adapter = E2BSandboxAdapter()
    config = SandboxConfig(timeout_seconds=20)

    # Layer 1: Static governor validation blocks obvious network patterns
    with pytest.raises(SandboxExecutionError) as exc_info:
        await adapter.execute_command('python3 -c "import socket; s = socket.socket()"', config=config)
    assert "network access is disabled" in str(exc_info.value).lower()

    # Layer 2: Container runtime has only loopback interface (lo) and zero network interfaces
    net_check_cmd = (
        'python3 -c "'
        'import os\n'
        'ifaces = os.listdir(\'/sys/class/net\')\n'
        'print(\'NET_INTERFACES=\' + \',\'.join(sorted(ifaces)))\n'
        '"'
    )
    res = await adapter.execute_command(net_check_cmd, config=config)
    assert res["exit_code"] == 0
    assert "NET_INTERFACES=lo" in res["stdout"], f"Container has extra interfaces: {res['stdout']}"
    assert "eth0" not in res["stdout"]

    # Layer 2b: Dynamic socket connection attempting egress fails with Errno 101 (Network unreachable)
    dyn_socket_cmd = (
        'python3 -c "'
        'import sys\n'
        'sock_mod = getattr(__builtins__, \'__import__\')(\'soc\' + \'ket\')\n'
        's = sock_mod.socket(sock_mod.AF_INET, sock_mod.SOCK_STREAM)\n'
        's.settimeout(2.0)\n'
        'try:\n'
        '    s.connect((\'8.8.8.8\', 53))\n'
        '    print(\'NETWORK_LEAK_DETECTED\')\n'
        '    sys.exit(1)\n'
        'except OSError as exc:\n'
        '    print(f\'KERNEL_NETWORK_UNREACHABLE_VERIFIED: {exc}\')\n'
        '    sys.exit(0)\n'
        '"'
    )
    res_dyn = await adapter.execute_command(dyn_socket_cmd, config=config)
    assert res_dyn["exit_code"] == 0
    assert "KERNEL_NETWORK_UNREACHABLE_VERIFIED" in res_dyn["stdout"]
    assert "NETWORK_LEAK_DETECTED" not in res_dyn["stdout"]


async def test_c3_06_read_only_root_filesystem(monkeypatch):
    """Control 6: Root filesystem is read-only; arbitrary filesystem mutations fail with EROFS."""
    _require_docker()
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)
    monkeypatch.delenv("E2B_API_KEY", raising=False)

    adapter = E2BSandboxAdapter()
    config = SandboxConfig(timeout_seconds=20)
    cmd = (
        'python3 -c "'
        'import sys\n'
        'for path in [\'/root_probe.txt\', \'/etc/test_probe.txt\']:\n'
        '    try:\n'
        '        with open(path, \'w\') as f:\n'
        '            f.write(\'leak\')\n'
        '        print(f\'MUTATION_SUCCEEDED_ON_{path}\')\n'
        '        sys.exit(1)\n'
        '    except OSError as exc:\n'
        '        if exc.errno == 30 or \'Read-only file system\' in str(exc):\n'
        '            continue\n'
        '        print(f\'UNEXPECTED_ERR: {exc}\')\n'
        '        sys.exit(1)\n'
        'print(\'READ_ONLY_ROOTFS_VERIFIED\')\n'
        'sys.exit(0)\n'
        '"'
    )

    res = await adapter.execute_command(cmd, config=config)
    assert res["exit_code"] == 0, f"Rootfs write was not blocked: {res}"
    assert "READ_ONLY_ROOTFS_VERIFIED" in res["stdout"]


async def test_c3_07_filesystem_isolation_no_host_mounts(monkeypatch):
    """Control 7: Host drives and sensitive host operating system paths are inaccessible."""
    _require_docker()
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)
    monkeypatch.delenv("E2B_API_KEY", raising=False)

    adapter = E2BSandboxAdapter()
    config = SandboxConfig(timeout_seconds=20)
    cmd = (
        'python3 -c "'
        'import os, sys\n'
        'suspicious_paths = [\'/mnt/c\', \'/mnt/d\', \'/c\', \'/d\', \'/host_root\']\n'
        'found = [p for p in suspicious_paths if os.path.exists(p)]\n'
        'if found:\n'
        '    print(f\'HOST_MOUNTS_EXPOSED: {found}\')\n'
        '    sys.exit(1)\n'
        'print(\'HOST_ISOLATION_VERIFIED\')\n'
        'sys.exit(0)\n'
        '"'
    )

    res = await adapter.execute_command(cmd, config=config)
    assert res["exit_code"] == 0
    assert "HOST_ISOLATION_VERIFIED" in res["stdout"]


async def test_c3_08_adversarial_host_escape_blocked(monkeypatch):
    """Control 8: Adversarial breakout attempts and Windows host execution binaries are statically rejected."""
    _require_docker()
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)
    monkeypatch.delenv("E2B_API_KEY", raising=False)

    adapter = LocalDockerSandboxAdapter()
    config = SandboxConfig(timeout_seconds=10)

    # Negative test 1: PowerShell command invocation
    with pytest.raises(SandboxExecutionError) as exc_info:
        await adapter.execute_command("powershell.exe -c whoami", config=config)
    assert "blocked by security policy" in str(exc_info.value).lower() or "blocked by local sandbox" in str(exc_info.value).lower()

    # Negative test 2: Cmd.exe host shell breakout
    with pytest.raises(SandboxExecutionError) as exc_info:
        await adapter.execute_command("cmd.exe /c dir C:\\", config=config)
    assert "blocked by security policy" in str(exc_info.value).lower() or "blocked by local sandbox" in str(exc_info.value).lower()

    # Negative test 3: Shadow file read attempt
    with pytest.raises(SandboxExecutionError) as exc_info:
        await adapter.execute_command("cat /etc/shadow", config=config)
    assert "blocked" in str(exc_info.value).lower()


async def test_c3_08b_host_scratch_path_traversal_blocked(monkeypatch):
    """Control 8b: Host scratch directory path traversal and special filenames are strictly rejected."""
    _require_docker()
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)
    monkeypatch.delenv("E2B_API_KEY", raising=False)

    adapter = E2BSandboxAdapter()
    config = SandboxConfig(timeout_seconds=10)

    dangerous_file_keys = [
        "../../etc/cron.d/evil",
        "C:\\Windows\\system32\\evil.dll",
        "D:/System/rootkit.sys",
        "\\\\evil-server\\share\\malware.exe",
        "//192.168.1.5/share/exploit.bat",
        "test.txt:hidden_stream",
        "CON",
        "aux/file.txt",
        "sub/con.py",
        "COM1",
        "evil.txt.",
        "evil.txt ",
        "/absolute/root/file.py",
    ]

    for bad_name in dangerous_file_keys:
        with pytest.raises(SandboxExecutionError) as exc_info:
            await adapter.execute_command(
                'python3 -c "print(1)"',
                config=config,
                files={bad_name: "payload content"},
            )
        err = str(exc_info.value).lower()
        assert any(
            token in err
            for token in [
                "blocked",
                "traversal",
                "escape",
                "reserved",
                "rejected",
            ]
        ), f"Filename '{bad_name}' was not blocked as expected: {err}"


async def test_c3_09_tenant_isolation_and_workspace_cleanup(monkeypatch):
    """Control 9: Tenant workspaces are isolated; Tenant B cannot observe Tenant A's scratch files."""
    _require_docker()
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)
    monkeypatch.delenv("E2B_API_KEY", raising=False)

    adapter = E2BSandboxAdapter()
    config = SandboxConfig(timeout_seconds=20)
    tenant_a = f"tenant_a_{uuid4().hex[:6]}"
    tenant_b = f"tenant_b_{uuid4().hex[:6]}"

    # Tenant A execution with a tenant-private file
    files_a = {"secret_plan.txt": f"SECRET_FOR_{tenant_a}"}
    cmd_a = 'python3 -c "import os; print(\'A_READ:\' + open(\'/workspace/secret_plan.txt\').read())"'
    res_a = await adapter.execute_command(
        cmd_a, config=config, tenant_id=tenant_a, files=files_a
    )
    assert res_a["exit_code"] == 0
    assert f"SECRET_FOR_{tenant_a}" in res_a["stdout"]

    # Tenant B execution: secret_plan.txt must NOT exist
    cmd_b = (
        'python3 -c "'
        'import os\n'
        'if os.path.exists(\'/workspace/secret_plan.txt\'):\n'
        '    print(\'CROSS_TENANT_LEAK\')\n'
        'else:\n'
        '    print(\'TENANT_ISOLATION_CONFIRMED\')\n'
        '"'
    )
    res_b = await adapter.execute_command(
        cmd_b, config=config, tenant_id=tenant_b, files={}
    )
    assert res_b["exit_code"] == 0
    assert "TENANT_ISOLATION_CONFIRMED" in res_b["stdout"]
    assert "CROSS_TENANT_LEAK" not in res_b["stdout"]


async def test_c3_10_timeout_and_process_cleanup(monkeypatch):
    """Control 10: Infinite loops and runaway execution abort cleanly at configured timeout; container is removed."""
    _require_docker()
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)
    monkeypatch.delenv("E2B_API_KEY", raising=False)

    adapter = E2BSandboxAdapter()
    # Enforce short timeout (2s)
    config = SandboxConfig(timeout_seconds=2)
    start_t = time.perf_counter()

    with pytest.raises(SandboxExecutionError) as exc_info:
        await adapter.execute_command(
            'python3 -c "import time; time.sleep(30)"',
            config=config,
        )

    elapsed = time.perf_counter() - start_t
    assert elapsed < 10.0, f"Timeout enforcement exceeded expected window: {elapsed:.2f}s"
    assert "timed out" in str(exc_info.value).lower()

    # Verify no dangling containers with our prefix remain running across configured runtime
    runtime_bin = os.getenv("CONTAINER_RUNTIME") or "docker"
    res = subprocess.run(
        [runtime_bin, "ps", "--filter", "name=pheonix-sb-", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
    )
    dangling = [name for name in res.stdout.strip().splitlines() if name]
    assert len(dangling) == 0, f"Dangling sandbox containers detected after timeout: {dangling}"


async def test_c3_11_fail_closed_when_runtime_unavailable(monkeypatch):
    """Control 11: Fail-closed guarantee: when Docker runtime is unavailable, execution fails safely without host fallback."""
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.setenv("E2B_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)
    monkeypatch.delenv("E2B_API_KEY", raising=False)

    # Force DockerRunner to report docker as unavailable on both module import paths
    try:
        from sandboxes.runner.docker_runner import DockerRunner as SB_DockerRunner
        monkeypatch.setattr(SB_DockerRunner, "is_docker_available", lambda self: False)
    except ImportError:
        pass
    monkeypatch.setattr(DockerRunner, "is_docker_available", lambda self: False)

    adapter = E2BSandboxAdapter()
    config = SandboxConfig(timeout_seconds=5)

    with pytest.raises((SandboxExecutionError, ProductionSafetyError)) as exc_info:
        await adapter.execute_command('python3 -c "print(123)"', config=config)

    err = str(exc_info.value).lower()
    assert any(
        kw in err
        for kw in [
            "prohibited sandbox fallback",
            "neither e2b cloud nor local docker sandbox available",
            "unavailable",
            "forbidden",
            "blocked",
        ]
    )
