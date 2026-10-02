"""OpenAI Responses API integration for JARVIS."""

from __future__ import annotations

import json
import logging
from typing import Dict, List, Optional, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config import is_valid_openai_api_key


_API_URL = "https://api.openai.com/v1/responses"
_SYSTEM_INSTRUCTIONS = (
	"You are JARVIS, a calm, capable personal AI assistant. "
	"Be helpful, concise, and clear about uncertainty. "
	"Do not claim to have performed actions outside this conversation."
)
_MAX_HISTORY_TURNS = 10
_REQUEST_TIMEOUT_SECONDS = 30


class BrainError(Exception):
	"""A safe, user-facing error from an AI request."""


class JarvisBrain:
	"""Send conversational text to OpenAI and retain recent context in memory."""

	def __init__(self, api_key: Optional[str], model: str) -> None:
		self._api_key = (api_key or "").strip()
		if self._api_key and not is_valid_openai_api_key(self._api_key):
			self._api_key = ""
		self._model = model.strip() or "gpt-4.1-mini"
		self._history: List[Dict[str, str]] = []

	def ask(self, user_message: str) -> str:
		"""Return an AI response, raising BrainError with a safe message on failure."""
		message = user_message.strip()
		if not message:
			raise BrainError("Please enter a message.")
		if not self._api_key:
			raise BrainError(
				"No valid OpenAI API key is configured. Add a real OpenAI API key to the application configuration."
			)

		recent_history = self._history[-(_MAX_HISTORY_TURNS * 2):]
		request_body = { # type: ignore
			"model": self._model,
			"instructions": _SYSTEM_INSTRUCTIONS,
			"input": recent_history + [{"role": "user", "content": message}],
			"store": False,
		}
		request = Request(
			_API_URL,
			data=json.dumps(request_body).encode("utf-8"),
			headers={
				"Authorization": f"Bearer {self._api_key}",
				"Content-Type": "application/json",
			},
			method="POST",
		)

		try:
			with urlopen(request, timeout=_REQUEST_TIMEOUT_SECONDS) as response:
				response_body = response.read()
			payload = json.loads(response_body.decode("utf-8"))
		except HTTPError as error:
			status_code = error.code
			error.close()
			logging.getLogger(__name__).warning(
				"OpenAI returned HTTP status %s", status_code
			)
			raise BrainError(self._http_error_message(status_code)) from None
		except (URLError, TimeoutError, OSError):
			logging.getLogger(__name__).warning("Could not connect to the OpenAI API")
			raise BrainError(
				"I couldn't connect to OpenAI. Check your internet connection and try again."
			) from None
		except (UnicodeDecodeError, json.JSONDecodeError):
			logging.getLogger(__name__).warning("OpenAI returned an unreadable response")
			raise BrainError(
				"OpenAI returned an unreadable response. Please try again."
			) from None

		answer = self._extract_response_text(payload)
		if not answer:
			logging.getLogger(__name__).warning("OpenAI response did not contain text")
			raise BrainError("OpenAI did not return a text response. Please try again.")

		self._history = recent_history + [
			{"role": "user", "content": message},
			{"role": "assistant", "content": answer},
		]
		return answer

	@staticmethod
	def _http_error_message(status_code: int) -> str:
		if status_code == 401:
			return "OpenAI rejected the API key. Check your API key configuration."
		if status_code == 403:
			return "OpenAI denied access. Check your account and model access."
		if status_code == 404:
			return "The configured OpenAI model was not found. Check your model configuration."
		if status_code == 429:
			return "OpenAI is receiving too many requests or your quota is exhausted. Try again later."
		if status_code >= 500:
			return "OpenAI is temporarily unavailable. Please try again later."
		return f"OpenAI returned an HTTP {status_code} error. Check your configuration and try again."

	@staticmethod
	def _extract_response_text(payload: object) -> str:
		if not isinstance(payload, dict):
			return ""

		response_data = cast(Dict[str, object], payload)
		text_parts: List[str] = []
		output = response_data.get("output")
		if not isinstance(output, list):
			return ""
		for item in cast(List[object], output):
			if not isinstance(item, dict):
				continue
			item_data = cast(Dict[str, object], item)
			if item_data.get("type") != "message":
				continue
			content = item_data.get("content")
			if not isinstance(content, list):
				continue
			for part in cast(List[object], content):
				if not isinstance(part, dict):
					continue
				part_data = cast(Dict[str, object], part)
				part_type = part_data.get("type")
				text = part_data.get("text")
				refusal = part_data.get("refusal")
				if part_type == "output_text" and isinstance(text, str):
					text_parts.append(text)
				elif part_type == "refusal" and isinstance(refusal, str):
					text_parts.append(refusal)
		return "".join(text_parts).strip()