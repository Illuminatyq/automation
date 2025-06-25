from playwright.sync_api import Page, expect
from pages.base_page import BasePage
from locators.login_locators import LoginLocators
from config.constants import DEFAULT_TIMEOUT, SHORT_TIMEOUT
import allure
import logging
import sys

# Настройка логирования с явным указанием кодировки
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

class LoginPage(BasePage):
    """Страница авторизации"""
    
    def __init__(self, page: Page, base_url: str = None):
        super().__init__(page, base_url)
        self.locators = LoginLocators()
        self.logger = logging.getLogger(__name__)

    @allure.step("Ввод имени пользователя: {username}")
    def enter_username(self, username: str) -> "LoginPage":
        """Ввод имени пользователя с проверкой"""
        try:
            self.fill_input(self.locators.USERNAME_INPUT, username, timeout=30000)
            self.logger.info(f"Введено имя пользователя: {username}")
            return self
        except Exception as e:
            self.logger.error(f"Ошибка при вводе имени пользователя: {str(e)}")
            raise

    @allure.step("Ввод пароля")
    def enter_password(self, password: str) -> "LoginPage":
        """Ввод пароля с проверкой"""
        try:
            self.fill_input(self.locators.PASSWORD_INPUT, password, timeout=30000)
            self.logger.info("Пароль введен успешно")
            return self
        except Exception as e:
            self.logger.error(f"Ошибка при вводе пароля: {str(e)}")
            raise

    @allure.step("Нажатие кнопки входа")
    def click_login_button(self) -> bool:
        """Нажатие кнопки входа с проверкой результата"""
        try:
            self.click_element(self.locators.LOGIN_BUTTON)
            self.logger.info("Нажата кнопка входа")
            self.wait_for_page_load()
            return self._check_login_result()
        except Exception as e:
            self.logger.error(f"Ошибка при нажатии кнопки входа: {str(e)}")
            self.take_error_screenshot("login_button_click_error")
            raise

    def _check_login_result(self) -> bool:
        """Проверка результата авторизации"""
        try:
            # Ждем полной загрузки страницы
            self.wait_for_page_load()
            
            # Проверяем наличие профиля пользователя - это надежный признак успешной авторизации
            # Используем тот же локатор, что и в методе logout
            if self.is_element_visible(self.locators.PROFILE_DROPDOWN, timeout=20000):
                self.logger.info("Авторизация успешна - найден профиль пользователя")
                return True

            # Если профиль не найден, проверяем наличие сообщения об ошибке
            if self.is_element_visible(self.locators.ERROR_NOTIFICATION, timeout=SHORT_TIMEOUT):
                error_text = self.get_text(self.locators.ERROR_NOTIFICATION)
                self.logger.warning(f"Получено сообщение об ошибке: {error_text}")
                self.take_error_screenshot("error_message_displayed")
                return False

            # Если ни профиль, ни ошибка не найдены, считаем авторизацию неуспешной
            self.logger.warning("Профиль пользователя не найден, и сообщение об ошибке не отображено. Авторизация неуспешна или страница не загрузилась полностью.")
            self.take_error_screenshot("login_failed_no_profile_or_error")
            return False
        except Exception as e:
            self.logger.error(f"Ошибка при проверке результата авторизации: {str(e)}")
            self.take_error_screenshot("check_login_result_exception")
            return False

    @allure.step("Очистка данных сессии")
    def clear_session_data(self) -> "LoginPage":
        """Безопасная очистка куки и локального хранилища"""
        try:
            self.page.context.clear_cookies()
            self.page.evaluate("""
                try {
                    if (typeof Storage !== 'undefined') {
                        if (window.localStorage) {
                            localStorage.clear();
                        }
                        if (window.sessionStorage) {
                            sessionStorage.clear();
                        }
                    }
                } catch (e) {
                    console.log('Storage clear error (expected in some environments):', e.message);
                }
            """)
            self.logger.info("Данные сессии очищены")
            return self
        except Exception as e:
            self.logger.warning(f"Частичная ошибка при очистке данных сессии (это может быть нормально): {str(e)}")
            return self

    @allure.step("Установка флага 'Запомнить пользователя'")
    def set_remember_me(self, remember: bool = True) -> "LoginPage":
        """Установка флага 'Запомнить пользователя'"""
        try:
            checkbox = self.page.locator(self.locators.REMEMBER_ME_CHECKBOX)
            if checkbox.is_visible():
                if remember:
                    if not checkbox.is_checked():
                        checkbox.check()
                else:
                    if checkbox.is_checked():
                        checkbox.uncheck()
                self.logger.info(f"Флаг 'Запомнить пользователя' установлен в {remember}")
            return self
        except Exception as e:
            self.logger.error(f"Ошибка при установке флага 'Запомнить пользователя': {str(e)}")
            return self

    @allure.step("Принудительный переход к форме авторизации")
    def force_navigate_to_login(self) -> "LoginPage":
        """Принудительный переход к форме авторизации с проверкой состояния"""
        try:
            self.clear_session_data()
            self.page.goto(self.base_url)
            self.wait_for_page_load()

            # Проверяем, если мы уже авторизованы (проверяем наличие дропдауна профиля)
            # Если PROFILE_DROPDOWN_TOGGLE виден, значит мы авторизованы и нужно выйти
            if self.is_element_visible(self.locators.PROFILE_DROPDOWN_TOGGLE, timeout=SHORT_TIMEOUT):
                self.logger.info("Пользователь все еще авторизован после очистки сессии, выполняем выход.")
                try:
                    self.logout()
                    # После выхода, убеждаемся, что форма логина готова
                    if not self.is_login_form_ready():
                        raise Exception("После выхода форма авторизации не готова.")
                except Exception as logout_error:
                    self.logger.warning(f"Ошибка при выходе во время принудительного перехода: {logout_error}")
                    # Если выход не удался, попробуем еще раз перейти на страницу логина
                    self.page.goto(self.base_url)
                    self.wait_for_page_load()
                    if not self.is_login_form_ready():
                        raise Exception("Не удалось вернуться на форму авторизации после неудачного выхода.")
            
            # Если мы все еще не на форме логина, значит что-то пошло не так
            if not self.is_login_form_ready():
                raise Exception("Не удалось принудительно перейти к форме авторизации: форма не найдена после всех попыток.")
            return self
        except Exception as e:
            self.logger.error(f"Ошибка при принудительном переходе к авторизации: {str(e)}")
            self.take_error_screenshot("force_navigate_error")
            raise

    # Алиас для обратной совместимости
    click_login = click_login_button

    @allure.step("Полная авторизация пользователя")
    def login(self, email: str, password: str, remember: bool = True) -> bool:
        """Полный процесс авторизации"""
        try:
            self.force_navigate_to_login()
            if self._check_login_result():
                self.logger.info("Пользователь уже авторизован")
                return True
            if not self.is_login_form_ready():
                raise Exception("Форма авторизации не готова для заполнения")
            self.enter_username(email)
            self.enter_password(password)
            self.set_remember_me(remember)
            result = self.click_login_button()
            if result:
                self.logger.info(f"Успешная авторизация пользователя: {email}")
            else:
                self.logger.error(f"Неудачная авторизация пользователя: {email}")
            return result
        except Exception as e:
            self.logger.error(f"Ошибка при авторизации: {str(e)}")
            self.take_error_screenshot("login_process_error")
            raise

    @allure.step("Выход из системы")
    def logout(self) -> bool:
        """Выход из системы"""
        try:
            # Ждем появления выпадающего меню профиля
            self.page.wait_for_selector(self.locators.PROFILE_DROPDOWN, state="visible", timeout=30000)
            # Кликаем по кнопке выпадающего меню
            self.page.click(self.locators.PROFILE_DROPDOWN_TOGGLE)
            # Ждем появления меню и кнопки выхода
            self.page.wait_for_selector(self.locators.LOGOUT_BUTTON, state="visible", timeout=5000)
            # Кликаем по кнопке выхода
            self.page.click(self.locators.LOGOUT_BUTTON)
            # Ждем завершения запросов
            self.page.wait_for_load_state("networkidle")
            # Проверяем, что мы действительно вышли
            if not self.is_login_form_ready():
                raise Exception("Выход из системы не был выполнен успешно")
            self.logger.info("Выход из системы выполнен успешно")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка при выходе из системы: {str(e)}")
            self.take_error_screenshot("logout_error")
            return False

    @allure.step("Переход на страницу восстановления пароля")
    def navigate_to_forgot_password(self) -> "LoginPage":
        """Переход на страницу восстановления пароля"""
        try:
            self.click_element(self.locators.FORGOT_PASSWORD_LINK)
            self.wait_for_page_load()
            current_url = self.get_current_url()
            if not ("forgot" in current_url.lower() or "reset" in current_url.lower()):
                raise Exception("Не удалось перейти на страницу восстановления пароля")
            self.logger.info("Переход на страницу восстановления пароля выполнен")
            return self
        except Exception as e:
            self.logger.error(f"Ошибка при переходе на страницу восстановления: {str(e)}")
            self.take_error_screenshot("forgot_password_navigation_error")
            raise

    def is_error_message_displayed(self) -> bool:
        """Проверка наличия сообщения об ошибке"""
        try:
            self.page.wait_for_selector(self.locators.ERROR_NOTIFICATION, state="visible", timeout=SHORT_TIMEOUT)
            return self.is_element_visible(self.locators.ERROR_NOTIFICATION, timeout=SHORT_TIMEOUT)
        except Exception as e:
            self.logger.warning(f"Ошибка при проверке сообщения: {str(e)}")
            self.take_error_screenshot("error_message_check_timeout")
            return False

    def get_error_message(self) -> str:
        """Получение текста сообщения об ошибке"""
        try:
            if self.is_error_message_displayed():
                error_element = self.page.locator(self.locators.ERROR_NOTIFICATION)
                return error_element.text_content().strip()
            return ""
        except Exception as e:
            self.logger.error(f"Ошибка при получении текста ошибки: {str(e)}")
            return ""

    def is_success_message_displayed(self) -> bool:
        """Проверка наличия сообщения об успехе"""
        try:
            self.page.wait_for_selector("#toast-container", timeout=5000)
            return self.is_element_visible(self.locators.SUCCESS_NOTIFICATION, timeout=5000)
        except Exception as e:
            self.logger.warning(f"Ошибка при проверке сообщения: {str(e)}")
            return False

    def get_success_message(self) -> str:
        """Получение текста сообщения об успехе"""
        try:
            if self.is_success_message_displayed():
                success_element = self.page.locator(self.locators.SUCCESS_NOTIFICATION)
                return success_element.text_content().strip()
            return ""
        except Exception as e:
            self.logger.error(f"Ошибка при получении текста успеха: {str(e)}")
            return ""

    @allure.step("Проверка готовности формы авторизации")
    def is_login_form_ready(self) -> bool:
        """Проверка готовности формы к заполнению"""
        try:
            self.wait_for_page_load()
            login_form = self.page.locator(self.locators.LOGIN_FORM)
            if not login_form.is_visible(timeout=30000):
                self.logger.warning("Форма авторизации не найдена")
                return False
            form_elements = [
                (self.locators.USERNAME_INPUT, "поле email"),
                (self.locators.PASSWORD_INPUT, "поле пароля"),
                (self.locators.LOGIN_BUTTON, "кнопка входа")
            ]
            for element_locator, element_name in form_elements:
                element = self.page.locator(element_locator)
                if not element.is_visible(timeout=30000):
                    self.logger.warning(f"{element_name} не найдено")
                    return False
                if "input" in element_locator and not element.is_enabled():
                    self.logger.warning(f"{element_name} недоступно для ввода")
                    return False
            login_button = self.page.locator(self.locators.LOGIN_BUTTON)
            if not login_button.is_enabled():
                self.logger.warning("Кнопка входа недоступна")
                return False
            button_text = login_button.text_content().strip()
            if "Войти" not in button_text:
                self.logger.warning(f"Неожиданный текст кнопки входа: {button_text}")
            self.logger.info("Форма авторизации готова к работе")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка при проверке готовности формы: {str(e)}")
            self.take_error_screenshot("form_ready_check_error")
            return False