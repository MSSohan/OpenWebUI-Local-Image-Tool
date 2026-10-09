# Open WebUI + Local Image Generation Tool

A free, local image-generation integration for the Aitek Ltd. recruitment task.

- Open WebUI runs in Docker.
- Ollama runs a small local chat model in Docker, so no paid LLM API is required.
- A Python/FastAPI tool server runs in Docker and exposes an authenticated OpenAPI operation.
- ComfyUI runs locally on the Windows host in CPU mode.
- ComfyUI uses a local checkpoint; no paid image-generation API or API credits are required.

> **Hardware note:** with 32 GB RAM but no dedicated GPU, CPU generation can be slow. SD Turbo is configured for 512×512 images and 4 steps to reduce runtime. Exact speed depends on your CPU. Model weights must be downloaded separately and their license must be followed.

## Architecture

```text
Browser
  └── Open WebUI (Docker, http://localhost:3000)
        ├── Ollama local chat model (Docker, ollama:11434)
        └── OpenAPI tool server (Docker network, image-tool:8000)
              └── ComfyUI on Windows host (host.docker.internal:8188)
                    └── local SD Turbo checkpoint
Generated images are saved in ./generated and served at http://localhost:8001/images/<filename>.
```

## Prerequisites

1. Windows 10/11 with Docker Desktop and Docker Compose v2.
2. Python 3.10 or 3.11 and Git for Windows.
3. Approximately 32 GB RAM is helpful for CPU-only generation. Keep other heavy applications closed.
4. Disk space for ComfyUI, PyTorch, and the model checkpoint (several GB).

## 1. Install ComfyUI on Windows (CPU mode)

ComfyUI is intentionally run outside Docker for this CPU-only Windows setup. The Open WebUI and FastAPI services are containerized; the tool server calls ComfyUI through Docker Desktop's `host.docker.internal` host gateway.

In PowerShell:

```powershell
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

Install the CPU build of PyTorch, then ComfyUI's requirements:

```powershell
python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements.txt
```

Download a ComfyUI-compatible SD Turbo checkpoint from a source you trust and whose license you accept. Save it as:

```text
ComfyUI\models\checkpoints\sd_turbo.safetensors
```

If the downloaded file has a different name, update `COMFYUI_CHECKPOINT` in this project's `.env`.

Start ComfyUI in CPU mode (keep this terminal open):

```powershell
python main.py --cpu --listen 0.0.0.0 --port 8188
```

Open `http://localhost:8188` to confirm ComfyUI loads. The `--listen 0.0.0.0` option allows the Docker container to reach it. Keep Windows Firewall enabled, do not port-forward 8188, and use this only on a trusted machine/network. If you have a stricter firewall setup, add a rule that restricts inbound port 8188 to the local Docker/host network.

## 2. Configure this project

In PowerShell, from this repository folder:

```powershell
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"
```

Run the Python command twice and paste the two different values into `.env`:

- `WEBUI_SECRET_KEY`
- `IMAGE_TOOL_API_TOKEN`

Do not commit `.env`. It is ignored by Git. Keep `.env.example` as a template only.

Example `.env` (use your own random values):

```dotenv
WEBUI_SECRET_KEY=your_own_random_secret
IMAGE_TOOL_API_TOKEN=a_different_random_secret
COMFYUI_URL=http://host.docker.internal:8188
COMFYUI_CHECKPOINT=sd_turbo.safetensors
COMFYUI_TIMEOUT_SECONDS=900
PUBLIC_IMAGE_BASE_URL=http://localhost:8001
```

## 3. Start Open WebUI and the tool server

From the repository root:

```powershell
docker compose up --build -d
docker compose ps
docker compose logs -f image-tool
```

Open:

- Open WebUI: http://localhost:3000
- Tool server health: http://localhost:8001/health
- OpenAPI schema: http://localhost:8001/openapi.json
- Interactive API docs: http://localhost:8001/docs

The image tool and Ollama host ports are bound to `127.0.0.1`, not all network interfaces. Open WebUI data and Ollama model files are persisted in named Docker volumes.

