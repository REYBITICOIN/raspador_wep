from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ALLOWED_TOOLS = {"Wait", "Snapshot"}


def sanitize(tool: str, arguments: dict) -> dict:
    if tool not in ALLOWED_TOOLS:
        raise ValueError("Ferramenta fora da lista segura")
    if tool == "Wait":
        duration = max(0, min(int(arguments.get("duration", 1)), 3))
        return {"duration": duration}
    return {
        "use_vision": False,
        "use_dom": bool(arguments.get("use_dom", False)),
    }


async def execute(tool: str, arguments: dict) -> dict:
    safe_arguments = sanitize(tool, arguments)
    server_env = os.environ | {
        "ANONYMIZED_TELEMETRY": "false",
        "WINDOWS_MCP_WATCHDOG": "off",
    }
    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "windows_mcp", "serve", "--transport", "stdio"],
        env=server_env,
    )
    async with Client(transport) as client:
        result = await asyncio.wait_for(
            client.call_tool(tool, safe_arguments),
            timeout=75,
        )
    payload = result.model_dump(mode="json") if hasattr(result, "model_dump") else {}
    rendered = json.dumps(payload, ensure_ascii=False)
    return {
        "success": not result.is_error,
        "tool": tool,
        "safe_arguments": safe_arguments,
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "result_preview": rendered[:12000],
        "result_truncated": len(rendered) > 12000,
    }


if __name__ == "__main__":
    try:
        selected_tool = sys.argv[1]
        selected_arguments = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
        print(json.dumps(asyncio.run(execute(selected_tool, selected_arguments)), ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({"success": False, "error": str(exc)[:500]}, ensure_ascii=False))
        raise SystemExit(1)
