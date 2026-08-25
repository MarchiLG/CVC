"""
geometry.py

Funções geométricas puras compartilhadas pelos TaskAnalyzers: centro
de uma bbox, ponto dentro de polígono (zonas), sobreposição entre
bboxes, e lado de um ponto em relação a uma linha (usado para
contagem por cruzamento de linha).
"""


def bbox_center(bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


def point_in_polygon(point: tuple[float, float], polygon: list) -> bool:
    """Ray casting. polygon: lista de (x, y) com pelo menos 3 pontos."""
    x, y = point
    inside = False
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            x_intersect = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < x_intersect:
                inside = not inside
    return inside


def line_side(point: tuple[float, float], p1: tuple[float, float], p2: tuple[float, float]) -> int:
    """Sinal do produto vetorial (p2-p1) x (point-p1): +1 de um lado da
    linha, -1 do outro, 0 sobre a linha. Usado para detectar quando um
    track cruza counting_line."""
    x, y = point
    x1, y1 = p1
    x2, y2 = p2
    cross = (x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)
    if cross > 0:
        return 1
    if cross < 0:
        return -1
    return 0


def bbox_overlaps(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    inter_w = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    inter_h = max(0.0, min(ay2, by2) - max(ay1, by1))
    return (inter_w * inter_h) > 0
