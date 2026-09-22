from __future__ import annotations

import io
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
from pydantic import BaseModel, Field

from .commerce import DATA_DIR, find_product

router = APIRouter(prefix="/v1", tags=["agents"])
MEDIA_DIR = DATA_DIR / "prepared-media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

AGENTS = [
    {
        "id": "source-importer",
        "name": "Importador de Produto",
        "stage": 1,
        "purpose": "Importar dados e imagens da fonte autorizada.",
        "input": "URL do produto",
        "output": "Produto canônico",
        "engine": "API da loja",
        "state": "active",
    },
    {
        "id": "data-validator",
        "name": "Validador Comercial",
        "stage": 2,
        "purpose": "Conferir título, preço, estoque, SKU e divergências.",
        "input": "Produto canônico",
        "output": "Relatório de campos",
        "engine": "Regras determinísticas",
        "state": "active",
    },
    {
        "id": "image-curator",
        "name": "Curador de Imagens",
        "stage": 3,
        "purpose": "Padronizar enquadramento, nitidez, fundo e qualidade.",
        "input": "Imagens originais",
        "output": "Imagens preparadas",
        "engine": "Pillow + perfil do canal",
        "state": "active",
    },
    {
        "id": "size-chart-builder",
        "name": "Tabela de Medidas",
        "stage": 4,
        "purpose": "Criar tabela visual usando apenas medidas confirmadas.",
        "input": "Medidas estruturadas",
        "output": "Arte e atributos de tamanho",
        "engine": "Template validado",
        "state": "blocked_without_data",
    },
    {
        "id": "copywriter-ai",
        "name": "Redator Comercial",
        "stage": 5,
        "purpose": "Otimizar título e descrição sem inventar informações.",
        "input": "Produto validado",
        "output": "Texto por canal",
        "engine": "NVIDIA ou Grok",
        "state": "active",
    },
    {
        "id": "seo-auditor",
        "name": "Auditor SEO",
        "stage": 6,
        "purpose": "Auditar intenção, palavras-chave, página e desempenho.",
        "input": "Página e texto final",
        "output": "Parecer SEO",
        "engine": "SEOMonster 0.9.3",
        "state": "installed_needs_auth",
    },
    {
        "id": "marketplace-validator",
        "name": "Validador Marketplace",
        "stage": 7,
        "purpose": "Validar categoria, atributos, imagens e políticas.",
        "input": "Anúncio preparado",
        "output": "Prévia aprovada ou bloqueio",
        "engine": "API oficial",
        "state": "active",
    },
    {
        "id": "publisher",
        "name": "Publicador",
        "stage": 8,
        "purpose": "Publicar somente anúncios aprovados.",
        "input": "Prévia aprovada",
        "output": "ID e URL do anúncio",
        "engine": "API oficial com OAuth",
        "state": "locked_until_oauth",
    },
    {
        "id": "sync-monitor",
        "name": "Monitor de Sincronização",
        "stage": 9,
        "purpose": "Sincronizar preço, estoque, pedidos e qualidade.",
        "input": "Eventos dos canais",
        "output": "Atualizações e alertas",
        "engine": "Webhooks + tarefas",
        "state": "planned",
    },
]


class PrepareImagesRequest(BaseModel):
    product_id: str
    size: int = Field(default=1200, ge=500, le=2000)
    quality: int = Field(default=94, ge=85, le=98)


class SizeChartRequest(BaseModel):
    product_id: str
    columns: list[str] = Field(min_length=2, max_length=8)
    rows: list[dict[str, str | int | float]] = Field(min_length=1, max_length=30)
    unit: str = Field(default="cm", min_length=1, max_length=12)


def prepare_one(url: str, target: Path, size: int, quality: int) -> dict:
    with httpx.Client(
        timeout=30,
        follow_redirects=True,
        trust_env=False,
    ) as client:
        response = client.get(url)
    response.raise_for_status()
    if len(response.content) > 20 * 1024 * 1024:
        raise ValueError("Imagem excede 20 MB")
    source = Image.open(io.BytesIO(response.content))
    source = ImageOps.exif_transpose(source).convert("RGB")
    fitted = ImageOps.contain(
        source,
        (size, size),
        method=Image.Resampling.LANCZOS,
    )
    fitted = fitted.filter(
        ImageFilter.UnsharpMask(radius=1.2, percent=110, threshold=3)
    )
    fitted = ImageEnhance.Contrast(fitted).enhance(1.02)
    canvas = Image.new("RGB", (size, size), "white")
    left = (size - fitted.width) // 2
    top = (size - fitted.height) // 2
    canvas.paste(fitted, (left, top))
    canvas.save(target, "JPEG", quality=quality, optimize=True)
    return {
        "file": target.name,
        "width": size,
        "height": size,
        "bytes": target.stat().st_size,
        "profile": f"square_{size}_white",
    }


def chart_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    family = "arialbd.ttf" if bold else "arial.ttf"
    path = Path("C:/Windows/Fonts") / family
    return ImageFont.truetype(str(path), size=size)


