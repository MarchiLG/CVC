"""
narrator.py

AlertNarrator: roda numa thread de background própria, periodicamente
agrupa os Flags mais recentes do FlagManager e pede ao Ollama um
resumo em linguagem natural, salvo em NarrationLog e disponível para a
GUI (aba de alertas) via latest_summary().

Camada só de "narração" — não decide nada nem gera novos Flags; se o
Ollama não estiver disponível, OllamaClient.generate() falha de forma
silenciosa e run_once() simplesmente não produz um resumo novo.

run_once() é síncrono e determinístico — usado tanto pelo loop de
background quanto por testes.
"""

import threading
import time

from db import repository
from db.session import get_session

from .ollama_client import OllamaClient

_DEFAULT_INTERVAL_SECONDS = 60.0
_DEFAULT_MAX_FLAGS = 20

_PROMPT_HEADER = (
    "Você é um assistente que resume alertas de um sistema de monitoramento "
    "por câmeras para um operador humano. Resuma os alertas abaixo em "
    "português, de forma breve (2-4 frases), destacando padrões ou os "
    "alertas mais graves. Não invente informação além do que está listado."
)


def _build_prompt(flags) -> str:
    lines = [
        f"- [{flag.severity}] câmera {flag.camera_id}, tarefa {flag.task_type}: {flag.message}"
        for flag in flags
    ]
    return _PROMPT_HEADER + "\n\n" + "\n".join(lines)


class AlertNarrator:
    def __init__(
        self,
        flag_manager,
        model: str,
        interval_seconds: float = _DEFAULT_INTERVAL_SECONDS,
        max_flags_per_summary: int = _DEFAULT_MAX_FLAGS,
        client: OllamaClient | None = None,
    ):
        self.flag_manager = flag_manager
        self.interval_seconds = interval_seconds
        self.max_flags_per_summary = max_flags_per_summary
        self.client = client or OllamaClient(model=model)

        self._running = False
        self._thread = None
        self._lock = threading.Lock()
        self._latest_summary: str | None = None
        self._last_summarized_timestamp = 0.0

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="AlertNarrator", daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def latest_summary(self) -> str | None:
        with self._lock:
            return self._latest_summary

    def _loop(self):
        while self._running:
            self.run_once()
            # dorme em passos curtos para reagir rápido a stop()
            remaining = self.interval_seconds
            while self._running and remaining > 0:
                step = min(0.2, remaining)
                time.sleep(step)
                remaining -= step

    def run_once(self) -> str | None:
        """Gera (e persiste) um resumo a partir dos Flags recentes, se
        houver algo mais novo do que o último resumo já gerado. Retorna
        o texto gerado, ou None se não havia novidade ou o Ollama falhou."""
        flags = self.flag_manager.recent(limit=self.max_flags_per_summary)
        if not flags:
            return None

        newest_timestamp = max(flag.timestamp for flag in flags)
        if newest_timestamp <= self._last_summarized_timestamp:
            return None  # nada novo desde o último resumo

        summary = self.client.generate(_build_prompt(flags))
        if summary is None:
            return None  # Ollama falhou — tenta de novo no próximo ciclo

        self._last_summarized_timestamp = newest_timestamp
        with self._lock:
            self._latest_summary = summary

        session = get_session()
        try:
            repository.add_narration(session, summary)
        finally:
            session.close()

        return summary
