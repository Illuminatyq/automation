# Автоматизация тестирования

Проект автоматизации тестирования с использованием Playwright и Python.

## Структура проекта

```
├── config/             # Конфигурационные файлы
├── locators/          # Локаторы элементов
├── pages/             # Page Objects
├── tests/             # Тесты
├── utils/             # Вспомогательные утилиты
├── logs/              # Логи выполнения
├── reports/           # Отчеты о тестировании
└── screenshots/       # Скриншоты
```

## Требования

- Python 3.8+
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
source venv/bin/activate  # для Linux/Mac
venv\Scripts\activate     # для Windows
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

4. Установите браузеры для Playwright:
```bash
playwright install
```

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
pytest --alluredir=allure-results
allure serve allure-results
```

## Структура тестов

- `tests/test_auth.py` - тесты авторизации
- `tests/test_ui_layout.py` - тесты верстки
- `tests/test_api.py` - API тесты

## Логирование

Логи сохраняются в директории `logs/` с датой в имени файла.

## Скриншоты

Скриншоты сохраняются в директории `screenshots/` при возникновении ошибок или по требованию теста.

## Конфигурация

Основные настройки находятся в файле `config/constants.py`:
- Таймауты
- URL
- Пути к файлам
- Поддерживаемые браузеры 