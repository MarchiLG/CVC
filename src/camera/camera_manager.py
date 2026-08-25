"""
camera_manager.py

Carrega o cadastro de câmeras (config/cameras.yaml) e orquestra o
ciclo de vida de todas elas, expondo uma interface simples para a GUI:
listar câmeras, iniciar/parar todas, e obter o frame mais recente de
uma câmera específica pelo seu id.
"""

from config.loader import load_cameras_config

from .camera_stream import CameraStream


class CameraManager:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.cameras: dict[str, CameraStream] = {}
        self._load_config()

    def _load_config(self):
        for entry in load_cameras_config(self.config_path):
            if not entry.enabled:
                continue
            camera = CameraStream(
                camera_id=entry.id,
                name=entry.name,
                url=entry.url,
            )
            self.cameras[camera.camera_id] = camera

    def start_all(self):
        for camera in self.cameras.values():
            camera.start()

    def stop_all(self):
        for camera in self.cameras.values():
            camera.stop()

    def list_cameras(self):
        """Lista de (id, nome) para popular o menu da GUI, na ordem cadastrada."""
        return [(cam.camera_id, cam.name) for cam in self.cameras.values()]

    def get_frame(self, camera_id: str):
        camera = self.cameras.get(camera_id)
        if camera is None:
            return None
        return camera.get_frame()

    def is_connected(self, camera_id: str) -> bool:
        camera = self.cameras.get(camera_id)
        return bool(camera and camera.is_connected)
