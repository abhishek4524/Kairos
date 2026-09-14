"""
gemini_provider.py — Google Gemini API LLM inference provider implementation.
"""

import os
from typing import Any, Dict, Iterator, List, Optional, Union
from openai import OpenAI
from providers.base_provider import BaseProvider, ProviderHealth

DEFAULT_GEMINI_MODEL = os.getenv("KAIROS_GEMINI_MODEL", "gemini-2.0-flash").strip()


class GeminiProvider(BaseProvider):
    name: str = "gemini"

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: str = DEFAULT_GEMINI_MODEL,
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.default_model = default_model
        self._client: Optional[OpenAI] = None
        if self.api_key:
            try:
                self._client = OpenAI(
                    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                    api_key=self.api_key,
                )
            except Exception as exc:
                print(f"[GeminiProvider] Initialization warning: {exc}")
                self._client = None

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self._client)

    def _get_client(self) -> Optional[OpenAI]:
        if self._client:
            return self._client
        key = self.api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if key:
            try:
                self.api_key = key
                self._client = OpenAI(
                    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                    api_key=key,
                )
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
            raise RuntimeError("Gemini client is not initialized or GEMINI_API_KEY is missing.")

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
            if ("404" in err_str or "not_found" in err_str.lower()) and target_model != "gemini-1.5-flash":
                fallback_model = "gemini-1.5-flash"
                print(f"[GeminiProvider] Model '{target_model}' failed, retrying with fallback '{fallback_model}'...")
                params["model"] = fallback_model

                if stream:
                    response = client.chat.completions.create(**params)

                    def _fb_gen() -> Iterator[str]:
                        for chunk in response:
                            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                                yield chunk.choices[0].delta.content

                    return _fb_gen()
                else:
                    response = client.chat.completions.create(**params)
                    if response.choices and response.choices[0].message:
                        return response.choices[0].message.content or ""
                    return ""
            raise exc


    def health_check(self, timeout: float = 2.0) -> ProviderHealth:
        if not self.is_configured:
            return ProviderHealth(available=False, provider_name=self.name, error="GEMINI_API_KEY not configured")
        try:
            client = self._get_client()
            resp = client.chat.completions.create(
                model=self.default_model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=2,
                timeout=timeout,
            )
            return ProviderHealth(available=True, provider_name=self.name, details={"model": self.default_model})
        except Exception as e:
            return ProviderHealth(available=False, provider_name=self.name, error=str(e))
