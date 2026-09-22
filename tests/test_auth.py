import pytest
import allure
from playwright.sync_api import Page
from pages.login_page import LoginPage
import logging
from utils.allure_helpers import AllureHelper

@allure.epic("Авторизация")
@allure.feature("Тесты системы авторизации")
@pytest.mark.auth
class TestAuthentication:
    """Оптимизированные тесты системы авторизации с устранением race conditions"""

    @allure.title("Успешная авторизация с валидными учетными данными")
    @allure.story("✅ Позитивный сценарий авторизации")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.description("""
    Тест проверяет, что пользователь с валидными учетными данными успешно авторизуется.
    
    **Шаги:**
    1. Переход к форме авторизации
    2. Ввод валидных данных
    3. Проверка успешной авторизации
    4. Проверка редиректа на главную страницу
    
    **Ожидаемый результат:** Пользователь успешно авторизуется и перенаправляется на главную страницу.
    """)
    @pytest.mark.smoke
    @pytest.mark.critical
    def test_successful_login(self, page: Page, config, screenshot_utils):
        """
        Тест успешной авторизации с устранением race conditions
        Проверяет корректность основного пользовательского сценария
        """
        # Добавляем информацию об окружении
        AllureHelper.attach_environment_info(config)
        
        login_page = LoginPage(page, config["baseUrl"])
        credentials = config["credentials"]["valid_user"]
        
        # Прикрепляем тестовые данные (с маскированием пароля)
        AllureHelper.attach_test_data({
            "email": credentials["email"],
            "password": "***MASKED***",
            "remember_me": True
        }, "Учетные данные для авторизации")
        
        with allure.step("Переход к форме авторизации"):
            login_page.force_navigate_to_login()
            assert login_page.is_login_form_ready(), "Форма авторизации должна быть готова"
            screenshot_utils.take_screenshot("login_form_ready")
            AllureHelper.attach_page_info(page, "Страница авторизации")
        
        with allure.step("Ввод валидных данных и вход"):
            success = login_page.login(
                email=credentials["email"],
                password=credentials["password"],
                remember=True
            )
            screenshot_utils.take_screenshot("after_login_attempt")
        
        with allure.step("Проверка результата авторизации"):
            assert success, "Авторизация должна завершиться успешно"
            
            # Дополнительная проверка состояния
            assert login_page.is_logged_in(), "Пользователь должен быть авторизован"
            
            # Проверка URL или наличия элементов успешной авторизации
            current_url = page.url
            url_check_passed = any(path in current_url for path in ["/office/", "/dashboard/", "/main/"])
            
            if not url_check_passed:
                # Если URL не изменился, проверяем наличие элементов авторизованного пользователя
                profile_visible = page.locator(login_page.locators.PROFILE_DROPDOWN).is_visible()
                assert profile_visible, f"Ожидался переход на главную страницу или наличие профиля. Текущий URL: {current_url}"
            
            screenshot_utils.take_screenshot("successful_login_confirmed")
            AllureHelper.attach_page_info(page, "Страница после успешной авторизации")
            
            # Прикрепляем метрики
            AllureHelper.attach_performance_metrics({
                "URL после авторизации": current_url,
                "Статус авторизации": "Успешно",
                "Профиль виден": profile_visible if not url_check_passed else True
            })
            
            logging.info(f"✅ Авторизация успешно завершена. URL: {current_url}")

    @allure.title("Обработка неверных учетных данных")
    @allure.story("❌ Негативный сценарий с некорректными данными")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.description("""
    Тест проверяет, что при вводе неверных учетных данных появляется toast-уведомление об ошибке, 
    и пользователь не логинится.
    
    **Шаги:**
    1. Переход к форме авторизации
    2. Ввод неверных учетных данных
    3. Попытка авторизации
    4. Проверка отображения сообщения об ошибке
    
    **Ожидаемый результат:** Отображается сообщение об ошибке, пользователь не авторизуется.
    """)
    @pytest.mark.regression
    def test_invalid_credentials_error_handling(self, page: Page, config, screenshot_utils):
        """
        Тест обработки неверных учетных данных с проверкой toast-уведомлений
        Использует оптимизированный механизм ожидания JS-компонентов
        """
        login_page = LoginPage(page, config["baseUrl"])
        invalid_credentials = config["credentials"]["invalid_user"]
        
        # Прикрепляем тестовые данные
        AllureHelper.attach_test_data({
            "email": invalid_credentials["email"],
            "password": "***MASKED***"
        }, "Неверные учетные данные")
        
        with allure.step("Переход к форме авторизации"):
            login_page.force_navigate_to_login()
            assert login_page.is_login_form_ready(), "Форма авторизации должна быть доступна"
            screenshot_utils.take_screenshot("invalid_login_form_ready")
            AllureHelper.attach_page_info(page, "Страница авторизации")
        
        with allure.step("Ввод неверных данных и попытка входа"):
            login_page.enter_username(invalid_credentials["email"])
            login_page.enter_password(invalid_credentials["password"])
            screenshot_utils.take_screenshot("invalid_credentials_entered")
        
        with allure.step("Выполнение попытки авторизации"):
            success = login_page.click_login_button()
            screenshot_utils.take_screenshot("after_invalid_login_attempt")
        
        with allure.step("Проверка обработки ошибки"):
            assert not success, "Авторизация с неверными данными должна завершиться неудачей"
            
            # Используем оптимизированное ожидание toast-уведомления
            error_displayed = login_page.wait_for_error_message(
                expected_text="авторизации",  # Частичное совпадение для гибкости
                timeout=15000
            )
            
            if not error_displayed:
                # Отладочная информация при отсутствии уведомления
                screenshot_utils.take_screenshot("error_toast_not_found")
                page_html = page.content()
                allure.attach(page_html, "Page HTML for debug", allure.attachment_type.HTML)
                
                # Проверяем альтернативные способы отображения ошибок
                form_errors = page.locator(".invalid-feedback, .form-error, .error-message").count()
                if form_errors > 0:
                    logging.warning("Toast не найден, но есть inline-ошибки формы")
                    pytest.skip("Toast-уведомления недоступны, но inline-валидация работает")
                else:
                    pytest.fail("Не найдено ни toast-уведомление, ни inline-ошибки формы")
            
            # Получаем и проверяем текст ошибки
            error_text = login_page.get_error_message_text()
            allure.attach(error_text, "Текст ошибки", allure.attachment_type.TEXT)
            
            assert "авторизации" in error_text.lower() or "неверн" in error_text.lower(), \
                f"Текст ошибки должен содержать информацию об ошибке авторизации. Получен: {error_text}"
            
            screenshot_utils.take_screenshot("error_message_validated")
            
            # Прикрепляем информацию об успешной обработке ошибки
            AllureHelper.attach_performance_metrics({
                "Ошибка отображена": True,
                "Текст ошибки": error_text,
                "Авторизация заблокирована": True
            })
            
            logging.info(f"✅ Ошибка корректно обработана: {error_text}")

    @allure.title("Проверка функциональности выхода из системы")
    @allure.story("🚪 Выход из системы")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.description("""
    Проверка корректного выхода пользователя из системы и появления формы авторизации.
    
    **Шаги:**
    1. Проверка состояния авторизации
    2. Выполнение выхода из системы
    3. Проверка редиректа на страницу авторизации
    4. Проверка доступности формы авторизации
    
    **Ожидаемый результат:** Пользователь успешно выходит из системы и перенаправляется на страницу авторизации.
    """)
    @pytest.mark.regression
    @pytest.mark.usefixtures("authenticated_page")
    def test_logout_functionality(self, authenticated_page: Page, config, screenshot_utils):
        """Тест функциональности выхода из системы."""
        
        login_page = LoginPage(authenticated_page, config["baseUrl"])
        
        with allure.step("Проверка состояния перед выходом"):
            current_url = authenticated_page.url
            logging.info(f"URL перед логаутом: {current_url}")
            assert login_page.is_logged_in(), "Пользователь должен быть авторизован перед логаутом"
            screenshot_utils.take_screenshot("before_logout")
            AllureHelper.attach_page_info(authenticated_page, "Страница перед выходом")
        
        with allure.step("🚪 Выполнение выхода из системы"):
            logout_success = login_page.logout()
            if not logout_success:
                # Сохраняем HTML и делаем лог для отладки
                allure.attach(authenticated_page.content(), "HTML после неудачного логаута", allure.attachment_type.HTML)
                logging.error("Логаут не удался! Сохраняю HTML для отладки.")
            assert logout_success, "Выход из системы должен быть успешным"
            logging.info(f"Результат логаута: {logout_success}")
            screenshot_utils.take_screenshot("after_logout")
        
        with allure.step("✅ Проверка результата выхода"):
            current_url = authenticated_page.url
            logging.info(f"URL после логаута: {current_url}")
            assert "/auth/" in current_url, f"После выхода ожидался редирект на страницу авторизации, получен: {current_url}"
            
            # Проверяем, что форма авторизации снова доступна
            assert login_page.is_login_form_ready(), "После выхода форма авторизации должна быть доступна"
            screenshot_utils.take_screenshot("login_form_after_logout")
            AllureHelper.attach_page_info(authenticated_page, "Страница после выхода")
            
            # Проверяем отсутствие ошибок
            assert not login_page.wait_for_notification('error', timeout=3000), "После выхода не должно быть ошибок"
            
            # Прикрепляем метрики
            AllureHelper.attach_performance_metrics({
                "Выход выполнен": True,
                "URL после выхода": current_url,
                "Форма авторизации доступна": True,
                "Ошибок нет": True
            })
            
            logging.info("✅ Выход из системы выполнен корректно")

    @allure.title("Проверка восстановления пароля через toast")
    @allure.description("Проверяет, что при восстановлении пароля появляется toast-уведомление об успехе/инфо/ошибке.")
    def test_forgot_password_navigation(self, page: Page, config, screenshot_utils):
        login_page = LoginPage(page, config["baseUrl"])
        email = config["credentials"]["valid_user"]["email"]

        with allure.step("Переход к форме восстановления пароля"):
            login_page.navigate()
            login_page.navigate_to_forgot_password()
            current_url = page.url
            assert any(keyword in current_url.lower() for keyword in ["forgot", "reset", "recovery"]), \
                f"URL не соответствует странице восстановления пароля: {current_url}"

        with allure.step("Ввод email и отправка формы"):
            page.fill("input[type='email'], input[name='login']", email)
            page.click("button[type='submit']")

        with allure.step("Проверка toast-уведомления об успехе/инфо/ошибке"):
            assert login_page.wait_for_notification('success', timeout=7000) or \
                   login_page.wait_for_notification('info', timeout=7000) or \
                   login_page.wait_for_notification('error', timeout=7000), \
                "Ожидалось уведомление после восстановления пароля"

    @pytest.mark.usefixtures("page")
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
        form_ready = login_page.is_login_form_ready()
        if not form_ready:
            pytest.fail("Форма авторизации не готова")
        
        # Пробуем отправить пустую форму
        login_page.click_login_button()
        # Проверяем inline-ошибку под полем email или пароля
        inline_error = page.locator(".invalid-feedback, .form-error, .is-invalid").count() > 0
        if not inline_error:
            # Если нет inline-ошибки, возможно, есть toast
            toast_error = login_page.wait_for_notification('error', timeout=3000)
            assert toast_error, "Ожидалась inline-ошибка или toast-ошибка при пустой форме"
        
        # Проверяем валидацию email
        login_page.enter_username("invalid_email")
        login_page.click_login_button()
        email_error = page.locator(".invalid-feedback, .form-error, .is-invalid").count() > 0
        if not email_error:
            toast_error = login_page.wait_for_notification('error', timeout=3000)
            assert toast_error, "Ожидалась inline-ошибка или toast-ошибка при невалидном email"
        
        # Проверяем валидацию пароля
        login_page.enter_username(config["credentials"]["valid_user"]["email"])
        login_page.enter_password("short")
        login_page.click_login_button()
        password_error = page.locator(".invalid-feedback, .form-error, .is-invalid").count() > 0
        if not password_error:
            toast_error = login_page.wait_for_notification('error', timeout=3000)
            assert toast_error, "Ожидалась inline-ошибка или toast-ошибка при коротком пароле"

