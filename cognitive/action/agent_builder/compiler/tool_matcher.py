"""Tool Matcher: Resolves relevant tools and MCP endpoints from natural language requests."""

import re
from typing import Dict, List, Set
from ..core.interfaces import BaseToolMatcher
from ..core.models import AgentToolBinding

TOOL_KEYWORDS: Dict[str, List[str]] = {
    "code_interpreter": ["code", "python", "script", "execute", "run program", "compute"],
    "grep_search": ["search code", "find function", "grep", "regex", "scan files"],
    "file_reader": ["read file", "read document", "inspect files", "open document"],
    "file_writer": ["write file", "save output", "modify file", "generate file"],
    "web_search": ["search web", "google", "online research", "latest news", "find online"],
    "browser_automation": ["browse", "web click", "login to site", "fill form", "automate web"],
    "sqlite_query": ["database", "sql", "query table", "database query"],
}

CONSEQUENTIAL_TOOLS: Set[str] = {
    "file_writer",
    "browser_automation",
    "code_interpreter",
    "sqlite_query",
}


UNSUPPORTED_CAPABILITY_KEYWORDS: Dict[str, List[str]] = {
    "sms_messenger": ["sms", "text message", "whatsapp", "phone call"],
    "quantum_simulator": ["quantum", "qiskit", "qubit"],
    "stock_trader": ["trade stocks", "buy shares", "nyse", "forex trading"],
    "drone_controller": ["drone", "fly quadcopter", "autopilot"],
}


class ToolMatcher(BaseToolMatcher):
    """Inspects agent description prompts and attaches optimal tools and MCP servers."""

    def match_tools(self, description_text: str) -> AgentToolBinding:
        text = description_text.lower()
        matched_tools: List[str] = []
        consequential: List[str] = []
        missing: List[str] = []

        for tool_id, keywords in TOOL_KEYWORDS.items():
            for kw in keywords:
                if re.search(r"\b" + re.escape(kw) + r"\b", text):
                    if tool_id not in matched_tools:
                        matched_tools.append(tool_id)
                        if tool_id in CONSEQUENTIAL_TOOLS:
                            consequential.append(tool_id)
                    break

        for capability, keywords in UNSUPPORTED_CAPABILITY_KEYWORDS.items():
            for kw in keywords:
                if re.search(r"\b" + re.escape(kw) + r"\b", text):
                    if capability not in missing:
                        missing.append(capability)
                    break

        # If no specific match found, provide baseline read/search tools
        if not matched_tools:
            matched_tools = ["file_reader", "grep_search"]

        mcp_servers: List[str] = []
        if "sqlite_query" in matched_tools:
            mcp_servers.append("mcp-sqlite-server")
        if "browser_automation" in matched_tools:
            mcp_servers.append("mcp-browser-server")

        return AgentToolBinding(
            tool_ids=matched_tools,
            mcp_server_ids=mcp_servers,
            consequential_tools=consequential,
            missing_tools=missing,
        )
