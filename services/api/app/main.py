from __future__ import annotations

import asyncio
import re
import socket
import json
from pathlib import Path
from datetime import datetime, timezone
from ipaddress import ip_address
from threading import Lock
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

from .agents import MEDIA_DIR, router as agents_router
from .commerce import router as commerce_router
from .seo_agents import router as seo_router
from .ml_oauth import start_token_keeper
from .extension_api import router as extension_router
from .margin import router as margin_router
from .agency_router import router as agency_router
from .reach_router import router as reach_router
from .local_memory import initialize as initialize_local_memory
from .local_memory import router as memory_router


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "development"
    cors_origins: str = "http://localhost:4173,http://127.0.0.1:4173"
    nvidia_api_key: str | None = None
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_model: str = "nvidia/nemotron-3.5-lightning-30b-a3b"
    xai_api_key: str | None = None
    xai_model: str | None = None
    default_model_provider: str = "nvidia"
    allow_paid_models: bool = False
    data_dir: str = "./data"


settings = Settings()
app = FastAPI(title="Toca Commerce OS API", version="0.4.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[item.strip() for item in settings.cors_origins.split(",")],
    allow_origin_regex=r"^chrome-extension://[a-p]{32}$",
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.include_router(commerce_router)
app.include_router(agents_router)
app.include_router(seo_router)
app.include_router(extension_router)
app.include_router(margin_router)
app.include_router(agency_router)
app.include_router(reach_router)
app.include_router(memory_router)
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")


@app.on_event("startup")
def start_background_services() -> None:
    initialize_local_memory()
    start_token_keeper()


data_file = Path(settings.data_dir) / "jobs.json"
data_file.parent.mkdir(parents=True, exist_ok=True)
try:
    jobs: dict[str, dict] = {item["id"]: item for item in json.loads(data_file.read_text(encoding="utf-8"))}
except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError):
    jobs = {}
jobs_lock = Lock()


def save_jobs() -> None:
    temporary = data_file.with_suffix(".tmp")
    temporary.write_text(json.dumps(list(jobs.values()), ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(data_file)


class JobRequest(BaseModel):
    url: HttpUrl
    instruction: str
    provider: str = "auto"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def assert_public_url(value: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(400, "URL inválida")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, parsed.port or 443)}
    except socket.gaierror as exc:
        raise HTTPException(400, "Domínio não encontrado") from exc
    for address in addresses:
        if not ip_address(address).is_global:
            raise HTTPException(400, "Endereços privados ou locais não são permitidos")


def extract_title(html: str) -> str | None:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    if not match:
        return None
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", match.group(1))).strip()[:300]


def html_to_text(html: str) -> str:
    cleaned = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", html, flags=re.I | re.S)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()[:24000]


def parse_json_answer(value: str) -> dict:
    value = value.strip()
    fence = chr(96) * 3
    if value.startswith(fence):
        value = value.removeprefix(fence + "json").removeprefix(fence).removesuffix(fence).strip()
    start, end = value.find("{"), value.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("A NVIDIA não devolveu JSON válido")
    return json.loads(value[start : end + 1])


def extract_with_nvidia(page_text: str, instruction: str, source_url: str) -> dict:
    if not settings.nvidia_api_key:
        raise ValueError("A chave NVIDIA não está configurada no arquivo .env")
    prompt = f"""Extraia dados comerciais apenas do conteúdo fornecido.
URL: {source_url}
Pedido do usuário: {instruction}
Responda SOMENTE JSON válido neste formato:
{{"page_type":"listing|product|blocked|other","summary":"","products":[{{"title":"","price":null,"currency":"BRL","url":"","image_url":"","availability":"","seller":""}}],"warnings":[]}}
Não invente dados. Se a página for login, CAPTCHA ou verificação, use page_type=blocked e explique em warnings.
CONTEÚDO:
{page_text}"""
    selected_model = (settings.nvidia_model or "").strip() or "nvidia/nemotron-3.5-lightning-30b-a3b"
    response = httpx.post(
        settings.nvidia_base_url.rstrip("/") + "/chat/completions",
        headers={"Authorization": f"Bearer {settings.nvidia_api_key}", "Content-Type": "application/json"},
        json={"model": selected_model, "messages": [{"role": "system", "content": "Você é um extrator de dados preciso. Nunca invente campos ausentes."}, {"role": "user", "content": prompt}], "temperature": 0.1, "max_tokens": 3000, "stream": False},
        timeout=180,
    )
    if response.is_error:
        raise ValueError(f"NVIDIA HTTP {response.status_code}: {response.text[:600]}")
    payload = response.json()
    return parse_json_answer(payload["choices"][0]["message"]["content"])


async def crawl_dynamic_page(target: str) -> dict:
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig
    except ImportError as exc:
        raise ValueError("Crawl4AI ainda não está instalado. Execute INSTALAR_CRAWL4AI.ps1.") from exc

    browser = BrowserConfig(
        browser_type="chromium",
        headless=True,
        viewport_width=1440,
        viewport_height=1000,
        verbose=False,
    )
    run = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        page_timeout=90000,
        delay_before_return_html=3.0,
        scan_full_page=True,
        remove_overlay_elements=True,
    )
    async with AsyncWebCrawler(config=browser) as crawler:
        result = await crawler.arun(url=target, config=run)
    if not result.success:
        raise ValueError(f"Crawl4AI não conseguiu renderizar a página: {result.error_message or 'erro desconhecido'}")

    markdown = getattr(result.markdown, "raw_markdown", result.markdown) if result.markdown else ""
    metadata = result.metadata or {}
    return {
        "title": metadata.get("title"),
        "final_url": result.url or target,
        "http_status": result.status_code,
        "html": result.html or "",
        "text": str(markdown).strip()[:30000],
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "environment": settings.app_env, "version": app.version}


