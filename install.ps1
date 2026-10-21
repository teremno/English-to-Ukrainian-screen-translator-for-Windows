# Install the built app for the current Windows user.

$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'dist\ScreenTranslator'
$executable = Join-Path $source 'ScreenTranslator.exe'
if (-not (Test-Path -LiteralPath $executable)) {
    throw 'Build the application with .\build.ps1 first.'
}
if (Get-Process -Name 'ScreenTranslator' -ErrorAction SilentlyContinue) {
    throw 'Close ScreenTranslator before installing an update.'
}

$target = Join-Path $env:LOCALAPPDATA 'Programs\ScreenTranslator'
New-Item -ItemType Directory -Force -Path $target | Out-Null
Copy-Item -Path (Join-Path $source '*') -Destination $target -Recurse -Force

$startMenu = [Environment]::GetFolderPath('Programs')
$shortcutPath = Join-Path $startMenu 'Screen Translator.lnk'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = Join-Path $target 'ScreenTranslator.exe'
$shortcut.WorkingDirectory = $target
$shortcut.Description = 'Translate English text from any screen area into Ukrainian'
$shortcut.Save()

Write-Output (Join-Path $target 'ScreenTranslator.exe')
Write-Output $shortcutPath
