"""Offline tests for text and voice mode integration."""

import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

from config import Config
import main as main_module
from main import main, run
from voice import VoiceError


class MainVoiceModeTests(unittest.TestCase):
	def test_config_diagnostic_reports_presence_without_printing_key(self):
		secret = "do-not-print-this-key"
		with patch("main.Config.from_environment", return_value=Config(openai_api_key=secret)):
			with patch("sys.argv", ["main.py", "--check-config"]):
				with redirect_stdout(io.StringIO()) as output:
					result = main()

		self.assertEqual(result, 0)
		self.assertEqual(output.getvalue(), "OPENAI_API_KEY detected: YES\n")
		self.assertNotIn(secret, output.getvalue())

	def test_config_diagnostic_reports_missing_key(self):
		with patch("main.Config.from_environment", return_value=Config()):
			with patch("sys.argv", ["main.py", "--check-config"]):
				with redirect_stdout(io.StringIO()) as output:
					result = main()

		self.assertEqual(result, 0)
		self.assertEqual(output.getvalue(), "OPENAI_API_KEY detected: NO\n")

	def test_transcribed_message_uses_brain_and_speaks_reply(self):
		brain = Mock()
		brain.ask.return_value = "Hello from JARVIS."
		config = Config(
			openai_api_key="sk-test-key",
			openai_model="test-model",
			openai_transcription_model="test-transcription-model",
		)
		output = io.StringIO()

		with patch("main.JarvisBrain", return_value=brain):
			with patch("main.listen_and_transcribe", side_effect=["Hello JARVIS.", "text"]) as listen:
				with patch("main.speak_text") as speak:
					with patch("builtins.input", side_effect=["2", "help", "exit"]):
						with redirect_stdout(output):
							run(config)

		brain.ask.assert_called_once_with("Hello JARVIS.")
		self.assertEqual(listen.call_count, 2)
		self.assertEqual(
			listen.call_args_list[0].kwargs,
			{"api_key": "sk-test-key", "model": "test-transcription-model"},
		)
		speak.assert_called_once_with("Hello from JARVIS.")
		self.assertIn("1. Text mode", output.getvalue())
		self.assertIn("Voice mode active.", output.getvalue())

	def test_voice_input_error_returns_to_text_mode(self):
		config = Config()
		output = io.StringIO()

		with patch("main.listen_and_transcribe", side_effect=VoiceError("microphone blocked")):
			with patch("builtins.input", side_effect=["2", "exit"]):
				with redirect_stdout(output):
					run(config)

		self.assertIn("microphone blocked", output.getvalue())
		self.assertIn("Switching to text mode.", output.getvalue())
		self.assertIn("Goodbye.", output.getvalue())

	def test_speech_output_failure_keeps_text_response_and_falls_back(self):
		brain = Mock()
		brain.ask.return_value = "Python is a programming language."
		config = Config(openai_api_key="sk-test-key")
		output = io.StringIO()

		with patch("main.JarvisBrain", return_value=brain):
			with patch("main.listen_and_transcribe", return_value="What is Python?"):
				with patch("main.speak_text", side_effect=VoiceError("speaker unavailable")):
					with patch("builtins.input", side_effect=["2", "exit"]):
						with redirect_stdout(output):
							run(config)

		self.assertIn("Python is a programming language.", output.getvalue())
		self.assertIn("speaker unavailable", output.getvalue())
		self.assertIn("Switching to text mode.", output.getvalue())

	def test_safe_diagnostic_redacts_credentials(self):
		diagnostic = getattr(main_module, "_safe_diagnostic")(
			"voice.listen_and_transcribe",
			ValueError("Authorization: Bearer sk-secret-token OPENAI_API_KEY=top-secret-key"),
		)

		self.assertIn("voice.listen_and_transcribe failed", diagnostic)
		self.assertIn("ValueError", diagnostic)
		self.assertNotIn("sk-secret-token", diagnostic)
		self.assertNotIn("top-secret-key", diagnostic)
		self.assertIn("[REDACTED]", diagnostic)

	def test_exit_from_startup_menu_does_not_create_brain(self):
		output = io.StringIO()
		with patch("main.JarvisBrain") as brain:
			with patch("builtins.input", return_value="3"):
				with redirect_stdout(output):
					run(Config())

		brain.assert_not_called()
		self.assertIn("3. Exit", output.getvalue())
		self.assertIn("Goodbye.", output.getvalue())

	def test_normal_text_conversation_does_not_save_memory(self):
		brain = Mock()
		brain.ask.return_value = "I am doing well."
		memory_store = Mock()
		with patch("main.JarvisBrain", return_value=brain):
			with patch("main.MemoryStore", return_value=memory_store):
				with patch("builtins.input", side_effect=["1", "How are you?", "exit"]):
					with redirect_stdout(io.StringIO()):
						run(Config(openai_api_key="sk-test-key"))

		brain.ask.assert_called_once_with("How are you?")
		memory_store.add_memory.assert_not_called()

	def test_memory_commands_are_handled_with_sentence_punctuation(self):
		brain = Mock()
		brain.ask.return_value = "Hello."
		config = Config(openai_api_key="sk-test-key")
		output = io.StringIO()
		def save_memory(value: str) -> str:
			return value

		def delete_memory(value: str) -> bool:
			return value == "I am learning Python"

		with patch("main.JarvisBrain", return_value=brain):
			with patch("main.MemoryStore") as memory_store:
				memory_store.return_value.add_memory.side_effect = save_memory
				memory_store.return_value.get_relevant_memories.side_effect = [
					["my name is Harshit"],
					["I am learning Python"],
					[],
				]
				memory_store.return_value.clear_memories.return_value = 1
				memory_store.return_value.delete_memory.side_effect = delete_memory
				with patch("builtins.input", side_effect=["1", "Remember that", "Remember that my name is Harshit.", "What do you know about me?", "Keep in mind that I am learning Python.", "What do you remember about Python?", "Forget that I am learning Python.", "exit"]):
					with redirect_stdout(output):
						run(config)

		self.assertIn("Saved memory: my name is Harshit", output.getvalue())
		self.assertIn("Saved memory: I am learning Python", output.getvalue())
		self.assertIn("I didn't catch anything to remember.", output.getvalue())
		self.assertEqual(memory_store.return_value.add_memory.call_count, 2)
		self.assertIn("I remember: my name is Harshit", output.getvalue())
		self.assertIn("I remember: I am learning Python", output.getvalue())
		self.assertIn("I forgot that memory.", output.getvalue())


if __name__ == "__main__":
	unittest.main()