import sys
import os
from pathlib import Path

# Add central-intelligence root and all module paths to sys.path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

cognitive_dir = root_dir / "cognitive"
control_dir = root_dir / "control"

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
]:
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

# Ensure platform package namespace works even if pytest pre-imported stdlib platform
platform_dir = root_dir / "platform"
if platform_dir.exists():
    import platform as _std_platform
    if not hasattr(_std_platform, "__path__"):
        _std_platform.__path__ = [str(platform_dir)]

