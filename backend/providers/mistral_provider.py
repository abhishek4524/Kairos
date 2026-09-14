"""
mistral_provider.py — Mistral AI provider for Kairos LLM fallback chain.

Mistral exposes an OpenAI-compatible API at https://api.mistral.ai/v1.
Configured via:
  MISTRAL_API_KEY      — required
  KAIROS_MISTRAL_MODEL — optional, defaults to mistral-large-latest
"""

import logging
import os
import time
from typing import Any, Dict, Iterator, List, Optional, Union

from openai import OpenAI

from providers.base_provider import BaseProvider, ProviderHealth

logger = logging.getLogger("kairos.mistral_provider")

_DEFAULT_MODEL = "mistral-large-latest"
_FALLBACK_MODEL = "mistral-small-latest"

MISTRAL_BASE_URL = "https://api.mistral.ai/v1"


class MistralProvider(BaseProvider):
    """OpenAI-compatible client pointing at Mistral AI."""

    def __init__(self) -> None:
        self.api_key = os.environ.get("MISTRAL_API_KEY", "")
        self.model = os.environ.get("KAIROS_MISTRAL_MODEL", _DEFAULT_MODEL)
        self.is_configured = bool(self.api_key)

        if self.is_configured:
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=MISTRAL_BASE_URL,
                timeout=30.0,
            )
            logger.info("[Mistral] Provider initialized. Model: %s", self.model)
        else:
            self._client = None
            logger.info("[Mistral] MISTRAL_API_KEY not set — provider disabled")

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
            raise RuntimeError("MistralProvider is not configured (missing MISTRAL_API_KEY)")

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
            logger.warning("[Mistral] Primary model %s failed, retrying with %s", chosen_model, _FALLBACK_MODEL)
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
                    yield chunk  # type: ignore[misc]
                elif delta.content:
                    yield delta.content

    def embed(
        self,
        texts: Union[str, List[str]],
        model: Optional[str] = None,
    ) -> List[List[float]]:
        raise NotImplementedError("MistralProvider does not support embeddings via this interface")

    def health_check(self) -> ProviderHealth:
        if not self.is_configured:
            return ProviderHealth(
                available=False,
                provider_name="mistral",
                error="MISTRAL_API_KEY not set",
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
                provider_name="mistral",
                latency_ms=latency_ms,
                models_status={self.model: "ok"},
            )
        except Exception as exc:
            latency_ms = (time.time() - t0) * 1000
            return ProviderHealth(
                available=False,
                provider_name="mistral",
                latency_ms=latency_ms,
                error=str(exc),
            )
