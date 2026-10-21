"""A real Windows OCR check using a generated image."""

from __future__ import annotations

import sys

import pytest
from PySide6.QtCore import QBuffer, QByteArray, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtWidgets import QApplication

from screen_translator.ocr import recognize_png


@pytest.mark.skipif(sys.platform != "win32", reason="Windows OCR only")
def test_windows_ocr_reads_clear_english() -> None:
    application = QApplication.instance() or QApplication([])
    assert application is not None
    image = QImage(900, 180, QImage.Format.Format_RGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    painter.setPen(QColor("black"))
    painter.setFont(QFont("Arial", 42))
    painter.drawText(image.rect(), Qt.AlignmentFlag.AlignCenter, "Hello World")
    painter.end()

    data = QByteArray()
    buffer = QBuffer(data)
    assert buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    assert image.save(buffer, "PNG")
    buffer.close()

    result = recognize_png(bytes(data))
    assert "Hello" in result
    assert "World" in result
