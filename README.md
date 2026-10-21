# Screen Translator

A small Windows app for translating English text found in any selected screen region into Ukrainian. It uses Windows OCR locally and Groq or Azure for text translation.

This repository is under development. The app can be built and installed for the current Windows user, but the full mouse-driven walkthrough and live provider translation have not yet been verified.

## Development

Requires Windows 11, Python 3.13, and the English (`en-US`) Windows OCR language pack.

```powershell
uv sync --extra dev
uv run screen-translator
```

The default provider is **Groq Free Plan**. Create a key at [GroqCloud API Keys](https://console.groq.com/keys), open Settings from the floating button, and paste the key into the **Groq API key** field. Stay on the Free Plan; it has [model-specific request and token limits](https://console.groq.com/docs/rate-limits). Groq requires a payment method to [upgrade to its paid Developer tier](https://console.groq.com/docs/billing-faqs). The app uses `openai/gpt-oss-120b` on Groq for English-to-Ukrainian text translation. The `openai/` prefix is part of the model name; requests go to Groq's API, not to OpenAI. Live translation quality still needs a user-key test.

Azure Translator is optional. If using Azure, create a Translator **F0** resource, select Azure in Settings, enter its key, and confirm its F0 tier. The app cannot query either provider for the account's billing tier. Screenshots stay on the computer; only recognized text is sent for translation. Keys are kept in Windows Credential Manager, not in this repository.

The floating button toggles capture mode and can be dragged to a new position. When capture mode is on, a frozen screen image accepts a left-button rectangle; click the floating button again to leave capture mode. After a result window closes, capture mode refreshes so another area can be selected.

Right-click the floating button, or use its system tray icon, to open Settings or quit. `Esc` cancels capture mode. Protected video, Windows secure desktop, and some elevated windows may not be capturable. Capture rectangles currently stay within one monitor; mixed-DPI and multiple monitors need a real desktop walkthrough.

## Build and install on Windows

```powershell
.\build.ps1
.\install.ps1
```

The build creates `dist/ScreenTranslator/ScreenTranslator.exe` with a bundled Python runtime. The installer copies it to `%LOCALAPPDATA%\Programs\ScreenTranslator` and adds a Start Menu shortcut. It does not add automatic startup. Before distribution, test the executable on a clean Windows 11 machine and decide the project's license and signing approach.

## Development checks

```powershell
uv run pytest
uv run ruff check .
```
