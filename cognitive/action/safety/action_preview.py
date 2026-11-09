"""Action Preview Renderer for Pre-Execution Impact Visualization.

Feature: 5.27 (Action Preview Renderer)
Generates structured, human-readable diffs and impact previews for:
- Shell commands (detects destructive flags, elevated privileges, wildcard deletion)
- SQL queries (detects unconstrained mutations, table drops, schema alters)
- File writes (unified diffs with line additions/deletions)
- API calls (payload redaction, endpoint classification)
"""

import difflib
import json
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class ActionPreview(BaseModel):
    """Structured preview of planned action impact."""
    model_config = ConfigDict(extra="ignore")

    action_type: str
    summary: str
    diff_content: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    danger_score: float = 0.0  # 0.0 (safe) to 1.0 (critical)
    requires_confirmation: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ActionPreviewRenderer:
    """Renders comprehensive action previews prior to execution."""

    SENSITIVE_KEYS = {"password", "token", "secret", "api_key", "authorization", "bearer", "private_key"}

    @classmethod
    def render_shell_preview(cls, command: str) -> ActionPreview:
        """Render impact preview for a shell command."""
        cmd_clean = command.strip()
        warnings: List[str] = []
        danger_score = 0.1

        # Check for dangerous patterns
        if re.search(r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f?|-f?[a-zA-Z]*r)\s+", cmd_clean):
            warnings.append("Destructive recursive deletion detected ('rm -rf' or equivalent).")
            danger_score = max(danger_score, 0.9)

        if "sudo " in cmd_clean or "runas" in cmd_clean.lower():
            warnings.append("Elevated administrative/root privileges requested.")
            danger_score = max(danger_score, 0.8)

        if re.search(r">\s*/dev/sd[a-z]|format\s+[a-zA-Z]:|dd\s+if=", cmd_clean):
            warnings.append("Direct disk or raw partition mutation detected.")
            danger_score = 1.0

        if re.search(r"chmod\s+(-R\s+)?777", cmd_clean):
            warnings.append("Insecure permissive permission change ('chmod 777').")
            danger_score = max(danger_score, 0.7)

        requires_confirmation = danger_score >= 0.7

        return ActionPreview(
            action_type="shell",
            summary=f"Execute shell command: {cmd_clean[:80]}{'...' if len(cmd_clean) > 80 else ''}",
            diff_content=f"$ {cmd_clean}",
            warnings=warnings,
            danger_score=danger_score,
            requires_confirmation=requires_confirmation,
            metadata={"command": cmd_clean},
        )

    @classmethod
    def render_sql_preview(
        cls, query: str, current_rows_estimate: Optional[int] = None
    ) -> ActionPreview:
        """Render impact preview for an SQL query."""
        q_upper = query.strip().upper()
        warnings: List[str] = []
        danger_score = 0.2

        is_mutation = any(
            q_upper.startswith(verb)
            for verb in ["UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "INSERT"]
        )

        if not is_mutation:
            return ActionPreview(
                action_type="sql",
                summary="Execute read-only SQL query",
                diff_content=query.strip(),
                warnings=[],
                danger_score=0.1,
                requires_confirmation=False,
                metadata={"is_read_only": True},
            )

        if q_upper.startswith("DROP") or q_upper.startswith("TRUNCATE"):
            warnings.append("Irreversible schema/table destruction detected.")
            danger_score = 0.95
        elif (q_upper.startswith("DELETE") or q_upper.startswith("UPDATE")) and "WHERE" not in q_upper:
            warnings.append("Unconstrained mutation: missing WHERE clause affects ALL rows in target table!")
            danger_score = 0.9
        else:
            danger_score = 0.5

        if current_rows_estimate is not None and current_rows_estimate > 1000:
            warnings.append(f"High blast radius: potentially impacts ~{current_rows_estimate} existing records.")
            danger_score = max(danger_score, 0.8)

        requires_confirmation = danger_score >= 0.7

        return ActionPreview(
            action_type="sql",
            summary=f"Execute SQL mutation ({q_upper.split()[0]})",
            diff_content=query.strip(),
            warnings=warnings,
            danger_score=danger_score,
            requires_confirmation=requires_confirmation,
            metadata={
                "is_mutation": True,
                "estimated_rows": current_rows_estimate,
            },
        )

    @classmethod
    def render_file_write_preview(
        cls, file_path: str, old_content: str, new_content: str
    ) -> ActionPreview:
        """Render unified diff and metrics for a file write or edit."""
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff = list(
            difflib.unified_diff(
                old_lines,
                new_lines,
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
            )
        )
        diff_text = "".join(diff)

        added = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
        removed = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))

        warnings: List[str] = []
        danger_score = 0.2

        if not old_content and new_content:
            summary = f"Create new file '{file_path}' ({len(new_lines)} lines)"
        elif old_content and not new_content:
            summary = f"Wipe contents of '{file_path}'"
            warnings.append("File truncation to empty contents.")
            danger_score = 0.8
        else:
            summary = f"Modify '{file_path}' (+{added} / -{removed} lines)"
            if removed > added * 3 and removed > 50:
                warnings.append(f"Significant code deletion: {removed} lines removed.")
                danger_score = 0.65

        # Check for system/config file writes
        if any(file_path.endswith(crit) for crit in [".env", "id_rsa", "passwd", "shadow", "credentials.json"]):
            warnings.append("Modifying sensitive credential or environment configuration file.")
            danger_score = max(danger_score, 0.85)

        requires_confirmation = danger_score >= 0.7

        return ActionPreview(
            action_type="file_write",
            summary=summary,
            diff_content=diff_text if diff_text else "(No changes detected)",
            warnings=warnings,
            danger_score=danger_score,
            requires_confirmation=requires_confirmation,
            metadata={
                "file_path": file_path,
                "lines_added": added,
                "lines_removed": removed,
            },
        )

    @classmethod
    def render_api_call_preview(
        cls,
        method: str,
        url: str,
        payload: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> ActionPreview:
        """Render API request preview with sensitive field masking."""
        m_upper = method.upper()
        warnings: List[str] = []
        danger_score = 0.2

        if m_upper in ["DELETE", "POST", "PUT", "PATCH"]:
            if m_upper == "DELETE":
                warnings.append("Remote resource deletion via HTTP DELETE.")
                danger_score = 0.75
            else:
                danger_score = 0.4

        # Redact payload and headers
        masked_payload = cls._mask_dict(payload) if payload else None
        masked_headers = cls._mask_dict(headers) if headers else None

        formatted_body = json.dumps(masked_payload, indent=2) if masked_payload else "(Empty body)"

        diff_view = f"{m_upper} {url}\nHeaders: {json.dumps(masked_headers or {}, indent=2)}\nBody:\n{formatted_body}"

        requires_confirmation = danger_score >= 0.7

        return ActionPreview(
            action_type="api_call",
            summary=f"HTTP {m_upper} request to {url}",
            diff_content=diff_view,
            warnings=warnings,
            danger_score=danger_score,
            requires_confirmation=requires_confirmation,
            metadata={"method": m_upper, "url": url},
        )

    @classmethod
    def _mask_dict(cls, data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Recursively redact sensitive keys from dictionaries."""
        if not data:
            return {}
        result: Dict[str, Any] = {}
        for k, v in data.items():
            if any(s in k.lower() for s in cls.SENSITIVE_KEYS):
                result[k] = "******** [REDACTED]"
            elif isinstance(v, dict):
                result[k] = cls._mask_dict(v)
            else:
                result[k] = v
        return result
