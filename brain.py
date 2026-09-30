"""OpenAI Responses API integration for JARVIS."""

from __future__ import annotations

import json
import logging
from typing import Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


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
		self._model = model.strip() or "gpt-4.1-mini"
		self._history: List[Dict[str, str]] = []

	def ask(self, user_message: str) -> str:
		"""Return an AI response, raising BrainError with a safe message on failure."""
		message = user_message.strip()
		if not message:
			raise BrainError("Please enter a message.")
		if not self._api_key:
			raise BrainError(
				"No OpenAI API key is configured. Add OPENAI_API_KEY to your .env file."
			)

		recent_history = self._history[-(_MAX_HISTORY_TURNS * 2):]
		request_body = {
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
			return "OpenAI rejected the API key. Check OPENAI_API_KEY in your .env file."
		if status_code == 403:
			return "OpenAI denied access. Check your account and model access."
		if status_code == 404:
			return "The configured OpenAI model was not found. Check OPENAI_MODEL in .env."
		if status_code == 429:
			return "OpenAI is receiving too many requests or your quota is exhausted. Try again later."
		if status_code >= 500:
			return "OpenAI is temporarily unavailable. Please try again later."
		return f"OpenAI returned an HTTP {status_code} error. Check your configuration and try again."

	@staticmethod
	def _extract_response_text(payload: object) -> str:
		if not isinstance(payload, dict):
			return ""

		text_parts: List[str] = []
		output = payload.get("output")
		if not isinstance(output, list):
			return ""
		for item in output:
			if not isinstance(item, dict) or item.get("type") != "message":
				continue
			content = item.get("content")
			if not isinstance(content, list):
				continue
			for part in content:
				if not isinstance(part, dict):
					continue
				if part.get("type") == "output_text" and isinstance(part.get("text"), str):
					text_parts.append(part["text"])
				elif part.get("type") == "refusal" and isinstance(part.get("refusal"), str):
					text_parts.append(part["refusal"])
		return "".join(text_parts).strip()