"""
openrouter_provider.py — OpenRouter provider for Kairos LLM fallback chain.

OpenRouter exposes an OpenAI-compatible API at https://openrouter.ai/api/v1.
Configured via:
  OPENROUTER_API_KEY      — required
  KAIROS_OPENROUTER_MODEL — optional, defaults to meta-llama/llama-3.3-70b-instruct:free
"""

import logging
import os
import time
from typing import Any, Dict, Iterator, List, Optional, Union

from openai import OpenAI, APIError, APIConnectionError, RateLimitError

from providers.base_provider import BaseProvider, ProviderHealth

logger = logging.getLogger("kairos.openrouter_provider")

_DEFAULT_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
_FALLBACK_MODEL = "mistralai/mistral-7b-instruct:free"

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterProvider(BaseProvider):
    """OpenAI-compatible client pointing at OpenRouter.ai."""

    def __init__(self) -> None:
        self.api_key = os.environ.get("OPENROUTER_API_KEY", "")
        self.model = os.environ.get("KAIROS_OPENROUTER_MODEL", _DEFAULT_MODEL)
        self.is_configured = bool(self.api_key)

        if self.is_configured:
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=OPENROUTER_BASE_URL,
                default_headers={
                    "HTTP-Referer": "https://kairos.app",
                    "X-Title": "Kairos Personal Assistant",
                },
                timeout=30.0,
            )
            logger.info("[OpenRouter] Provider initialized. Model: %s", self.model)
        else:
            self._client = None
            logger.info("[OpenRouter] OPENROUTER_API_KEY not set — provider disabled")

    # ── BaseProvider interface ─────────────────────────────────────────────── #

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: bool = True,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        intent_category: Optional[str] = None,
        **kwargs: Any,
    ) -> Union[Iterator[str], str]:
        if not self.is_configured or self._client is None:
            raise RuntimeError("OpenRouterProvider is not configured (missing OPENROUTER_API_KEY)")

        chosen_model = model or self.model
        kwargs_clean = {k: v for k, v in kwargs.items() if k not in ("timeout",)}

        call_kwargs: Dict[str, Any] = {
            "model": chosen_model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
            **kwargs_clean,
        }
        if max_tokens:
            call_kwargs["max_tokens"] = max_tokens
        if tools:
            call_kwargs["tools"] = tools
            call_kwargs["tool_choice"] = "auto"

        try:
            response = self._client.chat.completions.create(**call_kwargs)
        except Exception:
            # Retry with free fallback model
            logger.warning("[OpenRouter] Primary model %s failed, retrying with %s", chosen_model, _FALLBACK_MODEL)
            call_kwargs["model"] = _FALLBACK_MODEL
            response = self._client.chat.completions.create(**call_kwargs)

        if stream:
            return self._stream_generator(response)
        else:
            choice = response.choices[0]
            if choice.message.tool_calls:
                return choice.message  # type: ignore[return-value]
            return choice.message.content or ""

    def _stream_generator(self, response: Any) -> Iterator[str]:
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta:
                delta = chunk.choices[0].delta
                if delta.tool_calls:
                    # Yield the whole chunk object for tool-call handling upstream
                    yield chunk  # type: ignore[misc]
                elif delta.content:
                    yield delta.content

    def embed(
        self,
        texts: Union[str, List[str]],
        model: Optional[str] = None,
    ) -> List[List[float]]:
        raise NotImplementedError("OpenRouterProvider does not support embeddings")

    def health_check(self) -> ProviderHealth:
        if not self.is_configured:
            return ProviderHealth(
                available=False,
                provider_name="openrouter",
                error="OPENROUTER_API_KEY not set",
            )
        t0 = time.time()
        try:
            self._client.chat.completions.create(  # type: ignore[union-attr]
                model=self.model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
                stream=False,
            )
            latency_ms = (time.time() - t0) * 1000
            return ProviderHealth(
                available=True,
                provider_name="openrouter",
                latency_ms=latency_ms,
                models_status={self.model: "ok"},
            )
        except Exception as exc:
            latency_ms = (time.time() - t0) * 1000
            return ProviderHealth(
                available=False,
                provider_name="openrouter",
                latency_ms=latency_ms,
                error=str(exc),
            )
