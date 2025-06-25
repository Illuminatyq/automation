import os
import json
from pathlib import Path

# Базовые пути проекта
PROJECT_ROOT = Path(__file__).parent.parent
TEST_RESULTS_DIR = PROJECT_ROOT / "test_results"
SCREENSHOTS_DIR = TEST_RESULTS_DIR / "screenshots"
LOGS_DIR = TEST_RESULTS_DIR / "logs"
REPORTS_DIR = TEST_RESULTS_DIR / "reports"
ALLURE_RESULTS_DIR = TEST_RESULTS_DIR / "allure-results"

# Загрузка конфигурации из config.json
CONFIG_PATH = PROJECT_ROOT / "config" / "config.json"
try:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        CONFIG = json.load(f)
except Exception as e:
    print(f"Ошибка загрузки config.json: {e}")
    CONFIG = {}

# Создаем директории при импорте
for directory in [TEST_RESULTS_DIR, SCREENSHOTS_DIR, LOGS_DIR, REPORTS_DIR, ALLURE_RESULTS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Временные интервалы (в миллисекундах для Playwright)
DEFAULT_TIMEOUT = CONFIG.get("timeout", 30) * 1000  # 30 секунд по умолчанию
PAGE_LOAD_TIMEOUT = 60000  # 60 секунд
IMPLICIT_WAIT = 10000  # 10 секунд
SHORT_TIMEOUT = 10000  # 10 секунд

# Браузеры
SUPPORTED_BROWSERS = ["chromium", "firefox", "webkit"]
DEFAULT_BROWSER = CONFIG.get("browser", "chromium")

# Сообщения об ошибках
ERROR_MESSAGES = {
    "element_not_found": "Элемент не найден на странице",
    "timeout": "Превышено время ожидания",
    "invalid_credentials": "Неверные учетные данные",
    "page_not_loaded": "Страница не загрузилась",
    "authorization_failed": "Ошибка авторизации"
}

# Настройки для скриншотов
SCREENSHOT_CONFIG = {
    "full_page": True,
    "type": "png"
}

# Настройки для визуального тестирования
VISUAL_TESTING = {
    "threshold": 0.1,  # 10% различий
    "cleanup_days": 7
}

# Настройки окружения
ENVIRONMENTS = CONFIG.get("environments", {})
DEFAULT_ENVIRONMENT = CONFIG.get("defaultEnvironment", "dev")