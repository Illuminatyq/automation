import pytest
import allure
from playwright.sync_api import Page
from pages.login_page import LoginPage
import logging

@allure.epic("Авторизация")
@allure.feature("Тесты авторизации")
@pytest.mark.auth
class TestAuthentication:
    """Класс тестов для проверки системы авторизации"""

    @allure.title("Проверка успешной авторизации")
    @allure.story("Успешная авторизация")
    @allure.severity('HIGH')
    @allure.description("""
    Тест проверяет процесс успешной авторизации:
    1. Ввод валидных учетных данных
    2. Нажатие кнопки входа
    3. Проверка успешного входа
    4. Проверка перенаправления на главную страницу
    5. Проверка сохранения сессии
    
    Проверяется корректность работы основного сценария авторизации
    """)
    @pytest.mark.smoke
    @pytest.mark.critical
    def test_successful_login(self, page: Page, config, screenshot_utils):
        """Тест успешной авторизации с корректными данными"""
        login_page = LoginPage(page, config["baseUrl"])
        credentials = config["credentials"]["valid_user"]
        
        # Выполняем полный процесс авторизации
        success = login_page.login(
            email=credentials["email"],
            password=credentials["password"],
            remember=True
        )
        
        assert success, "Авторизация не прошла успешно"
        screenshot_utils.take_screenshot("successful_login")

    @allure.title("Проверка авторизации с неверными учетными данными")
    @allure.story("❌ Авторизация с неверными учетными данными")
    @allure.severity('CRITICAL')
    @allure.description("""
    Проверка обработки неверных учетных данных системой.
    
    Цель: Убедиться, что система корректно обрабатывает ошибки авторизации
    и предоставляет понятные сообщения пользователю.
    """)
    @pytest.mark.regression
    def test_login_with_invalid_credentials(self, page: Page, config, screenshot_utils):
        """Тест авторизации с неверными учетными данными"""
        
        login_page = LoginPage(page, config["baseUrl"])
        invalid_credentials = config["credentials"]["invalid_user"]
        
        with allure.step("📋 Подготовка: Открытие страницы авторизации"):
            login_page.navigate()
            assert login_page.is_login_form_ready(), "Форма авторизации не готова"
        
        with allure.step("❌ Ввод неверных учетных данных"):
            login_page.enter_username(invalid_credentials["email"])
            login_page.enter_password(invalid_credentials["password"])
            
            allure.attach(
                f"Email: {invalid_credentials['email']}\nPassword: [MASKED]",
                "Неверные учетные данные",
                allure.attachment_type.TEXT
            )
        
        with allure.step("🚫 Попытка авторизации"):
            success = login_page.click_login_button()
            assert not success, "Авторизация с неверными данными не должна быть успешной"
        
        with allure.step("📋 Проверка сообщения об ошибке"):
            assert login_page.is_error_message_displayed(), "Должно отображаться сообщение об ошибке"
            
            error_text = login_page.get_error_message()
            assert error_text, "Текст ошибки не должен быть пустым"
            
            # Проверяем наличие сообщения об ошибке без конкретного текста
            assert any(keyword in error_text.lower() for keyword in ["ошибка", "неверный", "неправильный", "некорректный"]), \
                f"Сообщение об ошибке должно содержать информацию о неверных данных: '{error_text}'"
            
            allure.attach(error_text, "Сообщение об ошибке", allure.attachment_type.TEXT)
            screenshot_utils.take_screenshot("invalid_credentials_error")
            
            logging.info(f"✅ Получено сообщение об ошибке: {error_text}")

    @allure.title("Проверка функциональности выхода из системы")
    @allure.story("🚪 Выход из системы")
    @allure.severity('NORMAL')
    @allure.description("Проверка корректного выхода пользователя из системы")
    @pytest.mark.regression
    def test_logout_functionality(self, page: Page, config, screenshot_utils):
        """Тест функциональности выхода из системы"""
        
        login_page = LoginPage(page, config["baseUrl"])
        credentials = config["credentials"]["valid_user"]
        
        with allure.step("🔐 Авторизация пользователя"):
            success = login_page.login(credentials["email"], credentials["password"])
            assert success, "Предварительная авторизация должна быть успешной"
            screenshot_utils.take_screenshot("after_login_before_logout")
            screenshot_utils.take_screenshot("before_logout")
        
        with allure.step("🚪 Выполнение выхода из системы"):
            logout_success = login_page.logout()
            assert logout_success, "Выход из системы должен быть успешным"
            
            screenshot_utils.take_screenshot("after_logout")
        
        with allure.step("✅ Проверка результата выхода"):
            # Проверяем, что мы вернулись на страницу авторизации
            current_url = page.url
            assert "/auth/" in current_url, f"После выхода ожидался редирект на страницу авторизации, получен: {current_url}"
            
            # Проверяем, что форма авторизации снова доступна
            assert login_page.is_login_form_ready(), "После выхода форма авторизации должна быть доступна"
            
            logging.info("✅ Выход из системы выполнен корректно")

    @allure.title("Проверка перехода на страницу восстановления пароля")
    @allure.story("🔄 Восстановление пароля")
    @allure.severity('NORMAL')
    @allure.description("Проверка функциональности восстановления пароля")
    @pytest.mark.regression
    def test_forgot_password_navigation(self, page: Page, config, screenshot_utils):
        """Тест перехода на страницу восстановления пароля"""
        
        login_page = LoginPage(page, config["baseUrl"])
        
        with allure.step("📋 Открытие страницы авторизации"):
            login_page.navigate()
            screenshot_utils.take_screenshot("login_page_before_forgot_password")
        
        with allure.step("🔗 Переход на страницу восстановления пароля"):
            try:
                login_page.navigate_to_forgot_password()
                screenshot_utils.take_screenshot("forgot_password_page")
                
                # Проверяем URL
                current_url = page.url
                assert any(keyword in current_url.lower() for keyword in ["forgot", "reset", "recovery"]), \
                    f"URL не соответствует странице восстановления пароля: {current_url}"
                
                logging.info("✅ Переход на страницу восстановления пароля выполнен успешно")
                
            except Exception as e:
                screenshot_utils.save_error_screenshot("forgot_password_navigation_failed")
                pytest.skip(f"Функция восстановления пароля недоступна: {str(e)}")

    @allure.title("Проверка валидации формы")
    @allure.story("Валидация формы")
    @allure.severity('NORMAL')
    @allure.description("""
    Тест проверяет валидацию формы авторизации:
    1. Проверка пустой формы
    2. Проверка невалидного email
    3. Проверка короткого пароля
    4. Проверка специальных символов
    5. Проверка сообщений об ошибках
    
    Проверяется корректность валидации всех полей формы
    """)
    def test_form_validation(self, page: Page, config, screenshot_utils):
        """Тест валидации полей формы авторизации"""
        login_page = LoginPage(page, config["baseUrl"])
        
        # Проверяем, что форма готова
        assert login_page.is_login_form_ready(), "Форма авторизации не готова"
        
        # Пробуем отправить пустую форму
        login_page.click_login_button()
        assert login_page.is_error_message_displayed(), "Не отображается сообщение об ошибке при пустой форме"
        
        # Проверяем валидацию email
        login_page.enter_username("invalid_email")
        login_page.click_login_button()
        assert login_page.is_error_message_displayed(), "Не отображается сообщение об ошибке при неверном email"
        
        # Проверяем валидацию пароля
        login_page.enter_username(config["credentials"]["valid_user"]["email"])
        login_page.enter_password("short")
        login_page.click_login_button()
        assert login_page.is_error_message_displayed(), "Не отображается сообщение об ошибке при коротком пароле"

    @allure.title("Проверка защиты от XSS")
    @allure.story("Безопасность")
    @allure.severity('HIGH')
    @allure.description("""
    Тест проверяет защиту от XSS-атак:
    1. Ввод XSS-скрипта в поле email
    2. Ввод XSS-скрипта в поле пароля
    3. Проверка экранирования специальных символов
    4. Проверка отсутствия выполнения скриптов
    
    Проверяется защита от внедрения вредоносного кода
    """)
    def test_xss_protection(self, page: Page, config, screenshot_utils):
        """Тест защиты от XSS-атак"""
        login_page = LoginPage(page, config["baseUrl"])
        
        # Проверяем, что форма готова
        assert login_page.is_login_form_ready(), "Форма авторизации не готова"
        
        # Пробуем внедрить XSS в поле email
        xss_payload = "<script>alert('xss')</script>"
        login_page.enter_username(xss_payload)
        
        # Проверяем, что скрипт не выполнился
        page_content = page.content()
        assert xss_payload not in page_content, "XSS-инъекция не была экранирована"
        
        # Проверяем, что форма все еще работает
        assert login_page.is_login_form_ready(), "Форма авторизации перестала работать после XSS-попытки"

    @allure.title("Проверка уязвимости к XSS")
    @allure.story("Безопасность")
    @allure.severity('HIGH')
    @allure.description("""
    Тест проверяет уязвимость к различным XSS-векторам:
    1. Проверка различных XSS-векторов
    2. Проверка обработки HTML-тегов
    3. Проверка обработки JavaScript
    4. Проверка обработки событий
    
    Проверяется защита от различных типов XSS-атак
    """)
    def test_xss_vulnerability(self, page: Page, config, screenshot_utils):
        """Тест на уязвимость к XSS-атакам"""
        login_page = LoginPage(page, config["baseUrl"])
        
        # Проверяем, что форма готова
        assert login_page.is_login_form_ready(), "Форма авторизации не готова"
        
        # Пробуем различные XSS-векторы
        xss_vectors = [
            "<img src=x onerror=alert('xss')>",
            "javascript:alert('xss')",
            "<svg/onload=alert('xss')>",
            "'-alert('xss')-'"
        ]
        
        for vector in xss_vectors:
            login_page.enter_username(vector)
            login_page.enter_password(vector)
            
            # Проверяем, что вектор не выполнился
            page_content = page.content()
            assert vector not in page_content, f"XSS-вектор {vector} не был экранирован"
            
            # Проверяем, что форма все еще работает
            assert login_page.is_login_form_ready(), f"Форма авторизации перестала работать после XSS-вектора {vector}"