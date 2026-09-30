"""Offline tests for text and voice mode integration."""

import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

from config import Config
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
			openai_api_key="test-key",
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
			{"api_key": "test-key", "model": "test-transcription-model"},
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
		config = Config(openai_api_key="test-key")
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

	def test_exit_from_startup_menu_does_not_create_brain(self):
		output = io.StringIO()
		with patch("main.JarvisBrain") as brain:
			with patch("builtins.input", return_value="3"):
				with redirect_stdout(output):
					run(Config())

		brain.assert_not_called()
		self.assertIn("3. Exit", output.getvalue())
		self.assertIn("Goodbye.", output.getvalue())


if __name__ == "__main__":
	unittest.main()