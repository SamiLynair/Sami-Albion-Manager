"""Read genuine item icons from a bundled offline ZIP without making requests."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import zipfile

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap


DEFAULT_ARCHIVE = Path(__file__).resolve().parent / "assets" / "item_icons.zip"
QUALITY_COLORS = {
    1: "#687365", 2: "#83aa68", 3: "#5dabe5",
    4: "#b18be5", 5: "#edc16f",
}


class OfflineIconStore:
    def __init__(self, path: Path = DEFAULT_ARCHIVE):
        self._zip = zipfile.ZipFile(path) if path.is_file() else None
        self._names = set(self._zip.namelist()) if self._zip else set()

    @property
    def count(self) -> int:
        return len(self._names)

    def has_icon(self, item_id: str) -> bool:
        return f"{item_id}.webp" in self._names

    @lru_cache(maxsize=1024)
    def icon(self, item_id: str, quality: int = 1) -> QIcon:
        # Keep the full resolution of the locally stored render. Qt scales the
        # same icon down in the table while the detail panel stays sharp.
        canvas = QPixmap(96, 96)
        # The bundled WEBP artwork already has transparent corners. Preserve
        # them instead of drawing an opaque dark square on parchment rows.
        canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        name = f"{item_id}.webp"
        if name in self._names:
            icon = QPixmap()
            if icon.loadFromData(self._zip.read(name), "WEBP"):
                scaled = icon.scaled(94, 94, Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation)
                painter.drawPixmap((96 - scaled.width()) // 2,
                                   (96 - scaled.height()) // 2, scaled)
        else:
            painter.setPen(QColor("#788a79"))
            font = painter.font()
            font.setPointSize(30)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(canvas.rect(), Qt.AlignmentFlag.AlignCenter, "?")

        if quality > 1:
            painter.setPen(QPen(QColor(QUALITY_COLORS.get(quality, "#687365")), 3))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(canvas.rect().adjusted(2, 2, -3, -3), 8, 8)
        painter.end()
        return QIcon(canvas)

    def close(self):
        if self._zip:
            self._zip.close()
            self._zip = None
