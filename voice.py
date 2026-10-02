"""Microphone capture, OpenAI transcription, and macOS speech output."""

from __future__ import annotations

import io
import importlib
import json
import logging
import platform
import subprocess
import uuid
import wave
from typing import Dict, Optional, Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config import is_valid_openai_api_key


_TRANSCRIPTION_API_URL = "https://api.openai.com/v1/audio/transcriptions"
_DEFAULT_TRANSCRIPTION_MODEL = "gpt-transcribe"
_RECORDING_SAMPLE_RATE = 16000
_REQUEST_TIMEOUT_SECONDS = 60


class _AudioRecording(Protocol):
	def tobytes(self) -> bytes: ...


class _SoundDevice(Protocol):
	def rec(
		self,
		frames: int,
		*,
		samplerate: int,
		channels: int,
		dtype: str,
	) -> _AudioRecording: ...

	def wait(self) -> None: ...


class VoiceError(Exception):
	"""A safe, user-facing error from a voice operation."""


def listen_for_audio(duration_seconds: int = 6) -> bytes:
	"""Record a short mono WAV clip from the default microphone."""
	if not 1 <= duration_seconds <= 30:
		raise ValueError("Recording duration must be between 1 and 30 seconds.")

	try:
		sounddevice = cast(_SoundDevice, importlib.import_module("sounddevice"))
	except (ImportError, OSError):
		raise VoiceError(
			"Microphone support couldn't be loaded. Reinstall packages from requirements.txt."
		) from None

	try:
		recording = sounddevice.rec(
			duration_seconds * _RECORDING_SAMPLE_RATE,
			samplerate=_RECORDING_SAMPLE_RATE,
			channels=1,
			dtype="int16",
		)
		sounddevice.wait()
	except Exception as error:
		logging.getLogger(__name__).warning(
			"Microphone capture failed (%s)", type(error).__name__
		)
		raise VoiceError(
			"Please allow microphone access for the application running JARVIS in "
			"System Settings > Privacy & Security > Microphone, then choose Voice mode to retry."
		) from None

	try:
		wav_buffer = io.BytesIO()
		with wave.open(wav_buffer, "wb") as wav_file:
			wav_file.setnchannels(1)
			wav_file.setsampwidth(2)
			wav_file.setframerate(_RECORDING_SAMPLE_RATE)
			wav_file.writeframes(recording.tobytes())
		return wav_buffer.getvalue()
	except (AttributeError, OSError, wave.Error):
		logging.getLogger(__name__).warning("Could not encode microphone audio")
		raise VoiceError("I couldn't prepare the microphone recording. Please try again.") from None


def listen_and_transcribe(
	api_key: Optional[str],
	model: str = _DEFAULT_TRANSCRIPTION_MODEL,
	duration_seconds: int = 6,
) -> str:
	"""Record speech and return its OpenAI transcription."""
	if not (api_key or "").strip():
		raise VoiceError(
			"No valid OpenAI API key is configured. Add a real OpenAI API key to the application configuration."
		)
	if not is_valid_openai_api_key(api_key):
		raise VoiceError(
			"The configured OpenAI API key is invalid. Add a real OpenAI API key to the application configuration."
		)
	audio_data = listen_for_audio(duration_seconds=duration_seconds)
	return transcribe_audio(audio_data, api_key or "", model)


