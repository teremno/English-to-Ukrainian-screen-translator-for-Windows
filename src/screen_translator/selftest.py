"""Packaged runtime checks for OCR and an optional live Groq translation."""

from __future__ import annotations

from PySide6.QtCore import QBuffer, QByteArray, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter

from screen_translator.groq_translator import translate
from screen_translator.ocr import recognize_png


def _sample_png() -> bytes | None:
    """Render a small English sample without reading the user's screen."""
    image = QImage(900, 180, QImage.Format.Format_RGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    painter.setPen(QColor("black"))
    painter.setFont(QFont("Arial", 42))
    painter.drawText(image.rect(), Qt.AlignmentFlag.AlignCenter, "Hello World")
    painter.end()
    data = QByteArray()
    buffer = QBuffer(data)
    if not buffer.open(QBuffer.OpenModeFlag.WriteOnly):
        return None
    saved = image.save(buffer, "PNG")
    buffer.close()
    return bytes(data) if saved else None


def run_self_test() -> int:
    png = _sample_png()
    if png is None:
        return 2
    result = recognize_png(png)
    return 0 if "Hello" in result and "World" in result else 3


def run_live_self_test(key: str) -> int:
    """Verify bundled OCR and one real Groq call; never print the credential."""
    if not key:
        return 4
    png = _sample_png()
    if png is None:
        return 2
    try:
        source = recognize_png(png)
        if "Hello" not in source or "World" not in source:
            return 3
        translated = translate(source, key)
    except Exception:  # noqa: BLE001 - diagnostics expose only a process exit code
        return 5
    return 0 if any("\u0400" <= char <= "\u04ff" for char in translated) else 6
