"""Qt application coordinator for screen capture, OCR, and translation."""

from __future__ import annotations

import logging
import sys

import keyring
from PySide6.QtCore import QObject, QPoint, QSettings, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
)

from screen_translator.capture import CaptureOverlay, FloatingToggle
from screen_translator.ocr import recognize_png
from screen_translator.translator import TranslationError, translate

KEYRING_SERVICE = "teremno-screen-translator"
KEYRING_ACCOUNT = "azure-translator"
logger = logging.getLogger(__name__)


class TranslationWorker(QObject):
    """Run OCR and translation away from the Qt event loop."""

    completed = Signal(str, str, str)

    def __init__(self, png: bytes, region: str):
        super().__init__()
        self.png = png
        self.region = region

    @Slot()
    def run(self) -> None:
        source = ""
        try:
            source = recognize_png(self.png)
            if not source:
                raise TranslationError("No English text was found in the selected area.")
            key = keyring.get_password(KEYRING_SERVICE, KEYRING_ACCOUNT) or ""
            target = translate(source, key, self.region)
            self.completed.emit(source, target, "")
        except TranslationError as exc:
            self.completed.emit(source, "", str(exc))
        except Exception as exc:  # noqa: BLE001 - redact all OCR and credential failure details
            # Do not include OCR text, screenshots, or credentials in errors.
            logger.error("Recognition failed (%s)", type(exc).__name__)
            self.completed.emit(source, "", "Screen recognition failed. Check Windows OCR settings.")


