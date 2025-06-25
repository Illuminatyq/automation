from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, expect
from datetime import datetime
import logging
import allure
from typing import Optional, Union
from config.constants import (
    DEFAULT_TIMEOUT, PAGE_LOAD_TIMEOUT, SCREENSHOTS_DIR, 
    ERROR_MESSAGES, SCREENSHOT_CONFIG
)

class BasePage:
    """Базовый класс для всех страниц приложения"""
    
    def __init__(self, page: Page, base_url: Optional[str] = None):
        self.page = page
        self.base_url = base_url.rstrip('/') if base_url else None
        self.logger = logging.getLogger(self.__class__.__name__)

    @allure.step("Переход на страницу: {path}")
    def navigate(self, path: str = "") -> "BasePage":
        """Переход на страницу с улучшенной обработкой ошибок"""
        url = f"{self.base_url}/{path.lstrip('/')}" if self.base_url else path
        
        try:
            self.page.goto(url, timeout=PAGE_LOAD_TIMEOUT)
            self.wait_for_page_load()
            self.logger.info(f"Успешный переход на {url}")
            return self
        except Exception as e:
            self.logger.error(f"Ошибка при переходе на {url}: {str(e)}")
            self.take_error_screenshot(f"navigation_error_{datetime.now().strftime('%H%M%S')}")
            raise

    def wait_for_page_load(self, timeout: int = PAGE_LOAD_TIMEOUT) -> None:
        """Ожидание полной загрузки страницы"""
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=timeout)
            # Убираем ожидание networkidle, так как оно может быть слишком строгим
            self.logger.info("Страница загружена")
        except PlaywrightTimeoutError:
            self.logger.warning("Превышен таймаут ожидания загрузки страницы, продолжаем выполнение")

    @allure.step("Ожидание элемента: {selector}")
    def wait_for_element(self, selector: str, timeout: int = DEFAULT_TIMEOUT, state: str = "visible") -> None:
        """Ожидание появления элемента с улучшенной диагностикой"""
        try:
            self.page.wait_for_selector(selector, state=state, timeout=timeout)
        except PlaywrightTimeoutError:
            self.logger.error(f"Элемент {selector} не найден в течение {timeout}мс")
            self.take_error_screenshot(f"element_not_found_{datetime.now().strftime('%H%M%S')}")
            raise TimeoutError(f"{ERROR_MESSAGES['element_not_found']}: {selector}")

    @allure.step("Клик по элементу: {selector}")
    def click_element(self, selector: str, timeout: int = DEFAULT_TIMEOUT) -> "BasePage":
        """Клик по элементу с проверками"""
        try:
            element = self.page.locator(selector)
            element.wait_for(state="visible", timeout=timeout)
            element.click(timeout=timeout)
            self.logger.info(f"Клик по элементу {selector}")
            return self
        except Exception as e:
            self.logger.error(f"Ошибка при клике по {selector}: {str(e)}")
            self.take_error_screenshot(f"click_error_{datetime.now().strftime('%H%M%S')}")
            raise

    @allure.step("Заполнение поля: {selector}")
    def fill_input(self, selector: str, value: str, timeout: int = DEFAULT_TIMEOUT) -> "BasePage":
        """Заполнение поля ввода с очисткой и проверками"""
        try:
            # Ждем появления элемента
            element = self.page.locator(selector)
            element.wait_for(state="visible", timeout=timeout)
            
            # Проверяем, что элемент интерактивен
            if not element.is_enabled():
                raise Exception(f"Элемент {selector} неактивен")
            
            # Очищаем поле
            element.clear()
            
            # Заполняем значение
            element.fill(value)
            
            # Проверяем, что значение установлено
            actual_value = element.input_value()
            if actual_value != value:
                self.logger.warning(f"Значение не установлено корректно. Ожидалось: {value}, получено: {actual_value}")
                # Пробуем еще раз
                element.fill(value)
            
            self.logger.info(f"Поле {selector} заполнено значением: {value}")
            return self
            
        except Exception as e:
            self.logger.error(f"Ошибка при заполнении {selector}: {str(e)}")
            self.take_error_screenshot(f"fill_error_{datetime.now().strftime('%H%M%S')}")
            raise

    def get_text(self, selector: str, timeout: int = DEFAULT_TIMEOUT) -> str:
        """Получение текста элемента"""
        try:
            element = self.page.locator(selector)
            element.wait_for(state="visible", timeout=timeout)
            return element.text_content() or ""
        except Exception as e:
            self.logger.error(f"Ошибка при получении текста {selector}: {str(e)}")
            return ""

    def is_element_visible(self, selector: str, timeout: int = DEFAULT_TIMEOUT) -> bool:
        """Проверка видимости элемента"""
        try:
            element = self.page.locator(selector)
            element.wait_for(state="visible", timeout=timeout)
            return True
        except PlaywrightTimeoutError:
            return False

    def is_element_present(self, selector: str) -> bool:
        """Проверка наличия элемента в DOM"""
        return self.page.locator(selector).count() > 0

    @allure.step("Создание скриншота")
    def take_screenshot(self, name: str) -> str:
        """Создание скриншота с улучшенным именованием"""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{name}_{timestamp}.png"
        path = SCREENSHOTS_DIR / filename
        
        self.page.screenshot(path=str(path), **SCREENSHOT_CONFIG)
        allure.attach.file(str(path), name=f"Скриншот: {name}", attachment_type=allure.attachment_type.PNG)
        self.logger.info(f"Скриншот сохранен: {path}")
        return str(path)

    def take_error_screenshot(self, name: str) -> str:
        """Создание скриншота при ошибке"""
        error_dir = SCREENSHOTS_DIR / "errors"
        error_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"ERROR_{name}_{timestamp}.png"
        path = error_dir / filename
        
        # Проверяем, есть ли реальная ошибка на странице
        error_elements = self.page.locator('.error-message, .alert-error, .alert-danger, .error, .danger')
        if error_elements.count() > 0:
            self.page.screenshot(path=str(path), **SCREENSHOT_CONFIG)
            allure.attach.file(str(path), name=f"Ошибка: {name}", attachment_type=allure.attachment_type.PNG)
            self.logger.error(f"Скриншот ошибки сохранен: {path}")
            return str(path)
        else:
            self.logger.info("Скриншот ошибки не создан, так как на странице нет видимых ошибок")
            return ""

    def scroll_to_element(self, selector: str) -> "BasePage":
        """Прокрутка к элементу"""
        try:
            element = self.page.locator(selector)
            element.scroll_into_view_if_needed()
            return self
        except Exception as e:
            self.logger.error(f"Ошибка при прокрутке к {selector}: {str(e)}")
            raise

    def wait_for_url_contains(self, url_part: str, timeout: int = DEFAULT_TIMEOUT) -> None:
        """Ожидание изменения URL"""
        try:
            self.page.wait_for_url(f"**/*{url_part}*", timeout=timeout)
        except PlaywrightTimeoutError:
            current_url = self.page.url
            self.logger.error(f"URL не содержит '{url_part}'. Текущий URL: {current_url}")
            raise TimeoutError(f"URL не изменился. Ожидали: {url_part}, получили: {current_url}")

    def get_current_url(self) -> str:
        """Получение текущего URL"""
        return self.page.url

    def assert_element_visible(self, selector: str, error_message: str = None) -> None:
        """Проверка видимости элемента с автоматическим скриншотом при ошибке"""
        try:
            element = self.page.locator(selector)
            expect(element).to_be_visible()
        except AssertionError:
            self.take_error_screenshot(f"assert_visible_{selector.replace('.', '_').replace('#', '_')}")
            raise AssertionError(error_message or f"Элемент {selector} не виден")

    def assert_element_has_text(self, selector: str, expected_text: str) -> None:
        """Проверка текста элемента"""
        try:
            element = self.page.locator(selector)
            expect(element).to_have_text(expected_text)
        except AssertionError:
            actual_text = self.get_text(selector)
            self.take_error_screenshot(f"assert_text_{selector.replace('.', '_').replace('#', '_')}")
            raise AssertionError(f"Ожидался текст '{expected_text}', получен '{actual_text}'")