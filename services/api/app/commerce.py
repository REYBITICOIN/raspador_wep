from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from urllib.parse import urlencode, urlparse
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl

load_dotenv()

router = APIRouter(prefix="/v1", tags=["commerce"])
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
CATALOG_FILE = DATA_DIR / "catalog.json"
PUBLICATIONS_FILE = DATA_DIR / "publications.json"
LOCK = Lock()
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_list(path: Path) -> list[dict]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def write_list(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(path)
class ImportProductRequest(BaseModel):
    url: HttpUrl


class MercadoLivrePreviewRequest(BaseModel):
    product_id: str
    category_id: str | None = None
    listing_type_id: str = "gold_special"
    condition: str = "new"


def toca_product_id(url: str) -> str:
    parsed = urlparse(url)
    if parsed.hostname not in {
        "tocadaoncamodas.com.br",
        "www.tocadaoncamodas.com.br",
    }:
        raise HTTPException(400, "Nesta etapa, importe uma URL da Toca da Onça")
    match = re.search(r"/produto/([0-9a-fA-F-]{36})", parsed.path)
    if not match:
        raise HTTPException(400, "URL de produto da Toca da Onça inválida")
    return match.group(1)
def fetch_toca_product(url: str) -> dict:
    product_id = toca_product_id(url)
    base_url = os.getenv(
        "TOCA_SUPABASE_URL",
        "https://wwwzcdmiusaulwlfrlfu.supabase.co",
    )
    publishable_key = os.getenv("TOCA_SUPABASE_PUBLISHABLE_KEY", "")
    if not publishable_key:
        raise HTTPException(
            503, "Configure TOCA_SUPABASE_PUBLISHABLE_KEY no arquivo .env"
        )
    fields = (
        "id,title,description,price,original_price,images,"
        "stock,status,brand,sku"
    )
    with httpx.Client(timeout=30, trust_env=False) as client:
        response = client.get(
            f"{base_url.rstrip('/')}/rest/v1/products",
            params={"id": f"eq.{product_id}", "select": fields},
            headers={"apikey": publishable_key},
        )
    if response.is_error:
        raise HTTPException(
            502, f"A loja respondeu HTTP {response.status_code}"
        )
    rows = response.json()
    if not rows:
        raise HTTPException(404, "Produto não encontrado na loja")
    source = rows[0]
    images = source.get("images") or []
    return {
        "id": str(uuid4()),
        "source": "toca-da-onca",
        "source_id": source.get("id"),
        "source_url": url,
        "title": (source.get("title") or "").strip(),
        "description": source.get("description") or "",
        "price": source.get("price"),
        "currency": "BRL",
        "images": images,
        "stock": source.get("stock") or 0,
        "status": source.get("status") or "draft",
        "brand": source.get("brand") or "Toca da Onça",
        "sku": source.get("sku") or "",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
def find_product(product_id: str) -> dict:
    product = next(
        (row for row in read_list(CATALOG_FILE) if row["id"] == product_id),
        None,
    )
    if not product:
        raise HTTPException(404, "Produto não encontrado no catálogo")
    return product


def mercadolivre_payload(
    product: dict, request: MercadoLivrePreviewRequest
) -> dict:
    pictures = [{"source": image} for image in product.get("images", [])]
    payload = {
        "title": product["title"][:60],
        "category_id": request.category_id,
        "price": product.get("price"),
        "currency_id": product.get("currency") or "BRL",
        "available_quantity": int(product.get("stock") or 0),
        "buying_mode": "buy_it_now",
        "listing_type_id": request.listing_type_id,
        "condition": request.condition,
        "pictures": pictures,
    }
    missing = [
        key
        for key in ("title", "category_id", "price", "available_quantity")
        if payload.get(key) in (None, "", 0)
    ]
    return {
        "channel": "mercadolivre",
        "mode": "preview",
        "ready": not missing,
        "missing": missing,
        "payload": payload,
        "description": product.get("description") or "",
        "warnings": (
            []
            if not missing
            else ["Complete os campos obrigatórios antes de publicar."]
        ),
    }


@router.get("/commerce/overview")
def commerce_overview() -> dict:
    products = read_list(CATALOG_FILE)
    publications = read_list(PUBLICATIONS_FILE)
    return {
        "products": len(products),
        "publications": len(publications),
        "channels": [
            {"id": "mercadolivre", "state": mercadolivre_state()},
            {"id": "shopee", "state": "planned"},
            {"id": "meta", "state": "planned"},
        ],
    }
@router.get("/catalog/products")
def list_products() -> list[dict]:
    return sorted(
        read_list(CATALOG_FILE),
        key=lambda item: item.get("updated_at", ""),
        reverse=True,
    )


@router.post("/catalog/import", status_code=201)
def import_product(request: ImportProductRequest) -> dict:
    product = fetch_toca_product(str(request.url))
    with LOCK:
        products = read_list(CATALOG_FILE)
        current = next(
            (
                row
                for row in products
                if row.get("source_id") == product["source_id"]
            ),
            None,
        )
        if current:
            product["id"] = current["id"]
            product["created_at"] = current.get("created_at", now_iso())
            products = [product if row["id"] == current["id"] else row for row in products]
        else:
            products.append(product)
        write_list(CATALOG_FILE, products)
    return product
def mercadolivre_state() -> str:
    app_id = os.getenv("MERCADOLIVRE_APP_ID")
    secret = os.getenv("MERCADOLIVRE_CLIENT_SECRET")
    return "configured" if app_id and secret else "needs_credentials"


@router.get("/channels/mercadolivre/status")
def mercadolivre_status() -> dict:
    return {
        "state": mercadolivre_state(),
        "secret_exposed_to_browser": False,
        "live_publish_enabled": False,
        "next_step": "Gere uma nova chave secreta e configure somente no backend.",
    }


@router.get("/channels/mercadolivre/oauth/start")
def mercadolivre_oauth_start() -> dict:
    app_id = os.getenv("MERCADOLIVRE_APP_ID")
    redirect_uri = os.getenv("MERCADOLIVRE_REDIRECT_URI")
    if not app_id or not redirect_uri:
        raise HTTPException(503, "OAuth do Mercado Livre ainda não configurado")
    query = urlencode(
        {
            "response_type": "code",
            "client_id": app_id,
            "redirect_uri": redirect_uri,
        }
    )
    return {
        "authorization_url": f"https://auth.mercadolivre.com.br/authorization?{query}"
    }
@router.post("/channels/mercadolivre/preview")
def mercadolivre_preview(
    request: MercadoLivrePreviewRequest,
) -> dict:
    product = find_product(request.product_id)
    return mercadolivre_payload(product, request)
