"""
Константы для проекта автоматизации тестирования
"""

# Временные интервалы
DEFAULT_TIMEOUT = 10
PAGE_LOAD_TIMEOUT = 30
IMPLICIT_WAIT = 5

# URL
BASE_URL = "https://example.com"  # Замените на ваш базовый URL

# Пути к файлам
SCREENSHOTS_DIR = "screenshots"
LOGS_DIR = "logs"
REPORTS_DIR = "reports"

# Браузеры
SUPPORTED_BROWSERS = ["chrome", "firefox", "safari"]

# Сообщения об ошибках
ERROR_MESSAGES = {
    "element_not_found": "Элемент не найден на странице",
    "timeout": "Превышено время ожидания",
    "invalid_credentials": "Неверные учетные данные"
} 