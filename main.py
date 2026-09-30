"""Phase 1: minimal, safe terminal interface for JARVIS."""

import logging

from config import Config, configure_logging


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
		if command.casefold() in {"exit", "quit", "bye"}:
			print(f"{config.name}: Goodbye.")
			return
		if command.casefold() == "help":
			print(f"{config.name}: Available commands: help, exit.")
			continue

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
