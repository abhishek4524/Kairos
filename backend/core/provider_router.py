"""
provider_router.py — Unified Router & Fallback Coordinator for LLM / Embedding requests.

Routing Order:
  Gemini (Primary Cloud) → OpenRouter → Groq → NVIDIA NIM → Mistral → Ollama (Offline Local)
  OR directly to Ollama when connectivity state is OFFLINE or KAIROS_FORCE_OFFLINE=1.
"""

import logging
import os
import time
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union

from agent_tools import audit_logger
from providers.base_provider import BaseProvider, ProviderHealth
from providers.gemini_provider import GeminiProvider
from providers.groq_provider import GroqProvider
from providers.mistral_provider import MistralProvider
from providers.nvidia_provider import NvidiaProvider
from providers.ollama_provider import OllamaProvider
from providers.openrouter_provider import OpenRouterProvider

logger = logging.getLogger("kairos.provider_router")

CLOUD_TIMEOUT_SECONDS = float(os.getenv("KAIROS_CLOUD_TIMEOUT_SECONDS", "2.5"))

# Global singleton provider instances
gemini_provider = GeminiProvider()
openrouter_provider = OpenRouterProvider()
groq_provider = GroqProvider()
nvidia_provider = NvidiaProvider()
mistral_provider = MistralProvider()
ollama_provider = OllamaProvider()

# Registry mapping
PROVIDERS: Dict[str, BaseProvider] = {
    "gemini": gemini_provider,
    "openrouter": openrouter_provider,
    "groq": groq_provider,
    "nvidia": nvidia_provider,
    "mistral": mistral_provider,
    "ollama": ollama_provider,
}


def get_provider(name: str) -> Optional[BaseProvider]:
    return PROVIDERS.get(name.lower().strip())


def is_offline_forced() -> bool:
    if os.getenv("KAIROS_FORCE_OFFLINE", "0").lower() in ("1", "true", "yes"):
        return True
    # If Phase B connectivity module exists, check its current state
    try:
        from core import connectivity
        return connectivity.current_state().value == "OFFLINE"
    except Exception:
        return False


def get_all_providers_health() -> Dict[str, Dict[str, Any]]:
    """Run health checks across all registered providers."""
    results: Dict[str, Dict[str, Any]] = {}
    for name, prov in PROVIDERS.items():
        try:
            health = prov.health_check()
            results[name] = health.to_dict()
        except Exception as exc:
            results[name] = {
                "available": False,
                "provider_name": name,
                "error": str(exc),
                "latency_ms": 0.0,
                "models_status": {},
                "details": {},
            }
    return results


