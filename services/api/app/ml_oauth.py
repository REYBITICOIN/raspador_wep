from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException

DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
TOKEN_FILE = DATA_DIR / "mercadolivre-token.enc"
STATE_FILE = DATA_DIR / "mercadolivre-oauth-state.json"
TOKEN_LOCK = threading.RLock()
REFRESH_MARGIN_SECONDS = 30 * 60
KEEPER_INTERVAL_SECONDS = 5 * 60
_KEEPER_STARTED = False


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _credentials() -> tuple[str, str, str]:
    app_id = os.getenv("MERCADOLIVRE_APP_ID", "").strip()
    secret = os.getenv("MERCADOLIVRE_CLIENT_SECRET", "").strip()
    redirect_uri = os.getenv("MERCADOLIVRE_REDIRECT_URI", "").strip()
    if not app_id or not secret or not redirect_uri:
        raise HTTPException(503, "Credenciais OAuth do Mercado Livre incompletas")
    return app_id, secret, redirect_uri


def _cipher() -> Fernet:
    app_id, secret, _ = _credentials()
    configured = os.getenv("MERCADOLIVRE_TOKEN_ENCRYPTION_KEY", "").strip()
    material = configured or f"{app_id}:{secret}"
    key = base64.urlsafe_b64encode(hashlib.sha256(material.encode()).digest())
    return Fernet(key)


def _save_token(payload: dict) -> dict:
    expires_in = int(payload.get("expires_in") or 21600)
    stored = {
        "access_token": payload["access_token"],
        "refresh_token": payload.get("refresh_token"),
        "token_type": payload.get("token_type", "Bearer"),
        "scope": payload.get("scope"),
        "user_id": payload.get("user_id"),
        "expires_in": expires_in,
        "issued_at": utcnow().isoformat(),
        "expires_at": (utcnow() + timedelta(seconds=expires_in)).isoformat(),
    }
    if not stored["refresh_token"]:
        current = _load_token(required=False)
        stored["refresh_token"] = current.get("refresh_token") if current else None
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temporary = TOKEN_FILE.with_suffix(".tmp")
    temporary.write_bytes(_cipher().encrypt(json.dumps(stored).encode()))
    temporary.replace(TOKEN_FILE)
    return stored


def _load_token(required: bool = True) -> dict | None:
    try:
        return json.loads(_cipher().decrypt(TOKEN_FILE.read_bytes()).decode())
    except FileNotFoundError:
        if required:
            raise HTTPException(401, "Mercado Livre ainda não foi autorizado")
        return None
    except HTTPException:
        if required:
            raise
        return None
    except (InvalidToken, ValueError, json.JSONDecodeError) as exc:
        if required:
            raise HTTPException(401, "Token salvo não pôde ser descriptografado; autorize novamente") from exc
        return None


def _request_token(data: dict) -> dict:
    response = httpx.post(
        "https://api.mercadolibre.com/oauth/token",
        data=data,
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
        trust_env=False,
    )
    if response.is_error:
        detail = response.text[:500]
        raise HTTPException(502, f"Mercado Livre recusou a renovação OAuth ({response.status_code}): {detail}")
    payload = response.json()
    if not payload.get("access_token"):
        raise HTTPException(502, "Mercado Livre não devolveu access_token")
    return payload


def begin_authorization() -> str:
    app_id, _, redirect_uri = _credentials()
    state = secrets.token_urlsafe(32)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({
        "state": state,
        "expires_at": (utcnow() + timedelta(minutes=10)).isoformat(),
    }), encoding="utf-8")
    query = urlencode({
        "response_type": "code",
        "client_id": app_id,
        "redirect_uri": redirect_uri,
        "state": state,
    })
    return f"https://auth.mercadolivre.com.br/authorization?{query}"


def finish_authorization(code: str, state: str) -> dict:
    app_id, secret, redirect_uri = _credentials()
    try:
        expected = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise HTTPException(400, "Estado OAuth ausente ou expirado; reinicie a conexão") from exc
    if not secrets.compare_digest(state or "", expected.get("state") or ""):
        raise HTTPException(400, "Estado OAuth inválido")
    if datetime.fromisoformat(expected["expires_at"]) < utcnow():
        raise HTTPException(400, "Autorização OAuth expirou; tente novamente")
    payload = _request_token({
        "grant_type": "authorization_code",
        "client_id": app_id,
        "client_secret": secret,
        "code": code,
        "redirect_uri": redirect_uri,
    })
    with TOKEN_LOCK:
        stored = _save_token(payload)
        STATE_FILE.unlink(missing_ok=True)
    return public_token_status(stored)


def refresh_access_token(force: bool = False) -> dict:
    with TOKEN_LOCK:
        token = _load_token()
        expires_at = datetime.fromisoformat(token["expires_at"])
        if not force and expires_at > utcnow() + timedelta(seconds=REFRESH_MARGIN_SECONDS):
            return token
        refresh_token = token.get("refresh_token")
        if not refresh_token:
            raise HTTPException(401, "Mercado Livre não devolveu refresh_token; autorize novamente")
        app_id, secret, _ = _credentials()
        payload = _request_token({
            "grant_type": "refresh_token",
            "client_id": app_id,
            "client_secret": secret,
            "refresh_token": refresh_token,
        })
        return _save_token(payload)


def get_valid_access_token(force_refresh: bool = False) -> str:
    return refresh_access_token(force=force_refresh)["access_token"]


def public_token_status(token: dict | None = None) -> dict:
    token = token or _load_token(required=False)
    if not token:
        return {"state": "authorization_required", "connected": False}
    expires_at = datetime.fromisoformat(token["expires_at"])
    remaining = max(0, int((expires_at - utcnow()).total_seconds()))
    return {
        "state": "connected" if remaining > 0 else "refresh_required",
        "connected": True,
        "user_id": token.get("user_id"),
        "expires_at": token.get("expires_at"),
        "seconds_remaining": remaining,
        "automatic_refresh": True,
        "refresh_margin_seconds": REFRESH_MARGIN_SECONDS,
        "token_exposed_to_browser": False,
    }


def call_with_auto_refresh(method: str, url: str, **kwargs) -> httpx.Response:
    headers = dict(kwargs.pop("headers", {}))
    headers["Authorization"] = f"Bearer {get_valid_access_token()}"
    response = httpx.request(method, url, headers=headers, timeout=30, trust_env=False, **kwargs)
    if response.status_code == 401:
        headers["Authorization"] = f"Bearer {get_valid_access_token(force_refresh=True)}"
        response = httpx.request(method, url, headers=headers, timeout=30, trust_env=False, **kwargs)
    return response


def _keeper_loop() -> None:
    while True:
        try:
            if TOKEN_FILE.exists():
                refresh_access_token(force=False)
        except Exception:
            pass
        time.sleep(KEEPER_INTERVAL_SECONDS)


def start_token_keeper() -> None:
    global _KEEPER_STARTED
    if _KEEPER_STARTED:
        return
    _KEEPER_STARTED = True
    thread = threading.Thread(target=_keeper_loop, name="ml-token-keeper", daemon=True)
    thread.start()