def render_size_chart(request: SizeChartRequest, title: str, target: Path) -> None:
    columns = [str(column).strip() for column in request.columns]
    if any(not column for column in columns) or len(set(columns)) != len(columns):
        raise HTTPException(422, "As colunas devem ser únicas e preenchidas")
    normalized = []
    for row_number, row in enumerate(request.rows, start=1):
        missing = [column for column in columns if column not in row]
        if missing:
            raise HTTPException(
                422,
                f"Linha {row_number} sem dados confirmados: {', '.join(missing)}",
            )
        normalized.append([str(row[column]).strip() for column in columns])
    if any(not value for row in normalized for value in row):
        raise HTTPException(422, "A tabela contém medidas vazias")

    width = height = 1200
    margin, top, row_height = 80, 260, 78
    table_width = width - margin * 2
    column_width = table_width / len(columns)
    if top + row_height * (len(normalized) + 1) > height - 100:
        raise HTTPException(422, "Há linhas demais para a arte de medidas")

    canvas = Image.new("RGB", (width, height), "#ffffff")
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, width, 170), fill="#061720")
    draw.text((margin, 50), "GUIA DE MEDIDAS", font=chart_font(48, True), fill="#33e7ff")
    draw.text((margin, 185), title[:55], font=chart_font(28, True), fill="#102b37")
    draw.text(
        (width - 260, 195),
        f"Unidade: {request.unit}",
        font=chart_font(22),
        fill="#426572",
    )

    for column_index, heading in enumerate(columns):
        left = margin + column_index * column_width
        right = margin + (column_index + 1) * column_width
        draw.rectangle((left, top, right, top + row_height), fill="#0c3140")
        draw.text(
            (left + 16, top + 23),
            heading[:18],
            font=chart_font(22, True),
            fill="#ffffff",
        )
    for row_index, row in enumerate(normalized, start=1):
        y = top + row_index * row_height
        fill = "#edf7fa" if row_index % 2 else "#ffffff"
        for column_index, value in enumerate(row):
            left = margin + column_index * column_width
            right = margin + (column_index + 1) * column_width
            draw.rectangle(
                (left, y, right, y + row_height),
                fill=fill,
                outline="#aac7d1",
                width=2,
            )
            draw.text(
                (left + 16, y + 24),
                value[:20],
                font=chart_font(21),
                fill="#102b37",
            )
    draw.text(
        (margin, height - 70),
        "Medidas fornecidas e confirmadas pelo catálogo.",
        font=chart_font(20),
        fill="#587580",
    )
    canvas.save(target, "JPEG", quality=95, optimize=True)


@router.get("/agents")
def list_agents() -> dict:
    ordered = sorted(AGENTS, key=lambda item: item["stage"])
    return {
        "agents": ordered,
        "count": len(ordered),
        "strategy": "single_responsibility_handoff",
    }


@router.get("/agents/pipeline")
def agent_pipeline() -> dict:
    return {
        "stages": [
            {
                "stage": item["stage"],
                "agent_id": item["id"],
                "name": item["name"],
                "input": item["input"],
                "output": item["output"],
                "state": item["state"],
            }
            for item in sorted(AGENTS, key=lambda row: row["stage"])
        ]
    }


@router.post("/media/prepare")
def prepare_images(request: PrepareImagesRequest) -> dict:
    product = find_product(request.product_id)
    images = product.get("images") or []
    if not images:
        raise HTTPException(422, "O produto não possui imagens")
    product_dir = MEDIA_DIR / request.product_id
    product_dir.mkdir(parents=True, exist_ok=True)
    prepared, errors = [], []
    for index, url in enumerate(images[:10], start=1):
        target = product_dir / f"{index:02d}.jpg"
        try:
            item = prepare_one(url, target, request.size, request.quality)
            item["url"] = f"/media/{request.product_id}/{target.name}"
            prepared.append(item)
        except Exception as exc:
            errors.append({"source": url, "error": str(exc)[:200]})
    if not prepared:
        raise HTTPException(502, {"message": "Nenhuma imagem preparada", "errors": errors})
    return {
        "product_id": request.product_id,
        "agent_id": "image-curator",
        "original_count": len(images),
        "prepared_count": len(prepared),
        "prepared": prepared,
        "errors": errors,
        "approval_required": True,
    }


@router.post("/media/size-chart")
def create_size_chart(request: SizeChartRequest) -> dict:
    product = find_product(request.product_id)
    product_dir = MEDIA_DIR / request.product_id
    product_dir.mkdir(parents=True, exist_ok=True)
    target = product_dir / "size-chart.jpg"
    render_size_chart(request, product.get("title") or "Produto", target)
    return {
        "product_id": request.product_id,
        "agent_id": "size-chart-builder",
        "file": target.name,
        "url": f"/media/{request.product_id}/{target.name}",
        "columns": request.columns,
        "rows": len(request.rows),
        "unit": request.unit,
        "source": "confirmed_user_or_catalog_data",
        "approval_required": True,
    }
