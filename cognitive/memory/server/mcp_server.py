"""Model Context Protocol (MCP) server for IDE integration (Antigravity, Cursor, Windsurf)."""

import json
from typing import Optional
from cognitive.memory.engine import MemoryEngine

try:
    # mcp 2.x
    from mcp.server.mcpserver import MCPServer
    mcp_app = MCPServer(
        name="pheonix-memory-mcp",
        instructions="Exposes cognitive memory layer tools for IDEs and autonomous agents.",
    )
except ImportError:
    # mcp 1.x fallback
    try:
        from mcp.server.fastmcp import FastMCP
        mcp_app = FastMCP("pheonix-memory-mcp")
    except Exception:
        mcp_app = None

# Initialize memory engine singleton
engine = MemoryEngine()

if mcp_app is not None:

    @mcp_app.tool()
    def recall_memory(user_id: str, query: str, session_id: Optional[str] = None) -> str:
        """Recall concentrated context (< 500 tokens) synthesized across Tier 1, Tier 2, and Tier 3.
        
        Args:
            user_id: Target user or agent ID.
            query: Query to match semantically against memory.
            session_id: Active session identifier if available.
        """
        pkg = engine.recall(user_id=user_id, query=query, session_id=session_id)
        return pkg.formatted_prompt

    @mcp_app.tool()
    def save_memory(user_id: str, text: str, session_id: Optional[str] = None) -> str:
        """Record an interaction, extract atomic facts, resolve contradictions, and store vector memory.
        
        Args:
            user_id: Target user or agent ID.
            text: Information or interaction to memorize.
            session_id: Active session identifier if available.
        """
        result = engine.remember(user_id=user_id, text=text, session_id=session_id)
        return json.dumps(result, indent=2)

    @mcp_app.tool()
    def list_user_facts(user_id: str) -> str:
        """Fetch all currently active ground-truth structured facts for a user.
        
        Args:
            user_id: Target user or agent ID.
        """
        facts = engine.get_active_facts(user_id=user_id)
        return json.dumps([f.model_dump(mode="json") for f in facts], indent=2)

    @mcp_app.tool()
    def consolidate_session(user_id: str, session_id: str) -> str:
        """Execute REM Sleep consolidation: summarize session milestones into Tier 3 and purge Tier 1 cache.
        
        Args:
            user_id: Target user or agent ID.
            session_id: Session ID to consolidate.
        """
        result = engine.consolidate(user_id=user_id, session_id=session_id)
        return json.dumps(result.model_dump(), indent=2)


def main():
    """Entry point for running the MCP server over standard I/O."""
    if mcp_app is not None:
        mcp_app.run()
    else:
        print("MCP SDK is not available in the current Python environment.")


if __name__ == "__main__":
    main()


# Alias for compatibility
mcp = mcp_app
