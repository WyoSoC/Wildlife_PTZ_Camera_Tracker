"""
Wildlife model registry endpoints.
"""
from __future__ import annotations
import asyncio
import logging
import re
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core.models import list_models, get_model, models_dir

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("")
async def get_models():
    """List all available models (wildlife catalog + custom in models/ + COCO fallbacks)."""
    return {
        "models": [
            {
                "name":           m.name,
                "path":           m.path,
                "description":    m.description,
                "species":        m.species,
                "source":         m.source,
                "auto_download":  m.auto_download,
                "detect_classes": m.detect_classes,
                "downloaded":     m.downloaded,
                "repo_id":        m.repo_id,
                "download_url":   m.download_url,
            }
            for m in list_models()
        ],
        "models_dir": models_dir(),
    }


@router.post("/{name}/download")
async def download_model(name: str):
    """
    Download a wildlife model. Supports HuggingFace repos and direct URLs.
    """
    info = get_model(name)
    if info is None:
        raise HTTPException(404, detail=f"Model '{name}' not found in catalog")
    if not info.auto_download:
        raise HTTPException(400, detail=f"Model '{name}' cannot be downloaded automatically")
    if not info.repo_id and not info.download_url:
        raise HTTPException(400, detail=f"Model '{name}' has no download source configured")

    target_dir = Path(models_dir()) / info.subdir if info.subdir else Path(models_dir())
    target_dir.mkdir(parents=True, exist_ok=True)
    dest = target_dir / f"{name}.pt"
    if dest.exists():
        return {"status": "already_downloaded", "path": str(dest)}

    # ── Direct URL download ────────────────────────────────────────────────────
    if info.download_url:
        logger.info("Downloading %s from %s …", name, info.download_url)
        tmp = dest.with_suffix(".tmp")
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=600) as client:
                async with client.stream("GET", info.download_url) as response:
                    response.raise_for_status()
                    with open(tmp, "wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=65536):
                            f.write(chunk)
            tmp.rename(dest)
            logger.info("Downloaded %s → %s", name, dest)
            return {"status": "downloaded", "path": str(dest)}
        except Exception as exc:
            tmp.unlink(missing_ok=True)
            logger.error("Download failed for %s: %s", name, exc)
            raise HTTPException(502, detail=f"Download failed: {exc}")

    # ── HuggingFace download ───────────────────────────────────────────────────
    try:
        from huggingface_hub import hf_hub_download  # type: ignore
    except ImportError:
        raise HTTPException(
            503,
            detail="huggingface_hub is not installed. Run: pip install huggingface_hub",
        )

    logger.info("Downloading %s from HuggingFace %s …", name, info.repo_id)
    loop = asyncio.get_event_loop()
    try:
        cached_str: str = await loop.run_in_executor(
            None,
            lambda: hf_hub_download(
                repo_id=info.repo_id,
                filename=info.hf_filename,
                local_dir=str(target_dir),
            ),
        )
        cached = Path(cached_str)
        if cached.resolve() != dest.resolve() and cached.exists():
            cached.rename(dest)
        logger.info("Downloaded %s → %s", name, dest)
        return {"status": "downloaded", "path": str(dest)}
    except Exception as exc:
        logger.error("Download failed for %s: %s", name, exc)
        raise HTTPException(502, detail=f"Download failed: {exc}")


# ── Custom HuggingFace model ───────────────────────────────────────────────────

class CustomModelRequest(BaseModel):
    repo_url:  str              # full HF URL or "owner/repo" shorthand
    filename:  str = "best.pt"  # filename inside the repo
    name:      Optional[str] = None   # local model name (defaults to repo name)


_HF_URL_RE = re.compile(r'huggingface\.co/([^/\s]+/[^/\s]+)', re.I)


def _parse_repo_id(raw: str) -> str:
    """Extract 'owner/repo' from a full HuggingFace URL or return as-is."""
    raw = raw.strip()
    m   = _HF_URL_RE.search(raw)
    if m:
        return m.group(1).rstrip('/')
    # Validate plain "owner/repo" format
    parts = raw.split('/')
    if len(parts) == 2 and all(p.strip() for p in parts):
        return raw
    raise ValueError(f"Cannot parse HuggingFace repo ID from: {raw!r}")


@router.post("/custom")
async def add_custom_model(req: CustomModelRequest):
    """
    Download a .pt file from any public HuggingFace repo into models/custom/.

    Accepts a full HuggingFace URL (https://huggingface.co/owner/repo) or a
    plain repo ID (owner/repo).  The file is saved as <name>.pt and will
    appear automatically in the model list on the next refresh.
    """
    try:
        repo_id = _parse_repo_id(req.repo_url)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    local_name = req.name or repo_id.split('/')[-1]
    # Sanitise: keep only alphanumeric, underscore, hyphen
    local_name = re.sub(r'[^\w\-]', '_', local_name).strip('_') or 'custom_model'

    try:
        from huggingface_hub import hf_hub_download  # type: ignore
    except ImportError:
        raise HTTPException(
            503,
            detail="huggingface_hub is not installed — run: pip install huggingface_hub",
        )

    target_dir = Path(models_dir()) / "custom"
    target_dir.mkdir(parents=True, exist_ok=True)
    dest = target_dir / f"{local_name}.pt"

    logger.info("Custom model: downloading %s / %s → %s", repo_id, req.filename, dest)
    loop = asyncio.get_event_loop()
    try:
        cached_str: str = await loop.run_in_executor(
            None,
            lambda: hf_hub_download(
                repo_id=repo_id,
                filename=req.filename,
                local_dir=str(target_dir),
            ),
        )
        cached = Path(cached_str)
        if cached.resolve() != dest.resolve() and cached.exists():
            cached.rename(dest)
        logger.info("Custom model saved → %s", dest)
        return {"status": "downloaded", "name": local_name, "path": str(dest)}
    except Exception as exc:
        logger.error("Custom model download failed: %s", exc)
        raise HTTPException(502, detail=f"Download failed: {exc}")
