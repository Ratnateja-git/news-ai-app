# Public local deployment: Priya AI through Cloudflare Tunnel

This is a local deployment. FastAPI, Ollama/Gemma, Kokoro, MongoDB access, and
all inference stay on this Windows PC. Cloudflare Tunnel publishes only the
FastAPI service at `http://127.0.0.1:8000`; it does **not** publish Ollama on
port 11434 or MongoDB.

The existing FastAPI application serves the frontend itself at `/app/`, so the
public page and its API share one HTTPS origin. No frontend or CORS change is
required.

## Prerequisites

- Windows PowerShell.
- A working project Python virtual environment (`.venv` is preferred, with
  `venv` accepted as a fallback).
- Local Ollama running at `http://127.0.0.1:11434` with `gemma3:4b` installed.
- `kokoro-v1.0.onnx` and `voices-v1.0.bin` in the project root, or in the
  directory named by `PRIYA_KOKORO_DIR`.
- `cloudflared` installed from [Cloudflare's official Windows download
  page](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/).
  Download the Windows x64 executable or MSI, then make `cloudflared.exe`
  available on your PATH and open a new PowerShell window.

Do not add API keys to scripts or frontend files. Keep local values only in
the already-gitignored `.env` file.

## Verify the local machine

From the project root:

```powershell
.\check_priya.ps1
```

It checks the virtual environment, Ollama executable/server, `gemma3:4b`,
FastAPI port 8000, both Kokoro files, and `cloudflared`, without displaying
any secrets. A missing model can be installed once with:

```powershell
ollama pull gemma3:4b
```

## Start Priya locally

Open PowerShell window 1 in this project directory:

```powershell
.\start_priya.ps1
```

This starts the existing app in production-style mode (no `--reload`) at:

```text
http://127.0.0.1:8000/app/
```

For normal development, the pre-existing command remains unchanged:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

## Start a free temporary public tunnel

With Priya still running, open PowerShell window 2 in this project directory:

```powershell
.\start_priya_tunnel.ps1
```

The script runs:

```powershell
cloudflared tunnel --url http://127.0.0.1:8000
```

Cloudflare prints a random `https://<name>.trycloudflare.com` URL in that
terminal. Open:

```text
https://<name>.trycloudflare.com/app/
```

from a phone using mobile data or another networked PC. Keep both PowerShell
windows open. Press `Ctrl+C` in the tunnel window to stop public access, then
`Ctrl+C` in the Priya window to stop FastAPI. Quick Tunnel URLs change when
the tunnel restarts and are intended for testing/development, as documented by
[Cloudflare Quick Tunnels](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/).

## What to test after Cloudflare prints a URL

1. Open `/app/` and confirm the existing page loads.
2. Confirm News loads.
3. Ask a Gemma-backed question and verify the response.
4. Trigger voice output and verify Kokoro audio plays.
5. Upload a Career Coach resume and test analysis/matching.
6. Test image/vision upload if it is enabled in `.env`.
7. Visit `/health` and `/api/system-status`. The latter reports only API,
   Ollama/model availability, model name, and TTS availability—never keys,
   paths, or environment values.

## Environment variables

Existing documented variables are:

```env
MONGODB_URI=
DATABASE_NAME=newsai
VISION_ENABLED=true
VISION_MODEL_NAME=gemma3:4b
MAX_IMAGE_SIZE_MB=10
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

The code also supports `OLLAMA_MODEL`, `PRIYA_KOKORO_DIR`,
`PRIYA_TTS_ENABLED`, `PRIYA_CAREER_DB`, `SEARCH_PROVIDER_PRIORITY`,
`TAVILY_API_KEY`, and `EXA_API_KEY` where applicable. Set values only in
`.env` or the local process environment; never commit them.

## Optional named tunnel (stable URL, requires a domain on Cloudflare)

A stable hostname is not needed for the free Quick Tunnel workflow. If you
later have a domain managed by Cloudflare, follow the official [named tunnel
guide](https://developers.cloudflare.com/tunnel/features/locally-managed-tunnels/create-local-tunnel/):

```powershell
cloudflared tunnel login
cloudflared tunnel create priya-local
cloudflared tunnel route dns priya-local priya.example.com
cloudflared tunnel run priya-local
```

Configure that named tunnel's ingress route to send `priya.example.com` to
`http://127.0.0.1:8000`, with a final catch-all `http_status:404` rule. Keep
the credentials file private. A named tunnel gives a stable hostname but does
not make a local PC highly available: it is offline whenever the PC, FastAPI,
Ollama, or tunnel process is stopped.

## Troubleshooting

- **Python launcher fails:** this project currently contains virtual
  environments created with Python 3.11. Repair/reinstall that interpreter,
  recreate the environment, then install `backend/requirements.txt` and
  `modal` only if the separate Modal option is needed.
- **Ollama not found/not ready:** start the local Ollama service, run
  `ollama list`, and ensure `gemma3:4b` is listed. Keep it bound locally; do
  not create a tunnel to port 11434.
- **Kokoro file missing:** restore the two existing model files. The startup
  script deliberately refuses to start instead of silently disabling TTS.
- **cloudflared not found:** install it from Cloudflare's official link above,
  add its folder to PATH, and reopen PowerShell.
- **Quick Tunnel does not start:** ensure no `config.yml` exists under your
  user `.cloudflared` directory; Cloudflare documents that Quick Tunnels do
  not run with that configuration present.
- **Public URL shows an error:** first open `http://127.0.0.1:8000/health` on
  the PC. If that fails, fix Priya locally before retrying the tunnel.

## Security notes

Only FastAPI is reachable through the tunnel. The static mount exposes only
the `frontend` directory, not `.env`, `.git`, source code, SQLite data, or
Kokoro model files. However, a Quick Tunnel URL is public to anyone who gets
it. Do not share it broadly; use Cloudflare Access with a named tunnel if you
need login restrictions, and stop the tunnel when it is not in use.
