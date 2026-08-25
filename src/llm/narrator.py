"""
narrator.py

AlertNarrator: runs on its own background thread, periodically groups
the most recent Flags from the FlagManager and asks Ollama for a
natural-language summary, which is stored in NarrationLog and made
available to the interfaces (alerts panel) through latest_summary().

This is a pure "narration" layer — it decides nothing and generates no
new Flags; if Ollama is unavailable, OllamaClient.generate() fails
quietly and run_once() simply produces no new summary.

run_once() is synchronous and deterministic — used both by the
background loop and by tests.
"""

import threading
import time

from db import repository
from db.session import get_session

from .ollama_client import OllamaClient

_DEFAULT_INTERVAL_SECONDS = 60.0
_DEFAULT_MAX_FLAGS = 20

# The summary is written in the language configured in app.yaml ->
# ui.language, so it matches the rest of the interface. Only the prompt
# changes; everything else about the narrator is language-agnostic.
_PROMPT_HEADERS = {
    "en": (
        "You are an assistant that summarizes alerts from a camera "
        "monitoring system for a human operator. Summarize the alerts "
        "below in English, briefly (2-4 sentences), highlighting patterns "
        "or the most severe alerts. Do not invent information beyond what "
        "is listed."
    ),
    "pt": (
        "Você é um assistente que resume alertas de um sistema de monitoramento "
        "por câmeras para um operador humano. Resuma os alertas abaixo em "
        "português, de forma breve (2-4 frases), destacando padrões ou os "
        "alertas mais graves. Não invente informação além do que está listado."
    ),
}
_DEFAULT_LANGUAGE = "en"


def _build_prompt(flags, language: str = _DEFAULT_LANGUAGE) -> str:
    header = _PROMPT_HEADERS.get(language, _PROMPT_HEADERS[_DEFAULT_LANGUAGE])
    lines = [
        f"- [{flag.severity}] camera {flag.camera_id}, task {flag.task_type}: {flag.message}"
        for flag in flags
    ]
    return header + "\n\n" + "\n".join(lines)


class AlertNarrator:
    def __init__(
        self,
        flag_manager,
        model: str,
        interval_seconds: float = _DEFAULT_INTERVAL_SECONDS,
        max_flags_per_summary: int = _DEFAULT_MAX_FLAGS,
        client: OllamaClient | None = None,
        language: str = _DEFAULT_LANGUAGE,
    ):
        self.flag_manager = flag_manager
        self.interval_seconds = interval_seconds
        self.max_flags_per_summary = max_flags_per_summary
        self.client = client or OllamaClient(model=model)
        self.language = language

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
            # Sleep in short steps so stop() is honored quickly.
            remaining = self.interval_seconds
            while self._running and remaining > 0:
                step = min(0.2, remaining)
                time.sleep(step)
                remaining -= step

    def run_once(self) -> str | None:
        """Generates (and persists) a summary from the recent Flags, if
        there is anything newer than the last summary already produced.
        Returns the generated text, or None when there was nothing new or
        Ollama failed."""
        flags = self.flag_manager.recent(limit=self.max_flags_per_summary)
        if not flags:
            return None

        newest_timestamp = max(flag.timestamp for flag in flags)
        if newest_timestamp <= self._last_summarized_timestamp:
            return None  # nothing new since the last summary

        summary = self.client.generate(_build_prompt(flags, self.language))
        if summary is None:
            return None  # Ollama failed — try again on the next cycle

        self._last_summarized_timestamp = newest_timestamp
        with self._lock:
            self._latest_summary = summary

        session = get_session()
        try:
            repository.add_narration(session, summary)
        finally:
            session.close()

        return summary
