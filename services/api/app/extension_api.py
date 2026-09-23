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
SEARCH_SNAPSHOTS_FILE = DATA_DIR / "marketplace-search-snapshots.json"
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
    listing_id: str | None = Field(default=None, max_length=50)
    brand: str | None = Field(default=None, max_length=200)
    category: str | None = Field(default=None, max_length=300)
    condition: str | None = Field(default=None, max_length=100)
    rating: float | None = Field(default=None, ge=0, le=5)
    review_count: int | None = Field(default=None, ge=0)
    sold_count: int | None = Field(default=None, ge=0)
    image_count: int | None = Field(default=None, ge=0)
    shipping: str | None = Field(default=None, max_length=500)
    listing_type: str | None = Field(default=None, max_length=100)
    seller_reputation: str | None = Field(default=None, max_length=200)
    is_catalog: bool | None = None
    is_sponsored: bool | None = None
    availability: str | None = Field(default=None, max_length=100)
    stock: int | None = Field(default=None, ge=0)
    sales_estimate: float | None = Field(default=None, ge=0)
    source_map: dict[str, str] = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list, max_length=30)
    confidence: str = Field(pattern="^(low|medium|high)$")
    warnings: list[str] = Field(default_factory=list, max_length=20)


class SearchProduct(BaseModel):
    position: int = Field(ge=1)
    listing_id: str | None = Field(default=None, max_length=50)
    title: str = Field(max_length=500)
    price: float = Field(ge=0)
    currency: str = Field(default="BRL", max_length=8)
    url: HttpUrl | None = None
    seller: str | None = Field(default=None, max_length=300)
    rating: float | None = Field(default=None, ge=0, le=5)
    shipping: str | None = Field(default=None, max_length=500)
    discount: str | None = Field(default=None, max_length=100)
    badge: str | None = Field(default=None, max_length=100)
    official_store: bool = False
    sponsored: bool = False
    image_url: HttpUrl | None = None
    evidence: list[str] = Field(default_factory=list, max_length=10)


class SearchSnapshotRequest(BaseModel):
    marketplace: str = Field(pattern="^mercadolivre$")
    page_type: str = Field(pattern="^search$")
    url: HttpUrl
    captured_at: str
    query: str = Field(max_length=300)
    visible_results: int = Field(ge=0, le=500)
    captured_results: int = Field(ge=0, le=500)
    sponsored_count: int = Field(ge=0)
    official_store_count: int = Field(ge=0)
    free_shipping_count: int = Field(ge=0)
    min_price: float | None = Field(default=None, ge=0)
    max_price: float | None = Field(default=None, ge=0)
    products: list[SearchProduct] = Field(default_factory=list, max_length=100)
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


@router.post("/search-snapshots", status_code=201)
def save_search_snapshot(request: SearchSnapshotRequest) -> dict:
    snapshot = request.model_dump(mode="json")
    snapshot.update({
        "id": str(uuid4()),
        "received_at": datetime.now(timezone.utc).isoformat(),
        "verified": bool(snapshot["products"] and snapshot["captured_results"] == len(snapshot["products"])),
    })
    with LOCK:
        rows = read_list(SEARCH_SNAPSHOTS_FILE)
        rows.append(snapshot)
        write_list(SEARCH_SNAPSHOTS_FILE, rows[-1000:])
    return snapshot


@router.get("/search-snapshots")
def list_search_snapshots(limit: int = 20) -> list[dict]:
    safe_limit = min(max(limit, 1), 100)
    return list(reversed(read_list(SEARCH_SNAPSHOTS_FILE)))[:safe_limit]
