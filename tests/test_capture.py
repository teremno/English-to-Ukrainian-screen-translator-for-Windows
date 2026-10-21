"""Check that mouse drag captures the matching image pixels."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication

from screen_translator.capture import CaptureOverlay


class FakeScreen:
    def __init__(self):
        self.image = QPixmap(200, 100)
        self.image.fill(QColor("red"))

    def geometry(self):
        return QRect(0, 0, 200, 100)

    def grabWindow(self, _window_id):
        return self.image


def test_drag_returns_cropped_png() -> None:
    app = QApplication.instance() or QApplication([])
    overlay = CaptureOverlay(FakeScreen())
    spy = QSignalSpy(overlay.captured)
    overlay.show()
    app.processEvents()

    QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=QPoint(20, 15))
    QTest.mouseMove(overlay, QPoint(100, 55))
    QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=QPoint(100, 55))

    assert spy.count() == 1
    png, _position = spy.at(0)
    image = QImage.fromData(png, "PNG")
    assert image.width() >= 80
    assert image.height() >= 40
    assert image.pixelColor(0, 0) == QColor("red")
    overlay.close()
