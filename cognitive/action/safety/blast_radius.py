"""Blast Radius Simulator: Dry-run simulation and impact assessment for planned actions.

Feature: 5.27
"""

from typing import Any, Dict, List
from .models import BlastRadiusReport


class BlastRadiusSimulator:
    """Predicts resources touched, reversibility, and financial cost before execution."""

    def simulate(
        self,
        action_name: str,
        parameters: Dict[str, Any],
    ) -> BlastRadiusReport:
        affected_files: List[str] = []
        affected_services: List[str] = []
        is_destructive = False
        reversibility = True
        estimated_cost = 0.0

        act_lower = action_name.lower()

        # Files analysis
        if "path" in parameters:
            affected_files.append(str(parameters["path"]))
        if "files" in parameters and isinstance(parameters["files"], (list, dict)):
            affected_files.extend(list(parameters["files"]))

        # Services touched
        if "channel" in parameters:
            affected_services.append(f"chat:{parameters['channel']}")
        if "url" in parameters:
            affected_services.append(f"http:{parameters['url']}")
        if "database" in parameters or "sql" in parameters:
            affected_services.append("database:primary")

        # Check destructiveness
        param_text = " ".join(str(v).lower() for v in parameters.values())
        if any(w in act_lower or w in param_text for w in ["drop", "delete", "destroy", "truncate", "rm -rf"]):
            is_destructive = True
            reversibility = False

        if "amount" in parameters:
            try:
                estimated_cost = float(parameters["amount"])
            except (ValueError, TypeError):
                pass

        summary = (
            f"Simulated '{action_name}': {len(affected_files)} files, "
            f"{len(affected_services)} services, destructive={is_destructive}"
        )

        return BlastRadiusReport(
            action_name=action_name,
            affected_files=affected_files,
            affected_services=affected_services,
            estimated_cost_usd=estimated_cost,
            is_destructive=is_destructive,
            reversibility_guaranteed=reversibility,
            summary=summary,
        )
