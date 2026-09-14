"""
base_provider.py — Abstract base class and common interface for LLM/embedding providers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Union


@dataclass
class ProviderHealth:
    available: bool
    provider_name: str
    models_status: Dict[str, bool] = field(default_factory=dict)
    error: Optional[str] = None
    latency_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "available": self.available,
            "provider_name": self.provider_name,
            "models_status": self.models_status,
            "error": self.error,
            "latency_ms": round(self.latency_ms, 2),
            "details": self.details,
        }


class BaseProvider(ABC):
    """Abstract interface that every LLM provider (Groq, NVIDIA NIM, Ollama) must implement."""

    name: str = "base"

    @abstractmethod
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
        """
        Execute chat completion.
        If stream=True, yields string chunks.
        If stream=False, returns the complete response string.
        """
        pass

    def embed(self, texts: Union[str, List[str]]) -> List[List[float]]:
        """
        Generate vector embeddings for input text(s).
        Returns a list of float vectors.
        """
        raise NotImplementedError(f"Provider {self.name} does not support embedding.")

    @abstractmethod
    def health_check(self) -> ProviderHealth:
        """
        Run a low-latency health check probe.
        Returns a structured ProviderHealth object.
        """
        pass
