"""Configuration and logging setup for the JARVIS application."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


_VALID_LOG_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}


@dataclass(frozen=True)
class Config:
	"""Runtime settings loaded from the project .env and environment."""

	name: str = "JARVIS"
	log_level: str = "INFO"
	openai_api_key: Optional[str] = field(default=None, repr=False)
	openai_model: str = "gpt-4.1-mini"
	openai_transcription_model: str = "gpt-transcribe"

	@classmethod
	def from_environment(cls) -> Config:
		env_path = Path(__file__).resolve().with_name(".env")
		load_dotenv(dotenv_path=env_path)
		name = os.getenv("JARVIS_NAME", "JARVIS").strip() or "JARVIS"
		log_level = os.getenv("JARVIS_LOG_LEVEL", "INFO").strip().upper()
		if log_level not in _VALID_LOG_LEVELS:
			log_level = "INFO"
		api_key = os.getenv("OPENAI_API_KEY", "").strip() or None
		model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip() or "gpt-4.1-mini"
		transcription_model = os.getenv(
			"OPENAI_TRANSCRIPTION_MODEL", "gpt-transcribe"
		).strip() or "gpt-transcribe"
		return cls(
			name=name,
			log_level=log_level,
			openai_api_key=api_key,
			openai_model=model,
			openai_transcription_model=transcription_model,
		)


def configure_logging(level_name: str) -> None:
	"""Configure concise terminal logging."""
	level = getattr(logging, level_name, logging.INFO)
	logging.basicConfig(level=level, format="%(levelname)s: %(message)s")