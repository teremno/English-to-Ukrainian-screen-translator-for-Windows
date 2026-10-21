"""Frozen per-monitor capture overlays and draggable floating toggle."""

from __future__ import annotations

from PySide6.QtCore import QBuffer, QByteArray, QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent, QPen, QPixmap
from PySide6.QtWidgets import QWidget


class CaptureOverlay(QWidget):
    """Consume mouse drags on one screen and emit a PNG of the chosen region."""

    captured = Signal(bytes, QRect)
    cancelled = Signal()

    def __init__(self, screen, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setGeometry(screen.geometry())
        self.snapshot: QPixmap = screen.grabWindow(0)
        self._start: QPoint | None = None
        self._selection = QRect()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self.snapshot)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 65))
        if not self._selection.isEmpty():
            painter.setPen(QPen(QColor("#ffd166"), 2))
            painter.setBrush(QColor(0, 120, 215, 55))
            painter.drawRect(self._selection)
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._start = event.position().toPoint()
            self._selection = QRect()
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._start is not None:
            self._selection = QRect(self._start, event.position().toPoint()).normalized()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self._start is None:
            return
        self._selection = QRect(self._start, event.position().toPoint()).normalized()
        self._start = None
        selected = self._selection.intersected(self.rect())
        if selected.width() < 12 or selected.height() < 12:
            self._selection = QRect()
            self.update()
            return

        ratio = self.snapshot.devicePixelRatio()
        pixels = QRect(
            round(selected.x() * ratio),
            round(selected.y() * ratio),
            round(selected.width() * ratio),
            round(selected.height() * ratio),
        ).intersected(self.snapshot.rect())
        cropped = self.snapshot.copy(pixels)
        cropped.setDevicePixelRatio(1.0)
        data = QByteArray()
        buffer = QBuffer(data)
        if not buffer.open(QBuffer.OpenModeFlag.WriteOnly) or not cropped.save(buffer, "PNG"):
            buffer.close()
            self.cancelled.emit()
            return
        buffer.close()
        self.captured.emit(
            bytes(data), QRect(self.mapToGlobal(selected.topLeft()), selected.size())
        )

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
        else:
            super().keyPressEvent(event)


class FloatingToggle(QWidget):
    """Always-on-top switch; dragging moves it, a click toggles capture mode."""

    toggled = Signal()
    moved = Signal(QPoint)
    context_requested = Signal(QPoint)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(76, 76)
        self.setToolTip("Click to turn screen translation on or off. Drag to move.")
        self.setAccessibleName("Screen translation toggle")
        self.enabled = False
        self._press_global: QPoint | None = None
        self._window_origin: QPoint | None = None
        self._dragging = False

    def set_enabled(self, value: bool) -> None:
        self.enabled = value
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#177245") if self.enabled else QColor("#4a5568"))
        painter.setPen(QPen(QColor("white"), 2))
        painter.drawEllipse(4, 4, 68, 68)
        painter.setPen(QColor("white"))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "ON" if self.enabled else "OFF")
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self.context_requested.emit(event.globalPosition().toPoint())
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_global = event.globalPosition().toPoint()
            self._window_origin = self.pos()
            self._dragging = False

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._press_global is None or self._window_origin is None:
            return
        delta = event.globalPosition().toPoint() - self._press_global
        if delta.manhattanLength() > 8:
            self._dragging = True
        if self._dragging:
            self.move(self._window_origin + delta)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self._press_global is None:
            return
        self._press_global = None
        self._window_origin = None
        if self._dragging:
            self.moved.emit(self.pos())
        else:
            self.toggled.emit()
