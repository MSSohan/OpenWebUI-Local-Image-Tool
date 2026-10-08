"""Minimal ComfyUI API client for a CPU-friendly SD Turbo checkpoint."""
from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Any

import requests


class ComfyUIError(RuntimeError):
    """Raised when ComfyUI fails to generate or return an image."""


class ComfyUIClient:
    def __init__(
        self,
        base_url: str,
        checkpoint: str,
        output_dir: Path,
        timeout_seconds: int = 900,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.checkpoint = checkpoint
        self.output_dir = output_dir
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()

    def _workflow(self, prompt: str, seed: int) -> dict[str, Any]:
        # ComfyUI's API-format workflow. sd_turbo works best with very few steps.
        return {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": self.checkpoint},
            },
            "2": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": prompt, "clip": ["1", 1]},
            },
            "3": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": "low quality, blurry, distorted",
                    "clip": ["1", 1],
                },
            },
            "4": {
                "class_type": "EmptyLatentImage",
                "inputs": {"width": 512, "height": 512, "batch_size": 1},
            },
            "5": {
                "class_type": "KSampler",
                "inputs": {
                    "model": ["1", 0],
                    "positive": ["2", 0],
                    "negative": ["3", 0],
                    "latent_image": ["4", 0],
                    "seed": seed,
                    "steps": 4,
                    "cfg": 1.5,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                },
            },
            "6": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["5", 0], "vae": ["1", 2]},
            },
            "7": {
                "class_type": "SaveImage",
                "inputs": {"images": ["6", 0], "filename_prefix": "openwebui_local"},
            },
        }

    def generate(self, prompt: str) -> str:
        """Generate one image; save it under output_dir and return its filename."""
        try:
            queued = self.session.post(
                f"{self.base_url}/prompt",
                json={
                    "prompt": self._workflow(prompt, random.randint(0, 2**31 - 1)),
                    "client_id": "openwebui-local-image-tool",
                },
                timeout=30,
            )
            queued.raise_for_status()
            prompt_id = queued.json().get("prompt_id")
            if not prompt_id:
                raise ComfyUIError("ComfyUI did not return a prompt_id.")

            deadline = time.monotonic() + self.timeout_seconds
            history: dict[str, Any] | None = None
            while time.monotonic() < deadline:
                response = self.session.get(
                    f"{self.base_url}/history/{prompt_id}", timeout=15
                )
                response.raise_for_status()
                data = response.json()
                history = data.get(prompt_id)
                if history and history.get("outputs"):
                    break
                time.sleep(2)

            if not history or not history.get("outputs"):
                raise ComfyUIError(
                    "Timed out waiting for ComfyUI. CPU generation may take several minutes."
                )

            images: list[dict[str, str]] = []
            for node_output in history["outputs"].values():
                images.extend(node_output.get("images", []))
            if not images:
                raise ComfyUIError(
                    "ComfyUI finished without an image. Check the model checkpoint and logs."
                )

            image_info = images[0]
            view = self.session.get(
                f"{self.base_url}/view",
                params={
                    "filename": image_info["filename"],
                    "subfolder": image_info.get("subfolder", ""),
                    "type": image_info.get("type", "output"),
                },
                timeout=60,
            )
            view.raise_for_status()

            self.output_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{prompt_id}.png"
            (self.output_dir / filename).write_bytes(view.content)
            return filename
        except ComfyUIError:
            raise
        except requests.RequestException as exc:
            raise ComfyUIError(
                f"Could not communicate with ComfyUI at {self.base_url}. "
                "Make sure ComfyUI is running on the host at port 8188."
            ) from exc
