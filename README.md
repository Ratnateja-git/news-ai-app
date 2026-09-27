# Priya AI

A local, voice-first assistant for news and career growth. Headlines are formatted directly from RSS; Gemma is used only for explicit explanations, follow-ups, and uploaded-image analysis.

## Career Coach

Career Coach adds private, in-memory PDF resume analysis, the transparent **Priya Resume Score**, job-description matching, skill-gap suggestions, non-fabricating resume-tailoring guidance, and a resume-aware mock interview with adaptive follow-ups and a deterministic final scorecard. Scores are heuristic estimates, never company ATS results.

Career API endpoints: `POST /career/resume/upload`, `/career/resume/analyze`, `/career/job/parse`, `/career/job/match`, `/career/resume/tailor`, `/career/interview/start`, `/career/interview/answer`, and `GET /career/interview/report/{id}`.

Demo: upload a real PDF resume, analyze it, paste a target job description, view the Priya Job Match Score and gaps, start a mixed interview, answer several questions, then open the report. The service never creates resume facts or metrics; add measurable results only when they are real.

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
