"""Offline speech recognition using a locally installed Vosk model."""

from __future__ import annotations

import importlib
import io
import json
import os
import wave
from pathlib import Path
from typing import Any, Dict


_PROJECT_ROOT = Path(__file__).resolve().parent
_DEFAULT_MODEL_PATH = _PROJECT_ROOT / "models" / "vosk-model-small-en-us-0.15"
_MODEL_PATH_ENV = "JARVIS_VOSK_MODEL_PATH"
_loaded_models: Dict[Path, Any] = {}


class LocalTranscriptionError(Exception):
	"""A safe, user-facing local transcription error."""


def _model_path() -> Path:
	configured_path = os.getenv(_MODEL_PATH_ENV, "").strip()
	path = Path(configured_path).expanduser() if configured_path else _DEFAULT_MODEL_PATH
	if not path.is_absolute():
		path = _PROJECT_ROOT / path
	return path


def transcribe_wav(audio_data: bytes) -> str:
	"""Transcribe a mono, 16 kHz WAV entirely on this machine."""
	if not audio_data:
		raise LocalTranscriptionError("Local speech recognition received no audio.")

	try:
		vosk = importlib.import_module("vosk")
	except ImportError:
		raise LocalTranscriptionError(
			"Local speech recognition is not installed. Run `python -m pip install -r requirements.txt`, "
			"then follow the local model setup instructions in README.md."
		) from None

	model_path = _model_path()
	if not model_path.is_dir():
		raise LocalTranscriptionError(
			"The local speech model is missing. Download vosk-model-small-en-us-0.15 to "
			"models/vosk-model-small-en-us-0.15, or set JARVIS_VOSK_MODEL_PATH. "
			"See the local model setup instructions in README.md."
		)

	try:
		model = _loaded_models.get(model_path)
		if model is None:
			model = vosk.Model(str(model_path))
			_loaded_models[model_path] = model
		with wave.open(io.BytesIO(audio_data), "rb") as wav_file:
			if (
				wav_file.getnchannels() != 1
				or wav_file.getsampwidth() != 2
				or wav_file.getframerate() != 16000
			):
				raise LocalTranscriptionError(
					"Local speech recognition requires 16 kHz mono 16-bit WAV audio."
				)
			recognizer = vosk.KaldiRecognizer(model, wav_file.getframerate())
			while True:
				frames = wav_file.readframes(4000)
				if not frames:
					break
				recognizer.AcceptWaveform(frames)
		result = json.loads(recognizer.FinalResult())
	except LocalTranscriptionError:
		raise
	except Exception:
		raise LocalTranscriptionError(
			"Local speech recognition could not process the recording or load its model. "
			"Check the local model setup and try again."
		) from None

	transcript = result.get("text") if isinstance(result, dict) else None
	if not isinstance(transcript, str) or not transcript.strip():
		raise LocalTranscriptionError(
			"Local speech recognition did not detect speech. Please try again."
		)
	return transcript.strip()