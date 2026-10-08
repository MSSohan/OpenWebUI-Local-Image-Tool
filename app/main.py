"""Authenticated OpenAPI tool server for local ComfyUI image generation."""
from __future__ import annotations

import hmac
import os
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, StringConstraints
from starlette.concurrency import run_in_threadpool

from app.comfy import ComfyUIClient, ComfyUIError

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "generated")).resolve()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

API_TOKEN = os.getenv("IMAGE_TOOL_API_TOKEN", "")
COMFYUI_URL = os.getenv("COMFYUI_URL", "http://host.docker.internal:8188")
CHECKPOINT = os.getenv("COMFYUI_CHECKPOINT", "sd_turbo.safetensors")
TIMEOUT = int(os.getenv("COMFYUI_TIMEOUT_SECONDS", "900"))
PUBLIC_IMAGE_BASE_URL = os.getenv(
    "PUBLIC_IMAGE_BASE_URL", "http://localhost:8001"
).rstrip("/")

bearer_scheme = HTTPBearer(auto_error=False)
app = FastAPI(
    title="Local Image Generation Tool",
    description=(
        "Generate an image using a locally hosted ComfyUI server. "
        "No paid image-generation API is used."
    ),
    version="1.0.0",
)
comfy = ComfyUIClient(COMFYUI_URL, CHECKPOINT, OUTPUT_DIR, TIMEOUT)


class GenerateImageRequest(BaseModel):
    prompt: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=3, max_length=1000),
    ] = Field(description="A clear description of the image to generate.")


class GenerateImageResponse(BaseModel):
    status: str
    filename: str
    image_url: str
    markdown: str
    note: str


def require_token(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Security(bearer_scheme)
    ],
) -> None:
    if not API_TOKEN or API_TOKEN.startswith("replace_with_"):
        raise HTTPException(
            status_code=503,
            detail="Server API token is not configured. Set IMAGE_TOOL_API_TOKEN.",
        )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Bearer token required.")
    if not hmac.compare_digest(credentials.credentials, API_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid bearer token.")


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Health check; does not reveal credentials."""
    return {"status": "ok"}


@app.post(
    "/generate-image",
    operation_id="generate_image",
    response_model=GenerateImageResponse,
    tags=["image-generation"],
    summary="Generate an image from a text prompt",
)
async def generate_image(
    request: GenerateImageRequest,
    _: Annotated[None, Depends(require_token)],
) -> GenerateImageResponse:
    """Generate one local image and return a browser-accessible link."""
    try:
        filename = await run_in_threadpool(comfy.generate, request.prompt)
    except ComfyUIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    image_url = f"{PUBLIC_IMAGE_BASE_URL}/images/{filename}"
    return GenerateImageResponse(
        status="success",
        filename=filename,
        image_url=image_url,
        markdown=f"![Generated image]({image_url})",
        note=(
            "Image generated locally by ComfyUI. If the image does not render "
            "automatically, open image_url in your browser."
        ),
    )


app.mount("/images", StaticFiles(directory=OUTPUT_DIR), name="images")
