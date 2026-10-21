"""Verify Azure request shape and safe failure messages without network calls."""

from __future__ import annotations

import io
import json
from urllib.error import HTTPError

import pytest

from screen_translator import translator


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def test_translator_sends_only_text_to_azure(monkeypatch) -> None:
    seen = {}

    def fake_open(request, timeout):
        seen["url"] = request.full_url
        seen["body"] = json.loads(request.data)
        seen["headers"] = request.headers
        seen["timeout"] = timeout
        return FakeResponse('[{"translations":[{"text":"Привіт"}]}]'.encode())

    monkeypatch.setattr(translator, "urlopen", fake_open)
    assert translator.translate("Hello", "test-key", "westeurope") == "Привіт"
    assert seen["url"].endswith("from=en&to=uk")
    assert seen["body"] == [{"Text": "Hello"}]
    assert seen["timeout"] == 10
    assert seen["headers"]["Ocp-apim-subscription-key"] == "test-key"


def test_auth_error_does_not_expose_key(monkeypatch) -> None:
    def fake_open(request, timeout):
        raise HTTPError(request.full_url, 401, "unauthorized", {}, None)

    monkeypatch.setattr(translator, "urlopen", fake_open)
    with pytest.raises(translator.TranslationError) as error:
        translator.translate("Hello", "private-test-key")
    assert "private-test-key" not in str(error.value)
    assert "key" in str(error.value).lower()
