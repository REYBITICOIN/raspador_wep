from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, HttpUrl

router = APIRouter(prefix="/v1/mcp", tags=["mcp-intelligence"])

READ_ONLY_TOOLS = {"screenshot", "snapshot", "scrape", "wait"}
HIGH_RISK_TOOLS = {
    "powershell", "filesystem.delete", "registry.set", "registry.delete",
    "click", "type", "drag", "shortcut", "process.kill",
}
DISCOVERY_PATHS = ("/.well-known/mcp.json", "/.well-known/webmcp.json", "/mcp.json")
PROJECT_ROOT = Path(__file__).resolve().parents[3]
WINDOWS_MCP_PYTHON = PROJECT_ROOT / ".venv-windows-mcp" / "Scripts" / "python.exe"
WINDOWS_MCP_PROBE = PROJECT_ROOT / "scripts" / "probe_windows_mcp.py"
WINDOWS_MCP_SAFE_EXECUTOR = PROJECT_ROOT / "scripts" / "execute_windows_mcp_safe.py"
SAFE_EXECUTION_TOOLS = {"Wait", "Snapshot"}
APPROVALS_FILE = PROJECT_ROOT / "data" / "mcp_approvals.json"
APPROVALS_LOCK = Lock()


class DiscoveryRequest(BaseModel):
    url: HttpUrl


class ApprovalRequest(BaseModel):
    tool: str
    purpose: str
    arguments: dict = Field(default_factory=dict)


class DecisionRequest(BaseModel):
    decision: str
    note: str = ""


def _config_candidates() -> list[Path]:
    home = Path.home()
    env_path = os.getenv("MCP_CONFIG_PATH")
    values = [
        Path(env_path) if env_path else None,
        home / "Desktop" / "MCP" / "mcp_config.json",
        home / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json",
    ]
    return [path for path in values if path and path.exists()]
def _risk_for(name: str, command: str, args: list[str]) -> tuple[str, list[str]]:
    text = " ".join([name, command, *args]).lower()
    reasons: list[str] = []
    if "windows_mcp" in text or "windows-mcp" in text:
        reasons.append("Controla o Windows real sem isolamento")
    if any(word in text for word in ("powershell", "cmd.exe", "bash", "sh.exe")):
        reasons.append("Pode executar comandos do sistema")
    return ("high" if reasons else "review"), reasons


def _inspect_server(name: str, spec: dict, config_path: Path) -> dict:
    command = str(spec.get("command", "")).strip()
    args = [str(item) for item in spec.get("args", [])]
    command_path = Path(command)
    command_found = bool(
        command and (
            (command_path.is_absolute() and command_path.exists())
            or shutil.which(command)
        )
    )
    risk, reasons = _risk_for(name, command, args)
    return {
        "name": name,
        "config_path": str(config_path),
        "command": command,
        "args": args,
        "command_found": command_found,
        "transport": "stdio",
        "risk": risk,
        "risk_reasons": reasons,
        "auto_start_allowed": False,
        "requires_human_approval": True,
    }


def scan_local_configs() -> dict:
    servers: list[dict] = []
    errors: list[dict] = []
    for path in _config_candidates():
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            entries = payload.get("mcpServers", {})
            if not isinstance(entries, dict):
                raise ValueError("mcpServers deve ser um objeto")
            servers.extend(_inspect_server(name, spec, path) for name, spec in entries.items())
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            errors.append({"config_path": str(path), "error": str(exc)})
    return {"configs_found": len(_config_candidates()), "servers": servers, "errors": errors}
def _assert_public_https(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise HTTPException(400, "A descoberta MCP exige URL HTTPS pública")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, 443)}
    except socket.gaierror as exc:
        raise HTTPException(400, "Domínio não encontrado") from exc
    if any(not ip_address(address).is_global for address in addresses):
        raise HTTPException(400, "Endereço privado ou local não é permitido")


def _validate_manifest(payload: object, source: str) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("manifesto não é um objeto JSON")
    name = payload.get("name") or payload.get("server", {}).get("name")
    transport = payload.get("transport")
    packages = payload.get("packages", [])
    return {
        "source": source,
        "name": name,
        "transport": transport,
        "packages": packages if isinstance(packages, list) else [],
        "raw_keys": sorted(payload.keys()),
        "verified": False,
        "connection_created": False,
        "requires_human_approval": True,
    }


@router.get("/policy")
def policy() -> dict:
    return {
        "automatic": ["descobrir manifestos", "validar JSON", "verificar executável", "ler metadados"],
        "approval_required": ["alterar configuração", "iniciar servidor MCP", "autenticar conta", "escrever arquivos"],
        "blocked_without_explicit_confirmation": sorted(HIGH_RISK_TOOLS),
        "read_only_tools": sorted(READ_ONLY_TOOLS),
        "unknown_servers_auto_start": False,
    }


@router.get("/status")
def status() -> dict:
    scan = scan_local_configs()
    return {
        "installed": True,
        "mode": "discover_validate_plan",
        "configs_found": scan["configs_found"],
        "server_count": len(scan["servers"]),
        "high_risk_count": sum(item["risk"] == "high" for item in scan["servers"]),
        "automatic_connection": False,
    }
@router.post("/scan-local")
def scan_local() -> dict:
    result = scan_local_configs()
    result["policy"] = policy()
    return result


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_approvals() -> list[dict]:
    try:
        payload = json.loads(APPROVALS_FILE.read_text(encoding="utf-8"))
        return payload if isinstance(payload, list) else []
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []


def _save_approvals(items: list[dict]) -> None:
    APPROVALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = APPROVALS_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(APPROVALS_FILE)


