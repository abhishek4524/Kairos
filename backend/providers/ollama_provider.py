"""
ollama_provider.py — Local Ollama inference provider with 6GB VRAM safety rules.
"""

import json
import os
import threading
import time
from typing import Any, Dict, Iterator, List, Optional, Union
import httpx
from providers.base_provider import BaseProvider, ProviderHealth

OLLAMA_URL = os.getenv("KAIROS_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_GENERAL_MODEL = os.getenv("KAIROS_OLLAMA_GENERAL_MODEL", "qwen2.5:7b").strip()
OLLAMA_CODER_MODEL = os.getenv("KAIROS_OLLAMA_CODER_MODEL", "qwen2.5-coder:7b").strip()
OLLAMA_EMBED_MODEL = os.getenv("KAIROS_OLLAMA_EMBED_MODEL", "nomic-embed-text").strip()

DEFAULT_NUM_CTX = int(os.getenv("KAIROS_LOCAL_NUM_CTX", "8192"))
DEFAULT_KEEP_ALIVE = os.getenv("KAIROS_LOCAL_KEEP_ALIVE", "15m").strip()
MAX_PARALLEL = int(os.getenv("KAIROS_LOCAL_MAX_PARALLEL", "1"))

# Cross-process/cross-thread shared concurrency guard for 6GB VRAM safety
_OLLAMA_SEMAPHORE = threading.Semaphore(MAX_PARALLEL)


def get_shared_semaphore() -> threading.Semaphore:
    return _OLLAMA_SEMAPHORE


def get_ollama_executable() -> Optional[str]:
    """Resolves installed Ollama binary path across system PATH and standard Windows locations."""
    import shutil
    import platform
    which_path = shutil.which("ollama") or shutil.which("ollama.exe")
    if which_path:
        return which_path

    if platform.system() == "Windows":
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        program_files = os.environ.get("PROGRAMFILES", r"C:\Program Files")
        candidates = [
            os.path.join(local_app_data, "Programs", "Ollama", "ollama.exe"),
            os.path.join(local_app_data, "Programs", "Ollama", "ollama app.exe"),
            os.path.join(program_files, "Ollama", "ollama.exe"),
        ]
        for c in candidates:
            if c and os.path.exists(c):
                return c
    return None


class OllamaProvider(BaseProvider):
    name: str = "ollama"

    def __init__(
        self,
        base_url: str = OLLAMA_URL,
        general_model: str = OLLAMA_GENERAL_MODEL,
        coder_model: str = OLLAMA_CODER_MODEL,
        embed_model: str = OLLAMA_EMBED_MODEL,
        num_ctx: int = DEFAULT_NUM_CTX,
        keep_alive: str = DEFAULT_KEEP_ALIVE,
    ):
        self.base_url = base_url.rstrip("/")
        self.general_model = general_model
        self.coder_model = coder_model
        self.embed_model = embed_model
        self.num_ctx = min(num_ctx, 8192) if os.getenv("KAIROS_ALLOW_HIGH_NUM_CTX") != "1" else num_ctx
        self.keep_alive = keep_alive
        self._semaphore = _OLLAMA_SEMAPHORE

    def ensure_ollama_server_running(self) -> bool:
        """Auto-launches local Ollama background server if installed but not running."""
        try:
            with httpx.Client(timeout=1.0) as client:
                r = client.get(f"{self.base_url}/api/tags")
                if r.status_code == 200:
                    return True
        except Exception:
            pass

        ollama_bin = get_ollama_executable()
        if not ollama_bin:
            print(f"[OLLAMA] Server offline and no Ollama executable found on system.")
            return False

        print(f"[OLLAMA] Server offline at {self.base_url}. Auto-launching '{ollama_bin}'...")
        try:
            import subprocess
            import platform
            popen_kwargs = {}
            if platform.system() == "Windows":
                popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            subprocess.Popen([ollama_bin, "serve"], **popen_kwargs)

            for _ in range(15):
                time.sleep(0.2)
                try:
                    with httpx.Client(timeout=0.5) as client:
                        r = client.get(f"{self.base_url}/api/tags")
                        if r.status_code == 200:
                            print("[OLLAMA] Auto-launched Ollama server successfully.")
                            return True
                except Exception:
                    pass
        except Exception as launch_err:
            print(f"[OLLAMA] Failed to auto-launch Ollama server: {launch_err}")

        return False

    def select_model_for_intent(self, intent_category: Optional[str] = None) -> str:
        if intent_category in ("coding", "dev", "terminal"):
            return self.coder_model
        return self.general_model

    def get_any_installed_model(self) -> Optional[str]:
        try:
            with httpx.Client(timeout=3.0) as client:
                resp = client.get(f"{self.base_url}/api/tags")
                if resp.status_code == 200:
                    models = resp.json().get("models", [])
                    if models:
                        return models[0].get("name")
        except Exception:
            pass
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
        intent_category: Optional[str] = None,
        **kwargs: Any,
    ) -> Union[Iterator[str], str]:
        if not kwargs.get("skip_server_check", False) and not self.ensure_ollama_server_running():
            raise RuntimeError(f"Ollama server at {self.base_url} is not running and could not be auto-launched.")

        target_model = model or self.select_model_for_intent(intent_category)
        req_timeout = timeout or 60.0

        options: Dict[str, Any] = {
            "num_ctx": self.num_ctx,
            "temperature": temperature,
        }
        if max_tokens is not None:
            options["num_predict"] = max_tokens

        payload: Dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "stream": stream,
            "keep_alive": self.keep_alive,
            "options": options,
        }
        if tools:
            payload["tools"] = tools

        endpoint = f"{self.base_url}/api/chat"

        def _execute_request(current_payload: Dict[str, Any], current_stream: bool):
            if current_stream:
                def _generator() -> Iterator[str]:
                    acquired = self._semaphore.acquire(timeout=req_timeout)
                    if not acquired:
                        raise TimeoutError("Ollama concurrency semaphore acquisition timed out (VRAM protection).")
                    try:
                        with httpx.Client(timeout=req_timeout) as client:
                            with client.stream("POST", endpoint, json=current_payload) as resp:
                                if resp.status_code == 404:
                                    alt_model = self.get_any_installed_model()
                                    if alt_model and alt_model != current_payload["model"]:
                                        print(f"[OLLAMA] Model '{current_payload['model']}' 404. Falling back to installed model '{alt_model}'...")
                                        current_payload["model"] = alt_model
                                        with client.stream("POST", endpoint, json=current_payload) as alt_resp:
                                            if alt_resp.status_code != 200:
                                                body = alt_resp.read().decode("utf-8", errors="replace")
                                                raise RuntimeError(f"Ollama returned HTTP {alt_resp.status_code}: {body}")
                                            for line in alt_resp.iter_lines():
                                                if line:
                                                    try:
                                                        data = json.loads(line)
                                                        content = data.get("message", {}).get("content", "")
                                                        if content:
                                                            yield content
                                                        if data.get("done", False):
                                                            break
                                                    except json.JSONDecodeError:
                                                        continue
                                            return
                                    else:
                                        from core.connectivity import GOLDEN_RULE_FALLBACK_MESSAGE
                                        raise RuntimeError(GOLDEN_RULE_FALLBACK_MESSAGE)

                                if resp.status_code != 200:
                                    body = resp.read().decode("utf-8", errors="replace")
                                    raise RuntimeError(f"Ollama returned HTTP {resp.status_code}: {body}")

                                for line in resp.iter_lines():
                                    if not line:
                                        continue
                                    try:
                                        data = json.loads(line)
                                        msg = data.get("message", {})
                                        content = msg.get("content", "")
                                        if content:
                                            yield content
                                        if data.get("done", False):
                                            break
                                    except json.JSONDecodeError:
                                        continue
                    finally:
                        self._semaphore.release()

                return _generator()
            else:
                acquired = self._semaphore.acquire(timeout=req_timeout)
                if not acquired:
                    raise TimeoutError("Ollama concurrency semaphore acquisition timed out (VRAM protection).")
                try:
                    with httpx.Client(timeout=req_timeout) as client:
                        resp = client.post(endpoint, json=current_payload)
                        if resp.status_code == 404:
                            alt_model = self.get_any_installed_model()
                            if alt_model and alt_model != current_payload["model"]:
                                print(f"[OLLAMA] Model '{current_payload['model']}' 404. Falling back to installed model '{alt_model}'...")
                                current_payload["model"] = alt_model
                                resp = client.post(endpoint, json=current_payload)
                            else:
                                from core.connectivity import GOLDEN_RULE_FALLBACK_MESSAGE
                                raise RuntimeError(GOLDEN_RULE_FALLBACK_MESSAGE)
                        if resp.status_code != 200:
                            raise RuntimeError(f"Ollama returned HTTP {resp.status_code}: {resp.text}")
                        data = resp.json()
                        return data.get("message", {}).get("content", "")
                finally:
                    self._semaphore.release()

        return _execute_request(payload, stream)

    def embed(self, texts: Union[str, List[str]], model: Optional[str] = None, timeout: float = 30.0) -> List[List[float]]:
        target_model = model or self.embed_model
        endpoint = f"{self.base_url}/api/embed"
        fallback_endpoint = f"{self.base_url}/api/embeddings"

        input_list = [texts] if isinstance(texts, str) else texts
        if not input_list:
            return []

        acquired = self._semaphore.acquire(timeout=timeout)
        if not acquired:
            raise TimeoutError("Ollama concurrency semaphore acquisition timed out during embedding.")

        try:
            with httpx.Client(timeout=timeout) as client:
                # Try modern /api/embed endpoint
                embed_payload = {
                    "model": target_model,
                    "input": input_list,
                    "keep_alive": self.keep_alive,
                    "options": {"num_ctx": self.num_ctx},
                }
                resp = client.post(endpoint, json=embed_payload)
                if resp.status_code == 200:
                    data = resp.json()
                    embeddings = data.get("embeddings", [])
                    if embeddings:
                        return embeddings

                # Fallback to single /api/embeddings for legacy Ollama versions
                results = []
                for text in input_list:
                    single_payload = {
                        "model": target_model,
                        "prompt": text,
                        "keep_alive": self.keep_alive,
                        "options": {"num_ctx": self.num_ctx},
                    }
                    s_resp = client.post(fallback_endpoint, json=single_payload)
                    if s_resp.status_code != 200:
                        raise RuntimeError(f"Ollama embedding failed (HTTP {s_resp.status_code}): {s_resp.text}")
                    results.append(s_resp.json().get("embedding", []))
                return results
        finally:
            self._semaphore.release()

    def health_check(self, timeout: float = 1.0) -> ProviderHealth:
        endpoint = f"{self.base_url}/api/tags"
        t0 = time.time()
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.get(endpoint)
            dt = (time.time() - t0) * 1000

            if resp.status_code != 200:
                return ProviderHealth(
                    available=False,
                    provider_name=self.name,
                    error=f"Ollama server returned HTTP {resp.status_code}",
                    latency_ms=dt,
                )

            data = resp.json()
            models = data.get("models", [])
            installed_names = {m.get("name", "").lower() for m in models}

            def _is_present(req_tag: str) -> bool:
                req_lower = req_tag.lower()
                base_req = req_lower.split(":")[0]
                return any(
                    req_lower == inst or inst.startswith(f"{req_lower}:") or inst.startswith(f"{base_req}:")
                    for inst in installed_names
                )

            models_status = {
                self.general_model: _is_present(self.general_model),
                self.coder_model: _is_present(self.coder_model),
                self.embed_model: _is_present(self.embed_model),
            }

            all_present = all(models_status.values())
            missing = [m for m, present in models_status.items() if not present]

            error_msg = None
            if not all_present:
                error_msg = f"Ollama running but missing model(s): {', '.join(missing)}"

            return ProviderHealth(
                available=all_present,
                provider_name=self.name,
                models_status=models_status,
                error=error_msg,
                latency_ms=dt,
                details={
                    "installed_models": list(installed_names),
                    "server_online": True,
                    "num_ctx": self.num_ctx,
                    "keep_alive": self.keep_alive,
                },
            )
        except Exception as exc:
            dt = (time.time() - t0) * 1000
            return ProviderHealth(
                available=False,
                provider_name=self.name,
                error=f"Ollama server unreachable at {self.base_url}: {exc}",
                latency_ms=dt,
                models_status={
                    self.general_model: False,
                    self.coder_model: False,
                    self.embed_model: False,
                },
                details={"server_online": False},
            )
