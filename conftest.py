import sys
import os
from pathlib import Path

# Add central-intelligence root and all module paths to sys.path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

# Load .env into os.environ if present so test runners match local docker compose configs
env_file = root_dir / ".env"
if env_file.is_file():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip("'\""))

cognitive_dir = root_dir / "cognitive"
control_dir = root_dir / "control"
platform_infra_dir = root_dir / "platform_infra"
surface_dir = root_dir / "surface"

for p in [
    cognitive_dir,
    cognitive_dir / "memory",
    cognitive_dir / "memory" / "storage",
    cognitive_dir / "knowledge",
    cognitive_dir / "perception",
    cognitive_dir / "action",
    cognitive_dir / "output",
    cognitive_dir / "learning",
    control_dir,
    control_dir / "orchestration",
    control_dir / "context",
    control_dir / "safety",
    control_dir / "safety" / "guardrails",
    control_dir / "evaluation",
    control_dir / "identity",
    control_dir / "identity" / "secrets",
    platform_infra_dir,
    platform_infra_dir / "data",
    platform_infra_dir / "compute",
    platform_infra_dir / "release",
    surface_dir,
    surface_dir / "interaction",
    surface_dir / "federation",
]:
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))
