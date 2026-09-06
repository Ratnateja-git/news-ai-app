# Priya News AI

A local, voice-first news assistant built with FastAPI and Ollama/Gemma 3. Headlines are formatted directly from RSS; Gemma is only used for explicit explanations, follow-ups, and uploaded-image analysis.

## Setup

Create and activate a virtual environment, then install the backend dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
```

Run from the project folder:

```powershell
uvicorn backend.main:app --reload
```

Open http://127.0.0.1:8000. Ollama is required only for detailed responses and image analysis; the configured model is `gemma3:4b`.

Image upload accepts JPG, PNG, and WEBP files up to 10 MB. Optional configuration:

```env
VISION_ENABLED=true
VISION_MODEL_NAME=gemma3:4b
MAX_IMAGE_SIZE_MB=10
OLLAMA_BASE_URL=http://127.0.0.1:11434
```
