"""
camera_grid.py

Grade com um CameraTile por câmera cadastrada — mostra todas as
câmeras simultaneamente, ao contrário da GUI Tkinter anterior (que só
exibia uma câmera selecionada por vez).
"""

import math

from PySide6.QtWidgets import QGridLayout, QWidget

from .camera_tile import CameraTile


class CameraGrid(QWidget):
    def __init__(self, cameras: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        self.tiles: dict[str, CameraTile] = {}

        layout = QGridLayout(self)
        layout.setSpacing(4)

        columns = max(1, math.ceil(math.sqrt(len(cameras)))) if cameras else 1
        for index, (camera_id, name) in enumerate(cameras):
            tile = CameraTile(camera_id, name)
            self.tiles[camera_id] = tile
            row, col = divmod(index, columns)
            layout.addWidget(tile, row, col)

    def update_camera(self, camera_id: str, frame, connected: bool, result):
        tile = self.tiles.get(camera_id)
        if tile is not None:
            tile.update_frame(frame, connected, result)
