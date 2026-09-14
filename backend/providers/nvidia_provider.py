"""
nvidia_provider.py — NVIDIA NIM OpenAI-compatible cloud inference provider.
"""

import os
import time
from typing import Any, Dict, Iterator, List, Optional, Union
from openai import OpenAI
from providers.base_provider import BaseProvider, ProviderHealth

DEFAULT_NVIDIA_MODEL = os.getenv("KAIROS_NVIDIA_MODEL", "meta/llama-3.3-70b-instruct").strip()
NVIDIA_BASE_URL = os.getenv("KAIROS_NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1").strip()


class NvidiaProvider(BaseProvider):
    name: str = "nvidia"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = NVIDIA_BASE_URL,
        default_model: str = DEFAULT_NVIDIA_MODEL,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.default_model = default_model
        self._client: Optional[OpenAI] = None
        if self.api_key:
            try:
                self._client = OpenAI(base_url=self.base_url, api_key=self.api_key)
            except Exception as exc:
                print(f"[NvidiaProvider] Initialization warning: {exc}")
                self._client = None

    @property
    def is_configured(self) -> bool:
        return self._get_client() is not None

    def _get_client(self) -> Optional[OpenAI]:
        if self._client is not None:
            return self._client
        try:
            import llm_agent
            ln = getattr(llm_agent, "nvidia_client", None)
            if ln is not None:
                return ln
        except Exception:
            pass
        key = self.api_key or os.getenv("NVIDIA_API_KEY")
        if key:
            try:
                self._client = OpenAI(base_url=self.base_url, api_key=key)
                return self._client
            except Exception:
                return None
        return None

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: bool = True,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = 1024,
        timeout: Optional[float] = None,
        **kwargs: Any,
    ) -> Union[Iterator[str], str]:
        client = self._get_client()
        if not client:
            raise RuntimeError("NVIDIA client is not initialized or NVIDIA_API_KEY is missing.")

        target_model = model or self.default_model
        params: Dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "stream": stream,
            "temperature": temperature,
        }
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        if timeout is not None:
            params["timeout"] = timeout

        if stream:
            response = client.chat.completions.create(**params)

            def _generator() -> Iterator[str]:
                for chunk in response:
                    if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content

            return _generator()
        else:
            response = self._client.chat.completions.create(**params)
            if response.choices and response.choices[0].message:
                return response.choices[0].message.content or ""
            return ""

    def health_check(self, timeout: float = 2.0) -> ProviderHealth:
        if not self._client or not self.api_key:
            return ProviderHealth(
                available=False,
                provider_name=self.name,
                error="NVIDIA_API_KEY not set or client unavailable",
                models_status={self.default_model: False},
            )

        t0 = time.time()
        try:
            self._client.chat.completions.create(
                model=self.default_model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=2,
                timeout=timeout,
            )
            dt = (time.time() - t0) * 1000
            return ProviderHealth(
                available=True,
                provider_name=self.name,
                models_status={self.default_model: True},
                latency_ms=dt,
                details={"model": self.default_model},
            )
        except Exception as exc:
            dt = (time.time() - t0) * 1000
            return ProviderHealth(
                available=False,
                provider_name=self.name,
                error=str(exc),
                latency_ms=dt,
                models_status={self.default_model: False},
            )
