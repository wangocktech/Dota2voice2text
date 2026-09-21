Dota2voice2text v0.3.0 — Onboarding + Microphone Test

Что добавлено:
- мастер первого запуска;
- 3 шага onboarding;
- выбор микрофона;
- живой индикатор уровня;
- тест микрофона в главном окне;
- кнопка «Настройка» в шапке;
- onboarding_completed в config.json;
- повторный запуск мастера в любой момент.

Установка:
1. Распаковать архив.
2. Открыть PowerShell в распакованной папке.
3. Запустить:

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\INSTALL_V030_ONBOARDING.ps1

Потом:
& ".\.venv313\Scripts\python.exe" ".\app.py"
