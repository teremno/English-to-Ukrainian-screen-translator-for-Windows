$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
uv sync --extra dev
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
# Isolate binary discovery from unrelated tools on the caller's PATH. In
# particular, third-party ICU/UCRT DLLs can make the frozen Qt app fail to load.
$venvScripts = Join-Path $PSScriptRoot '.venv\Scripts'
$env:PATH = @(
    $venvScripts,
    (Join-Path $env:SystemRoot 'System32'),
    $env:SystemRoot,
    (Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0')
) -join ';'
& (Join-Path $venvScripts 'pyinstaller.exe') --noconfirm --clean --windowed --onedir --name ScreenTranslator --collect-submodules winrt launcher.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }
Write-Output (Join-Path $PSScriptRoot 'dist\ScreenTranslator\ScreenTranslator.exe')
