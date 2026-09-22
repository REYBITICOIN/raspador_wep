from __future__ import annotations

import json
import os
import shutil
import socket
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl

router = APIRouter(prefix="/v1/mcp", tags=["mcp-intelligence"])

READ_ONLY_TOOLS = {"screenshot", "snapshot", "scrape", "wait"}
HIGH_RISK_TOOLS = {
    "powershell", "filesystem.delete", "registry.set", "registry.delete",
    "click", "type", "drag", "shortcut", "process.kill",
}
DISCOVERY_PATHS = ("/.well-known/mcp.json", "/.well-known/webmcp.json", "/mcp.json")


class DiscoveryRequest(BaseModel):
    url: HttpUrl


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
