@echo off
echo Запуск тестов...

REM Запуск тестов напрямую
python -m pytest tests/test_auth.py tests/test_ui_layout.py -v --alluredir=./allure-results

REM Запуск Allure
allure serve ./allure-results

pause 