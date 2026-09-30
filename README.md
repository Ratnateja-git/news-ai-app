Priya AI

Local, voice-first AI assistant for news, resume analysis, job matching, and mock interview coaching.






Priya AI is a local-first AI assistant built with FastAPI, JavaScript, Ollama/Gemma, and Kokoro TTS. It combines a conversational news assistant with a practical Career Coach that can analyze resumes, compare them with job descriptions, detect contradictory requirements, identify skill gaps, and conduct a resume-aware mock interview.

The project is designed so the main AI workload can run on the user's own machine instead of requiring a paid cloud GPU.

✨ Features

📰 News Assistant

Fetches and formats current headlines from configured RSS/news sources.

Supports topic and category-based requests.

Provides concise, spoken-style responses for normal news queries.

Uses local Gemma for explicit explanations and follow-ups instead of unnecessarily sending every headline through an LLM.

Supports text and voice interaction.

💬 Conversational AI

Natural-language chat through the Priya UI.

Identity-aware responses for questions such as "Who are you?" and "What can you do?".

Existing news, chat, voice, and image workflows remain available from the main conversation interface.

Active interview context can be passed into normal Priya chat for question explanations without changing interview state.

📄 Resume Analyzer

Upload a PDF resume and extract/analyze:

Profile information

Skills

Education

Experience

Internships

Projects

Resume quality signals

Priya Resume Score

Project extraction is section-aware so descriptive bullets are not blindly counted as separate projects.

Note: Priya Resume Score is a heuristic project metric, not an official ATS score or hiring decision.

🎯 Job Description Matching

Paste a target job description to generate:

Parsed job requirements

Resume-to-JD match signals

Matching strengths

Skill gaps

Role-relevant suggestions

Non-fabricating resume tailoring guidance

Priya does not invent experience, employers, projects, certifications, or metrics.

🚨 Contradiction-Aware JD Analysis

Priya checks whether a job description contains internally conflicting requirements before blindly optimizing a resume against it.

Example:

Entry-level AI/ML Engineer

Requirements:
- 5+ years of production AI experience
- Senior AI architect experience
- Strong Python and ML skills
- Bachelor's degree in Computer Science

Instead of silently choosing one interpretation, the system can flag the seniority conflict and preserve that context for matching and interviewing.

JD Analyzer
    ↓
Contradiction Detector
    ↓
Resume Matcher
    ↓
Recommendation Agent
    ↓
Interview Coach

🎤 Mock Interview Coach

Resume-aware interview sessions

Multiple interview types and difficulty levels

Project, technical, architecture, fundamentals, behavioral, testing, impact, and problem-solving topics

Adaptive follow-ups

Typed answers

Final scorecard/report

Kokoro voice playback for interview questions

Replay, Next Question, and Stop controls

Session-wide question history

Similarity-based duplicate-question filtering

💡 Interview Help Mode

The user can ask Priya for help from the normal chat while an interview question is active.

Examples:

Explain this question
What does this question mean?
Give me a hint
What should I talk about?
Can you explain what the interviewer is asking?

The help request explains the active question without submitting an answer, advancing the interview, or changing the score.

🖼️ Image Understanding

Optional local image analysis through Ollama/Gemma.

Supported formats:

JPG / JPEG

PNG

WEBP

Default maximum upload size: 10 MB.

🛠️ Tech Stack

Layer

Technology

Backend

Python, FastAPI

Frontend

HTML, CSS, JavaScript

Local LLM

Ollama + Gemma 3 4B

TTS

Kokoro ONNX

Resume parsing

Python PDF tooling

Career storage

SQLite / local storage

News

RSS + configured news/search providers

Deployment for demos

Local host + optional Cloudflare Quick Tunnel

🏗️ Architecture

                    ┌──────────────────────┐
                    │      Priya UI        │
                    │ Text • Voice • Image │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │    FastAPI Backend   │
                    ├──────────────────────┤
                    │ Intent / Routing     │
                    │ News                  │
                    │ Normal Chat          │
                    │ Resume Analyzer      │
                    │ JD Analyzer          │
                    │ JD Contradictions    │
                    │ Job Matcher          │
                    │ Resume Tailoring     │
                    │ Mock Interview       │
                    │ Interview Help       │
                    │ Image Analysis       │
                    └───────┬────────┬─────┘
                            │        │
                  ┌─────────▼──┐  ┌──▼──────────┐
                  │ Ollama /   │  │ Kokoro ONNX │
                  │ Gemma 3 4B │  │     TTS     │
                  └────────────┘  └─────────────┘

Career Coach flow

Resume PDF + Job Description
             ↓
        JD Analyzer
             ↓
   Contradiction Detector
             ↓
       Resume Matcher
             ↓
   Skill Gap / Suggestions
             ↓
       Interview Coach
             ↓
       Final Report

📁 Project Structure

