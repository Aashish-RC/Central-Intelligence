"""Integration test for remote MCP JSON-RPC 2.0 transport."""

import http.server
import json
import threading
from tools_mcp.mcp.client import MCPClient
from tools_mcp.core.models import ToolType


class MockMCPServerHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length).decode("utf-8")
        req_data = json.loads(raw_body)
        method = req_data.get("method")
        req_id = req_data.get("id")

        if method == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": [
                        {
                            "name": "remote_echo",
                            "description": "Echoes back input",
                            "parameters": [
                                {"name": "message", "type": "string", "required": True}
                            ],
                        }
                    ]
                },
            }
        elif method == "tools/call":
            params = req_data.get("params", {})
            name = params.get("name")
            args = params.get("arguments", {})
            if name == "remote_echo":
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {"type": "text", "text": f"Echo: {args.get('message', '')}"}
                        ],
                        "isError": False,
                    },
                }
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method {name} not found"},
                }
        else:
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Unknown method: {method}"},
            }

        body_bytes = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def log_message(self, format, *args):
        # Silence HTTP server logs during test
        pass


def test_remote_mcp_client_transport():
    server = http.server.HTTPServer(("127.0.0.1", 0), MockMCPServerHandler)
    port = server.server_port
    server_thread = threading.Thread(target=server.handle_request, daemon=True)
    server_thread.start()

    client = MCPClient(
        server_name="remote_test_server",
        server_url=f"http://127.0.0.1:{port}",
    )

    tools = client.list_mcp_tools()
    assert len(tools) == 1
    assert tools[0].name == "remote_echo"
    assert tools[0].tool_type == ToolType.MCP

    # Handle the second request for call_mcp_tool
    server_thread2 = threading.Thread(target=server.handle_request, daemon=True)
    server_thread2.start()

    res = client.call_mcp_tool("remote_echo", {"message": "Hello MCP!"})
    assert res["isError"] is False
    assert res["content"][0]["text"] == "Echo: Hello MCP!"

    server.server_close()
