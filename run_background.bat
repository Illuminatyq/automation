@echo off
echo Запуск тестов в фоновом режиме...

REM Активация виртуального окружения
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)

REM Запуск тестов в фоновом режиме с headless браузером
start /B python -m pytest tests/test_auth.py tests/test_ui_layout.py -v --alluredir=./allure-results --browser=chromium --headless

REM Ждем завершения тестов (примерно 30 секунд)
timeout /t 30 /nobreak

REM Запуск Allure в фоновом режиме
start /B allure serve ./allure-results --config-file ./config/allure_config.json

echo.
echo Тесты запущены в фоновом режиме.
echo Отчет Allure будет доступен через несколько секунд.
echo.
echo Для просмотра результатов откройте браузер по адресу, указанному выше.
echo.
pause 