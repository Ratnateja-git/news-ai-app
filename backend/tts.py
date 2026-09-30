"""Kokoro local text-to-speech integration for Priya."""

import os
import re
import time
from io import BytesIO
from pathlib import Path
from threading import Lock

try:
    import soundfile as sf
    from kokoro_onnx import Kokoro
    _TTS_IMPORT_ERROR = None
except ImportError as error:  # Render can run without local voice support.
    sf = None
    Kokoro = None
    _TTS_IMPORT_ERROR = error

from .identity import CREATOR_NAME, CREATOR_SPEECH_NAME


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

# Local development keeps using the repository root. A deployment can mount
# private model files elsewhere without copying them into source control.
KOKORO_DIR = Path(os.getenv("PRIYA_KOKORO_DIR", str(BASE_DIR))).expanduser()
MODEL_PATH = KOKORO_DIR / "kokoro-v1.0.onnx"
VOICES_PATH = KOKORO_DIR / "voices-v1.0.bin"


# ============================================================
# PRIYA VOICE SETTINGS
# ============================================================

# Female Kokoro voices:
# af_heart
# af_bella
# af_sarah
# af_nicole
# af_sky
#
# Start with af_heart.
VOICE_NAME = "af_heart"

# Natural speaking speed.
VOICE_SPEED = 1.0


# ============================================================
# MODEL
# ============================================================

_kokoro = None
_kokoro_lock = Lock()


TTS_UNAVAILABLE_DETAIL = (
    "Voice/TTS is unavailable in this deployment because the Kokoro model is not installed."
)


class TTSUnavailableError(RuntimeError):
    """Raised when this deployment cannot provide local Kokoro speech."""


def _tts_disabled_by_environment() -> bool:
    """Allow deployments to opt out without changing local defaults."""
    return os.getenv("PRIYA_TTS_ENABLED", "").strip().lower() in {
        "0", "false", "no", "off",
    }


def tts_is_available() -> bool:
    """Return whether Kokoro can be loaded without attempting initialization."""
    return (
        not _tts_disabled_by_environment()
        and Kokoro is not None
        and sf is not None
        and MODEL_PATH.is_file()
        and VOICES_PATH.is_file()
    )


def _ensure_tts_available() -> None:
    if _tts_disabled_by_environment():
        raise TTSUnavailableError("Kokoro TTS is disabled by PRIYA_TTS_ENABLED.")
    if Kokoro is None or sf is None:
        raise TTSUnavailableError("Kokoro TTS dependencies are unavailable.") from _TTS_IMPORT_ERROR
    if not MODEL_PATH.is_file() or not VOICES_PATH.is_file():
        raise TTSUnavailableError(TTS_UNAVAILABLE_DETAIL)


def get_kokoro():
    """Load Kokoro once and reuse it.

    Thread-safe double-checked locking: the outer check is lock-free so
    the common case (model already loaded) never pays lock overhead per
    request. Only the very first call(s) — which may race across
    FastAPI's threadpool for a sync route — take the lock, and the inner
    check under the lock ensures the ONNX model and voices are
    constructed exactly once no matter how many requests arrive
    concurrently during that cold start.
    """

    global _kokoro

    _ensure_tts_available()

    if _kokoro is not None:
        print("[PERF][TTS] model already loaded")
        return _kokoro

    with _kokoro_lock:

        if _kokoro is None:
            load_started = time.perf_counter()

            print("Loading Kokoro TTS model...")
            try:
                _kokoro = Kokoro(
                    str(MODEL_PATH),
                    str(VOICES_PATH),
                )
            except (OSError, RuntimeError, ValueError) as error:
                raise TTSUnavailableError("Kokoro TTS could not be initialized.") from error

            print("Kokoro TTS model loaded.")
            print(f"[PERF][TTS] model load: {time.perf_counter() - load_started:.3f}s")
        else:
            print("[PERF][TTS] model already loaded")

    return _kokoro


# ============================================================
# SANITIZE TEXT FOR SPEECH
# ============================================================

def sanitize_for_speech(text: str) -> str:
    """Strip punctuation this Kokoro build vocalizes literally.

    On this installation, Kokoro's phonemizer reads a comma out loud as
    the word "comma" instead of treating it as a pause. Rather than rely
    on the model to handle it, drop commas (and a couple of other
    punctuation marks with the same risk) before synthesis, since the
    natural pause is already carried by surrounding periods.
    """

    # Keep the written UI/API identity exact while giving Kokoro a reliable
    # phonetic form only in the audio-generation path.
    text = re.sub(rf"\b{re.escape(CREATOR_NAME)}\b", CREATOR_SPEECH_NAME, text)

    # Replace comma with a space so words don't run together, but never
    # speak the character itself.
    text = text.replace(",", " ")

    # Semicolons and em/en dashes carry the same literal-readout risk.
    text = text.replace(";", ".")
    text = text.replace("—", " ")
    text = text.replace("–", " ")

    # Collapse any double spaces created above.
    text = re.sub(r"[ \t]{2,}", " ", text)

    return text.strip()


# ============================================================
# GENERATE AUDIO
# ============================================================

def generate_speech(text: str, chunk_number: int | None = None) -> bytes:
    """
    Convert text into WAV audio using Kokoro.

    Returns:
        WAV audio as bytes.
    """

    total_started = time.perf_counter()
    text = text.strip()
    chunk_label = str(chunk_number) if chunk_number is not None else "unknown"
    print(
        f"[PERF][TTS] chunk={chunk_label} chars={len(text)} "
        f"words={len(text.split())}"
    )

    if not text:
        raise ValueError(
            "Text cannot be empty."
        )

    # Prevent unnecessarily huge TTS requests.
    if len(text) > 2000:
        text = text[:2000]

    text = sanitize_for_speech(text)

    if not text:
        raise ValueError(
            "Text cannot be empty."
        )
    print(
        f"[PERF][TTS] chunk={chunk_label} normalized_chars={len(text)} "
        f"normalized_words={len(text.split())}"
    )

    kokoro = get_kokoro()

    # Lock generation because the same local model instance
    # should not be used concurrently in an unsafe way.
    queue_started = time.perf_counter()
    with _kokoro_lock:
        queue_wait = time.perf_counter() - queue_started
        inference_started = time.perf_counter()
        samples, sample_rate = kokoro.create(
            text,
            voice=VOICE_NAME,
            speed=VOICE_SPEED,
            lang="en-us",
        )
    inference_seconds = time.perf_counter() - inference_started
    audio_duration = len(samples) / sample_rate if sample_rate else 0.0
    print(f"[PERF][TTS] chunk={chunk_label} queue_wait: {queue_wait:.3f}s")
    print(f"[PERF][TTS] chunk={chunk_label} inference: {inference_seconds:.3f}s")
    print(f"[PERF][TTS] chunk={chunk_label} samples={len(samples)} audio_duration={audio_duration:.3f}s")
    print(f"[PERF][TTS] generation: {inference_seconds:.3f}s")

    audio_buffer = BytesIO()

    sf.write(
        audio_buffer,
        samples,
        sample_rate,
        format="WAV",
    )

    audio_buffer.seek(0)

    audio = audio_buffer.read()
    print(f"[PERF][TTS] total: {time.perf_counter() - total_started:.3f}s")
    return audio


# ============================================================
# TEST MODEL
# ============================================================

def test_kokoro() -> bool:
    """Check that Kokoro can generate speech."""

    audio = generate_speech(
        "Hello, I'm Priya. How can I help you?"
    )

    return bool(audio)
