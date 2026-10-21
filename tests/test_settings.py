"""Ensure the selected provider saves its key under the right account."""

from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from screen_translator import app


def test_groq_is_default_and_uses_separate_credential_account(monkeypatch, tmp_path) -> None:
    qapp = QApplication.instance() or QApplication([])
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    saved = {}
    monkeypatch.setattr(app.keyring, "set_password", lambda service, account, key: saved.update(
        service=service, account=account, key=key
    ))

    dialog = app.SettingsDialog(settings)
    assert dialog.provider.currentData() == "groq"
    assert dialog.confirm_f0.isHidden()
    dialog.provider.setCurrentIndex(1)
    assert not dialog.confirm_f0.isHidden()
    dialog.provider.setCurrentIndex(0)
    assert dialog.confirm_f0.isHidden()
    dialog.key.setText("test-groq-key")
    dialog.save()

    assert settings.value("provider") == "groq"
    assert saved == {
        "service": app.KEYRING_SERVICE,
        "account": app.GROQ_KEYRING_ACCOUNT,
        "key": "test-groq-key",
    }
    assert qapp is not None
