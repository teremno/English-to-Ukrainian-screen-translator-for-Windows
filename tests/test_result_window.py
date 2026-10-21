"""Regression checks for the one-capture popup lifecycle."""

from __future__ import annotations

import time

from PySide6.QtCore import QPoint, QRect, QSettings, QSize
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QSizeGrip

from screen_translator import app as translator_app


def test_result_font_and_window_size_are_readable_and_saved(tmp_path) -> None:
    qapp = QApplication.instance() or QApplication([])
    settings = QSettings(str(tmp_path / "display.ini"), QSettings.Format.IniFormat)
    dialog = translator_app.ResultDialog(settings)

    assert dialog.size() == QSize(720, 560)
    assert dialog.source.font().pointSize() == 14
    assert dialog.target.font().pointSize() == 14
    assert dialog.findChild(QSizeGrip) is not None

    dialog.larger_button.click()
    dialog.larger_button.click()
    assert dialog.font_size_label.text() == "16 pt"
    assert dialog.source.font().pointSize() == 16
    assert dialog.target.font().pointSize() == 16
    dialog.smaller_button.click()
    assert dialog.source.font().pointSize() == 15

    dialog.resize(810, 620)
    dialog.show()
    qapp.processEvents()
    dialog.close()
    reopened = translator_app.ResultDialog(settings)
    assert reopened.size() == QSize(810, 620)
    assert reopened.source.font().pointSize() == 15
    reopened.close()


def test_popup_stays_beside_selection_and_inside_screen() -> None:
    screen = QRect(0, 0, 1920, 1080)
    popup = QSize(420, 300)

    assert translator_app.popup_position(QRect(200, 100, 100, 30), popup, screen) == QPoint(
        311, 100
    )
    assert translator_app.popup_position(QRect(1800, 900, 100, 30), popup, screen) == QPoint(
        1368, 780
    )

    second_screen = QRect(-1920, 0, 1920, 1080)
    position = translator_app.popup_position(QRect(-20, 980, 15, 20), popup, second_screen)
    assert second_screen.contains(QRect(position, popup))


def test_capture_turns_off_but_keeps_result_open_until_closed(monkeypatch, tmp_path) -> None:
    qapp = QApplication.instance() or QApplication([])
    qapp.setQuitOnLastWindowClosed(False)
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(translator_app, "QSettings", lambda *_args: settings)
    monkeypatch.setattr(translator_app.ScreenTranslator, "_show_overlays", lambda _self: None)

    monkeypatch.setattr(translator_app, "recognize_png", lambda _png: "Hello")
    monkeypatch.setattr(translator_app, "translate_groq", lambda _text, _key: "Привіт")
    monkeypatch.setattr(translator_app.keyring, "get_password", lambda _service, _account: "test")
    controller = translator_app.ScreenTranslator(qapp)
    controller.change_mode()
    assert controller.enabled

    controller._capture(b"placeholder", QRect(100, 100, 80, 25))
    assert not controller.enabled
    assert not controller.toggle.enabled
    assert controller.mode_action.text() == "Увімкнути"
    assert controller.result is not None
    assert controller.result.isVisible()

    deadline = time.monotonic() + 5
    while (
        controller.thread is not None
        or (controller.result is not None and controller.result.target.toPlainText() != "Привіт")
    ) and time.monotonic() < deadline:
        QTest.qWait(20)
    assert controller.thread is None
    assert controller.result is not None
    assert controller.result.isVisible()
    assert controller.result.target.toPlainText() == "Привіт"
    controller.result.close()
    QTest.qWait(50)
    assert controller.result is None
    assert controller.toggle.isVisible()
    assert not controller.enabled
    assert not qapp.closingDown()

    controller.tray.hide()
    controller.toggle.close()
