"""Qt application coordinator for screen capture, OCR, and translation."""

from __future__ import annotations

import logging
import sys

import keyring
from PySide6.QtCore import (
    QObject,
    QPoint,
    QRect,
    QSettings,
    QSize,
    Qt,
    QThread,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
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
from screen_translator.groq_translator import translate as translate_groq
from screen_translator.ocr import recognize_png
from screen_translator.translator import TranslationError
from screen_translator.translator import translate as translate_azure

KEYRING_SERVICE = "teremno-screen-translator"
AZURE_KEYRING_ACCOUNT = "azure-translator"
GROQ_KEYRING_ACCOUNT = "groq"
logger = logging.getLogger(__name__)


class TranslationWorker(QObject):
    """Run OCR and translation away from the Qt event loop."""

    completed = Signal(str, str, str)

    def __init__(self, png: bytes, provider: str, region: str):
        super().__init__()
        self.png = png
        self.provider = provider
        self.region = region

    @Slot()
    def run(self) -> None:
        source = ""
        try:
            source = recognize_png(self.png)
            if not source:
                raise TranslationError("No English text was found in the selected area.")
            if self.provider == "groq":
                key = keyring.get_password(KEYRING_SERVICE, GROQ_KEYRING_ACCOUNT) or ""
                target = translate_groq(source, key)
            elif self.provider == "azure":
                key = keyring.get_password(KEYRING_SERVICE, AZURE_KEYRING_ACCOUNT) or ""
                target = translate_azure(source, key, self.region)
            else:
                raise TranslationError("Невідомий сервіс перекладу. Обери сервіс у налаштуваннях.")
            self.completed.emit(source, target, "")
        except TranslationError as exc:
            self.completed.emit(source, "", str(exc))
        except Exception as exc:  # noqa: BLE001 - redact all OCR and credential failure details
            # Do not include OCR text, screenshots, or credentials in errors.
            logger.error("Recognition or translation failed (%s)", type(exc).__name__)
            self.completed.emit(source, "", "Помилка розпізнавання або перекладу. Перевір налаштування.")


class ResultDialog(QDialog):
    """Display the OCR source alongside its Ukrainian translation."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Screen Translator")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        self.status = QLabel("Розпізнаю англійський текст…")
        layout.addWidget(self.status)
        layout.addWidget(QLabel("Англійський текст з екрана:"))
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


def popup_position(selection: QRect, popup_size: QSize, available: QRect) -> QPoint:
    """Place a result beside the selected area and keep it on the same screen."""
    gap = 12
    right = selection.right() + gap
    left = selection.left() - popup_size.width() - gap
    below = selection.bottom() + gap
    above = selection.top() - popup_size.height() - gap

    if right + popup_size.width() <= available.right() + 1:
        candidate = QPoint(right, selection.top())
    elif left >= available.left():
        candidate = QPoint(left, selection.top())
    elif below + popup_size.height() <= available.bottom() + 1:
        candidate = QPoint(selection.left(), below)
    elif above >= available.top():
        candidate = QPoint(selection.left(), above)
    else:
        candidate = QPoint(selection.center().x(), selection.center().y())

    max_x = max(available.left(), available.right() - popup_size.width() + 1)
    max_y = max(available.top(), available.bottom() - popup_size.height() + 1)
    return QPoint(
        min(max(candidate.x(), available.left()), max_x),
        min(max(candidate.y(), available.top()), max_y),
    )


class SettingsDialog(QDialog):
    """Configure a translation provider without displaying stored secrets."""

    def __init__(self, settings: QSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Налаштування перекладу")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.provider = QComboBox()
        self.provider.addItem("Groq Free Plan", "groq")
        self.provider.addItem("Azure Translator F0", "azure")
        saved_provider = str(settings.value("provider", "groq"))
        self.provider.setCurrentIndex(max(0, self.provider.findData(saved_provider)))
        self.provider.currentIndexChanged.connect(self._provider_changed)
        form.addRow("Сервіс перекладу:", self.provider)
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText("Новий ключ; порожнє поле збереже старий")
        self.key_label = QLabel()
        form.addRow(self.key_label, self.key)
        self.region = QLineEdit(str(settings.value("azure_region", "")))
        self.region.setPlaceholderText("Лише для регіонального ресурсу")
        self.region_label = QLabel("Azure Region:")
        form.addRow(self.region_label, self.region)
        layout.addLayout(form)
        self.provider_info = QLabel()
        self.provider_info.setWordWrap(True)
        self.provider_info.setOpenExternalLinks(True)
        layout.addWidget(self.provider_info)
        self.confirm_f0 = QCheckBox("Я перевірив, що мій ресурс Azure має безкоштовний тариф F0")
        self.confirm_f0.setChecked(bool(settings.value("confirmed_f0", False, type=bool)))
        layout.addWidget(self.confirm_f0)
        self._provider_changed()
        buttons = QHBoxLayout()
        save_button = QPushButton("Зберегти")
        save_button.clicked.connect(self.save)
        buttons.addWidget(save_button)
        cancel_button = QPushButton("Скасувати")
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)

    def _provider_changed(self) -> None:
        is_azure = self.provider.currentData() == "azure"
        self.key_label.setText("Azure key:" if is_azure else "Groq API key:")
        self.region_label.setVisible(is_azure)
        self.region.setVisible(is_azure)
        self.confirm_f0.setVisible(is_azure)
        if is_azure:
            self.provider_info.setText("Azure потребує ресурсу Translator тарифу F0.")
        else:
            self.provider_info.setText(
                'Створи ключ на <a href="https://console.groq.com/keys">console.groq.com/keys</a> '
                "і залишайся на Groq Free Plan. Платний Developer може виставляти рахунки."
            )

    def save(self) -> None:
        try:
            provider = str(self.provider.currentData())
            if self.key.text().strip():
                account = GROQ_KEYRING_ACCOUNT if provider == "groq" else AZURE_KEYRING_ACCOUNT
                keyring.set_password(KEYRING_SERVICE, account, self.key.text().strip())
            self.settings.setValue("provider", provider)
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

    def _show_overlays(self) -> None:
        if (
            not self.enabled
            or self.overlays
            or self.thread is not None
            or (self.result is not None and self.result.isVisible())
        ):
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

    @Slot(bytes, QRect)
    def _capture(self, png: bytes, selection: QRect) -> None:
        self._hide_overlays()
        self.enabled = False
        self.toggle.set_enabled(False)
        self.mode_action.setText("Увімкнути")
        self.result = ResultDialog()
        self.result.finished.connect(self._result_closed)
        self.result.show()
        screen = self.app.screenAt(selection.center()) or self.app.primaryScreen()
        if screen is not None:
            self.result.move(
                popup_position(selection, self.result.frameGeometry().size(), screen.availableGeometry())
            )
        self.result.raise_()
        self.result.activateWindow()

        provider = str(self.settings.value("provider", "groq"))
        if provider == "azure" and not self.settings.value("confirmed_f0", False, type=bool):
            self.result.show_result(
                "",
                "",
                "Відкрий налаштування та підтвердь безкоштовний тариф Azure F0.",
            )
            return

        self.thread = QThread()
        self.worker = TranslationWorker(
            png, provider, str(self.settings.value("azure_region", ""))
        )
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
        # Qt is still returning from QDialog.close here. Release its Python owner
        # on the next event-loop turn so the native widget remains alive meanwhile.
        QTimer.singleShot(0, self._release_closed_result)
        if self.enabled:
            self._show_overlays()

    def _release_closed_result(self) -> None:
        if self.result is not None and not self.result.isVisible():
            self.result.deleteLater()
            self.result = None

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
    controller = ScreenTranslator(app)
    if "--smoke-test" in sys.argv:
        QTimer.singleShot(500, app.quit)
    exit_code = app.exec()
    controller.tray.hide()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
