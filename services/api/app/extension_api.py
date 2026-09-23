from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from statistics import mean
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


def normalized_query(value: str) -> str:
    return " ".join(value.casefold().split())


def product_key(product: dict) -> str:
    return product.get("listing_id") or normalized_query(product.get("title") or "")


@router.get("/search-history")
def search_history(query: str) -> dict:
    wanted = normalized_query(query)
    snapshots = sorted(
        [row for row in read_list(SEARCH_SNAPSHOTS_FILE) if normalized_query(row.get("query", "")) == wanted],
        key=lambda row: row.get("captured_at", ""),
    )
    timeline = []
    for row in snapshots:
        prices = [item["price"] for item in row.get("products", []) if item.get("price") is not None]
        timeline.append({
            "snapshot_id": row.get("id"),
            "captured_at": row.get("captured_at"),
            "captured_results": row.get("captured_results", 0),
            "average_price": round(mean(prices), 2) if prices else None,
            "min_price": min(prices) if prices else None,
            "max_price": max(prices) if prices else None,
            "sponsored_count": row.get("sponsored_count", 0),
            "official_store_count": row.get("official_store_count", 0),
            "free_shipping_count": row.get("free_shipping_count", 0),
        })
    competitors = []
    if snapshots:
        latest = snapshots[-1]
        previous = snapshots[-2] if len(snapshots) > 1 else None
        prior = {product_key(item): item for item in (previous or {}).get("products", [])}
        for item in latest.get("products", []):
            old = prior.get(product_key(item))
            price_change = round(item["price"] - old["price"], 2) if old and old.get("price") is not None else None
            position_change = old["position"] - item["position"] if old else None
            trend = "new" if not old else "rising" if position_change > 0 else "falling" if position_change < 0 else "stable"
            competitors.append({
                "listing_id": item.get("listing_id"), "title": item.get("title"),
                "seller": item.get("seller"), "current_position": item.get("position"),
                "previous_position": old.get("position") if old else None,
                "position_change": position_change, "current_price": item.get("price"),
                "previous_price": old.get("price") if old else None,
                "price_change": price_change, "rating": item.get("rating"),
                "sponsored": item.get("sponsored", False),
                "official_store": item.get("official_store", False), "trend": trend,
            })
    return {
        "query": query, "snapshot_count": len(snapshots),
        "has_comparison": len(snapshots) > 1,
        "timeline": timeline, "competitors": competitors,
        "method": "Comparação determinística entre capturas reais; não estima vendas, visitas ou estoque.",
    }
