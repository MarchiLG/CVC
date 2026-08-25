"""
camera_stream.py

Encapsula a captura contínua de UMA câmera IP em uma thread dedicada,
mantendo sempre o frame mais recente disponível para consulta — sem
bloquear quem estiver lendo (a GUI, por exemplo) enquanto a rede/câmera
responde.

Nada além da captura é feito aqui de propósito: o ponto de extensão para
processamento (detecção, gravação, inferência do seu modelo, etc.) está
marcado com "TODO" dentro de _capture_loop.
"""

import threading
import time

import cv2


class CameraStream:
    """Representa uma câmera IP individual e sua thread de captura."""

    def __init__(self, camera_id: str, name: str, url: str, reconnect_delay: float = 2.0):
        self.camera_id = camera_id
        self.name = name
        self.url = url
        self.reconnect_delay = reconnect_delay

        self._capture = None
        self._thread = None
        self._running = False
        self._lock = threading.Lock()

        # Equivalente ao "MOST_RECENT_FRAME" pedido, mas por câmera:
        # cada CameraStream guarda o próprio último frame lido.
        self.most_recent_frame = None  # numpy.ndarray | None
        self.is_connected = False

    # ------------------------------------------------------------------ #
    # Controle da thread
    # ------------------------------------------------------------------ #
    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._capture_loop,
            name=f"CameraThread-{self.camera_id}",
            daemon=True,
        )
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        self.is_connected = False

    # ------------------------------------------------------------------ #
    # Loop principal de captura
    # ------------------------------------------------------------------ #
    def _capture_loop(self):
        while self._running:
            if self._capture is None or not self._capture.isOpened():
                self._connect()
                if self._capture is None or not self._capture.isOpened():
                    self.is_connected = False
                    time.sleep(self.reconnect_delay)
                    continue

            ok, frame = self._capture.read()

            if not ok:
                self.is_connected = False
                self._capture.release()
                self._capture = None
                time.sleep(self.reconnect_delay)
                continue

            self.is_connected = True
            with self._lock:
                self.most_recent_frame = frame

            # TODO: ponto de extensão.
            # As próximas funções (detecção de objetos, gravação em disco,
            # inferência do seu modelo, etc.) devem ser plugadas a partir
            # daqui — ou lendo get_frame() de fora desta thread, para não
            # travar o loop de captura.

    def _connect(self):
        self._capture = cv2.VideoCapture(self.url)

    # ------------------------------------------------------------------ #
    # Acesso externo (thread-safe)
    # ------------------------------------------------------------------ #
    def get_frame(self):
        """Retorna uma cópia do frame mais recente, ou None se ainda não houver."""
        with self._lock:
            if self.most_recent_frame is None:
                return None
            return self.most_recent_frame.copy()
