"""Prompt Templates Module (Layer 9: Context Engineering, Feature 9.08)."""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


class TemplateRenderError(Exception):
    """Raised when variable substitution fails or required variables are missing."""
    pass


@dataclass
class PromptTemplate:
    """Parameterized prompt template with strict variable interpolation and defaults."""
    name: str
    template: str
    version: str = "1.0.0"
    description: str = ""
    defaults: Dict[str, Any] = field(default_factory=dict)
    required_variables: Set[str] = field(default_factory=set)

    def __post_init__(self):
        # Extract variables enclosed in {{var}} or {var}
        detected = set(re.findall(r"\{\{([a-zA-Z0-9_]+)\}\}", self.template))
        detected.update(re.findall(r"\{([a-zA-Z0-9_]+)\}", self.template))
        # Exclude variables that already have defaults
        if not self.required_variables:
            self.required_variables = {v for v in detected if v not in self.defaults}

    def render(self, variables: Optional[Dict[str, Any]] = None) -> str:
        """Substitutes variables into the template string."""
        variables = variables or {}
        merged = {**self.defaults, **variables}

        missing = [v for v in self.required_variables if v not in merged]
        if missing:
            raise TemplateRenderError(
                f"Missing required variables for template '{self.name}:{self.version}': {missing}"
            )

        rendered = self.template

        # Support both {{var}} and {var}
        for key, value in merged.items():
            str_val = str(value)
            rendered = rendered.replace(f"{{{{{key}}}}}", str_val)
            rendered = re.sub(rf"\{{{key}\}}", str_val, rendered)

        return rendered
