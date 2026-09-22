from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/v1/agency", tags=["agency-router"])
REPO_ROOT = Path(__file__).resolve().parents[3]
AGENCY_ROOT = REPO_ROOT / "vendor" / "agency-agents"


def _frontmatter(path: Path) -> tuple[dict[str, str], str]:
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---"):
        return {}, raw
    _, header, body = raw.split("---", 2)
    values: dict[str, str] = {}
    for line in header.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip("'\\\"")
    return values, body.strip()


@lru_cache(maxsize=1)
def catalog() -> list[dict]:
    divisions_file = AGENCY_ROOT / "divisions.json"
    if not divisions_file.exists():
        return []
    divisions = json.loads(divisions_file.read_text(encoding="utf-8"))["divisions"]
    rows = []
    for division in divisions:
        for path in sorted((AGENCY_ROOT / division).rglob("*.md")):
            metadata, _ = _frontmatter(path)
            if not metadata.get("name"):
                continue
            rows.append({
                "slug": path.stem,
                "name": metadata["name"],
                "description": metadata.get("description", ""),
                "division": division,
                "source_path": str(path.relative_to(AGENCY_ROOT)).replace("\\", "/"),
            })
    return rows


def _score(row: dict, terms: list[str]) -> int:
    fields = {
        "slug": row["slug"].lower(),
        "name": row["name"].lower(),
        "description": row["description"].lower(),
        "division": row["division"].lower(),
    }
    score = 0
    for term in terms:
        if term in fields["name"]: score += 8
        if term in fields["slug"]: score += 6
        if term in fields["division"]: score += 4
        if term in fields["description"]: score += 2
    return score


@router.get("/search")
def search_agents(
    q: str = Query(min_length=2, max_length=200),
    division: str | None = None,
    limit: int = Query(default=8, ge=1, le=20),
) -> dict:
    terms = [item for item in re.findall(r"[\w-]+", q.lower()) if len(item) > 1]
    candidates = [row for row in catalog() if not division or row["division"] == division]
    ranked = [(score, row) for row in candidates if (score := _score(row, terms)) > 0]
    ranked.sort(key=lambda item: (-item[0], item[1]["name"]))
    return {"query": q, "count": len(ranked), "agents": [row | {"score": score} for score, row in ranked[:limit]]}


@router.get("/agents/{slug}")
def inspect_agent(slug: str, include_body: bool = False) -> dict:
    row = next((item for item in catalog() if item["slug"] == slug), None)
    if not row:
        raise HTTPException(404, "Agente não encontrado")
    result = dict(row)
    if include_body:
        _, result["body"] = _frontmatter(AGENCY_ROOT / row["source_path"])
    return result


class LoadAgentRequest(BaseModel):
    slug: str = Field(min_length=2, max_length=200)
    task: str = Field(min_length=3, max_length=4000)


@router.post("/load")
def load_agent(request: LoadAgentRequest) -> dict:
    agent = inspect_agent(request.slug, include_body=True)
    prompt = (
        f"ESPECIALISTA: {agent['name']}\n"
        f"DIVISÃO: {agent['division']}\n"
        f"TAREFA LIMITADA: {request.task}\n\n"
        "REGRAS DO SISTEMA TOCA:\n"
        "- Execute somente esta tarefa limitada.\n"
        "- Não acesse credenciais nem execute ações externas sem autorização.\n"
        "- Entregue evidências e indique incertezas.\n\n"
        f"INSTRUÇÕES DO ESPECIALISTA:\n{agent['body']}"
    )
    return {
        "slug": agent["slug"],
        "name": agent["name"],
        "division": agent["division"],
        "prompt": prompt,
        "execution_authorized": False,
    }


@router.get("/status")
def agency_status() -> dict:
    rows = catalog()
    return {
        "available": bool(rows),
        "agent_count": len(rows),
        "lazy_loading": True,
        "computer_access": "not_granted",
    }

