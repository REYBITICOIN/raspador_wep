from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel, Field, HttpUrl

from .commerce import DATA_DIR, read_list, write_list

router = APIRouter(prefix="/v1/extension", tags=["browser-extension"])
SNAPSHOTS_FILE = DATA_DIR / "marketplace-snapshots.json"
LOCK = Lock()


class SnapshotRequest(BaseModel):
    marketplace: str = Field(pattern="^(mercadolivre|shopee|amazon)$")
    url: HttpUrl
    canonical_url: HttpUrl
    captured_at: str
    title: str | None = Field(default=None, max_length=500)
    price: float | None = Field(default=None, ge=0)
    currency: str = Field(default="BRL", max_length=8)
    seller: str | None = Field(default=None, max_length=300)
    availability: str | None = Field(default=None, max_length=100)
    stock: int | None = Field(default=None, ge=0)
    sales_estimate: float | None = Field(default=None, ge=0)
    evidence: list[str] = Field(default_factory=list, max_length=30)
    confidence: str = Field(pattern="^(low|medium|high)$")
    warnings: list[str] = Field(default_factory=list, max_length=20)


@router.post("/snapshots", status_code=201)
def save_snapshot(request: SnapshotRequest) -> dict:
    snapshot = request.model_dump(mode="json")
    snapshot.update({
        "id": str(uuid4()),
        "received_at": datetime.now(timezone.utc).isoformat(),
        "verified": bool(snapshot["title"] and snapshot["price"] is not None),
    })
    with LOCK:
        rows = read_list(SNAPSHOTS_FILE)
        rows.append(snapshot)
        write_list(SNAPSHOTS_FILE, rows[-5000:])
    return snapshot


@router.get("/snapshots")
def list_snapshots(limit: int = 50) -> list[dict]:
    safe_limit = min(max(limit, 1), 200)
    return list(reversed(read_list(SNAPSHOTS_FILE)))[:safe_limit]
