"""Offline tests for local WAV speech recognition."""

import io
import json
import os
import tempfile
import unittest
import wave
from unittest.mock import Mock, patch

import local_stt
from local_stt import LocalTranscriptionError, transcribe_wav


def _wav_data(sample_rate=16000):
	buffer = io.BytesIO()
	with wave.open(buffer, "wb") as wav_file:
		wav_file.setnchannels(1)
		wav_file.setsampwidth(2)
		wav_file.setframerate(sample_rate)
		wav_file.writeframes(b"\x01\x00" * sample_rate)
	return buffer.getvalue()


class LocalSpeechRecognitionTests(unittest.TestCase):
	def setUp(self):
		local_stt._loaded_models.clear()

	def tearDown(self):
		local_stt._loaded_models.clear()

	def test_transcribes_wav_with_local_model(self):
		with tempfile.TemporaryDirectory() as model_directory:
			vosk = Mock()
			model = object()
			vosk.Model.return_value = model
			recognizer = Mock()
			recognizer.FinalResult.return_value = json.dumps({"text": " hello offline "})
			vosk.KaldiRecognizer.return_value = recognizer
			with patch.dict(os.environ, {"JARVIS_VOSK_MODEL_PATH": model_directory}):
				with patch("local_stt.importlib.import_module", return_value=vosk):
					transcript = transcribe_wav(_wav_data())

		self.assertEqual(transcript, "hello offline")
		vosk.Model.assert_called_once_with(model_directory)
		vosk.KaldiRecognizer.assert_called_once_with(model, 16000)
		self.assertEqual(recognizer.AcceptWaveform.call_count, 4)
		self.assertEqual(
			sum(len(call.args[0]) for call in recognizer.AcceptWaveform.call_args_list),
			16000 * 2,
		)

	def test_missing_vosk_package_has_setup_instructions(self):
		with patch("local_stt.importlib.import_module", side_effect=ImportError):
			with self.assertRaisesRegex(LocalTranscriptionError, "pip install -r requirements.txt"):
				transcribe_wav(_wav_data())

	def test_missing_model_has_setup_instructions(self):
		with tempfile.TemporaryDirectory() as temporary_directory:
			missing_model = os.path.join(temporary_directory, "not-installed")
			with patch.dict(os.environ, {"JARVIS_VOSK_MODEL_PATH": missing_model}):
				with patch("local_stt.importlib.import_module", return_value=Mock()):
					with self.assertRaisesRegex(LocalTranscriptionError, "local speech model is missing"):
						transcribe_wav(_wav_data())

	def test_rejects_unsupported_wav_format(self):
		with tempfile.TemporaryDirectory() as model_directory:
			vosk = Mock()
			vosk.Model.return_value = object()
			with patch.dict(os.environ, {"JARVIS_VOSK_MODEL_PATH": model_directory}):
				with patch("local_stt.importlib.import_module", return_value=vosk):
					with self.assertRaisesRegex(LocalTranscriptionError, "16 kHz mono 16-bit"):
						transcribe_wav(_wav_data(sample_rate=8000))


if __name__ == "__main__":
	unittest.main()