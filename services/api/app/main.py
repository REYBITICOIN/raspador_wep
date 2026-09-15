from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "development"
    nvidia_api_key: str | None = None
    nvidia_model: str | None = None
    xai_api_key: str | None = None
    xai_model: str | None = None
    default_model_provider: str = "nvidia"
    allow_paid_models: bool = False


settings = Settings()
app = FastAPI(title="Web Intelligence Lab API", version="0.1.0")


class JobRequest(BaseModel):
    url: HttpUrl
    instruction: str
    provider: str = "auto"


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "environment": settings.app_env}


@app.get("/v1/providers")
def providers() -> dict:
    return {
        "default": settings.default_model_provider,
        "providers": [
            {
                "id": "nvidia",
                "configured": bool(settings.nvidia_api_key),
                "model": settings.nvidia_model,
                "paid": False,
            },
            {
                "id": "grok",
                "configured": bool(settings.xai_api_key),
                "model": settings.xai_model,
                "paid": True,
                "enabled": settings.allow_paid_models,
            },
        ],
    }


@app.post("/v1/jobs", status_code=202)
def create_job(job: JobRequest) -> dict:
    if job.provider == "grok" and not settings.allow_paid_models:
        return {"accepted": False, "reason": "paid_provider_disabled"}
    return {
        "accepted": True,
        "status": "queued",
        "url": str(job.url),
        "provider": job.provider,
    }

