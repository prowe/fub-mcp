"""AWS Lambda entry point for the FUB MCP Server.

Handles Lambda URL invocations.  Each HTTP request must supply the Follow Up
Boss API key as the ``fub_api_key`` query parameter.  No credentials are
stored in the Lambda environment.

Supported MCP JSON-RPC 2.0 methods
------------------------------------
* ``initialize``        – negotiate protocol version & capabilities
* ``tools/list``        – enumerate available tools
* ``tools/call``        – invoke a tool
* ``resources/list``    – enumerate available resources
* ``resources/read``    – read a resource by URI
"""

import asyncio
import base64
import json
import logging
import os
import sys

# ---------------------------------------------------------------------------
# Logging: configure the root logger BEFORE importing fub_mcp.server.
# server.py calls logging.basicConfig() with a file handler that writes to
# 'fub_mcp_server.log' in the cwd (read-only in Lambda).  basicConfig() is a
# no-op when the root logger already has handlers, so pre-configuring here
# keeps Lambda output in CloudWatch only.
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path: the SAM build copies this file and the entire repo into /var/task/.
# The package lives under src/, so we add that to sys.path.
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# ---------------------------------------------------------------------------
# Import server components.  Config.validate() is no longer called at module
# level (it was moved into server.main()), so this import succeeds even when
# FUB_API_KEY is absent from the environment.
# ---------------------------------------------------------------------------
from fub_mcp.config import Config  # noqa: E402
from fub_mcp.server import (  # noqa: E402
    call_tool,
    list_resources,
    list_tools,
    read_resource,
)

_QUERY_PARAM = "fub_api_key"


# ---------------------------------------------------------------------------
# Public Lambda handler
# ---------------------------------------------------------------------------

def lambda_handler(event: dict, context) -> dict:
    """AWS Lambda entry point for Lambda URL invocations.

    Expects a JSON-RPC 2.0 request body and the Follow Up Boss API key
    supplied as the ``fub_api_key`` query-string parameter.

    Returns a standard Lambda URL HTTP response dict with a JSON-RPC 2.0
    body.
    """
    logger.info("Lambda invocation – requestContext: %s",
                json.dumps(event.get("requestContext", {}), default=str))

    # ------------------------------------------------------------------
    # 1. Extract and validate the FUB API key from query parameters.
    # ------------------------------------------------------------------
    query_params = event.get("queryStringParameters") or {}
    api_key = query_params.get(_QUERY_PARAM, "").strip()

    if not api_key:
        return _http_error(
            401,
            f"Missing required query parameter '{_QUERY_PARAM}'. "
            "Supply your Follow Up Boss API key as a query parameter: "
            f"?{_QUERY_PARAM}=<your_key>",
        )

    # ------------------------------------------------------------------
    # 2. Inject the per-request key into the shared Config class so that
    #    FUBClient picks it up when constructing its HTTP session.
    #
    #    Concurrency safety: AWS Lambda guarantees that each container
    #    processes exactly one invocation at a time.  Concurrent requests
    #    are served by separate container instances (separate processes),
    #    so there is no shared memory between simultaneous invocations and
    #    mutating this class attribute is safe.
    # ------------------------------------------------------------------
    Config.FUB_API_KEY = api_key

    # ------------------------------------------------------------------
    # 3. Parse the request body.
    # ------------------------------------------------------------------
    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")

    if not body:
        return _http_error(400, "Empty request body")

    try:
        request = json.loads(body)
    except json.JSONDecodeError as exc:
        return _http_error(400, f"Invalid JSON body: {exc}")

    # ------------------------------------------------------------------
    # 4. Dispatch the JSON-RPC request.
    # ------------------------------------------------------------------
    try:
        response = asyncio.run(_handle_jsonrpc(request))
    except (RuntimeError, ValueError, TypeError, KeyError) as exc:
        logger.error("Unhandled Lambda error: %s", exc, exc_info=True)
        return _http_error(500, f"Internal server error: {exc}")

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(response),
    }


# ---------------------------------------------------------------------------
# JSON-RPC dispatch
# ---------------------------------------------------------------------------

async def _handle_jsonrpc(request: dict) -> dict:
    """Process one JSON-RPC 2.0 request and return a response object."""
    jsonrpc_id = request.get("id")
    method = request.get("method", "")
    params = request.get("params") or {}

    try:
        result = await _dispatch(method, params)
        return {"jsonrpc": "2.0", "id": jsonrpc_id, "result": result}
    except (ValueError, KeyError, TypeError, RuntimeError) as exc:
        logger.error("Error in JSON-RPC method '%s': %s", method, exc, exc_info=True)
        return {
            "jsonrpc": "2.0",
            "id": jsonrpc_id,
            "error": {"code": -32603, "message": str(exc)},
        }


async def _dispatch(method: str, params: dict) -> dict:
    """Map a JSON-RPC method name to the appropriate MCP handler."""

    if method == "initialize":
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}, "resources": {}},
            "serverInfo": {"name": "fub-mcp", "version": "0.1.0"},
        }

    if method == "tools/list":
        tools = await list_tools()
        return {
            "tools": [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": t.inputSchema,
                }
                for t in tools
            ]
        }

    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        content = await call_tool(name, arguments)
        return {
            "content": [{"type": c.type, "text": c.text} for c in content],
            "isError": False,
        }

    if method == "resources/list":
        resources = await list_resources()
        return {
            "resources": [
                {
                    "uri": str(r.uri),
                    "name": r.name,
                    "description": r.description,
                    "mimeType": r.mimeType,
                }
                for r in resources
            ]
        }

    if method == "resources/read":
        uri = params.get("uri", "")
        content = await read_resource(uri)
        return {
            "contents": [
                {"uri": uri, "mimeType": "application/json", "text": content}
            ]
        }

    raise ValueError(f"Method not found: {method}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _http_error(status_code: int, message: str) -> dict:
    """Return an HTTP error response compatible with Lambda URL."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": message}),
    }
