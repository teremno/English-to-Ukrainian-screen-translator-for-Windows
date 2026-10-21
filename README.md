# Screen Translator

A small Windows app for translating English text found in any selected screen region into Ukrainian. It uses Windows OCR locally and Groq or Azure for text translation.

This repository is under development. The local image → Windows OCR → Groq → Ukrainian result path has been verified with a small live request. A full mouse-driven walkthrough on other Windows setups still needs verification.

## Development

Requires Windows 11, Python 3.13, and the English (`en-US`) Windows OCR language pack.

```powershell
uv sync --extra dev
uv run screen-translator
```

The default provider is **Groq Free Plan**. Create a key at [GroqCloud API Keys](https://console.groq.com/keys), open Settings from the floating button, and paste the key into the **Groq API key** field. Stay on the Free Plan; it has [model-specific request and token limits](https://console.groq.com/docs/rate-limits). Groq requires a payment method to [upgrade to its paid Developer tier](https://console.groq.com/docs/billing-faqs). The app uses `openai/gpt-oss-120b` on Groq for English-to-Ukrainian text translation. The `openai/` prefix is part of the model name; requests go to Groq's API, not to OpenAI.

Azure Translator is optional. If using Azure, create a Translator **F0** resource, select Azure in Settings, enter its key, and confirm its F0 tier. The app cannot query either provider for the account's billing tier. Screenshots stay on the computer; only recognized text is sent for translation. Keys are kept in Windows Credential Manager, not in this repository.

The floating button toggles capture mode and can be dragged to a new position. When capture mode is on, a frozen screen image accepts a left-button rectangle. The result window shows only the Ukrainian translation beside the selection on the same screen and stays open until you close it. On failure it shows a Ukrainian error instead of an empty result. The floating button switches to OFF after each capture; click it again when you want another translation.

The result window starts at a readable size with 14 pt text. Use **A−** and **A+** (or `Ctrl+-` and `Ctrl++`) to change the text size. Drag a window edge or its bottom-right grip to resize the window. Both sizes are remembered for the next translation.

Right-click the floating button, or use its system tray icon, to open Settings or quit. `Esc` cancels capture mode. Protected video, Windows secure desktop, and some elevated windows may not be capturable. Capture rectangles currently stay within one monitor; mixed-DPI and multiple monitors need a real desktop walkthrough.

## Build and install on Windows

```powershell
.\build.ps1
.\install.ps1
```

The build creates `dist/ScreenTranslator/ScreenTranslator.exe` with a bundled Python runtime. The installer copies it to `%LOCALAPPDATA%\Programs\ScreenTranslator` and adds a Start Menu shortcut. It does not add automatic startup. Before distribution, test the executable on a clean Windows 11 machine and decide the project's license and signing approach.

For an optional live check of the installed build, run `ScreenTranslator.exe --live-self-test`. It uses the stored Groq key for one short API request, prints no secret, and exits with code 0 only when OCR and Ukrainian translation both succeed.

## Development checks

```powershell
uv run pytest
uv run ruff check .
```
