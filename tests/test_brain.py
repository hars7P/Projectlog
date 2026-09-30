"""Offline tests for JARVIS's AI request layer."""

import io
import json
import unittest
from urllib.error import HTTPError, URLError
from unittest.mock import patch

from brain import BrainError, JarvisBrain


def _response(text):
	body = {
		"output": [
			{
				"type": "message",
				"content": [{"type": "output_text", "text": text}],
			}
		]
	}
	return io.BytesIO(json.dumps(body).encode("utf-8"))


class JarvisBrainTests(unittest.TestCase):
	def test_returns_clean_response_text(self):
		brain = JarvisBrain(api_key="test-key", model="test-model")
		with patch("brain.urlopen", return_value=_response("  Hello there.  ")) as send:
			answer = brain.ask("  Hi JARVIS.  ")

		self.assertEqual(answer, "Hello there.")
		request = send.call_args.args[0]
		self.assertEqual(request.get_header("Authorization"), "Bearer test-key")
		payload = json.loads(request.data.decode("utf-8"))
		self.assertEqual(payload["input"][0]["content"], "Hi JARVIS.")
		self.assertFalse(payload["store"])

	def test_includes_recent_conversation_context(self):
		brain = JarvisBrain(api_key="test-key", model="test-model")
		with patch("brain.urlopen", side_effect=[_response("First answer."), _response("Second answer.")]) as send:
			brain.ask("Remember this context.")
			brain.ask("What did I just say?")

		second_request = send.call_args_list[1].args[0]
		payload = json.loads(second_request.data.decode("utf-8"))
		self.assertEqual(
			[message["role"] for message in payload["input"]],
			["user", "assistant", "user"],
		)

	def test_missing_key_does_not_send_request(self):
		brain = JarvisBrain(api_key=None, model="test-model")
		with patch("brain.urlopen") as send:
			with self.assertRaisesRegex(BrainError, "No OpenAI API key"):
				brain.ask("Hello")

		send.assert_not_called()

	def test_authentication_error_does_not_expose_key(self):
		secret = "never-display-this-key"
		api_error = HTTPError(
			"https://api.openai.com/v1/responses",
			401,
			"Unauthorized",
			None,
			io.BytesIO(b"authentication failed"),
		)
		brain = JarvisBrain(api_key=secret, model="test-model")
		with patch("brain.urlopen", side_effect=api_error):
			with self.assertRaises(BrainError) as raised:
				brain.ask("Hello")

		self.assertIn("rejected the API key", str(raised.exception))
		self.assertNotIn(secret, str(raised.exception))

	def test_connection_error_is_user_friendly(self):
		brain = JarvisBrain(api_key="test-key", model="test-model")
		with patch("brain.urlopen", side_effect=URLError("private transport detail")):
			with self.assertRaises(BrainError) as raised:
				brain.ask("Hello")

		self.assertIn("couldn't connect", str(raised.exception))
		self.assertNotIn("private transport detail", str(raised.exception))


if __name__ == "__main__":
	unittest.main()