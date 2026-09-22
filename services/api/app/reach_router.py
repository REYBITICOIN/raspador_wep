from __future__ import annotations

import asyncio
from importlib.metadata import version

from agent_reach.channels import get_all_channels
from agent_reach.channels.web import WebChannel
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, HttpUrl

router = APIRouter(prefix="/v1/reach", tags=["agent-reach"])
MAX_CONTENT_CHARS = 120_000


class ReadRequest(BaseModel):
    url: HttpUrl
    purpose: str = Field(min_length=3, max_length=500)


@router.get("/status")
def reach_status() -> dict:
    channels = [
        {
            "name": channel.name,
            "description": channel.description,
            "backends": channel.backends,
            "tier": channel.tier,
        }
        for channel in get_all_channels()
    ]
    return {
        "installed": True,
        "version": version("agent-reach"),
        "mode": "read_only",
        "channel_count": len(channels),
        "channels": channels,
        "credentials_loaded": False,
    }


@router.post("/read")
async def read_public_page(request: ReadRequest) -> dict:
    try:
        content = await asyncio.to_thread(WebChannel().read, str(request.url))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, f"Leitura externa falhou: {str(exc)[:300]}") from exc
    truncated = len(content) > MAX_CONTENT_CHARS
    return {
        "url": str(request.url),
        "purpose": request.purpose,
        "content": content[:MAX_CONTENT_CHARS],
        "content_chars": min(len(content), MAX_CONTENT_CHARS),
        "truncated": truncated,
        "source": "agent-reach:jina-reader",
        "execution_mode": "read_only",
    }

