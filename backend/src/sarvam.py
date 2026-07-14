"""Sarvam AI speech-to-text and text-to-speech client."""
import base64
import os

from sarvamai import AsyncSarvamAI
from sarvamai.core.api_error import ApiError

_API_KEY = os.getenv("SARVAM_AI")
_DEFAULT_LANGUAGE = "en-IN"
_DEFAULT_SPEAKER = "priya"
_MAX_TTS_CHARS = 2500  # bulbul:v3 request limit

_client = AsyncSarvamAI(api_subscription_key=_API_KEY) if _API_KEY else None


class SarvamError(RuntimeError):
    """Raised when a Sarvam AI API call fails."""


async def transcribe(audio_bytes: bytes, filename: str) -> str:
    if _client is None:
        raise SarvamError("SARVAM_AI API key is not configured.")
    try:
        response = await _client.speech_to_text.transcribe(
            file=(filename, audio_bytes, "audio/webm"),
            model="saaras:v3",
        )
    except ApiError as e:
        raise SarvamError(f"Sarvam STT failed ({e.status_code}): {e.body}") from e
    return response.transcript or ""


async def synthesize(text: str, language_code: str = _DEFAULT_LANGUAGE, speaker: str = _DEFAULT_SPEAKER) -> bytes:
    if _client is None:
        raise SarvamError("SARVAM_AI API key is not configured.")
    try:
        response = await _client.text_to_speech.convert(
            text=text[:_MAX_TTS_CHARS],
            target_language_code=language_code,
            model="bulbul:v3",
            speaker=speaker,
        )
    except ApiError as e:
        raise SarvamError(f"Sarvam TTS failed ({e.status_code}): {e.body}") from e
    if not response.audios:
        raise SarvamError("Sarvam TTS returned no audio.")
    return base64.b64decode(response.audios[0])
