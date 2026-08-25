"""
inference_engine.py

Uma única thread de background que percorre (round-robin) as câmeras
com pipeline atribuído, lê o frame mais recente via
CameraManager.get_frame() e roda o CameraPipeline de cada uma,
publicando o resultado em um ResultsStore.

De propósito, não há uma thread de inferência por câmera: um único
modelo YOLO carregado é compartilhado entre câmeras (fase 2), e
inferência dentro de cada thread de captura degradaria a própria
captura (ver seção "Threading/process model" do plano). O throttle por
câmera (detect_fps, via fps_by_camera) é o que torna essa thread única
viável para várias câmeras.

run_once() executa uma única passada de forma síncrona e determinística
— usado tanto pelo loop de background quanto pelos testes.
"""

import threading
import time

from .camera_pipeline import CameraPipeline
from .results_store import ResultsStore


class InferenceEngine:
    def __init__(
        self,
        camera_manager,
        pipelines: dict[str, CameraPipeline],
        results_store: ResultsStore,
        fps_by_camera: dict[str, float] | None = None,
        default_fps: float = 5.0,
    ):
        self.camera_manager = camera_manager
        self.pipelines = pipelines
        self.results_store = results_store
        self.fps_by_camera = fps_by_camera or {}
        self.default_fps = default_fps

        self._running = False
        self._thread = None
        self._last_run: dict[str, float] = {}

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="InferenceEngine", daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def _loop(self):
        while self._running:
            self.run_once()
            time.sleep(0.01)

    def run_once(self, now: float | None = None) -> list[str]:
        """Roda uma passada round-robin sobre as câmeras, respeitando o
        throttle por câmera. Retorna os ids processados nesta passada."""
        now = time.time() if now is None else now
        processed = []

        for camera_id, pipeline in self.pipelines.items():
            fps = self.fps_by_camera.get(camera_id, self.default_fps)
            min_interval = 1.0 / max(fps, 0.001)
            last = self._last_run.get(camera_id, 0.0)
            if (now - last) < min_interval:
                continue

            frame = self.camera_manager.get_frame(camera_id)
            if frame is None:
                continue

            result = pipeline.process(frame)
            self._last_run[camera_id] = now
            if result is not None:
                self.results_store.set(camera_id, result)
            processed.append(camera_id)

        return processed
