"""Modal deployment entry point for the existing Priya FastAPI application."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import modal


APP_NAME = "priya-ai"
GPU_TYPE = os.getenv("PRIYA_MODAL_GPU", "L4")
DEFAULT_OLLAMA_MODEL = "gemma3:4b"
OLLAMA_MODELS_DIR = "/models/llm"
KOKORO_DIR = "/models/kokoro"
CAREER_DB_DIR = "/data/career"

app = modal.App(APP_NAME)
model_volume = modal.Volume.from_name("priya-ai-models", create_if_missing=True)
career_volume = modal.Volume.from_name("priya-ai-career-data", create_if_missing=True)

# Ollama remains local to the Modal container, preserving the existing HTTP
# interface used by backend.llm and backend.vision.
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("curl", "zstd")
    .run_commands("curl -fsSL https://ollama.com/install.sh | sh")
    .pip_install_from_requirements("backend/requirements.txt")
    .add_local_dir("backend", remote_path="/root/backend")
    .add_local_dir("frontend", remote_path="/root/frontend")
)


def _wait_for_ollama(process: subprocess.Popen[bytes], timeout_seconds: int = 120) -> None:
    """Wait for the colocated Ollama server before importing FastAPI."""
    import requests

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Ollama exited while starting; inspect the Modal container logs.")
        try:
            response = requests.get("http://127.0.0.1:11434/api/tags", timeout=2)
            if response.ok:
                return
        except requests.RequestException:
            pass
        time.sleep(1)
    raise RuntimeError("Ollama did not become ready within two minutes.")


@app.cls(
    image=image,
    gpu=GPU_TYPE,
    timeout=20 * 60,
    max_containers=1,
    scaledown_window=60,
    volumes={"/models": model_volume, "/data/career": career_volume},
    secrets=[modal.Secret.from_name("priya-ai-secrets")],
    env={
        "OLLAMA_BASE_URL": "http://127.0.0.1:11434",
        "OLLAMA_MODELS": OLLAMA_MODELS_DIR,
        "PRIYA_KOKORO_DIR": KOKORO_DIR,
        "PRIYA_CAREER_DB": f"{CAREER_DB_DIR}/priya_career.db",
        "PRIYA_TTS_ENABLED": "true",
    },
)
class PriyaModalService:
    """One reusable GPU container running both FastAPI and its Ollama sidecar."""

    @modal.enter()
    def start_models(self) -> None:
        kokoro_model = Path(KOKORO_DIR) / "kokoro-v1.0.onnx"
        kokoro_voices = Path(KOKORO_DIR) / "voices-v1.0.bin"
        if not kokoro_model.is_file() or not kokoro_voices.is_file():
            raise RuntimeError(
                "Kokoro model files are missing from the priya-ai-models Volume. "
                "Upload kokoro-v1.0.onnx and voices-v1.0.bin before deploying."
            )

        environment = os.environ.copy()
        environment["OLLAMA_MODELS"] = OLLAMA_MODELS_DIR
        # A value in the Modal Secret can override the existing default without
        # putting model configuration or credentials in source control.
        self.ollama_model = environment.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
        self.ollama_process = subprocess.Popen(
            ["ollama", "serve"], env=environment, stdout=None, stderr=None
        )
        _wait_for_ollama(self.ollama_process)
        result = subprocess.run(
            ["ollama", "pull", self.ollama_model],
            env=environment,
            check=False,
            timeout=15 * 60,
        )
        if result.returncode:
            raise RuntimeError(f"Ollama could not pull required model {self.ollama_model!r}.")
        model_volume.commit()

    @modal.exit()
    def stop_models(self) -> None:
        process = getattr(self, "ollama_process", None)
        if process and process.poll() is None:
            process.terminate()

    @modal.asgi_app()
    def fastapi_app(self):
        from backend.main import app as existing_fastapi_app

        return existing_fastapi_app
