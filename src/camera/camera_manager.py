"""
camera_manager.py

Loads the camera registry (config/cameras.yaml) and orchestrates the
lifecycle of all of them, exposing a simple surface to the user
interfaces: list cameras, start/stop all of them, and get the most
recent frame of a specific camera by its id.
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
        """List of (id, name) to populate the interface menus, in registration order."""
        return [(cam.camera_id, cam.name) for cam in self.cameras.values()]

    def get_frame(self, camera_id: str):
        camera = self.cameras.get(camera_id)
        if camera is None:
            return None
        return camera.get_frame()

    def is_connected(self, camera_id: str) -> bool:
        camera = self.cameras.get(camera_id)
        return bool(camera and camera.is_connected)
