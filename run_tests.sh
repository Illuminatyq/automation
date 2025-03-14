#!/bin/bash
echo "Запуск тестов..."

# Очистка старых результатов
if [ -d "allure-results" ]; then
    echo "Удаление старых результатов..."
    rm -rf allure-results
fi
mkdir -p allure-results

# Запуск API-тестов
echo "Запуск API-тестов..."
python -m pytest tests/test_api.py -v --env=dev --alluredir=./allure-results

# Запуск UI-тестов
echo "Запуск UI-тестов..."
python -m pytest tests/test_auth.py tests/test_ui_layout.py -v --env=dev --browser=chromium --alluredir=./allure-results

# Запуск сервера Allure
echo "Запуск сервера Allure..."
allure serve ./allure-results

echo "Тесты завершены." 