
# Open WebUI + Local Image Generation Tool

A local image-generation integration built for the Aitek Ltd. recruitment task. Open WebUI connects to an authenticated FastAPI OpenAPI tool server, which sends generation requests to ComfyUI running on the Windows host.

No paid LLM or image-generation API is required.

## Architecture

```text
Browser
  └── Open WebUI (Docker)
        ├── Ollama (local LLM)
        └── FastAPI OpenAPI Tool Server (Docker)
              └── ComfyUI (Windows host, CPU)
                    └── Local Stable Diffusion Turbo checkpoint
```

## Prerequisites

- Windows 10/11, Docker Desktop, and Docker Compose v2
- Python 3.10 or 3.11 and Git
- Disk space for dependencies and model weights
- A compatible Stable Diffusion Turbo checkpoint

## Setup & Run

### 1. Install and Start ComfyUI

Install ComfyUI and its CPU dependencies using the [official installation guide](https://docs.comfy.org/installation).

Place the checkpoint at:

`ComfyUI/models/checkpoints/sd_turbo.safetensors`

Start ComfyUI from its installation directory:

```powershell
python main.py --cpu --listen 0.0.0.0 --port 8188
```

Keep this terminal open.

### 2. Configure Environment Variables

From the project root:

```powershell
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"
```

Generate two different secrets and configure `.env`:

```dotenv
WEBUI_SECRET_KEY=<your-random-secret>
IMAGE_TOOL_API_TOKEN=<your-different-random-token>
COMFYUI_URL=http://host.docker.internal:8188
COMFYUI_CHECKPOINT=sd_turbo.safetensors
COMFYUI_TIMEOUT_SECONDS=900
PUBLIC_IMAGE_BASE_URL=http://localhost:8001
```

Never commit `.env` to Git.

### 3. Start Docker Services

```powershell
docker compose up --build -d
docker compose exec ollama ollama pull qwen2.5:3b
```

Open WebUI: http://localhost:3000

API health check: http://localhost:8001/health

### 4. Connect the Image-Generation Tool

In Open WebUI, add an OpenAPI tool server using:

`http://image-tool:8000/openapi.json`

Configure **Bearer authentication** with the exact `IMAGE_TOOL_API_TOKEN` from `.env`.

Enable the tool in a chat with a model that supports tool calling.

Example prompt:

> A photorealistic modern desk with a black printer, a smartphone displaying a document ready to print, soft natural daylight, clean professional workspace, realistic photography

The tool returns the generated image URL and a Markdown image link.

## Testing

Run the automated tests locally:

```powershell
python -m venv .venv-test
.\.venv-test\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest -q
```

The automated tests mock ComfyUI. For end-to-end verification, keep ComfyUI running, ensure the checkpoint is installed, and generate an image through Open WebUI.

## Security

- Secrets are stored in `.env` and excluded from Git.
- The image-generation endpoint requires a Bearer token.
- Keep Open WebUI and tool-server host ports bound to localhost.
- Do not expose ComfyUI port `8188` to the public internet.
- Follow the license of the downloaded model checkpoint.

## Stop Services

```powershell
docker compose down
```

## License

This project is intended for demonstration and recruitment evaluation. Third-party dependencies and model checkpoints retain their respective licenses.