## 3a. Download a small local chat model

Once the containers are running, pull a small model suitable for CPU-only use:

```powershell
docker compose exec ollama ollama pull qwen2.5:3b
```

Then select `qwen2.5:3b` from the model selector in Open WebUI. It runs locally and does not require a paid model API. Performance depends on your CPU.

## 4. Connect the OpenAPI tool to Open WebUI

1. Open `http://localhost:3000` and create the local admin account.
2. Open the tool/server integration settings. Depending on the Open WebUI version, this may appear under **Admin Settings → Tool Servers** or **Settings → Integrations → Tools**.
3. Add an OpenAPI tool server using this URL from the Docker network:

   `http://image-tool:8000/openapi.json`

4. Configure authentication as **Bearer** and paste the exact `IMAGE_TOOL_API_TOKEN` value from `.env`. Do not paste `WEBUI_SECRET_KEY` here.
5. Save/verify the tool server. The discovered operation should be `generate_image`.
6. Start a chat with a model that supports tool calling. Enable the image tool if the UI asks which tools to use.

Example prompt:

> Use the generate_image tool to create a small red cabin in a snowy pine forest at sunrise. Generate the image; do not just describe it.

The tool returns an `image_url` and Markdown image link. If the model does not render the image automatically, open the returned `image_url` in the same browser.

**Model note:** This project includes Ollama for a local chat model, so the full stack can be used without paid API credentials. Tool-call reliability varies by model; if the model does not call the tool correctly, try another small local model with stronger tool-calling support.

## 5. Test the tool server directly

With the containers running, test the health endpoint:

```powershell
Invoke-RestMethod http://localhost:8001/health
```

Test authorization (replace the value with your `.env` token):

```powershell
$token = "YOUR_IMAGE_TOOL_API_TOKEN"
$headers = @{ Authorization = "Bearer $token" }
$body = @{ prompt = "A simple watercolor illustration of a blue bicycle" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8001/generate-image -Headers $headers -ContentType "application/json" -Body $body
```

The response should include `status`, `filename`, `image_url`, and `markdown`. A full generation test requires ComfyUI to be running with the checkpoint installed.

## 6. Run automated tests

The tests mock ComfyUI so they do not download a model or consume image-generation compute.

```powershell
python -m venv .venv-test
.\.venv-test\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest -q
```

Expected: all six tests pass. These tests cover health, OpenAPI bearer security, missing/invalid tokens, request validation, and the successful response path. They do not replace an end-to-end image-generation test.

## 7. Git and repository submission

```powershell
git init
git add .
git status
```

Before committing, verify `.env` is not listed by `git status`. Then:

```powershell
git commit -m "Build authenticated Open WebUI local image generation tool"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/openwebui-local-image-tool.git
git push -u origin main
```

Create an empty GitHub repository first, then replace `YOUR_USERNAME` with your account. Never include API keys, `.env`, model weights, generated images, or a local ComfyUI checkout in the repository.

## Troubleshooting

- **Connection refused / 502:** confirm ComfyUI is running at `http://localhost:8188`; from Docker, the tool server uses `http://host.docker.internal:8188`.
- **Checkpoint not found:** ensure the checkpoint filename exactly matches `COMFYUI_CHECKPOINT` and is under `ComfyUI\models\checkpoints`.
- **CPU generation is slow:** SD Turbo is set to 512×512 and 4 steps. Wait for the configured timeout or lower the image size/steps in `app/comfy.py` if your checkpoint supports it.
- **Tool is not called:** select a model with reliable native tool calling, enable the tool for the chat, and explicitly ask the model to use `generate_image`.
- **Image URL does not open:** check that `http://localhost:8001/health` works and that the file exists in `generated/`.

## Security notes

- The image-generation operation requires an HTTP Bearer token.
- The token is read from an environment variable; it is not hard-coded in source.
- `.env` is excluded from Git.
- Open WebUI and the tool server ports are bound to localhost only.
- ComfyUI is reachable from Docker through the host gateway; do not expose port 8188 to the public internet.
- This is a local demo project, not a hardened multi-user production service.
