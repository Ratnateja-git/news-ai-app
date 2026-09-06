"""Local, in-memory image understanding for Priya.

Images are validated before they reach Ollama and are never written to disk.
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
from dataclasses import dataclass

import requests
from dotenv import load_dotenv
from PIL import Image, UnidentifiedImageError

load_dotenv()

SUPPORTED_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
VISION_SYSTEM_MESSAGE = (
    "You are Priya, a helpful visual assistant. Analyze the supplied image carefully. "
    "Describe only what can reasonably be determined visually. Do not invent brands, "
    "models, identities, locations, or unreadable text. State uncertainty plainly. "
    "Answer directly in concise, natural spoken language. Do not mention prompts, "
    "system messages, internal reasoning, or model details."
)


class VisionError(RuntimeError):
    """Safe error message intended for the API client."""


@dataclass(frozen=True)
class ValidatedImage:
    data: bytes
    media_type: str


def _setting(name: str, default: str) -> str:
    return os.getenv(name, default).strip() or default


def _max_image_bytes() -> int:
    try:
        megabytes = float(_setting("MAX_IMAGE_SIZE_MB", "10"))
    except ValueError:
        megabytes = 10
    return max(1, megabytes) * 1024 * 1024


def validate_image(image_bytes: bytes) -> ValidatedImage:
    """Validate real image content rather than trusting names or MIME headers."""
    if not image_bytes:
        raise VisionError("Please choose an image to upload.")
    if len(image_bytes) > _max_image_bytes():
        raise VisionError(f"Image is too large. Maximum size is {_setting('MAX_IMAGE_SIZE_MB', '10')} MB.")

    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            image.verify()
        with Image.open(io.BytesIO(image_bytes)) as image:
            image.load()
            image_format = image.format
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise VisionError("The uploaded file is not a valid image.") from error

    media_type = SUPPORTED_FORMATS.get(str(image_format).upper())
    if not media_type:
        raise VisionError("Please upload a JPG, PNG, or WEBP image.")
    return ValidatedImage(data=image_bytes, media_type=media_type)


def _vision_enabled() -> bool:
    return _setting("VISION_ENABLED", "true").lower() in {"1", "true", "yes", "on"}


def _strip_json_fence(raw: str) -> str:
    """Remove a Markdown JSON fence without altering normal answer text."""
    fenced = re.fullmatch(r"\s*```(?:json)?\s*\n?([\s\S]*?)\n?```\s*", raw, re.IGNORECASE)
    return fenced.group(1).strip() if fenced else raw.strip()


def _field_from_json_like_text(raw: str, field: str) -> str:
    """Best-effort field extraction for nearly-JSON local model replies."""
    pattern = rf'["\']?{re.escape(field)}["\']?\s*:\s*"((?:\\.|[^"\\])*)"'
    match = re.search(pattern, raw, re.IGNORECASE)
    if match:
        try:
            return json.loads(f'"{match.group(1)}"').strip()
        except (TypeError, ValueError):
            return match.group(1).replace(r'\"', '"').strip()

    # This only handles a model reply such as
    # {"answer": A visible red car, ...}; valid JSON uses the branch above.
    unquoted = re.search(
        rf'["\']?{re.escape(field)}["\']?\s*:\s*([^,\n}}]+)',
        raw,
        re.IGNORECASE,
    )
    return unquoted.group(1).strip(" \t\"'") if unquoted else ""


def _clean_text_fallback(raw: str) -> str:
    """Avoid ever returning JSON labels or code fences as a spoken answer."""
    cleaned = _strip_json_fence(raw)
    answer = _field_from_json_like_text(cleaned, "answer")
    if answer:
        return answer
    description = _field_from_json_like_text(cleaned, "description")
    if description:
        return description
    cleaned = re.sub(r"^\s*priya\s*:\s*", "", cleaned, flags=re.IGNORECASE)
    # A malformed object with no readable answer/description should not leak
    # implementation labels to the user.
    if re.match(r"^\s*[{[]", cleaned):
        return ""
    return cleaned.strip()


def _parse_answer(raw: str) -> tuple[str, str, list[str]]:
    """Return only natural-language fields from bare or fenced model JSON."""
    raw = _strip_json_fence(raw)
    try:
        payload = json.loads(raw)
        if isinstance(payload, dict):
            description = str(payload.get("description") or payload.get("answer") or "").strip()
            answer = str(payload.get("answer") or description).strip()
            objects = payload.get("objects") if isinstance(payload.get("objects"), list) else []
            return description, answer, [str(item).strip() for item in objects if str(item).strip()][:8]
    except (TypeError, ValueError):
        pass
    cleaned = _clean_text_fallback(raw)
    return cleaned, cleaned, []


def analyze_image(image_bytes: bytes, question: str | None = None) -> dict:
    """Ask the configured local Ollama vision model about a validated image."""
    image = validate_image(image_bytes)
    if not _vision_enabled():
        raise VisionError("Image understanding is currently disabled.")

    model_name = _setting("VISION_MODEL_NAME", "gemma3:4b")
    ollama_base_url = _setting("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    question = (question or "").strip()
    prompt = (
        "Describe this image." if not question else f"Question about this image: {question}"
    ) + (
        " Return JSON only with keys description, answer, and objects. "
        "Use a short list of visible object names for objects."
    )
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": VISION_SYSTEM_MESSAGE},
            {"role": "user", "content": prompt, "images": [base64.b64encode(image.data).decode("ascii")]},
        ],
        "stream": False,
        "options": {"temperature": 0.15, "top_p": 0.8, "num_predict": 280},
    }
    try:
        response = requests.post(f"{ollama_base_url}/api/chat", json=payload, timeout=120)
    except requests.RequestException as error:
        raise VisionError("Priya's local vision service is unavailable. Please make sure Ollama is running.") from error

    if response.status_code >= 400:
        raise VisionError("The configured vision model is unavailable or does not support images.")
    try:
        raw = response.json().get("message", {}).get("content", "")
    except ValueError as error:
        raise VisionError("Priya could not analyze that image right now.") from error
    description, answer, objects = _parse_answer(raw)
    if not answer:
        raise VisionError("Priya could not determine enough from that image.")
    return {"success": True, "description": description, "answer": answer, "objects": objects}
