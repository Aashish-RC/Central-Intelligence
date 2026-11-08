"""
Pheonix Rules Storage Engine
Handles atomic persistence of rule definitions.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, List

from ..models import RuleDefinition


class RulesStore:
    """Manages atomic disk storage and loading of rule definitions."""

    def __init__(self, store_path: Path):
        self.store_path = Path(store_path)

    def exists(self) -> bool:
        return self.store_path.exists()

    def save(self, rules: List[RuleDefinition]):
        """Atomically persist rules to disk."""
        data = {
            "schema_version": "1.0",
            "rules": [r.model_dump() for r in rules],
        }
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.store_path.with_suffix(f".tmp.{os.getpid()}")

        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())

        os.replace(tmp_path, self.store_path)

    def load(self) -> List[RuleDefinition]:
        """Load rules from disk."""
        if not self.store_path.exists():
            return []

        with open(self.store_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return [RuleDefinition(**item) for item in data.get("rules", [])]
