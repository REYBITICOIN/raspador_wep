from __future__ import annotations

import json
import os
import re
import unicodedata
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .commerce import DATA_DIR, find_product, read_list, write_list

load_dotenv()
router = APIRouter(prefix="/v1", tags=["seo-agents"])
DRAFTS_FILE = DATA_DIR / "seo-drafts.json"
LOCK = Lock()


class DraftRequest(BaseModel):
    product_id: str
    channel: str = "mercadolivre"


class DecisionRequest(BaseModel):
    decision: str
    note: str = ""
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_seed(title: str) -> str:
    value = re.sub(r"\b(pct|pcs|pçs?|pacote|kit)\b", " ", title, flags=re.I)
    value = re.sub(r"\bcom\s+\d+\s*(un|und|unidades?)\b", " ", value, flags=re.I)
    return re.sub(r"\s+", " ", value).strip(" -|")


def google_autocomplete(seed: str) -> list[str]:
    try:
        query = urlencode({"client": "firefox", "hl": "pt-BR", "q": seed})
        request = Request(
            "https://suggestqueries.google.com/complete/search?" + query,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
        return [item for item in data[1] if isinstance(item, str)][:10]
    except Exception:
        return []


def research_keywords(product: dict) -> dict:
    seed = clean_seed(product.get("title") or "")
    generic = unicodedata.normalize("NFKD", seed.split()[0] if seed else "").encode("ascii", "ignore").decode()
    seeds = list(dict.fromkeys(filter(None, [seed, f"{generic} feminino", f"{generic} atacado"])))
    per_seed = [{"seed": item, "suggestions": google_autocomplete(item)} for item in seeds[:3]]
    terms = list(dict.fromkeys(
        term.strip().lower()
        for group in per_seed
        for term in group["suggestions"]
        if term.strip()
    ))
    return {
        "engine": "SEOMonster.serp_adjacency_expand-compatible",
        "source": "Google Autocomplete",
        "seeds": seeds,
        "per_seed": per_seed,
        "keywords": terms[:25],
        "caveat": "Sugestões são candidatas; volume depende de GSC/Google Ads/DataForSEO.",
    }


def parse_json_answer(value: str) -> dict:
    value = value.strip()
    start, end = value.find("{"), value.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("O redator não devolveu JSON válido")
    return json.loads(value[start : end + 1])


def draft_with_nvidia(product: dict, research: dict, channel: str) -> dict:
    key = os.getenv("NVIDIA_API_KEY")
    if not key:
        raise HTTPException(503, "NVIDIA_API_KEY não configurada")
    facts = {
        "title": product.get("title"),
        "description": product.get("description"),
        "price": product.get("price"),
        "stock": product.get("stock"),
        "sku": product.get("sku"),
        "sizes": product.get("sizes"),
        "package_quantity": 12 if re.search(r"12\s*(un|und)", product.get("title") or "", re.I) else None,
    }
    prompt = f"""Crie uma proposta de anúncio para {channel}.
FATOS CONFIRMADOS: {json.dumps(facts, ensure_ascii=False)}
PALAVRAS CANDIDATAS DO GOOGLE: {json.dumps(research["keywords"], ensure_ascii=False)}
Regras: não invente material, tamanho, cor, benefício ou medida.
Se package_quantity=12, é UM anúncio de UM pacote contendo 12 unidades.
Não altere preço nem quantidade. Use palavras candidatas somente se forem compatíveis.
Para Mercado Livre, título com no máximo 60 caracteres.
Responda SOMENTE JSON:
{{"title":"","description":"","keywords":[],"facts_used":[],"warnings":[]}}"""
    model = os.getenv("NVIDIA_MODEL") or "nvidia/nemotron-3.5-lightning-30b-a3b"
    base = os.getenv("NVIDIA_BASE_URL") or "https://integrate.api.nvidia.com/v1"
    response = httpx.post(
        base.rstrip("/") + "/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": "Você é um redator de e-commerce factual e conservador."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.15,
            "max_tokens": 1800,
            "stream": False,
        },
        timeout=35,
    )
    if response.is_error:
        raise HTTPException(502, f"NVIDIA HTTP {response.status_code}")
    proposal = parse_json_answer(response.json()["choices"][0]["message"]["content"])
    if not proposal.get("title") or not proposal.get("description"):
        quantity = facts["package_quantity"]
        proposal = {
            "title": f"{facts['title'].split(' pct')[0]} - Pacote com {quantity} Unidades"[:60] if quantity else facts["title"][:60],
            "description": (
                f"{facts['title'].split(' pct')[0]}. Anúncio referente a 1 pacote com {quantity} unidades. "
                f"Estoque informado pela fonte: {facts['stock']}. Consulte variações e medidas antes da compra."
                if quantity else f"{facts['description']} Estoque informado pela fonte: {facts['stock']}."
            ),
            "keywords": [term for term in research["keywords"] if not re.search(r"renner|preto|bojo|infantil|cintura|cos alto|fortaleza|sao paulo|rio de janeiro|goiania|manaus|\bbh\b", term, re.I)][:8],
            "facts_used": ["título", "quantidade do pacote", "estoque"],
            "warnings": [],
        }
    return proposal