def transcribe_audio(audio_data: bytes, api_key: str, model: str) -> str:
	"""Send a WAV clip to OpenAI and return the recognized words."""
	key = api_key.strip()
	if not key:
		raise VoiceError(
			"No valid OpenAI API key is configured. Add a real OpenAI API key to the application configuration."
		)
	if not is_valid_openai_api_key(key):
		raise VoiceError(
			"The configured OpenAI API key is invalid. Add a real OpenAI API key to the application configuration."
		)
	if not audio_data:
		raise VoiceError("I didn't receive any microphone audio. Please try again.")
	if not model.strip() or "\r" in model or "\n" in model:
		raise VoiceError("The transcription model setting is invalid. Check .env.")

	boundary = "----JARVIS" + uuid.uuid4().hex
	boundary_bytes = boundary.encode("ascii")
	model_field = (
		b"--" + boundary_bytes + b"\r\n"
		b'Content-Disposition: form-data; name="model"\r\n\r\n'
		+ model.encode("utf-8")
		+ b"\r\n"
	)
	file_field = (
		b"--" + boundary_bytes + b"\r\n"
		b'Content-Disposition: form-data; name="file"; filename="speech.wav"\r\n'
		b"Content-Type: audio/wav\r\n\r\n"
		+ audio_data
		+ b"\r\n"
	)
	body = model_field + file_field + b"--" + boundary_bytes + b"--\r\n"
	request = Request(
		_TRANSCRIPTION_API_URL,
		data=body,
		headers={
			"Authorization": f"Bearer {key}",
			"Content-Type": f"multipart/form-data; boundary={boundary}",
		},
		method="POST",
	)

	try:
		with urlopen(request, timeout=_REQUEST_TIMEOUT_SECONDS) as response:
			payload = json.loads(response.read().decode("utf-8"))
	except HTTPError as error:
		status_code = error.code
		error.close()
		logging.getLogger(__name__).warning(
			"OpenAI transcription returned HTTP status %s", status_code
		)
		raise VoiceError(
			f"OpenAI transcription failed with HTTP {status_code}: "
			f"{_transcription_error_message(status_code)}"
		) from None
	except (URLError, TimeoutError, OSError):
		logging.getLogger(__name__).warning("Could not connect to OpenAI transcription")
		raise VoiceError(
			"I couldn't connect to OpenAI for transcription. Check your internet connection and try again."
		) from None
	except (UnicodeDecodeError, json.JSONDecodeError):
		logging.getLogger(__name__).warning("OpenAI returned an unreadable transcription")
		raise VoiceError("OpenAI returned an unreadable transcription. Please try again.") from None

	if not isinstance(payload, dict):
		logging.getLogger(__name__).warning("OpenAI response did not contain a transcript")
		raise VoiceError("I couldn't understand that. Please try again.")
	payload_data = cast(Dict[str, object], payload)
	transcript_value = payload_data.get("text")
	if not isinstance(transcript_value, str):
		logging.getLogger(__name__).warning("OpenAI response did not contain a transcript")
		raise VoiceError("I couldn't understand that. Please try again.")
	transcript = transcript_value.strip()
	if not transcript:
		raise VoiceError("Sorry, I didn't hear anything.")
	return transcript


def speak_text(text: str) -> None:
	"""Speak text through macOS's built-in speech synthesizer."""
	message = text.strip()
	if not message:
		return
	if platform.system() != "Darwin":
		raise VoiceError("Spoken output uses the built-in macOS speech synthesizer.")

	try:
		subprocess.run(
			["say", message],
			check=True,
			timeout=120,
			stdout=subprocess.DEVNULL,
			stderr=subprocess.DEVNULL,
		)
	except FileNotFoundError:
		raise VoiceError("The macOS speech synthesizer is unavailable.") from None
	except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
		logging.getLogger(__name__).warning("macOS speech synthesis failed")
		raise VoiceError("I couldn't speak the response. Check your Mac's audio output.") from None


def _transcription_error_message(status_code: int) -> str:
	if status_code == 401:
		return "OpenAI rejected the API key. Check your API key configuration."
	if status_code == 403:
		return "OpenAI denied access to speech transcription. Check your account access."
	if status_code == 404:
		return "The transcription model was not found. Check your transcription model configuration."
	if status_code == 429:
		return "OpenAI is receiving too many requests or your quota is exhausted. Try again later."
	if status_code >= 500:
		return "OpenAI transcription is temporarily unavailable. Please try again later."
	return f"OpenAI transcription returned an HTTP {status_code} error. Check your configuration."
