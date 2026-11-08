"""Built-in File I/O Tool."""

import os
import time
from typing import Any, Dict
from ..base import BaseTool, ToolContext, ToolResult


class FileIOTool(BaseTool):
    """Performs scoped file reading, writing, and listing."""

    name = "file_io"
    description = "Reads, writes, or inspects files."
    parameters_schema = {
        "type": "object",
        "properties": {
            "operation": {"type": "string", "enum": ["read", "write", "list", "exists"]},
            "path": {"type": "string", "description": "Target file or directory path"},
            "content": {"type": "string", "description": "Content to write (if operation is write)"}
        },
        "required": ["operation", "path"]
    }

    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        start_time = time.perf_counter()
        op = params.get("operation", "read").lower()
        path = params.get("path", "")
        content = params.get("content", "")

        if not path:
            return ToolResult(
                success=False,
                output=None,
                error="Path parameter is required",
                execution_time_ms=(time.perf_counter() - start_time) * 1000
            )

        try:
            if op == "read":
                if not os.path.exists(path):
                    return ToolResult(
                        success=False,
                        output=None,
                        error=f"File not found: {path}",
                        execution_time_ms=(time.perf_counter() - start_time) * 1000
                    )
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    data = f.read()
                return ToolResult(
                    success=True,
                    output=data,
                    execution_time_ms=(time.perf_counter() - start_time) * 1000,
                    metadata={"bytes": len(data), "path": path}
                )

            elif op == "write":
                os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                return ToolResult(
                    success=True,
                    output=f"Successfully wrote {len(content)} characters to {path}",
                    execution_time_ms=(time.perf_counter() - start_time) * 1000,
                    metadata={"bytes": len(content), "path": path}
                )

            elif op == "list":
                if not os.path.exists(path):
                    return ToolResult(
                        success=False,
                        output=None,
                        error=f"Directory not found: {path}",
                        execution_time_ms=(time.perf_counter() - start_time) * 1000
                    )
                entries = os.listdir(path)
                return ToolResult(
                    success=True,
                    output=entries,
                    execution_time_ms=(time.perf_counter() - start_time) * 1000,
                    metadata={"count": len(entries), "path": path}
                )

            elif op == "exists":
                exists = os.path.exists(path)
                return ToolResult(
                    success=True,
                    output=exists,
                    execution_time_ms=(time.perf_counter() - start_time) * 1000,
                    metadata={"exists": exists, "path": path}
                )

            else:
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Unknown file operation: {op}",
                    execution_time_ms=(time.perf_counter() - start_time) * 1000
                )

        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"File I/O error: {str(e)}",
                execution_time_ms=(time.perf_counter() - start_time) * 1000
            )
