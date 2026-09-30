"""Terminal interface for JARVIS."""

import argparse
import logging
from typing import Optional

from config import Config, configure_logging
from brain import BrainError, JarvisBrain
from voice import VoiceError, listen_and_transcribe, speak_text


def _select_mode(config: Config) -> Optional[bool]:
	while True:
		print("\n================================")
		print(config.name)
		print("\n1. Text mode\n2. Voice mode\n3. Exit")
		try:
			selection = input("Select mode: ").strip().casefold()
		except (EOFError, KeyboardInterrupt):
			print(f"\n{config.name}: Goodbye.")
			return None

		if selection == "1":
			print(f"{config.name}: Text mode active.")
			return False
		if selection == "2":
			print(f"{config.name}: Voice mode active.")
			return True
		if selection in {"3", "exit", "quit"}:
			print(f"{config.name}: Goodbye.")
			return None
		print(f"{config.name}: Choose 1, 2, or 3.")


def run(config: Config) -> None:
	voice_mode = _select_mode(config)
	if voice_mode is None:
		return
	brain = JarvisBrain(api_key=config.openai_api_key, model=config.openai_model)
	while True:
		if voice_mode:
			print(f"{config.name}: Listening for up to 6 seconds...")
			try:
				command = listen_and_transcribe(
					api_key=config.openai_api_key,
					model=config.openai_transcription_model,
				)
			except KeyboardInterrupt:
				print(f"\n{config.name}: Goodbye.")
				return
			except VoiceError as error:
				logging.getLogger(__name__).warning("Voice input could not be completed")
				print(f"{config.name}: {error}")
				print(f"{config.name}: Switching to text mode. Type 'voice' to retry.")
				voice_mode = False
				continue
			if command:
				print(f"You (voice): {command}")
		else:
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
			print(
				f"{config.name}: Available commands: ask a question, voice, text, help, exit."
			)
			continue
		if command.casefold() == "voice":
			voice_mode = True
			print(f"{config.name}: Voice mode active. Say 'text' to switch back.")
			continue
		if command.casefold() == "text":
			voice_mode = False
			print(f"{config.name}: Text mode on.")
			continue

		try:
			answer = brain.ask(command)
		except BrainError as error:
			logging.getLogger(__name__).warning("AI request could not be completed")
			print(f"{config.name}: {error}")
			continue
		print(f"{config.name}: {answer}")
		if voice_mode:
			try:
				speak_text(answer)
			except KeyboardInterrupt:
				print(f"\n{config.name}: Goodbye.")
				return
			except VoiceError as error:
				logging.getLogger(__name__).warning("Voice output could not be completed")
				print(f"{config.name}: {error}")
				print(f"{config.name}: Switching to text mode. Type 'voice' to retry.")
				voice_mode = False


def main() -> int:
	parser = argparse.ArgumentParser(description="Run the JARVIS terminal assistant.")
	parser.add_argument(
		"--check-config",
		action="store_true",
		help="report whether OPENAI_API_KEY is configured without displaying it",
	)
	arguments = parser.parse_args()
	config = Config.from_environment()
	if arguments.check_config:
		status = "YES" if config.openai_api_key else "NO"
		print(f"OPENAI_API_KEY detected: {status}")
		return 0

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
