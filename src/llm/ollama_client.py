"""
ollama_client.py

Thin wrapper over the Ollama Python client. Ollama is an external local
service — not a pip dependency that "just works" — so generate() fails
quietly (logs and returns None) instead of taking down the rest of the
application when the service is not running. See the README for how to
install/run Ollama.
"""

import logging

import ollama

logger = logging.getLogger("cv_central.llm.ollama")


def _extract_text(response) -> str:
    if isinstance(response, dict):
        return (response.get("response") or "").strip()
    return (getattr(response, "response", "") or "").strip()


class OllamaClient:
    def __init__(self, model: str, host: str | None = None):
        self.model = model
        self._client = ollama.Client(host=host) if host else ollama.Client()

    def generate(self, prompt: str) -> str | None:
        try:
            response = self._client.generate(model=self.model, prompt=prompt)
        except Exception:
            logger.warning(
                "Failed to call Ollama (model=%s) — check that the service is running (`ollama serve`).",
                self.model, exc_info=True,
            )
            return None

        text = _extract_text(response)
        return text or None
