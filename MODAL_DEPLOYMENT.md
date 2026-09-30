# Modal deployment: Priya AI

This deployment keeps the existing FastAPI application and its `/app` frontend
as one same-origin Modal ASGI endpoint. The frontend continues to use its
existing relative URLs (`/news`, `/ask`, `/tts`, and Career Coach routes); do
not set `window.PRIYA_API_BASE_URL` for this deployment.

## Architecture

- `modal_app.py` exposes `backend.main:app` through `@modal.asgi_app`.
- The browser receives the existing frontend from `/app/` on the same HTTPS
  origin. No permissive CORS policy is needed.
- A GPU-backed container starts Ollama on `127.0.0.1:11434`; the existing
  `backend.llm` and `backend.vision` code call it without modification.
- The default model remains `OLLAMA_MODEL=gemma3:4b`. Ollama persists its
  downloaded model under `/models/llm` in the `priya-ai-models` Volume.
- Existing Kokoro ONNX inference remains in `backend/tts.py`, using `af_heart`.
  Its two private files are mounted at `/models/kokoro` from that same Volume.
- Career Coach uses `/data/career/priya_career.db` on the separate
  `priya-ai-career-data` Volume. Uploaded PDF bytes are still handled only in
  memory by the existing application.

The default GPU is `L4`, selected as a practical single-GPU option for Gemma
3 4B plus this small TTS workload. Change `PRIYA_MODAL_GPU` in `modal_app.py`
to `T4` if lower-cost capacity is sufficient for your traffic. `max_containers`
is intentionally one because this app contains in-process conversation state,
an Ollama sidecar, and a SQLite database. It scales to zero after 60 seconds
of idleness, so cold starts are expected but there is no always-on GPU.

## One-time Modal setup

Run these commands from the project root, using a working Python environment
that has the Modal CLI installed:

```powershell
modal volume create priya-ai-models
modal volume create priya-ai-career-data
modal volume put priya-ai-models .\kokoro-v1.0.onnx /kokoro/kokoro-v1.0.onnx
modal volume put priya-ai-models .\voices-v1.0.bin /kokoro/voices-v1.0.bin
```

Do not upload the files if they are not the intended private Kokoro assets.
The service refuses to start if either one is absent, rather than presenting a
disabled TTS endpoint as working.

Create the secret without putting values in source control. Include only the
variables your deployment actually uses:

```powershell
modal secret create priya-ai-secrets MONGODB_URI='...' DATABASE_NAME='newsai' TAVILY_API_KEY='...' EXA_API_KEY='...'
```

`MONGODB_URI` and `DATABASE_NAME` are needed only for stored-news and database
health features. `TAVILY_API_KEY` and `EXA_API_KEY` are optional search
providers. Other optional existing settings are `OLLAMA_MODEL` (default:
`gemma3:4b`), `VISION_MODEL_NAME`, `VISION_ENABLED`, `MAX_IMAGE_SIZE_MB`, and
`SEARCH_PROVIDER_PRIORITY`. Keep `OLLAMA_MODEL` and `VISION_MODEL_NAME` at
Gemma 3 4B unless you intentionally upload/pull and validate another model.

## Deploy and test

```powershell
python -m compileall backend modal_app.py
git diff --check
modal serve modal_app.py
modal deploy modal_app.py
```

The successful `modal deploy` output prints the public HTTPS URL. Open its
`/app/` path. Lightweight liveness is available at `/health`; it does not run
LLM or TTS inference. Verify `/tts/test` separately after first startup.

## Troubleshooting

- **Kokoro missing:** repeat the two `modal volume put` commands above, then
  redeploy. The startup error names the missing requirement.
- **First startup is slow:** Modal downloads Gemma through Ollama only when
  `/models/llm` is empty. Subsequent containers reuse the Volume.
- **Ollama pull fails:** confirm your Modal account can provision the selected
  GPU and inspect the deployment logs; the app does not silently fall back to
  a different model.
- **Modal CLI/Python will not run on Windows:** recreate/activate the project
  virtual environment with an installed Python, then reinstall `modal` and run
  `modal setup` again. This does not change the application code.
