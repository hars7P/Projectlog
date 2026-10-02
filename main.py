"""Terminal interface for JARVIS."""

import argparse
import logging
import re
from typing import Optional

import memory
from config import Config, configure_logging
from brain import BrainError, JarvisBrain
from memory import MemoryStore, MemoryStoreError, parse_memory_request
from voice import VoiceError, listen_and_transcribe, speak_text


def _safe_exception_message(raw_message: str) -> str:
	message = raw_message.strip() or "(no message)"
	message = re.sub(r"OPENAI_API_KEY", "API key", message, flags=re.IGNORECASE)
	message = re.sub(r"OPENAI_MODEL", "model", message, flags=re.IGNORECASE)
	message = re.sub(r"OPENAI_TRANSCRIPTION_MODEL", "transcription model", message, flags=re.IGNORECASE)
	message = re.sub(r"API key\s*[:=]\s*[^\s\r\n]+", "API key=[REDACTED]", message, flags=re.IGNORECASE)
	message = re.sub(r"Authorization\s*[:=]\s*Bearer\s+[^\s\r\n]+", "Authorization: Bearer [REDACTED]", message, flags=re.IGNORECASE)
	message = re.sub(r"Bearer\s+[A-Za-z0-9._-]+", "Bearer [REDACTED]", message, flags=re.IGNORECASE)
	message = re.sub(r"sk-[A-Za-z0-9]+", "[REDACTED_TOKEN]", message)
	return message


def _safe_diagnostic(component: str, error: BaseException) -> str:
	return (
		f"{component} failed: {type(error).__name__}: "
		f"{_safe_exception_message(str(error))}"
	)


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
	memory_store = MemoryStore()
	brain = JarvisBrain(api_key=config.openai_api_key, model=config.openai_model, memory_store=memory_store)
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
				logging.getLogger(__name__).warning(
					"Voice input failed in listen_and_transcribe: %s: %s",
					type(error).__name__,
					_safe_exception_message(str(error)),
				)
				print(f"{config.name}: {_safe_diagnostic('voice.listen_and_transcribe', error)}")
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
		normalized_command = command.rstrip(" .!?")
		if normalized_command.casefold() in {"exit", "quit", "bye"}:
			print(f"{config.name}: Goodbye.")
			return
		if normalized_command.casefold() == "help":
			print(
				f"{config.name}: Available commands: ask a question, remember, what do you remember, forget, clear my memories, voice, text, help, exit."
			)
			continue
		if normalized_command.casefold() == "voice":
			voice_mode = True
			print(f"{config.name}: Voice mode active. Say 'text' to switch back.")
			continue
		if normalized_command.casefold() == "text":
			voice_mode = False
			print(f"{config.name}: Text mode on.")
			continue
		intent = memory.parse_memory_intent(command)
		if normalized_command.casefold() in {"clear my memories", "clear memories", "clear my memory"}:
			print(f"{config.name}: Clear all saved memories? Type 'yes' to confirm.")
			try:
				confirmation = input("Confirm: ").strip()
			except (EOFError, KeyboardInterrupt):
				print(f"\n{config.name}: Memory clear canceled.")
				continue
			if confirmation.casefold() not in {"yes", "y", "confirm", "clear all memories"}:
				print(f"{config.name}: Memory clear canceled.")
				continue
			deleted = memory_store.clear_memories()
			print(f"{config.name}: Cleared {deleted} saved memory(s).")
			continue
		if intent and intent.get("action") == "save":
			memory_text = str(intent.get("content", "")).strip()
			if not memory_text:
				print(f"{config.name}: I didn't catch anything to remember.")
				continue
			try:
				stored = memory_store.add_memory(memory_text)
			except MemoryStoreError as error:
				print(f"{config.name}: {error}")
				continue
			print(f"{config.name}: Saved memory: {stored}")
			continue
		if intent and intent.get("action") == "retrieve":
			query = str(intent.get("query", "")).strip()
			memories = memory_store.get_relevant_memories(query or None)
			if not memories:
				print(f"{config.name}: I don't have any saved memories yet.")
				continue
			print(f"{config.name}: I remember: {', '.join(memories)}")
			continue
		if intent and intent.get("action") == "delete":
			target = str(intent.get("target") or intent.get("content") or "").strip()
			if target in {"", "latest"}:
				if memory_store.delete_latest_memory():
					print(f"{config.name}: I forgot the most recent memory.")
				else:
					print(f"{config.name}: I don't have a recent memory to forget.")
				continue
			if memory_store.delete_memory(target):
				print(f"{config.name}: I forgot that memory.")
			else:
				print(f"{config.name}: I couldn't find that memory.")
			continue
		if normalized_command.casefold().startswith("remember"):
			memory_text = parse_memory_request(command)
			if not memory_text:
				print(f"{config.name}: I didn't catch anything to remember.")
				continue
			try:
				stored = memory_store.add_memory(memory_text)
			except MemoryStoreError as error:
				print(f"{config.name}: {error}")
				continue
			print(f"{config.name}: Saved memory: {stored}")
			continue
		if normalized_command.casefold().startswith(("what do you remember", "what memories do you have", "list my memories", "show my memories")):
			memories = memory_store.get_relevant_memories(command)
			if not memories:
				print(f"{config.name}: I don't have any saved memories yet.")
				continue
			print(f"{config.name}: I remember: {', '.join(memories)}")
			continue
		if normalized_command.casefold().startswith(("forget ", "delete ")):
			content = command.split(None, 1)[1].strip().rstrip(" .!?")
			if content.casefold() in {"that memory", "this memory", "it"}:
				if memory_store.delete_latest_memory():
					print(f"{config.name}: I forgot the most recent memory.")
				else:
					print(f"{config.name}: I don't have a recent memory to forget.")
				continue
			for prefix in ("that ", "this "):
				if content.casefold().startswith(prefix):
					content = content[len(prefix):].strip()
					break
			if memory_store.delete_memory(content):
				print(f"{config.name}: I forgot that memory.")
			else:
				print(f"{config.name}: I couldn't find that memory.")
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
				logging.getLogger(__name__).warning(
					"Voice output failed in speak_text: %s: %s",
					type(error).__name__,
					_safe_exception_message(str(error)),
				)
				print(f"{config.name}: {_safe_diagnostic('voice.speak_text', error)}")
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
	except Exception as error:
		logging.getLogger(__name__).exception("JARVIS encountered an unexpected error")
		print(f"{config.name}: {_safe_diagnostic('main', error)}")
		return 1
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
