"""Central Intelligence Platform Layers: L15 Data, L16 Compute, L17 Release.

Transparently proxies Python's standard library `platform` module while providing
the package namespace for Central Intelligence platform subsystems:
platform.data, platform.compute, and platform.release.
"""

import importlib.util
import pathlib
import sys

# Locate and load standard library platform module
_stdlib_platform_path = pathlib.Path(sys.base_prefix) / "Lib" / "platform.py"
if _stdlib_platform_path.exists():
    _spec = importlib.util.spec_from_file_location("_stdlib_platform", str(_stdlib_platform_path))
    if _spec and _spec.loader:
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        # Expose all standard library platform attributes
        for _attr in dir(_mod):
            if not _attr.startswith("__"):
                globals()[_attr] = getattr(_mod, _attr)
