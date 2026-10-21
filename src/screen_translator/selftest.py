"""Packaged runtime check for Windows OCR and Qt image conversion."""

from __future__ import annotations

from PySide6.QtCore import QBuffer, QByteArray, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter

from screen_translator.ocr import recognize_png


def run_self_test() -> int:
    image = QImage(900, 180, QImage.Format.Format_RGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    painter.setPen(QColor("black"))
    painter.setFont(QFont("Arial", 42))
    painter.drawText(image.rect(), Qt.AlignmentFlag.AlignCenter, "Hello World")
    painter.end()
    data = QByteArray()
    buffer = QBuffer(data)
    if not buffer.open(QBuffer.OpenModeFlag.WriteOnly) or not image.save(buffer, "PNG"):
        return 2
    buffer.close()
    result = recognize_png(bytes(data))
    return 0 if "Hello" in result and "World" in result else 3
