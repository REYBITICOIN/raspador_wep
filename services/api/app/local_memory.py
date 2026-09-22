from __future__ import annotations

import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/v1/memory", tags=["local-memory"])
DB_PATH = Path(os.getenv("LOCAL_DATABASE_PATH", "./data/commerce.db"))
VAULT_PATH = Path(os.getenv("OBSIDIAN_VAULT_PATH", "./data/obsidian"))
LOCK = Lock()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


@contextmanager
def database():
    connection = connect()
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def initialize() -> None:
    VAULT_PATH.mkdir(parents=True, exist_ok=True)
    with database() as db:
        db.executescript("""
        create table if not exists memories (
          id text primary key,
          kind text not null,
          title text not null,
          content text not null,
          source text,
          tags text not null default '',
          created_at text not null,
          updated_at text not null
        );
        create index if not exists memories_kind_created_idx
          on memories(kind, created_at desc);
        create virtual table if not exists memories_fts using fts5(
          id unindexed, title, content, tags, tokenize='unicode61'
        );
        """)


def safe_filename(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", value).strip(" .")
    return (cleaned[:100] or "memoria") + ".md"


class MemoryRequest(BaseModel):
    kind: str = Field(pattern="^(decision|research|product|procedure|note)$")
    title: str = Field(min_length=3, max_length=200)
    content: str = Field(min_length=3, max_length=100_000)
    source: str | None = Field(default=None, max_length=1000)
    tags: list[str] = Field(default_factory=list, max_length=30)


@router.post("", status_code=201)
def create_memory(request: MemoryRequest) -> dict:
    initialize()
    memory_id = str(uuid4())
    timestamp = now_iso()
    tags = ",".join(sorted({tag.strip().lower() for tag in request.tags if tag.strip()}))
    with LOCK, database() as db:
        db.execute(
            "insert into memories(id,kind,title,content,source,tags,created_at,updated_at) values(?,?,?,?,?,?,?,?)",
            (memory_id, request.kind, request.title, request.content, request.source, tags, timestamp, timestamp),
        )
        db.execute(
            "insert into memories_fts(id,title,content,tags) values(?,?,?,?)",
            (memory_id, request.title, request.content, tags),
        )
    note_dir = VAULT_PATH / request.kind
    note_dir.mkdir(parents=True, exist_ok=True)
    note_path = note_dir / safe_filename(f"{timestamp[:10]} - {request.title}")
    note = (
        f"---\nid: {memory_id}\nkind: {request.kind}\n"
        f"created_at: {timestamp}\ntags: [{tags}]\n---\n\n"
        f"# {request.title}\n\n{request.content}\n"
    )
    note_path.write_text(note, encoding="utf-8")
    return {"id": memory_id, "created_at": timestamp, "note_path": str(note_path)}


@router.get("/search")
def search_memory(q: str = Query(min_length=2, max_length=200), limit: int = Query(10, ge=1, le=50)) -> list[dict]:
    initialize()
    terms = " ".join(re.findall(r"[\w-]+", q, flags=re.UNICODE))
    if not terms:
        raise HTTPException(400, "Consulta sem termos válidos")
    with database() as db:
        rows = db.execute(
            """select m.id,m.kind,m.title,m.content,m.source,m.tags,m.created_at
               from memories_fts f join memories m on m.id=f.id
               where memories_fts match ? order by bm25(memories_fts) limit ?""",
            (terms, limit),
        ).fetchall()
    return [dict(row) for row in rows]


@router.get("/status")
def memory_status() -> dict:
    initialize()
    with database() as db:
        count = db.execute("select count(*) from memories").fetchone()[0]
    return {
        "database": str(DB_PATH),
        "vault": str(VAULT_PATH),
        "memory_count": count,
        "database_exists": DB_PATH.exists(),
        "vault_exists": VAULT_PATH.exists(),
        "local_only": True,
    }

