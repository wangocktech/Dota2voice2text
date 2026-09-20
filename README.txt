Dota2voice2text v0.2.0 — Product Patch

Что добавлено:
- логирование в %LOCALAPPDATA%\Dota2voice2text\logs\app.log;
- ротация логов (до 5 МБ, 3 резервных файла);
- перехват необработанных Python-ошибок;
- кнопка «О программе» в главном окне;
- статус модели RU→EN;
- ручная проверка обновлений;
- тихая фоновая проверка обновлений при запуске;
- фильтрация служебного релиза translation-model-v1;
- поиск только нормальных тегов vX.Y.Z;
- скачивание Windows ZIP в фоне;
- обязательная проверка SHA-256;
- автоустановка только в собранном EXE;
- PUBLISH_APP_RELEASE.ps1, который собирает ZIP + SHA256 и публикует GitHub Release.

Установка:
1. Распаковать этот архив.
2. Открыть PowerShell в распакованной папке.
3. Выполнить:

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\INSTALL_PRODUCT_PATCH.ps1

После установки сначала тестируйте через python app.py.
GitHub Release пока не публикуйте, пока не проверите GUI и сборку EXE.
