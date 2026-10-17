"""Minimal client for local LLM generation through Ollama's /api/chat (no paid APIs)."""

import json
import time
from dataclasses import dataclass

import httpx

from agents.prompts import PromptSpec


class LLMError(Exception):
    pass


@dataclass
class LLMResult:
    text: str
    model: str
    prompt_ref: str
    seconds: float
    eval_tokens: int | None
    truncated: bool = False  # generation stopped at the token limit


class OllamaChatClient:
    def __init__(self, base_url: str, model: str, translation_model: str | None = None, timeout: float = 300.0):
        self._url = base_url.rstrip("/") + "/api/chat"
        self.model = model
        self.translation_model = translation_model or model
        self._timeout = timeout

    def model_for(self, spec: PromptSpec) -> str:
        return self.translation_model if spec.model_role == "translation" else self.model

    def run(self, spec: PromptSpec, **values: str) -> LLMResult:
        system, user = spec.render(**values)
        messages = ([{"role": "system", "content": system}] if system.strip() else []) + [{"role": "user", "content": user}]
        model = self.model_for(spec)
        body = {"model": model, "messages": messages, "stream": False, "options": spec.options, "keep_alive": "10m"}
        if spec.json_output:
            body["format"] = spec.response_schema or "json"
        started = time.perf_counter()
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(self._url, json=body)
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise LLMError(f"Ollama chat request failed ({model}): {exc}") from exc
        text = (data.get("message") or {}).get("content", "")
        return LLMResult(text=text.strip(), model=model, prompt_ref=spec.ref,
                         seconds=round(time.perf_counter() - started, 2), eval_tokens=data.get("eval_count"),
                         truncated=data.get("done_reason") == "length")
