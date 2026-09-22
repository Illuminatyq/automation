from playwright.sync_api import Page, expect
from pages.base_page import BasePage
from pages.base_notifications import BaseNotifications
from locators.login_locators import LoginLocators
from config.constants import DEFAULT_TIMEOUT, SHORT_TIMEOUT
import allure
import logging
import time

class LoginPage(BasePage, BaseNotifications):
    """Оптимизированная страница авторизации с устранением race conditions"""
    
    def __init__(self, page: Page, base_url: str = None):
        BasePage.__init__(self, page, base_url)
        BaseNotifications.__init__(self, page)
        self.locators = LoginLocators()
        self.logger = logging.getLogger(__name__)

    @allure.step("Ввод имени пользователя: {username}")
    def enter_username(self, username: str) -> "LoginPage":
        """Ввод имени пользователя с надежным ожиданием"""
        try:
            username_input = self.page.locator(self.locators.USERNAME_INPUT)
            expect(username_input).to_be_visible(timeout=15000)
            expect(username_input).to_be_enabled(timeout=5000)
            
            username_input.clear()
            username_input.fill(username)
            
            # Проверяем, что значение действительно введено
            expect(username_input).to_have_value(username, timeout=3000)
            
            self.logger.info(f"Введено имя пользователя: {username}")
            return self
        except Exception as e:
            self.logger.error(f"Ошибка при вводе имени пользователя: {str(e)}")
            self.take_error_screenshot("username_input_error")
            raise

    @allure.step("Ввод пароля")
    def enter_password(self, password: str) -> "LoginPage":
        """Ввод пароля с проверкой состояния поля"""
        try:
            password_input = self.page.locator(self.locators.PASSWORD_INPUT)
            expect(password_input).to_be_visible(timeout=15000)
            expect(password_input).to_be_enabled(timeout=5000)
            
            password_input.clear()
            password_input.fill(password)
            
            # Для полей паролей проверяем наличие символов, а не точное значение
            filled_value = password_input.input_value()
            assert len(filled_value) == len(password), "Пароль введен не полностью"
            
            self.logger.info("Пароль введен успешно")
            return self
        except Exception as e:
            self.logger.error(f"Ошибка при вводе пароля: {str(e)}")
            self.take_error_screenshot("password_input_error")
            raise

    @allure.step("Нажатие кнопки входа")
    def click_login_button(self) -> bool:
        """Нажатие кнопки входа с асинхронной проверкой результата"""
        try:
            login_button = self.page.locator(self.locators.LOGIN_BUTTON)
            expect(login_button).to_be_visible(timeout=10000)
            expect(login_button).to_be_enabled(timeout=5000)
            
            # Сохраняем текущий URL для сравнения
            initial_url = self.page.url
            
            login_button.click()
            self.logger.info("Нажата кнопка входа")
            
            # Ждем либо смены URL (успешная авторизация), либо появления ошибки
            return self._wait_for_login_result(initial_url)
            
        except Exception as e:
            self.logger.error(f"Ошибка при нажатии кнопки входа: {str(e)}")
            self.take_error_screenshot("login_button_click_error")
            raise

    def _wait_for_login_result(self, initial_url: str, timeout: int = 20000) -> bool:
        """Асинхронное ожидание результата авторизации"""
        start_time = time.time()
        poll_interval = 0.5

        while (time.time() - start_time) * 1000 < timeout:
            try:
                # Проверяем URL
                current_url = self.page.url
                if current_url != initial_url and ("/office/" in current_url or "/dashboard/" in current_url):
                    self.logger.info(f"Успешная авторизация: переход на {current_url}")
                    return True

                # Проверяем профиль
                profile_dropdown = self.page.locator(self.locators.PROFILE_DROPDOWN_TOGGLE)
                if profile_dropdown.count() > 0 and profile_dropdown.is_visible():
                    self.logger.info("Успешная авторизация: найден дропдаун профиля")
                    return True

                # Проверяем ошибку
                error_container = self.page.locator(self.TOAST_SELECTORS['container'])
                if error_container.count() > 0:
                    error_notification = self.page.locator(self.TOAST_SELECTORS['error']).first
                    if error_notification.count() > 0 and error_notification.is_visible():
                        error_text = error_notification.text_content()
                        self.logger.warning(f"Ошибка авторизации: {error_text}")
                        self.take_error_screenshot("login_error_notification")
                        return False

                time.sleep(poll_interval)
            except Exception as e:
                self.logger.debug(f"Промежуточная ошибка при проверке результата авторизации: {str(e)}")
                time.sleep(poll_interval)

        self.logger.warning("Таймаут при ожидании результата авторизации")
        self.take_error_screenshot("login_timeout")
        allure.attach(self.page.content(), "HTML страницы при таймауте авторизации", allure.attachment_type.HTML)
        return self._final_login_check()

    def _final_login_check(self) -> bool:
        """Финальная проверка состояния авторизации"""
        try:
            # Ждем стабилизации состояния страницы
            self.page.wait_for_load_state("domcontentloaded", timeout=5000)
            
            # Проверяем URL
            current_url = self.page.url
            if "/office/" in current_url or "/dashboard/" in current_url:
                return True
            
            # Проверяем наличие профиля
            profile_elements = self.page.locator(self.locators.PROFILE_DROPDOWN).count()
            if profile_elements > 0:
                return True
            
            # Если ничего не найдено, считаем авторизацию неуспешной
            self.take_error_screenshot("login_final_check_failed")
            return False
            
        except Exception as e:
            self.logger.error(f"Ошибка при финальной проверке авторизации: {str(e)}")
            self.take_error_screenshot("login_final_check_exception")
            return False

    @allure.step("Полная авторизация пользователя")
    def login(self, email: str, password: str, remember: bool = True) -> bool:
        """Оптимизированный процесс авторизации"""
        try:
            # Проверяем, не авторизованы ли мы уже
            if self.is_logged_in():
                self.logger.info("Пользователь уже авторизован")
                return True

            # Убеждаемся, что форма готова
            if not self.is_login_form_ready():
                self.logger.error("Форма авторизации не готова")
                self.take_error_screenshot("login_form_not_ready")
                raise Exception("Форма авторизации не готова")

            # Выполняем авторизацию
            self.enter_username(email)
            self.enter_password(password)

            if remember:
                self.set_remember_me(True)

            result = self.click_login_button()

            if result:
                self.logger.info(f"✅ Успешная авторизация пользователя: {email}")
            else:
                self.logger.error(f"❌ Неудачная авторизация пользователя: {email}")
                self.take_error_screenshot("login_failed")

            return result

        except Exception as e:
            self.logger.error(f"Исключение при авторизации: {str(e)}")
            self.take_error_screenshot("login_process_exception")
            allure.attach(self.page.content(), "HTML страницы при ошибке авторизации", allure.attachment_type.HTML)
            raise

    @allure.step("Выход из системы")
    def logout(self) -> bool:
        """Оптимизированный выход из системы"""
        try:
            if not self.is_logged_in():
                self.logger.info("Пользователь уже не авторизован")
                return True

            # Проверяем, что мы на странице офиса
            current_url = self.page.url
            if "/office/" not in current_url and "/dashboard/" not in current_url:
                self.logger.warning(f"Логаут не со страницы офиса/дашборда, а с: {current_url}")
            profile_dropdown = self.page.locator(self.locators.PROFILE_DROPDOWN_TOGGLE)
            self.logger.info(f"Найдено элементов профиля: {profile_dropdown.count()}")
            if profile_dropdown.count() != 1:
                self.logger.error(f"Ожидался 1 элемент профиля, найдено: {profile_dropdown.count()}")
                self.take_error_screenshot("profile_dropdown_error")
                allure.attach(self.page.content(), "HTML страницы при ошибке дропдауна", allure.attachment_type.HTML)
                return False
            expect(profile_dropdown).to_be_visible(timeout=15000)
            profile_dropdown.click()
            self.logger.info("Кликнули по дропдауну профиля")
            self.take_screenshot("after_profile_dropdown_click")

            logout_button = self.page.locator(self.locators.LOGOUT_BUTTON)
            self.logger.info(f"Найдено элементов кнопки выхода: {logout_button.count()}")
            if logout_button.count() != 1:
                self.logger.error(f"Ожидался 1 элемент кнопки выхода, найдено: {logout_button.count()}")
                self.take_error_screenshot("logout_button_error")
                allure.attach(self.page.content(), "HTML страницы при ошибке кнопки выхода", allure.attachment_type.HTML)
                return False
            expect(logout_button).to_be_visible(timeout=10000)
            logout_button.click()
            self.logger.info("Кликнули по кнопке выхода")
            self.take_screenshot("after_logout_button_click")

            try:
                self.page.wait_for_url("**/auth/**", timeout=20000)
                self.logger.info(f"Редирект после логаута: {self.page.url}")
            except Exception as e:
                self.logger.error(f"Таймаут при ожидании редиректа на /auth/: {str(e)}")
                self.take_error_screenshot("logout_redirect_error")
                allure.attach(self.page.content(), "HTML страницы при ошибке редиректа", allure.attachment_type.HTML)
                return False

            if self.is_login_form_ready():
                self.logger.info("✅ Выход из системы выполнен успешно")
                return True
            else:
                self.logger.error("После выхода форма авторизации недоступна")
                self.take_error_screenshot("login_form_not_ready")
                return False
        except Exception as e:
            self.logger.error(f"Ошибка при выходе из системы: {str(e)}")
            self.take_error_screenshot("logout_error")
            allure.attach(self.page.content(), "HTML страницы при ошибке логаута", allure.attachment_type.HTML)
            return False

    def is_logged_in(self) -> bool:
        """Быстрая проверка авторизации"""
        try:
            # Проверяем URL
            current_url = self.page.url
            if "/office/" in current_url or "/dashboard/" in current_url:
                return True
            
            # Проверяем наличие сайдбара
            sidebar = self.page.locator('.sidebar')
            if sidebar.count() > 0 and sidebar.is_visible():
                return True
            
            # Проверяем наличие профиля
            profile_dropdown = self.page.locator(self.locators.PROFILE_DROPDOWN)
            return profile_dropdown.count() > 0 and profile_dropdown.is_visible()
            
        except Exception:
            return False

    @allure.step("Проверка готовности формы авторизации")
    def wait_for_form(self, timeout: int = 30000) -> None:
        """Ожидание загрузки формы авторизации"""
        form_selectors = [
            'form[action*="auth"]',
            'form[action*="login"]',
            'form.auth-form',
            'form.login-form'
        ]
        form_found = False
        for selector in form_selectors:
            try:
                form = self.page.locator(selector)
                if form.count() > 0:
                    expect(form).to_be_visible(timeout=timeout)
                    self.logger.info(f"Форма авторизации найдена по селектору: {selector}")
                    form_found = True
                    break
            except Exception as e:
                self.logger.warning(f"Ошибка при поиске формы по селектору {selector}: {str(e)}")
        if not form_found:
            raise Exception("Форма авторизации не найдена")

    # Методы для работы с уведомлениями (используем наследование от BaseNotifications)
    def wait_for_error_message(self, expected_text: str = None, timeout: int = 10000) -> bool:
        """Ожидание сообщения об ошибке"""
        return self.wait_for_notification('error', timeout, expected_text)
    
    def get_error_message_text(self) -> str:
        """Получение текста ошибки"""
        return self.get_notification_text('error')
    
    def is_error_message_displayed(self, timeout: int = 3000) -> bool:
        """Проверка наличия сообщения об ошибке"""
        return self.wait_for_notification('error', timeout=timeout)
    
    def wait_for_success_message(self, expected_text: str = None, timeout: int = 5000) -> bool:
        """Ожидание сообщения об успехе"""
        return self.wait_for_notification('success', timeout, expected_text)

    # Вспомогательные методы
    def set_remember_me(self, remember: bool = True) -> "LoginPage":
        """Установка флага 'Запомнить пользователя'"""
        try:
            checkbox = self.page.locator(self.locators.REMEMBER_ME_CHECKBOX)
            if checkbox.count() > 0 and checkbox.is_visible():
                if remember != checkbox.is_checked():
                    checkbox.click()
                self.logger.info(f"Флаг 'Запомнить пользователя' установлен в {remember}")
            return self
        except Exception as e:
            self.logger.warning(f"Не удалось установить флаг 'Запомнить пользователя': {str(e)}")
            return self

    @allure.step("Принудительный переход к форме авторизации")
    def force_navigate_to_login(self) -> "LoginPage":
        """Принудительный переход к форме авторизации с очисткой состояния"""
        try:
            # Переходим на страницу авторизации
            self.navigate()
            
            # Ждем загрузки страницы
            self.page.wait_for_load_state("domcontentloaded", timeout=10000)
            
            # Проверяем, что мы на странице авторизации
            current_url = self.page.url
            if "/auth/" not in current_url and "/login" not in current_url:
                self.logger.warning(f"Не удалось перейти на страницу авторизации. Текущий URL: {current_url}")
                self.take_error_screenshot("force_navigate_failed")
            
            # Ждем готовности формы
            self.wait_for_form()
            
            return self
            
        except Exception as e:
            self.logger.error(f"Ошибка при принудительном переходе к форме авторизации: {str(e)}")
            self.take_error_screenshot("force_navigate_exception")
            raise

    @allure.step("Очистка формы авторизации")
    def clear_form(self) -> "LoginPage":
        """Очистка всех полей формы авторизации"""
        try:
            # Очищаем поле username
            username_input = self.page.locator(self.locators.USERNAME_INPUT)
            if username_input.count() > 0 and username_input.is_visible():
                username_input.clear()
            
            # Очищаем поле password
            password_input = self.page.locator(self.locators.PASSWORD_INPUT)
            if password_input.count() > 0 and password_input.is_visible():
                password_input.clear()
            
            # Сбрасываем чекбокс "Запомнить меня"
            remember_checkbox = self.page.locator(self.locators.REMEMBER_ME_CHECKBOX)
            if remember_checkbox.count() > 0 and remember_checkbox.is_checked():
                try:
                    remember_checkbox.click(force=True)
                except Exception:
                    # Лейбл перекрывает чекбокс — пробуем кликнуть по нему
                    label_locator = self.page.locator(
                        f"{self.locators.REMEMBER_ME_CHECKBOX} + label, .custom-control-label"
                    ).first
                    if label_locator.count() > 0 and label_locator.is_visible():
                        label_locator.click(force=True)
                    else:
                        # Жёсткий fallback через JS, чтобы не блокировать тест
                        self.page.evaluate(
                            """selector => {
                                const el = document.querySelector(selector);
                                if (el) { el.checked = false; el.dispatchEvent(new Event('change', {bubbles: true})); }
                            }""",
                            self.locators.REMEMBER_ME_CHECKBOX,
                        )
            
            self.logger.info("Форма авторизации очищена")
            return self
            
        except Exception as e:
            self.logger.error(f"Ошибка при очистке формы авторизации: {str(e)}")
            self.take_error_screenshot("clear_form_error")
            raise

    @allure.step("Переход на страницу восстановления пароля")
    def navigate_to_forgot_password(self) -> "LoginPage":
        """Переход на страницу восстановления пароля"""
        try:
            forgot_link = self.page.locator(self.locators.FORGOT_PASSWORD_LINK)
            expect(forgot_link).to_be_visible(timeout=5000)
            forgot_link.click()
            
            # Ждем изменения URL
            self.page.wait_for_url("**/*forgot*", timeout=10000)
            
            current_url = self.page.url.lower()
            if not any(keyword in current_url for keyword in ["forgot", "reset", "recovery"]):
                raise Exception(f"Неожиданный URL страницы восстановления: {current_url}")
            
            self.logger.info("✅ Переход на страницу восстановления пароля выполнен")
            return self
            
        except Exception as e:
            self.logger.error(f"Ошибка при переходе на страницу восстановления: {str(e)}")
            self.take_error_screenshot("forgot_password_navigation_error")
            raise

    def is_login_form_ready(self, timeout: int = 5000) -> bool:
        """Проверяет, что форма авторизации готова к работе (есть и видима)"""
        form_selectors = [
            'form[action*="auth"]',
            'form[action*="login"]',
            'form.auth-form',
            'form.login-form'
        ]
        for selector in form_selectors:
            try:
                form = self.page.locator(selector)
                if form.count() > 0 and form.is_visible():
                    self.logger.info(f"Форма авторизации готова по селектору: {selector}")
                    return True
            except Exception as e:
                self.logger.warning(f"Ошибка при поиске формы по селектору {selector}: {str(e)}")
        self.logger.warning("Форма авторизации не готова")
        return False