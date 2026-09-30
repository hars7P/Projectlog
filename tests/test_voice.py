"""Offline tests for JARVIS voice input and output."""

import io
import json
import sys
import unittest
import wave
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from voice import VoiceError, listen_and_transcribe, listen_for_audio, speak_text, transcribe_audio


class FakeRecording:
	def tobytes(self):
		return b"\x00\x00" * 16000


def _transcription_response(text):
	return io.BytesIO(json.dumps({"text": text}).encode("utf-8"))


class VoiceTests(unittest.TestCase):
	def test_records_audio_as_mono_wav(self):
		sounddevice = Mock()
		sounddevice.rec.return_value = FakeRecording()
		with patch.dict(sys.modules, {"sounddevice": sounddevice}):
			audio = listen_for_audio(duration_seconds=1)

		with wave.open(io.BytesIO(audio), "rb") as wav_file:
			self.assertEqual(wav_file.getnchannels(), 1)
			self.assertEqual(wav_file.getsampwidth(), 2)
			self.assertEqual(wav_file.getframerate(), 16000)
			sounddevice.rec.assert_called_once_with(
				16000, samplerate=16000, channels=1, dtype="int16"
			)

	def test_transcribes_audio_and_returns_clean_text(self):
		with patch("voice.urlopen", return_value=_transcription_response("  Turn on the lights.  ")) as send:
			transcript = transcribe_audio(b"fake wav data", "test-key", "gpt-transcribe")

		self.assertEqual(transcript, "Turn on the lights.")
		request = send.call_args.args[0]
		self.assertEqual(request.get_header("Authorization"), "Bearer test-key")
		self.assertIn(b'name="model"', request.data)
		self.assertIn(b"gpt-transcribe", request.data)
		self.assertIn(b'filename="speech.wav"', request.data)
		self.assertIn(b"fake wav data", request.data)

	def test_missing_key_does_not_record_microphone(self):
		with patch("voice.listen_for_audio") as record:
			with self.assertRaisesRegex(VoiceError, "No OpenAI API key"):
				listen_and_transcribe(api_key=None)

		record.assert_not_called()

	def test_microphone_error_explains_macos_permission_steps(self):
		sounddevice = Mock()
		sounddevice.rec.side_effect = RuntimeError("permission denied")
		with patch.dict(sys.modules, {"sounddevice": sounddevice}):
			with self.assertRaises(VoiceError) as raised:
				listen_for_audio(duration_seconds=1)

		self.assertIn("System Settings > Privacy & Security > Microphone", str(raised.exception))

	def test_empty_transcript_reports_no_speech(self):
		with patch("voice.urlopen", return_value=_transcription_response("")):
			with self.assertRaisesRegex(VoiceError, "Sorry, I didn't hear anything"):
				transcribe_audio(b"fake wav data", "test-key", "gpt-transcribe")

	def test_invalid_transcription_shape_reports_unrecognized_speech(self):
		with patch("voice.urlopen", return_value=io.BytesIO(b"{}")):
			with self.assertRaisesRegex(VoiceError, "I couldn't understand that"):
				transcribe_audio(b"fake wav data", "test-key", "gpt-transcribe")

	def test_authentication_error_does_not_expose_key(self):
		secret = "never-display-this-key"
		api_error = HTTPError(
			"https://api.openai.com/v1/audio/transcriptions",
			401,
			"Unauthorized",
			None,
			io.BytesIO(b"authentication failed"),
		)
		with patch("voice.urlopen", side_effect=api_error):
			with self.assertRaises(VoiceError) as raised:
				transcribe_audio(b"audio", secret, "gpt-transcribe")

		self.assertIn("rejected the API key", str(raised.exception))
		self.assertNotIn(secret, str(raised.exception))

	def test_speaks_with_macos_command_without_a_shell(self):
		with patch("voice.platform.system", return_value="Darwin"):
			with patch("voice.subprocess.run") as run:
				speak_text("Hello from JARVIS.")

		run.assert_called_once()
		self.assertEqual(run.call_args.args[0], ["say", "Hello from JARVIS."])
		self.assertTrue(run.call_args.kwargs["check"])


if __name__ == "__main__":
	unittest.main()