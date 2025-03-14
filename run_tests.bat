@echo off
echo Запуск тестов...

REM Очистка старых результатов
if exist allure-results (
    echo Удаление старых результатов...
    rmdir /s /q allure-results
)
mkdir allure-results

REM Запуск API-тестов
echo Запуск API-тестов...
python -m pytest tests/test_api.py -v --env=dev --alluredir=./allure-results

REM Запуск UI-тестов
echo Запуск UI-тестов...
python -m pytest tests/test_auth.py tests/test_ui_layout.py -v --env=dev --browser=chromium --alluredir=./allure-results

REM Запуск сервера Allure
echo Запуск сервера Allure...
allure serve ./allure-results

echo Тесты завершены. 