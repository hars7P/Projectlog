"""Offline tests for JARVIS configuration safety."""

import unittest
import os
from pathlib import Path
from unittest.mock import patch

import config
from config import Config


class ConfigTests(unittest.TestCase):
	def test_api_key_is_not_in_configuration_repr(self):
		secret = "never-display-this-key"
		config = Config(openai_api_key=secret)

		self.assertNotIn(secret, repr(config))

	def test_environment_key_is_read_and_dotenv_path_is_project_relative(self):
		with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-only-key"}, clear=True):
			with patch("config.load_dotenv") as load_dotenv:
				settings = Config.from_environment()

		self.assertEqual(settings.openai_api_key, "sk-test-only-key")
		self.assertEqual(
			load_dotenv.call_args.kwargs["dotenv_path"],
			Path(config.__file__).resolve().with_name(".env"),
		)

	def test_malformed_key_is_rejected_before_network_calls(self):
		with patch.dict(os.environ, {"OPENAI_API_KEY": "key_BGy7RTJ6LuGLx01"}, clear=True):
			settings = Config.from_environment()

		self.assertIsNone(settings.openai_api_key)


if __name__ == "__main__":
	unittest.main()