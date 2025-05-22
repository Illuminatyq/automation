"""
Базовый класс для всех страниц
"""
from playwright.sync_api import Page, TimeoutError
from datetime import datetime
import logging
import os
from config.constants import DEFAULT_TIMEOUT, SCREENSHOTS_DIR

class BasePage:
    def __init__(self, page: Page, base_url: str = None, timeout: int = DEFAULT_TIMEOUT):
        self.page = page
        self.base_url = base_url.rstrip('/') if base_url else None
        self.default_timeout = timeout
        self._setup_logging()

    def _setup_logging(self):
        """Настройка логирования"""
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        log_file = os.path.join(log_dir, f"test_{datetime.now().strftime('%Y%m%d')}.log")
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )

    def navigate(self, path: str = "") -> "BasePage":
        """Переход на страницу"""
        url = f"{self.base_url}/{path.lstrip('/')}" if self.base_url else path
        self.page.goto(url)
        self.page.wait_for_load_state("networkidle", timeout=self.default_timeout)
        logging.info(f"Navigated to {url}")
        return self

    def wait_for_element(self, selector: str, timeout: int = None) -> None:
        """Ожидание появления элемента"""
        timeout = timeout or self.default_timeout
        self.page.wait_for_selector(selector, timeout=timeout)

    def click_element(self, selector: str, timeout: int = None) -> "BasePage":
        """Клик по элементу"""
        timeout = timeout or self.default_timeout
        self.page.click(selector, timeout=timeout)
        return self

    def fill_input(self, selector: str, value: str, timeout: int = None) -> "BasePage":
        """Заполнение поля ввода"""
        timeout = timeout or self.default_timeout
        self.page.fill(selector, value, timeout=timeout)
        return self

    def get_text(self, selector: str, timeout: int = None) -> str:
        """Получение текста элемента"""
        timeout = timeout or self.default_timeout
        return self.page.text_content(selector, timeout=timeout)

    def is_element_visible(self, selector: str, timeout: int = None) -> bool:
        """Проверка видимости элемента"""
        timeout = timeout or self.default_timeout
        try:
            self.page.wait_for_selector(selector, state="visible", timeout=timeout)
            return True
        except TimeoutError:
            return False

    def take_screenshot(self, name: str) -> str:
        """Создание скриншота"""
        if not os.path.exists(SCREENSHOTS_DIR):
            os.makedirs(SCREENSHOTS_DIR)
            
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{name}_{timestamp}.png"
        path = os.path.join(SCREENSHOTS_DIR, filename)
        self.page.screenshot(path=path)
        logging.info(f"Screenshot saved: {path}")
        return path 