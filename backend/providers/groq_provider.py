"""
groq_provider.py — Groq LPUs inference provider implementation.
"""

import os
import time
from typing import Any, Dict, Iterator, List, Optional, Union
from groq import Groq
from providers.base_provider import BaseProvider, ProviderHealth

DEFAULT_GROQ_MODEL = os.getenv("KAIROS_GROQ_MODEL", "qwen/qwen3.8-27b").strip()


class GroqProvider(BaseProvider):
    name: str = "groq"

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: str = DEFAULT_GROQ_MODEL,
    ):
        self.api_key = api_key
        self.default_model = default_model
        self._client: Optional[Groq] = None
        if self.api_key:
            try:
                self._client = Groq(api_key=self.api_key)
            except Exception as exc:
                print(f"[GroqProvider] Initialization warning: {exc}")
                self._client = None

    @property
    def is_configured(self) -> bool:
        return self._get_client() is not None

    def _get_client(self) -> Optional[Groq]:
        if self._client is not None:
            return self._client
        try:
            import llm_agent
            lg = getattr(llm_agent, "groq_client", None)
            if lg is not None:
                return lg
        except Exception:
            pass
        key = self.api_key or os.getenv("GROQ_API_KEY")
        if key:
            try:
                self._client = Groq(api_key=key)
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
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        **kwargs: Any,
    ) -> Union[Iterator[str], str]:
        client = self._get_client()
        if not client:
            raise RuntimeError("Groq client is not initialized or GROQ_API_KEY is missing.")

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

        try:
            if stream:
                response = client.chat.completions.create(**params)

                def _generator() -> Iterator[str]:
                    for chunk in response:
                        if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                            yield chunk.choices[0].delta.content

                return _generator()
            else:
                response = client.chat.completions.create(**params)
                if response.choices and response.choices[0].message:
                    return response.choices[0].message.content or ""
                return ""
        except Exception as exc:
            err_str = str(exc)
            if ("rate_limit" in err_str.lower() or "429" in err_str or "OTPM" in err_str) and target_model != "llama-3.3-70b-versatile":
                print(f"[GroqProvider] Rate limit / OTPM hit on {target_model}. Retrying with fallback model 'llama-3.3-70b-versatile'...")
                params["model"] = "llama-3.3-70b-versatile"
                params["max_tokens"] = min(params.get("max_tokens", 450) or 450, 450)
                if stream:
                    response = client.chat.completions.create(**params)

                    def _fallback_gen() -> Iterator[str]:
                        for chunk in response:
                            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                                yield chunk.choices[0].delta.content

                    return _fallback_gen()
                else:
                    response = client.chat.completions.create(**params)
                    if response.choices and response.choices[0].message:
                        return response.choices[0].message.content or ""
                    return ""
            raise exc

    def health_check(self, timeout: float = 1.5) -> ProviderHealth:
        if not self._client or not self.api_key:
            return ProviderHealth(
                available=False,
                provider_name=self.name,
                error="GROQ_API_KEY not set or client unavailable",
                models_status={self.default_model: False},
            )

        t0 = time.time()
        try:
            # Low latency ping probe
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
