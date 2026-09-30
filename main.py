"""Phase 1: minimal, safe terminal interface for JARVIS."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
	"""Basic runtime configuration, overridable through environment variables."""

	name: str = "JARVIS"
	log_level: str = "INFO"

	@classmethod
	def from_environment(cls) -> Config:
		return cls(
			name=os.getenv("JARVIS_NAME", "JARVIS").strip() or "JARVIS",
			log_level=os.getenv("JARVIS_LOG_LEVEL", "INFO").upper(),
		)


def configure_logging(level_name: str) -> None:
	level = getattr(logging, level_name, logging.INFO)
	logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


def run(config: Config) -> None:
	print(f"{config.name}: Online. Type 'help' for commands or 'exit' to quit.")
	while True:
		try:
			command = input("You: ").strip()
		except (EOFError, KeyboardInterrupt):
			print(f"\n{config.name}: Goodbye.")
			return

		if not command:
			continue
		match command.casefold():
			case "exit" | "quit" | "bye":
				print(f"{config.name}: Goodbye.")
				return
			case "help":
				print(f"{config.name}: Available commands: help, exit.")
			case _:
				logging.getLogger(__name__).info("Received unimplemented command")
				print(f"{config.name}: That command is not available yet. Type 'help' for options.")


def main() -> int:
	config = Config.from_environment()
	configure_logging(config.log_level)
	try:
		run(config)
	except Exception:
		logging.getLogger(__name__).exception("JARVIS encountered an unexpected error")
		print(f"{config.name}: An unexpected error occurred. See the terminal log for details.")
		return 1
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
