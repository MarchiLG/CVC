"""
flag.py

Representa um evento de alerta gerado por uma tarefa de análise
(TaskAnalyzer) — ex.: EPI ausente, contagem abaixo do esperado, rosto
desconhecido.
"""

import time
from dataclasses import dataclass, field


@dataclass
class Flag:
    camera_id: str
    task_type: str
    flag_id: str
    severity: str = "info"
    message: str = ""
    notify: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
