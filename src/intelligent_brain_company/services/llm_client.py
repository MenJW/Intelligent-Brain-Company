from __future__ import annotations

import json
import time
import threading
from dataclasses import dataclass
from typing import Any
from urllib import error, request

from intelligent_brain_company.config import AppConfig


# A shared gate to smooth bursty concurrent calls across departments/employee agents.
_GLOBAL_LLM_REQUEST_GATE = threading.BoundedSemaphore(3)


def _strip_code_fences(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            return "\n".join(lines[1:-1]).strip()
    return text


def _extract_first_json_value(text: str) -> str | None:
    """Extract the first balanced JSON object or array from mixed text."""
    source = _strip_code_fences(text)
    object_start = source.find("{")
    array_start = source.find("[")
    starts = [index for index in (object_start, array_start) if index >= 0]
    if not starts:
        return None
    start = min(starts)
    if start < 0:
        return None

    opening = source[start]
    closing = "}" if opening == "{" else "]"

    depth = 0
    in_string = False
    escaped = False
    for index, ch in enumerate(source[start:], start=start):
        if in_string:
            if escaped:
                escaped = False
                continue
            if ch == "\\":
                escaped = True
                continue
            if ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            continue
        if ch == opening:
            depth += 1
            continue
        if ch == closing:
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    return None


def _as_text_content(raw_content: Any) -> str:
    if isinstance(raw_content, str):
        return raw_content
    if isinstance(raw_content, list):
        parts: list[str] = []
        for item in raw_content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text", "")))
        return "\n".join(part for part in parts if part)
    return str(raw_content)


@dataclass(slots=True)
class LLMClient:
    api_key: str
    base_url: str
    model: str
    timeout_seconds: int = 45
    max_retries: int = 3
    retry_backoff_seconds: float = 0.8

    @classmethod
    def from_config(cls, config: AppConfig) -> "LLMClient | None":
        if not config.llm_enabled:
            return None
        return cls(
            api_key=config.llm_api_key,
            base_url=config.llm_base_url,
            model=config.llm_model,
            timeout_seconds=config.llm_timeout_seconds,
        )

    @staticmethod
    def _retryable_http(code: int) -> bool:
        return code in {408, 409, 425, 429, 500, 502, 503, 504}

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.2,
    ) -> dict[str, Any] | None:
        payload = {
            "model": self.model,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        body = json.dumps(payload).encode("utf-8")
        endpoint = self.base_url.rstrip("/") + "/chat/completions"
        req = request.Request(
            endpoint,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        attempts = max(1, self.max_retries)
        for attempt in range(attempts):
            acquired = _GLOBAL_LLM_REQUEST_GATE.acquire(timeout=max(1, self.timeout_seconds))
            if not acquired:
                if attempt < attempts - 1:
                    time.sleep(self.retry_backoff_seconds * (2**attempt))
                    continue
                return None
            try:
                with request.urlopen(req, timeout=self.timeout_seconds) as response:
                    raw = response.read().decode("utf-8")
            except error.HTTPError as exc:
                if attempt < attempts - 1 and self._retryable_http(getattr(exc, "code", 0)):
                    time.sleep(self.retry_backoff_seconds * (2**attempt))
                    continue
                return None
            except (TimeoutError, error.URLError):
                if attempt < attempts - 1:
                    time.sleep(self.retry_backoff_seconds * (2**attempt))
                    continue
                return None
            finally:
                _GLOBAL_LLM_REQUEST_GATE.release()

            try:
                data = json.loads(raw)
                content = _as_text_content(data["choices"][0]["message"].get("content", ""))

                stripped = _strip_code_fences(content)
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError:
                    candidate = _extract_first_json_value(content)
                    if not candidate:
                        if attempt < attempts - 1:
                            time.sleep(self.retry_backoff_seconds * (2**attempt))
                            continue
                        return None
                    parsed = json.loads(candidate)

                if isinstance(parsed, dict):
                    return parsed
                if isinstance(parsed, list):
                    return {"solutions": parsed}
                return None
            except (KeyError, IndexError, TypeError, json.JSONDecodeError):
                if attempt < attempts - 1:
                    time.sleep(self.retry_backoff_seconds * (2**attempt))
                    continue
                return None

        return None