def route_chat(
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
    stream: bool = True,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    intent_category: Optional[str] = None,
    session_id: str = "default",
    force_provider: Optional[str] = None,
    **kwargs: Any,
) -> Tuple[Union[Iterator[str], str], str]:
    """
    Main chat routing entrypoint.
    Returns a tuple of (response_or_generator, provider_name_used).
    """
    t0 = time.time()
    errors_encountered: List[str] = []

    # 1. Forced provider override
    if force_provider:
        prov = get_provider(force_provider)
        if not prov:
            raise ValueError(f"Unknown provider '{force_provider}'")
        res = prov.chat(
            messages=messages,
            tools=tools,
            stream=stream,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            intent_category=intent_category,
            **kwargs,
        )
        audit_logger.log_event(
            event_type="LLM_REQUEST",
            tool_name="route_chat",
            target=force_provider,
            outcome="SUCCESS",
            details={"provider": force_provider, "stream": stream, "intent": intent_category},
        )
        return res, force_provider

    # 2. Check offline state
    if is_offline_forced():
        logger.info("[Router] OFFLINE mode active → routing directly to Ollama")
        try:
            res = ollama_provider.chat(
                messages=messages,
                tools=tools,
                stream=stream,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                intent_category=intent_category,
                **kwargs,
            )
            audit_logger.log_event(
                event_type="LLM_REQUEST",
                tool_name="route_chat",
                target="ollama",
                outcome="SUCCESS",
                details={"provider": "ollama", "reason": "offline_mode", "intent": intent_category},
            )
            return res, "ollama"
        except Exception as ollama_err:
            logger.error("[Router] Ollama call failed in offline mode: %s", ollama_err)
            raise

    # 3. Fallthrough chain: Groq (Ultra-fast LPUs) → OpenRouter → Gemini → NVIDIA NIM → Mistral → Ollama

    # Step A: Try Groq (Primary Ultra-Fast)
    if groq_provider.is_configured:
        try:
            res = groq_provider.chat(
                messages=messages,
                tools=tools,
                stream=stream,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=CLOUD_TIMEOUT_SECONDS,
                **kwargs,
            )
            audit_logger.log_event(
                event_type="LLM_REQUEST",
                tool_name="route_chat",
                target="groq",
                outcome="SUCCESS",
                details={"provider": "groq", "stream": stream, "intent": intent_category},
            )
            return res, "groq"
        except Exception as groq_err:
            msg = f"Groq failed ({groq_err})"
            logger.warning("[Router] %s → falling back to OpenRouter", msg)
            errors_encountered.append(msg)

    # Step B: Try OpenRouter
    if openrouter_provider.is_configured:
        try:
            res = openrouter_provider.chat(
                messages=messages,
                tools=tools,
                stream=stream,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=CLOUD_TIMEOUT_SECONDS,
                **kwargs,
            )
            audit_logger.log_event(
                event_type="LLM_REQUEST",
                tool_name="route_chat",
                target="openrouter",
                outcome="SUCCESS",
                details={"provider": "openrouter", "fallback_from": "groq", "intent": intent_category},
            )
            return res, "openrouter"
        except Exception as or_err:
            msg = f"OpenRouter failed ({or_err})"
            logger.warning("[Router] %s → falling back to Gemini", msg)
            errors_encountered.append(msg)

    # Step C: Try Gemini
    if gemini_provider.is_configured:
        try:
            res = gemini_provider.chat(
                messages=messages,
                tools=tools,
                stream=stream,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=CLOUD_TIMEOUT_SECONDS,
                **kwargs,
            )
            audit_logger.log_event(
                event_type="LLM_REQUEST",
                tool_name="route_chat",
                target="gemini",
                outcome="SUCCESS",
                details={"provider": "gemini", "stream": stream, "intent": intent_category},
            )
            return res, "gemini"
        except Exception as gemini_err:
            msg = f"Gemini failed ({gemini_err})"
            logger.warning("[Router] %s → falling back to NVIDIA NIM", msg)
            errors_encountered.append(msg)

    # Step D: Try NVIDIA NIM
    if nvidia_provider.is_configured:
        try:
            res = nvidia_provider.chat(
                messages=messages,
                tools=tools,
                stream=stream,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=CLOUD_TIMEOUT_SECONDS,
                **kwargs,
            )
            audit_logger.log_event(
                event_type="LLM_REQUEST",
                tool_name="route_chat",
                target="nvidia",
                outcome="SUCCESS",
                details={"provider": "nvidia", "fallback_from": "groq", "intent": intent_category},
            )
            return res, "nvidia"
        except Exception as nim_err:
            msg = f"NVIDIA NIM failed ({nim_err})"
            logger.warning("[Router] %s → falling back to Mistral", msg)
            errors_encountered.append(msg)

    # Step E: Try Mistral
    if mistral_provider.is_configured:
        try:
            res = mistral_provider.chat(
                messages=messages,
                tools=tools,
                stream=stream,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=CLOUD_TIMEOUT_SECONDS,
                **kwargs,
            )
            audit_logger.log_event(
                event_type="LLM_REQUEST",
                tool_name="route_chat",
                target="mistral",
                outcome="SUCCESS",
                details={"provider": "mistral", "fallback_from": "nvidia", "intent": intent_category},
            )
            return res, "mistral"
        except Exception as mistral_err:
            msg = f"Mistral failed ({mistral_err})"
            logger.warning("[Router] %s → falling back to local Ollama", msg)
            errors_encountered.append(msg)

    # Step F: Final fallback — local Ollama
    try:
        res = ollama_provider.chat(
            messages=messages,
            tools=tools,
            stream=stream,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            intent_category=intent_category,
            **kwargs,
        )
        audit_logger.log_event(
            event_type="LLM_REQUEST",
            tool_name="route_chat",
            target="ollama",
            outcome="SUCCESS",
            details={
                "provider": "ollama",
                "fallback_chain": errors_encountered,
                "intent": intent_category,
            },
        )
        return res, "ollama"
    except Exception as ollama_err:
        errors_encountered.append(f"Ollama failed ({ollama_err})")
        logger.error("[Router] All providers in fallback chain failed: %s", errors_encountered)
        raise RuntimeError(f"All LLM providers failed: {'; '.join(errors_encountered)}")


def route_embed(
    texts: Union[str, List[str]],
    model: Optional[str] = None,
    force_provider: Optional[str] = None,
) -> Tuple[List[List[float]], str]:
    """
    Routes embedding generation to Ollama or configured embedding provider.
    """
    target = force_provider or "ollama"
    prov = get_provider(target)
    if not prov:
        raise ValueError(f"Unknown embedding provider '{target}'")

    results = prov.embed(texts, model=model)
    return results, target
