"""Configuration and logging setup for the Phase 1 JARVIS application."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass


_VALID_LOG_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}


@dataclass(frozen=True)
class Config:
	"""Basic runtime settings, overridable through environment variables."""

	name: str = "JARVIS"
	log_level: str = "INFO"

	@classmethod
	def from_environment(cls) -> Config:
		name = os.getenv("JARVIS_NAME", "JARVIS").strip() or "JARVIS"
		log_level = os.getenv("JARVIS_LOG_LEVEL", "INFO").strip().upper()
		if log_level not in _VALID_LOG_LEVELS:
			log_level = "INFO"
		return cls(name=name, log_level=log_level)


def configure_logging(level_name: str) -> None:
	"""Configure concise terminal logging."""
	level = getattr(logging, level_name, logging.INFO)
	logging.basicConfig(level=level, format="%(levelname)s: %(message)s")