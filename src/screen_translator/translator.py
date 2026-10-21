"""Azure Translator adapter; only OCR text leaves the computer."""

from __future__ import annotations

import json
import random
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

TRANSLATE_URL = (
    "https://api.cognitive.microsofttranslator.com/translate?api-version=3.0&from=en&to=uk"
)
MAX_TEXT_LENGTH = 5000


class TranslationError(RuntimeError):
    """A user-facing translation failure with no credential data."""


def translate(text: str, key: str, region: str = "") -> str:
    """Translate one bounded English fragment; retry only transient failures."""
    source = text.strip()
    if not source:
        raise TranslationError("No English text was found in the selected area.")
    if len(source) > MAX_TEXT_LENGTH:
        raise TranslationError("The selected text is too long. Please select a smaller area.")
    if not key.strip():
        raise TranslationError("Set an Azure Translator F0 key in Settings first.")

    headers = {
        "Ocp-Apim-Subscription-Key": key.strip(),
        "Content-Type": "application/json; charset=UTF-8",
    }
    if region.strip():
        headers["Ocp-Apim-Subscription-Region"] = region.strip()
    payload = json.dumps([{"Text": source}], ensure_ascii=False).encode("utf-8")

    for attempt in range(2):
        request = Request(TRANSLATE_URL, data=payload, headers=headers, method="POST")
        try:
            with urlopen(request, timeout=10) as response:
                result = json.load(response)
            translated = result[0]["translations"][0]["text"].strip()
            if not translated:
                raise TranslationError("The translator returned an empty result.")
            return translated
        except HTTPError as exc:
            if exc.code in (429, 502, 503, 504) and attempt == 0:
                # One bounded retry; this endpoint only computes a translation.
                time.sleep(0.2 + random.uniform(0, 0.2))
                continue
            if exc.code in (401, 403):
                raise TranslationError("Azure rejected the key or the free quota is exhausted.") from None
            if exc.code == 429:
                raise TranslationError("Azure rate limit reached. Try again later.") from None
            raise TranslationError(f"Translation service returned HTTP {exc.code}.") from None
        except (TimeoutError, URLError):
            if attempt == 0:
                time.sleep(0.2 + random.uniform(0, 0.2))
                continue
            raise TranslationError("Could not reach the translation service.") from None
        except (ValueError, KeyError, IndexError, TypeError):
            raise TranslationError("The translation service returned an invalid response.") from None
    raise TranslationError("Translation was unavailable.")
