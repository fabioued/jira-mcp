#!/usr/bin/env python3
"""
Jira Model Context Protocol (MCP) Server.
Implements the MCP Stdio JSON-RPC 2.0 protocol with zero external dependencies.
"""

import json
import os
import sys
import traceback
from typing import Any, Dict, Optional

# Ensure package imports work regardless of working directory
server_dir = os.path.dirname(os.path.abspath(__file__))
if server_dir not in sys.path:
    sys.path.insert(0, server_dir)

from config import config
from tools import TOOL_HANDLERS, get_tools_manifest

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "jira-mcp-server"
SERVER_VERSION = "1.0.0"


def log(msg: str) -> None:
    """Logs diagnostics safely to stderr so as not to pollute stdout JSON-RPC stream."""
    sys.stderr.write(f"[{SERVER_NAME}] {msg}\n")
    sys.stderr.flush()


def send_response(response: Dict[str, Any]) -> None:
    """Serializes and sends a JSON-RPC response to stdout followed by newline."""
    data = json.dumps(response, ensure_ascii=False)
    sys.stdout.write(data + "\n")
    sys.stdout.flush()


def send_error(req_id: Optional[Any], code: int, message: str, data: Optional[Any] = None) -> None:
    """Sends a JSON-RPC error response."""
    err_obj: Dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err_obj["data"] = data
    send_response({
        "jsonrpc": "2.0",
        "id": req_id,
        "error": err_obj,
    })


def handle_initialize(req_id: Any, params: Dict[str, Any]) -> None:
    """Handles the client initialize handshake."""
    client_info = params.get("clientInfo", {})
    client_name = client_info.get("name", "unknown")
    client_ver = client_info.get("version", "")
    log(f"Client connected: {client_name} {client_ver}")

    send_response({
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {
                "tools": {
                    "listChanged": False,
                }
            },
            "serverInfo": {
                "name": SERVER_NAME,
                "version": SERVER_VERSION,
            },
        },
    })


def handle_tools_list(req_id: Any, params: Dict[str, Any]) -> None:
    """Returns available tools and their schemas."""
    manifest = get_tools_manifest()
    send_response({
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "tools": manifest,
        },
    })


def handle_tools_call(req_id: Any, params: Dict[str, Any]) -> None:
    """Executes a tool and returns the formatted response."""
    name = params.get("name", "")
    arguments = params.get("arguments", {})

    log(f"Executing tool '{name}' with args {arguments}")

    handler = TOOL_HANDLERS.get(name)
    if not handler:
        send_response({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error: Tool '{name}' not found.",
                    }
                ],
                "isError": True,
            },
        })
        return

    try:
        output = handler(arguments)
        send_response({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": str(output),
                    }
                ],
                "isError": False,
            },
        })
    except Exception as e:
        err_trace = traceback.format_exc()
        log(f"Tool execution failed: {err_trace}")
        send_response({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error executing tool '{name}': {str(e)}",
                    }
                ],
                "isError": True,
            },
        })


def run_stdio_server() -> None:
    """Main input loop reading JSON-RPC messages from stdin."""
    log(f"Starting {SERVER_NAME} v{SERVER_VERSION} (Jira URL: {config.url or 'Not set'})")

    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue

        try:
            msg = json.loads(line)
        except json.JSONDecodeError as je:
            log(f"Invalid JSON: {je}")
            send_error(None, -32700, "Parse error: Invalid JSON")
            continue

        method = msg.get("method")
        req_id = msg.get("id")
        params = msg.get("params", {})

        # Handle notifications (no id)
        if req_id is None:
            if method == "notifications/initialized":
                log("Received notifications/initialized handshake completion.")
            elif method == "notifications/cancelled":
                log("Received cancellation notice.")
            else:
                log(f"Received unhandled notification: {method}")
            continue

        # Handle request methods
        if method == "initialize":
            handle_initialize(req_id, params)
        elif method == "ping":
            send_response({"jsonrpc": "2.0", "id": req_id, "result": {}})
        elif method == "tools/list":
            handle_tools_list(req_id, params)
        elif method == "tools/call":
            handle_tools_call(req_id, params)
        else:
            log(f"Unknown method requested: {method}")
            send_error(req_id, -32601, f"Method '{method}' not found")


if __name__ == "__main__":
    try:
        run_stdio_server()
    except (KeyboardInterrupt, BrokenPipeError):
        log("Server shutting down.")
    except Exception as ex:
        log(f"Fatal error: {traceback.format_exc()}")
        sys.exit(1)