def factual_review(product: dict, proposal: dict) -> dict:
    original = (product.get("title") or "").lower()
    combined = (proposal.get("title", "") + " " + proposal.get("description", "")).lower()
    warnings = list(proposal.get("warnings") or [])
    if re.search(r"12\s*(un|und)", original) and not re.search(r"12\s*(un|und)", combined):
        warnings.append("A proposta omitiu que o anúncio é um pacote com 12 unidades.")
    if len(proposal.get("title", "")) > 60:
        warnings.append("Título excede 60 caracteres para Mercado Livre.")
    return {
        "agent_id": "factual-reviewer",
        "passed": not warnings,
        "warnings": warnings,
        "checked": ["quantidade do pacote", "limite do título", "campos sem fonte"],
    }
@router.post("/seo/drafts", status_code=201)
def create_seo_draft(request: DraftRequest) -> dict:
    product = find_product(request.product_id)
    research = research_keywords(product)
    try:
        proposal = draft_with_nvidia(product, research, request.channel)
    except Exception:
        title = product.get("title") or "Produto"
        quantity = 12 if re.search(r"12\s*(un|und)", title, re.I) else None
        base_title = re.split(r"\s+(pct|pcs|pçs?|pacote)\b", title, flags=re.I)[0].strip()
        proposal = {
            "title": (f"{base_title} - Pacote com {quantity} Unidades" if quantity else base_title)[:60],
            "description": (
                f"{base_title}. Anúncio referente a 1 pacote com {quantity} unidades. "
                f"Estoque informado pela fonte: {product.get('stock')}. "
                "Consulte variações e medidas antes da compra."
            ),
            "keywords": [term for term in research["keywords"] if not re.search(r"renner|preto|bojo|infantil|cintura|cos alto|fortaleza|sao paulo|rio de janeiro|goiania|manaus|\bbh\b", term, re.I)][:8],
            "facts_used": ["título", "quantidade do pacote", "estoque"],
            "warnings": [],
        }
    review = factual_review(product, proposal)
    draft = {
        "id": str(uuid4()),
        "product_id": request.product_id,
        "channel": request.channel,
        "original": {
            "title": product.get("title"),
            "description": product.get("description"),
        },
        "research": research,
        "proposal": proposal,
        "review": review,
        "approval": {"state": "pending", "note": ""},
        "created_at": now_iso(),
    }
    with LOCK:
        rows = read_list(DRAFTS_FILE)
        rows.append(draft)
        write_list(DRAFTS_FILE, rows)
    return draft


@router.get("/seo/drafts/{draft_id}")
def get_seo_draft(draft_id: str) -> dict:
    draft = next((row for row in read_list(DRAFTS_FILE) if row["id"] == draft_id), None)
    if not draft:
        raise HTTPException(404, "Proposta não encontrada")
    return draft
@router.post("/seo/drafts/{draft_id}/decision")
def decide_seo_draft(draft_id: str, request: DecisionRequest) -> dict:
    if request.decision not in {"approved", "rejected"}:
        raise HTTPException(422, "Use approved ou rejected")
    with LOCK:
        rows = read_list(DRAFTS_FILE)
        draft = next((row for row in rows if row["id"] == draft_id), None)
        if not draft:
            raise HTTPException(404, "Proposta não encontrada")
        draft["approval"] = {
            "state": request.decision,
            "note": request.note.strip(),
            "decided_at": now_iso(),
        }
        write_list(DRAFTS_FILE, rows)
    return draft
