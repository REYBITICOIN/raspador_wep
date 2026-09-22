from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone

from fastmcp import Client
from fastmcp.client.transports import StdioTransport


async def probe() -> dict:
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
        tools = await asyncio.wait_for(client.list_tools(), timeout=60)
        wait_result = await asyncio.wait_for(
            client.call_tool("Wait", {"duration": 1}),
            timeout=60,
        )
    names = sorted(tool.name for tool in tools)
    return {
        "connected": True,
        "transport": "stdio",
        "tested_at": datetime.now(timezone.utc).isoformat(),
        "tool_count": len(names),
        "tools": names,
        "safe_test": "Wait",
        "safe_test_passed": not wait_result.is_error,
        "writes_performed": False,
    }


if __name__ == "__main__":
    try:
        print(json.dumps(asyncio.run(probe()), ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({
            "connected": False,
            "error": str(exc)[:500],
            "writes_performed": False,
        }, ensure_ascii=False))
        raise SystemExit(1)