news-ai-app/
├── backend/
│   ├── career/
│   │   ├── core.py
│   │   └── router.py
│   ├── main.py
│   ├── intent.py
│   ├── llm.py
│   ├── tts.py
│   ├── test_core.py
│   └── requirements.txt
│
├── frontend/
│   ├── index.html
│   ├── styles.css
│   ├── voice.js
│   └── career.js
│
├── data/
│   └── priya_career.db
│
├── .env.example
├── .gitignore
├── LICENSE
├── package.json
├── requirements.txt
├── check_priya.ps1
├── start_priya.ps1
├── start_priya_tunnel.ps1
└── README.md

🚀 Quick Start

1. Clone

git clone https://github.com/Ratnateja-git/news-ai-app.git
cd news-ai-app

2. Create a virtual environment

python -m venv .venv
.\.venv\Scripts\Activate.ps1

3. Install dependencies

python -m pip install -r backend\requirements.txt

4. Install and start Ollama

Install Ollama, start it locally, and pull the configured model:

ollama pull gemma3:4b
ollama list

Default Ollama endpoint:

http://127.0.0.1:11434

5. Configure environment

Copy-Item .env.example .env

Typical local settings:

OLLAMA_BASE_URL=http://127.0.0.1:11434
VISION_ENABLED=true
VISION_MODEL_NAME=gemma3:4b
MAX_IMAGE_SIZE_MB=10

Add external API keys only when required by your configuration. Never commit real secrets.

6. Start Priya AI

uvicorn backend.main:app --reload

Open:

http://127.0.0.1:8000/app/

Or use the included Windows startup script:

.\start_priya.ps1

🔊 Kokoro TTS

Kokoro provides local speech generation and interview-question playback.

The configured model directory should contain the required Kokoro assets, including files such as:

kokoro-v1.0.onnx
voices-v1.0.bin

The TTS layer is optional from an application-flow perspective: when Kokoro is unavailable, text-based features can continue to run.

🌐 Optional Public Demo

For a temporary public demo while Priya is running locally, use Cloudflare Quick Tunnel:

& "$env:USERPROFILE\Downloads\cloudflared-windows-amd64.exe" tunnel --protocol http2 --url http://127.0.0.1:8000

Cloudflare will provide a temporary trycloudflare.com URL.

This is a development/demo tunnel. The application, LLM, and TTS still run on the local machine.

🧩 Career Coach API

Endpoint

Purpose

POST /career/resume/upload

Upload and parse a PDF resume

POST /career/resume/analyze

Analyze the resume and generate score/signals

POST /career/job/parse

Parse a target job description

POST /career/job/match

Compare resume and JD

POST /career/jd/analyze

Analyze JD requirements and contradictions

POST /career/resume/tailor

Generate non-fabricating tailoring guidance

POST /career/interview/start

Start a mock interview

POST /career/interview/answer

Submit an interview answer

GET /career/interview/report/{id}

Retrieve the interview report

The FastAPI backend contains the request and response schemas for each route.

🧪 Testing

Run the Career Coach unit tests:

python -m unittest backend.test_core -v

Before a Git commit, useful checks are:

git --no-pager diff --check
git status
git --no-pager diff

🔐 Design Principles

Local-first

The main AI experience is designed around local Ollama/Gemma inference and local Kokoro TTS.

No fabricated resume data

Priya should never create fake experience, employers, projects, certifications, years of experience, or performance metrics.

Explainable scoring

Resume and job-match scores are project heuristics intended to expose strengths and gaps. They are not official ATS scores, hiring decisions, or guarantees.

Contradiction-aware matching

The system checks whether the JD is internally consistent before treating its requirements as a clean optimization target.

Interview continuity

Question history and similarity checks are used to reduce duplicate or rephrased interview questions within a session.

🎬 Recommended Demo

A complete portfolio demo can follow this path:

1. Ask Priya for current news
2. Ask a follow-up explanation
3. Upload a resume
4. Run Resume Analysis
5. Paste a target JD
6. Run JD Analysis
7. Show contradiction detection when applicable
8. Review Job Match + skill gaps
9. Start Mock Interview
10. Hear the question through Kokoro
11. Ask Priya for a hint in normal chat
12. Submit the answer
13. Continue through unique questions
14. Open the final interview report

A useful project showcase line:

Priya AI doesn't just match a resume to a job description — it checks whether the job description itself is internally consistent before using it as a matching target.

🔮 Future Improvements

More robust resume section extraction

Better job-description normalization

Broader interview-question diversity

Richer interview analytics

More language and voice options

Additional local model backends

Stronger end-to-end UI regression testing

Easier self-hosted deployment packaging

🔒 Security Notes

Keep API keys in .env or a secret manager.

Never commit private resumes, candidate documents, or credentials.

Do not expose a development server publicly without understanding the security implications.

A Cloudflare Quick Tunnel is temporary public access, not a hardened production deployment.

📄 License

This project is released under the license included in the repository.

👨‍💻 Author

Ratna Tej

GitHub: https://github.com/Ratnateja-git

Project: https://github.com/Ratnateja-git/news-ai-app