@app.get("/v1/providers")
def providers() -> dict:
    return {
        "default": settings.default_model_provider,
        "providers": [
            {"id": "nvidia", "configured": bool(settings.nvidia_api_key), "model": settings.nvidia_model, "paid": False, "enabled": bool(settings.nvidia_api_key)},
            {"id": "grok", "configured": bool(settings.xai_api_key), "model": settings.xai_model, "paid": True, "enabled": bool(settings.xai_api_key) and settings.allow_paid_models},
        ],
    }


@app.get("/v1/stats")
def stats() -> dict:
    values = list(jobs.values())
    return {
        "total_jobs": len(values),
        "completed": sum(item["status"] == "completed" for item in values),
        "failed": sum(item["status"] == "failed" for item in values),
        "pages": sum(item["status"] == "completed" for item in values),
    }


@app.get("/v1/jobs")
def list_jobs() -> list[dict]:
    return sorted(jobs.values(), key=lambda item: item["created_at"], reverse=True)


@app.get("/v1/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    if job_id not in jobs:
        raise HTTPException(404, "Trabalho não encontrado")
    return jobs[job_id]


@app.post("/v1/jobs", status_code=201)
def create_job(request: JobRequest) -> dict:
    if request.provider not in {"auto", "nvidia", "grok"}:
        raise HTTPException(400, "Provedor inválido")
    if request.provider == "grok" and not settings.allow_paid_models:
        raise HTTPException(403, "Grok está bloqueado até a autorização de gasto")
    target = str(request.url)
    assert_public_url(target)
    job_id = str(uuid4())
    job = {"id": job_id, "url": target, "instruction": request.instruction.strip(), "provider": request.provider, "status": "running", "created_at": now_iso(), "completed_at": None, "result": None, "error": None}
    with jobs_lock:
        jobs[job_id] = job
        save_jobs()
    try:
        page = asyncio.run(crawl_dynamic_page(target))
        final_url = page["final_url"]
        page_text = page["text"]
        if not page_text:
            raise ValueError("O navegador abriu a página, mas nenhum conteúdo legível foi encontrado")
        if page["http_status"] and page["http_status"] >= 400:
            raise ValueError(f"A página respondeu HTTP {page['http_status']}")
        is_blocked = any(marker in final_url.lower() or marker in page_text[:2000].lower() for marker in ["account-verification", "captcha", "access denied", "verifique sua identidade"])
        actual_provider = "baseline"
        extraction = None
        if request.provider == "nvidia" or (request.provider == "auto" and settings.nvidia_api_key):
            extraction = extract_with_nvidia(page_text, request.instruction, final_url)
            actual_provider = "nvidia"
        elif request.provider == "grok":
            raise ValueError("A integração Grok ainda não está implementada")
        products = extraction.get("products", []) if extraction else []
        page_type = extraction.get("page_type") if extraction else None
        empty_product_result = bool(extraction) and not products and page_type in {"product", "listing", "other"}
        job["result"] = {"title": page["title"] or extract_title(page["html"]), "final_url": final_url, "http_status": page["http_status"], "bytes": len(page["html"].encode("utf-8")), "collector": "crawl4ai-playwright", "actual_provider": actual_provider, "blocked": is_blocked, "extraction": extraction, "note": "A página redirecionou para verificação e não entregou os produtos." if is_blocked else ("Crawl4AI renderizou a página e a NVIDIA concluiu a extração." if extraction and not empty_product_result else "A página foi renderizada, mas nenhum produto foi identificado.")}
        job["status"] = "failed" if is_blocked or empty_product_result else "completed"
        if empty_product_result:
            job["error"] = "A coleta terminou sem localizar dados de produto; o resultado não foi aprovado."
    except Exception as exc:
        job["status"] = "failed"
        job["error"] = str(exc)[:500]
    finally:
        job["completed_at"] = now_iso()
        with jobs_lock:
            save_jobs()
    return job
