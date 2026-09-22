# Автоматизация тестирования

Проект автоматизации тестирования с использованием Playwright и Python.

## Структура проекта

```
├── config/             # Конфигурационные файлы
├── locators/          # Локаторы элементов
├── pages/             # Page Objects
├── tests/             # Тесты
├── utils/             # Вспомогательные утилиты
├── logs/              # Логи выполнения (в .gitignore)
├── test_results/      # Результаты тестирования (в .gitignore)
└── screenshots/       # Скриншоты (в .gitignore)
```

## Требования

- Python 3.11
- Playwright
- pytest
- allure-pytest

## Установка

1. Клонируйте репозиторий:
```bash
git clone <repository-url>
cd automation
```

2. Создайте виртуальное окружение и активируйте его:
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

4. Установите браузеры для Playwright:
```bash
playwright install
```

## Конфигурация

- Основные настройки в `config/config.json`. Чувствительные данные берутся из переменных окружения.
- Создайте файл `.env` на основе примера ниже или задайте переменные окружения в CI.

### .env.example
```dotenv
# API ключи
LINER_API_KEY=your_api_key_here

# Тестовые пользователи
# Укажите реальные креды для тестового окружения
TEST_USER_EMAIL=test@example.com
TEST_USER_PASSWORD=your_test_password_here

# Креды оператора (для тестов телефонии)
TEST_OPERATOR_EMAIL=operator@example.com
TEST_OPERATOR_PASSWORD=your_operator_password_here

# Режимы моков телефонии
USE_MOCK=true
TELEPHONY_USE_MOCKS=true
USE_VOXIMPLANT_MOCK=true

# Интеграция с Graylog (опционально)
GRAYLOG_ENABLED=false
GRAYLOG_URL=graylog.example.com
GRAYLOG_PORT=12201
```

**Важно:** Создайте файл `.env` на основе `.env.example` и заполните реальными значениями. Файл `.env` должен быть в `.gitignore` и не попадать в репозиторий.

## Запуск тестов

### Запуск всех тестов
```bash
pytest
```

### Запуск конкретного теста
```bash
pytest tests/test_auth.py
```

### Запуск с генерацией отчета Allure
```bash
pytest --alluredir=test_results/allure-results
allure serve test_results/allure-results
```

### Запуск тестов авторизации
```bash
# Все тесты авторизации
pytest tests/test_auth.py -v

# Только smoke тесты
pytest tests/test_auth.py -m smoke

# С указанием окружения
pytest tests/test_auth.py --env=dev
```

## Allure отчеты

Проект использует улучшенные Allure отчеты с:
- Детальной информацией об окружении
- Метаданными тестов (параметры, ссылки, категории)
- Автоматическим прикреплением скриншотов
- Структурированными шагами тестов
- Метриками производительности
- Маскированием чувствительных данных

### Улучшения в отчетах

- **Информация об окружении**: автоматически добавляется в каждый отчет
- **Тестовые данные**: прикрепляются с автоматическим маскированием паролей
- **Детали ошибок**: полная трассировка и контекст ошибок
- **Метрики производительности**: время выполнения, статусы операций
- **Информация о страницах**: URL, заголовки, viewport

## Интеграция с Graylog

Проект поддерживает интеграцию с Graylog для централизованного логирования. Подробности в [документации](docs/graylog_integration.md).

Для включения интеграции:
1. Установите `GRAYLOG_ENABLED=true` в `.env`
2. Укажите `GRAYLOG_URL` с адресом сервера Graylog

Интеграция автоматически отправляет:
- События начала/завершения тестов
- События начала/завершения сессий
- Детали ошибок
- Статистику выполнения

## Логирование и артефакты

- Все артефакты пишутся в `test_results/` (логи, отчеты, видео, скриншоты) и игнорируются Git.

## Качество кода

- Конфигурации `black`, `isort`, `flake8`, `mypy`, `bandit` заданы в `pyproject.toml` и `.flake8`.
- Быстрая проверка перед пушем:
```bash
black . && isort . && flake8 . && mypy . --ignore-missing-imports
```

## Примечания

- Проект использует только Playwright для UI. Остатки Selenium удалены/не используются.
- Для CI используется workflow в `.github/workflows/ci.yml`.

## Подготовка к заливке на сервер/CI

- Очистка локальных артефактов:
```bash
rm -rf test_results allure-results allure-report logs __pycache__
```
- Подготовка коммита (пример):
```bash
git checkout -b ci-cd-integration
git add .
# убедитесь, что не добавлены секреты в config/config.json
git commit -m "chore: refactor configs, unify allure paths, remove selenium, add CI"
```
- Переменные CI:
  - `LINER_API_KEY`, `TEST_USER_EMAIL`, `TEST_USER_PASSWORD`, `TEST_OPERATOR_EMAIL`, `TEST_OPERATOR_PASSWORD` 