def _approval_risk(tool: str) -> str:
    normalized = tool.strip().lower()
    if normalized in HIGH_RISK_TOOLS:
        return "high"
    if normalized in READ_ONLY_TOOLS:
        return "read_only"
    return "review"


@router.get("/approvals")
def list_approvals() -> dict:
    with APPROVALS_LOCK:
        items = _load_approvals()
    return {"items": list(reversed(items)), "pending": sum(item["state"] == "pending" for item in items)}


@router.post("/approvals", status_code=201)
def create_approval(request: ApprovalRequest) -> dict:
    if not request.tool.strip() or len(request.purpose.strip()) < 3:
        raise HTTPException(400, "Ferramenta e finalidade são obrigatórias")
    item = {
        "id": str(uuid4()),
        "tool": request.tool.strip(),
        "purpose": request.purpose.strip(),
        "arguments": request.arguments,
        "risk": _approval_risk(request.tool),
        "state": "pending",
        "created_at": _now(),
        "decided_at": None,
        "decision_note": "",
        "executed": False,
        "execution_state": "awaiting_approval",
        "execution_result": None,
    }
    with APPROVALS_LOCK:
        items = _load_approvals()
        items.append(item)
        _save_approvals(items)
    return item


@router.post("/approvals/{approval_id}/decision")
def decide_approval(approval_id: str, request: DecisionRequest) -> dict:
    if request.decision not in {"approved", "rejected"}:
        raise HTTPException(400, "Decisão deve ser approved ou rejected")
    with APPROVALS_LOCK:
        items = _load_approvals()
        item = next((entry for entry in items if entry["id"] == approval_id), None)
        if not item:
            raise HTTPException(404, "Pedido de aprovação não encontrado")
        if item["state"] != "pending":
            raise HTTPException(409, "Pedido já foi decidido")
        item["state"] = request.decision
        item["decided_at"] = _now()
        item["decision_note"] = request.note.strip()[:500]
        item["executed"] = False
        item["execution_state"] = "awaiting_execution" if request.decision == "approved" else "blocked"
        _save_approvals(items)
    return item


@router.post("/approvals/{approval_id}/execute")
def execute_approval(approval_id: str) -> dict:
    with APPROVALS_LOCK:
        items = _load_approvals()
        item = next((entry for entry in items if entry["id"] == approval_id), None)
        if not item:
            raise HTTPException(404, "Pedido de aprovação não encontrado")
        if item["state"] != "approved":
            raise HTTPException(403, "Somente pedidos aprovados podem executar")
        if item.get("executed") or item.get("execution_state") == "running":
            raise HTTPException(409, "Pedido já foi executado ou está em execução")
        if item.get("risk") != "read_only":
            raise HTTPException(403, "Somente ações classificadas como leitura podem executar")
        if item["tool"] not in SAFE_EXECUTION_TOOLS:
            raise HTTPException(403, "Ferramenta ainda não liberada para execução")
        item["execution_state"] = "running"
        _save_approvals(items)
    try:
        completed = subprocess.run(
            [
                str(WINDOWS_MCP_PYTHON),
                str(WINDOWS_MCP_SAFE_EXECUTOR),
                item["tool"],
                json.dumps(item["arguments"], ensure_ascii=False),
            ],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        result = json.loads(lines[-1]) if lines else {"success": False, "error": "Sem resposta"}
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        result = {"success": False, "error": str(exc)[:500]}
        completed = None
    with APPROVALS_LOCK:
        items = _load_approvals()
        stored = next(entry for entry in items if entry["id"] == approval_id)
        stored["executed"] = bool(result.get("success"))
        stored["execution_state"] = "completed" if result.get("success") else "failed"
        stored["executed_at"] = _now()
        stored["execution_result"] = result
        _save_approvals(items)
    if not result.get("success"):
        raise HTTPException(502, result)
    return stored


@router.post("/probe/windows-sistema")
def probe_windows_system() -> dict:
    if not WINDOWS_MCP_PYTHON.exists() or not WINDOWS_MCP_PROBE.exists():
        raise HTTPException(503, "Ambiente isolado do Windows-MCP não está instalado")
    try:
        completed = subprocess.run(
            [str(WINDOWS_MCP_PYTHON), str(WINDOWS_MCP_PROBE)],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=75,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(504, "Windows-MCP não respondeu dentro de 75 segundos") from exc
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if not lines:
        raise HTTPException(502, "Windows-MCP não devolveu o resultado do teste")
    try:
        result = json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise HTTPException(502, "Resposta inválida do teste Windows-MCP") from exc
    result["exit_code"] = completed.returncode
    result["execution_policy"] = "safe_probe_only"
    if completed.returncode != 0 or not result.get("connected"):
        raise HTTPException(502, result)
    return result


@router.post("/discover")
def discover(request: DiscoveryRequest) -> dict:
    root = str(request.url)
    _assert_public_https(root)
    parsed = urlparse(root)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    attempts: list[dict] = []
    discoveries: list[dict] = []
    with httpx.Client(timeout=12, follow_redirects=False) as client:
        for suffix in DISCOVERY_PATHS:
            candidate = urljoin(origin, suffix)
            try:
                response = client.get(candidate, headers={"Accept": "application/json"})
                attempts.append({"url": candidate, "status": response.status_code})
                if response.status_code == 200:
                    content_type = response.headers.get("content-type", "")
                    if "json" not in content_type.lower():
                        continue
                    discoveries.append(_validate_manifest(response.json(), candidate))
            except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
                attempts.append({"url": candidate, "error": str(exc)[:240]})
    return {
        "origin": origin,
        "discoveries": discoveries,
        "attempts": attempts,
        "connection_created": False,
        "next_step": "Revisão humana antes de gravar configuração ou iniciar servidor",
    }
