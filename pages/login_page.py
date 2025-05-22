from playwright.sync_api import TimeoutError, Page, expect
from pages.base_page import BasePage
from locators.login_locators import LoginLocators
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class LoginPage(BasePage):
    def __init__(self, page: Page, base_url: str = None, timeout: int = None):
        super().__init__(page, base_url, timeout)
        self.locators = LoginLocators()
        self.default_timeout = 30000  # Уменьшаем таймаут до 30 секунд
        self.short_timeout = 5000     # Короткий таймаут для быстрых операций

    def enter_username(self, username: str):
        """Ввод имени пользователя"""
        try:
            self.fill_input(self.locators.USERNAME_INPUT, username)
            logging.info(f"Введено имя пользователя: {username}")
        except Exception as e:
            logging.error(f"Ошибка при вводе имени пользователя: {str(e)}")
            raise

    def enter_password(self, password: str):
        """Ввод пароля"""
        try:
            self.fill_input(self.locators.PASSWORD_INPUT, password)
            logging.info("Пароль введен")
        except Exception as e:
            logging.error(f"Ошибка при вводе пароля: {str(e)}")
            raise

    def click_login(self):
        """Нажатие кнопки входа"""
        try:
            self.click_element(self.locators.LOGIN_BUTTON)
            logging.info("Нажата кнопка входа")
            
            # Ждем загрузки DOM
            self.page.wait_for_load_state("domcontentloaded", timeout=self.short_timeout)
            
            # Пытаемся дождаться networkidle, но продолжаем если таймаут
            try:
                self.page.wait_for_load_state("networkidle", timeout=self.short_timeout)
            except Exception:
                logging.warning("Превышен таймаут ожидания networkidle, продолжаем выполнение")
            
            # Проверяем наличие ключевых элементов на странице
            try:
                # Проверяем успешный вход
                if self.page.locator(self.locators.PROFILE_DROPDOWN).is_visible(timeout=self.short_timeout):
                    logging.info("Авторизация успешна - найден профиль пользователя")
                    return True
                
                # Проверяем наличие ошибки
                if self.page.locator(self.locators.ERROR_NOTIFICATION).is_visible(timeout=self.short_timeout):
                    error_text = self.page.locator(self.locators.ERROR_NOTIFICATION).text_content()
                    logging.warning(f"Получено сообщение об ошибке: {error_text}")
                    return False
                
                # Проверяем URL
                current_url = self.page.url
                if "/office/" in current_url:
                    logging.info("Авторизация успешна - выполнен редирект")
                    return True
                
                logging.error("Не удалось определить результат авторизации")
                return False
                
            except Exception as e:
                logging.error(f"Ошибка при проверке результата авторизации: {str(e)}")
                return False
            
        except Exception as e:
            logging.error(f"Ошибка при нажатии кнопки входа: {str(e)}")
            raise

    def login(self, email: str, password: str) -> "LoginPage":
        self.navigate()
        self.enter_username(email)
        self.enter_password(password)
        self.click_login()
        logging.info(f"Login attempted with email: {email}")
        return self

    def click_forgot_password(self) -> "LoginPage":
        self.click_element(self.locators.FORGOT_PASSWORD_LINK)
        self.page.wait_for_load_state("networkidle", timeout=self.default_timeout)
        logging.info("Clicked forgot password link")
        return self

    def request_password_reset(self, email: str) -> "LoginPage":
        self.navigate()
        self.click_forgot_password()
        self.enter_username(email)
        self.click_element("button[type='submit']")
        self.page.wait_for_load_state("networkidle", timeout=self.default_timeout)
        
        if not self.is_success_message_displayed():
            self.take_screenshot("recovery_no_success")
        return self

    def logout(self):
        """Выход из системы"""
        try:
            # Ждем появления дропдауна
            self.page.wait_for_selector(self.locators.PROFILE_DROPDOWN, timeout=self.short_timeout)
            
            # Кликаем по дропдауну
            self.page.locator(self.locators.PROFILE_DROPDOWN).click()
            
            # Ждем появления меню и кликаем по кнопке выхода
            self.page.wait_for_selector(self.locators.LOGOUT_BUTTON, timeout=self.short_timeout)
            self.page.locator(self.locators.LOGOUT_BUTTON).click()
            
            # Ждем редиректа на страницу авторизации
            self.page.wait_for_url("**/auth/**", timeout=self.short_timeout)
            
            # Проверяем, что мы на странице авторизации
            if not self.page.locator(self.locators.LOGIN_FORM).is_visible(timeout=self.short_timeout):
                raise Exception("Не удалось подтвердить выход из системы")
            
            logging.info("Выход из системы выполнен успешно")
            return True
            
        except Exception as e:
            logging.error(f"Ошибка при выходе из системы: {str(e)}")
            return False

    def is_error_message_displayed(self) -> bool:
        """Проверка наличия сообщения об ошибке"""
        try:
            return self.page.locator(self.locators.ERROR_NOTIFICATION).is_visible(timeout=self.short_timeout)
        except Exception:
            return False

    def get_error_message(self) -> str:
        """Получение текста сообщения об ошибке"""
        try:
            if self.is_error_message_displayed():
                return self.page.locator(self.locators.ERROR_NOTIFICATION).text_content()
            return ""
        except Exception:
            return ""

    def is_success_message_displayed(self) -> bool:
        """Проверка наличия сообщения об успехе"""
        try:
            return self.page.locator(self.locators.SUCCESS_NOTIFICATION).is_visible(timeout=self.short_timeout)
        except Exception:
            return False