class ResultDialog(QDialog):
    """Display the OCR source alongside its Ukrainian translation."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Screen Translator")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        self.status = QLabel("Recognizing English text…")
        layout.addWidget(self.status)
        layout.addWidget(QLabel("English text recognized from screen:"))
        self.source = QTextEdit()
        self.source.setReadOnly(True)
        self.source.setMaximumHeight(110)
        layout.addWidget(self.source)
        layout.addWidget(QLabel("Український переклад:"))
        self.target = QTextEdit()
        self.target.setReadOnly(True)
        self.target.setMinimumHeight(100)
        layout.addWidget(self.target)
        close_button = QPushButton("Закрити")
        close_button.clicked.connect(self.close)
        layout.addWidget(close_button)

    def show_result(self, source: str, target: str, error: str) -> None:
        self.source.setPlainText(source)
        self.target.setPlainText(target)
        self.status.setText(error or "Переклад готовий")


class SettingsDialog(QDialog):
    """Collect the Azure key without displaying a stored secret."""

    def __init__(self, settings: QSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Налаштування перекладу")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Використовуй ресурс Azure Translator тарифу F0."))
        form = QFormLayout()
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText("Новий ключ; порожнє поле збереже старий")
        form.addRow("Azure key:", self.key)
        self.region = QLineEdit(str(settings.value("azure_region", "")))
        self.region.setPlaceholderText("Лише для регіонального ресурсу")
        form.addRow("Region:", self.region)
        layout.addLayout(form)
        self.confirm_f0 = QCheckBox("Я перевірив, що мій ресурс Azure має безкоштовний тариф F0")
        self.confirm_f0.setChecked(bool(settings.value("confirmed_f0", False, type=bool)))
        layout.addWidget(self.confirm_f0)
        buttons = QHBoxLayout()
        save_button = QPushButton("Зберегти")
        save_button.clicked.connect(self.save)
        buttons.addWidget(save_button)
        cancel_button = QPushButton("Скасувати")
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)

    def save(self) -> None:
        try:
            if self.key.text().strip():
                keyring.set_password(KEYRING_SERVICE, KEYRING_ACCOUNT, self.key.text().strip())
            self.settings.setValue("azure_region", self.region.text().strip())
            self.settings.setValue("confirmed_f0", self.confirm_f0.isChecked())
            self.settings.sync()
        except Exception as exc:  # noqa: BLE001 - platform key stores raise varied exceptions
            logger.error("Credential storage failed (%s)", type(exc).__name__)
            QMessageBox.warning(self, "Помилка", "Не вдалося зберегти ключ у Windows Credential Manager.")
            return
        self.accept()


def _app_icon() -> QIcon:
    image = QPixmap(32, 32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#177245"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(1, 1, 30, 30)
    painter.setPen(QColor("white"))
    painter.drawText(image.rect(), Qt.AlignmentFlag.AlignCenter, "У")
    painter.end()
    return QIcon(image)


class ScreenTranslator(QObject):
    """Own the floating switch, overlays, and one translation at a time."""

    def __init__(self, app: QApplication):
        super().__init__(app)
        self.app = app
        self.settings = QSettings("teremno", "ScreenTranslator")
        self.enabled = False
        self._quitting = False
        self.overlays: list[CaptureOverlay] = []
        self.result: ResultDialog | None = None
        self.thread: QThread | None = None
        self.worker: TranslationWorker | None = None
        self.toggle = FloatingToggle()
        self.toggle.toggled.connect(self.change_mode)
        self.toggle.context_requested.connect(self._show_context_menu)
        self.toggle.moved.connect(lambda point: self.settings.setValue("button_position", point))
        saved_position = self.settings.value("button_position")
        if isinstance(saved_position, QPoint):
            self.toggle.move(saved_position)
        else:
            self.toggle.move(80, 80)
        self.toggle.show()

        self.tray = QSystemTrayIcon(_app_icon(), self.app)
        self.tray.setToolTip("Screen Translator")
        self.menu = QMenu()
        self.mode_action = self.menu.addAction("Увімкнути")
        self.mode_action.triggered.connect(self.change_mode)
        self.menu.addAction("Налаштування", self.open_settings)
        self.menu.addSeparator()
        self.menu.addAction("Вийти", self.request_quit)
        self.tray.setContextMenu(self.menu)
        self.tray.show()

    @Slot(QPoint)
    def _show_context_menu(self, position: QPoint) -> None:
        self.menu.popup(position)

    @Slot()
    def change_mode(self) -> None:
        self.enabled = not self.enabled
        self.toggle.set_enabled(self.enabled)
        self.mode_action.setText("Вимкнути" if self.enabled else "Увімкнути")
        if self.enabled:
            self._show_overlays()
        else:
            self._hide_overlays()
            if self.result is not None:
                self.result.close()

    def _show_overlays(self) -> None:
        if not self.enabled or self.overlays or self.thread is not None:
            return
        for screen in self.app.screens():
            overlay = CaptureOverlay(screen)
            overlay.captured.connect(self._capture)
            overlay.cancelled.connect(self._cancel_capture)
            self.overlays.append(overlay)
        for overlay in self.overlays:
            overlay.show()
        self.toggle.raise_()
        self.toggle.activateWindow()

    def _hide_overlays(self) -> None:
        for overlay in self.overlays:
            overlay.hide()
            overlay.deleteLater()
        self.overlays.clear()

    @Slot()
    def _cancel_capture(self) -> None:
        self.change_mode()

    @Slot(bytes, QPoint)
    def _capture(self, png: bytes, near: QPoint) -> None:
        self._hide_overlays()
        self.result = ResultDialog()
        self.result.move(near + QPoint(12, 12))
        self.result.finished.connect(self._result_closed)
        self.result.open()

        if not self.settings.value("confirmed_f0", False, type=bool):
            self.result.show_result(
                "",
                "",
                "Open Settings and confirm that your Azure resource uses the free F0 tier.",
            )
            return

        self.thread = QThread()
        self.worker = TranslationWorker(png, str(self.settings.value("azure_region", "")))
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.completed.connect(self._translation_completed)
        self.worker.completed.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self._thread_finished)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    @Slot(str, str, str)
    def _translation_completed(self, source: str, target: str, error: str) -> None:
        if self.result is not None and self.result.isVisible():
            self.result.show_result(source, target, error)

    @Slot()
    def _thread_finished(self) -> None:
        self.thread = None
        self.worker = None
        if self._quitting:
            self.app.quit()
            return
        if self.enabled and (self.result is None or not self.result.isVisible()):
            self._show_overlays()

    @Slot(int)
    def _result_closed(self, _code: int) -> None:
        self.result = None
        if self.enabled:
            self._show_overlays()

    @Slot()
    def open_settings(self) -> None:
        if self.enabled:
            self.change_mode()
        SettingsDialog(self.settings).exec()

    @Slot()
    def request_quit(self) -> None:
        self._quitting = True
        self.enabled = False
        self._hide_overlays()
        if self.result is not None:
            self.result.close()
        if self.thread is None:
            self.app.quit()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Screen Translator")
    app.setQuitOnLastWindowClosed(False)
    if "--self-test" in sys.argv:
        from screen_translator.selftest import run_self_test

        return run_self_test()
    ScreenTranslator(app)
    if "--smoke-test" in sys.argv:
        QTimer.singleShot(500, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
