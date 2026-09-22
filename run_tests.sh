#!/usr/bin/env bash
set -euo pipefail

# Очистка старых результатов
rm -rf test_results/allure-results || true
mkdir -p test_results/allure-results

# Установка браузеров (если не установлены)
playwright install || true

# API тесты
python -m pytest tests/test_api.py -v --env=dev --alluredir=./test_results/allure-results

# UI тесты
python -m pytest tests/test_auth.py tests/test_ui_layout.py -v --env=dev --browser=chromium --alluredir=./test_results/allure-results

# Локальный просмотр отчета
allure serve ./test_results/allure-results 