"""
ollama_client.py

Wrapper fino sobre o cliente Python do Ollama. Ollama é um serviço
local externo — não uma dependência pip que "só funciona" — então
generate() falha de forma silenciosa (loga e retorna None) em vez de
derrubar o resto da aplicação se o serviço não estiver rodando. Ver
README para como instalar/rodar o Ollama.
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
                "Falha ao chamar Ollama (modelo=%s) — verifique se o serviço está rodando (`ollama serve`).",
                self.model, exc_info=True,
            )
            return None

        text = _extract_text(response)
        return text or None
