"""Verify Groq request shape and safe failure handling without a live key."""

from __future__ import annotations

import io
import json
from urllib.error import HTTPError

import pytest

from screen_translator import groq_translator
from screen_translator.translator import TranslationError


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def test_groq_receives_only_ocr_text(monkeypatch) -> None:
    seen = {}

    def fake_open(request, timeout):
        seen["url"] = request.full_url
        seen["body"] = json.loads(request.data)
        seen["headers"] = request.headers
        seen["timeout"] = timeout
        return FakeResponse(
            json.dumps(
                {"choices": [{"message": {"content": "Привіт, світе!"}, "finish_reason": "stop"}]}
            ).encode()
        )

    monkeypatch.setattr(groq_translator, "urlopen", fake_open)
    assert groq_translator.translate("Hello, world!", "test-groq-key") == "Привіт, світе!"
    assert seen["url"] == groq_translator.GROQ_URL
    assert seen["body"]["model"] == groq_translator.GROQ_MODEL
    assert seen["body"]["reasoning_effort"] == "low"
    assert seen["body"]["messages"][1] == {"role": "user", "content": "Hello, world!"}
    assert seen["headers"]["Authorization"] == "Bearer test-groq-key"
    assert seen["headers"]["User-agent"] == groq_translator.USER_AGENT
    assert seen["timeout"] == 15


@pytest.mark.parametrize("status", [401, 429])
def test_groq_errors_do_not_expose_key_or_retry_free_limit(monkeypatch, status) -> None:
    calls = 0

    def fake_open(request, timeout):
        nonlocal calls
        calls += 1
        raise HTTPError(request.full_url, status, "failed", {}, None)

    monkeypatch.setattr(groq_translator, "urlopen", fake_open)
    with pytest.raises(TranslationError) as error:
        groq_translator.translate("Hello", "private-test-groq-key")
    assert "private-test-groq-key" not in str(error.value)
    assert calls == 1


def test_groq_rejects_truncated_response(monkeypatch) -> None:
    def fake_open(request, timeout):
        return FakeResponse(
            b'{"choices":[{"message":{"content":"partial"},"finish_reason":"length"}]}'
        )

    monkeypatch.setattr(groq_translator, "urlopen", fake_open)
    with pytest.raises(TranslationError, match="обірвався"):
        groq_translator.translate("Hello", "test-groq-key")


def test_cloudflare_block_is_not_misreported_as_a_bad_key(monkeypatch) -> None:
    def fake_open(request, timeout):
        raise HTTPError(request.full_url, 403, "blocked", {"Content-Type": "text/plain"}, None)

    monkeypatch.setattr(groq_translator, "urlopen", fake_open)
    with pytest.raises(TranslationError, match="Захист Groq заблокував запит"):
        groq_translator.translate("Hello", "private-test-groq-key")
