"""
base.py

Interface comum para canais de notificação (log, desktop, etc.).
"""

from abc import ABC, abstractmethod

from ..flag import Flag


class Notifier(ABC):
    name: str

    @abstractmethod
    def notify(self, flag: Flag) -> None:
        ...
