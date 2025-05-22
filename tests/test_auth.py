import pytest
import allure
from playwright.sync_api import Page, expect
from pages.login_page import LoginPage
from utils.screenshot_utils import ScreenshotUtils
import logging

@allure.epic("Авторизация в системе")
@allure.feature("Функционал авторизации")
class TestAuth:
    @allure.story("Успешная авторизация")
    @allure.severity(allure.severity_level.CRITICAL)
    @allure.description("""
    Проверка успешной авторизации с валидными учетными данными.
    Ожидаемый результат: пользователь успешно авторизуется в системе.
    """)
    def test_login_success(self, page: Page, config, screenshot_utils):
        login_page = LoginPage(page)
        
        with allure.step("Подготовка: Открытие страницы авторизации"):
            page.goto(config["baseUrl"])
            page.wait_for_load_state("domcontentloaded", timeout=60000)
            try:
                page.wait_for_load_state("networkidle", timeout=60000)
            except Exception:
                logging.warning("Превышен таймаут ожидания networkidle, продолжаем выполнение")
        
        with allure.step("Действие: Ввод валидных учетных данных"):
            login_page.enter_username(config["credentials"]["valid_user"]["email"])
            login_page.enter_password(config["credentials"]["valid_user"]["password"])
        
        with allure.step("Действие: Нажатие кнопки входа"):
            login_result = login_page.click_login()
            assert login_result, "Авторизация не удалась"
        
        with allure.step("Проверка: Успешная авторизация"):
            try:
                page.wait_for_selector(login_page.locators.PROFILE_DROPDOWN, timeout=60000)
                expect(page.locator(login_page.locators.PROFILE_DROPDOWN)).to_be_visible()
                logging.info("Авторизация успешна")
            except Exception as e:
                screenshot_utils.save_error_screenshot("login_error")
                pytest.fail(f"Ошибка авторизации: {str(e)}")
    
    @allure.story("Неуспешная авторизация")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.description("""
    Проверка обработки неверных учетных данных.
    Ожидаемый результат: система показывает корректное сообщение об ошибке.
    """)
    def test_login_invalid_credentials(self, page: Page, config, screenshot_utils):
        login_page = LoginPage(page)
        
        with allure.step("Подготовка: Открытие страницы авторизации"):
            page.goto(config["baseUrl"])
            page.wait_for_load_state("domcontentloaded", timeout=60000)
        
        with allure.step("Действие: Ввод неверных учетных данных"):
            login_page.enter_username(config["credentials"]["invalid_user"]["email"])
            login_page.enter_password(config["credentials"]["invalid_user"]["password"])
        
        with allure.step("Действие: Попытка входа"):
            login_result = login_page.click_login()
            assert not login_result, "Авторизация не должна была удаться"
        
        with allure.step("Проверка: Сообщение об ошибке"):
            try:
                page.wait_for_selector(login_page.locators.ERROR_NOTIFICATION, timeout=10000)
                expect(page.locator(login_page.locators.ERROR_NOTIFICATION)).to_be_visible()
                error_text = login_page.get_error_message()
                assert any(msg in error_text.lower() for msg in [
                    "неверный логин или пароль",
                    "ошибка в данных авторизации",
                    "пользователь не активен"
                ]), f"Неожиданный текст ошибки: {error_text}"
                logging.info("Получено ожидаемое сообщение об ошибке")
            except Exception as e:
                screenshot_utils.save_error_screenshot("invalid_credentials_error")
                pytest.fail(f"Ошибка при проверке сообщения: {str(e)}")
    
    @allure.story("Выход из системы")
    @allure.severity(allure.severity_level.NORMAL)
    def test_logout(self, page: Page, config, screenshot_utils):
        login_page = LoginPage(page)
        
        with allure.step("Открытие страницы авторизации"):
            page.goto(config["baseUrl"])
            page.wait_for_load_state("domcontentloaded", timeout=30000)
        
        with allure.step("Ввод учетных данных"):
            login_page.enter_username(config["credentials"]["valid_user"]["email"])
            login_page.enter_password(config["credentials"]["valid_user"]["password"])
        
        with allure.step("Нажатие кнопки входа"):
            login_result = login_page.click_login()
            assert login_result, "Авторизация не удалась"
        
        with allure.step("Выход из системы"):
            try:
                logout_result = login_page.logout()
                assert logout_result, "Выход из системы не удался"
                logging.info("Выход из системы выполнен успешно")
            except Exception as e:
                screenshot_utils.save_error_screenshot("logout_error")
                pytest.fail(f"Ошибка при выходе из системы: {str(e)}")
    
    @allure.story("Запрос восстановления пароля")
    @allure.severity(allure.severity_level.NORMAL)
    def test_forgot_password(self, page: Page, config, screenshot_utils):
        login_page = LoginPage(page)
        
        with allure.step("Открытие страницы авторизации"):
            page.goto(config["baseUrl"])
            page.wait_for_load_state("domcontentloaded", timeout=60000)
        
        with allure.step("Переход на страницу восстановления пароля"):
            try:
                page.locator(login_page.locators.FORGOT_PASSWORD_LINK).click()
                page.wait_for_load_state("domcontentloaded", timeout=60000)
                
                # Проверяем, что мы на странице восстановления пароля
                assert "forgot" in page.url.lower() or "reset" in page.url.lower()
                logging.info("Успешно перешли на страницу восстановления пароля")
            except Exception as e:
                screenshot_utils.save_error_screenshot("forgot_password_error")
                pytest.fail(f"Ошибка при переходе на страницу восстановления пароля: {str(e)}")

    @allure.story("Проверка таймаута")
    @allure.severity(allure.severity_level.NORMAL)
    def test_timeout_error(self, page: Page, config, screenshot_utils):
        """Тест демонстрирует ошибку таймаута при ожидании элемента"""
        login_page = LoginPage(page)
        
        with allure.step("Открытие страницы авторизации"):
            page.goto(config["baseUrl"])
        
        with allure.step("Ожидание несуществующего элемента"):
            try:
                # Намеренно ждем элемент, которого нет
                page.wait_for_selector(".non-existent-element", timeout=5000)
                pytest.fail("Элемент не должен был быть найден")
            except Exception as e:
                screenshot_utils.save_error_screenshot("timeout_error")
                assert "Timeout" in str(e), "Ожидалась ошибка таймаута"
                logging.info("Получена ожидаемая ошибка таймаута")

    @allure.story("Проверка валидации формы")
    @allure.severity(allure.severity_level.NORMAL)
    def test_form_validation(self, page: Page, config, screenshot_utils):
        """Тест демонстрирует ошибки валидации формы"""
        login_page = LoginPage(page)
        
        with allure.step("Открытие страницы авторизации"):
            page.goto(config["baseUrl"])
        
        with allure.step("Проверка валидации пустых полей"):
            login_page.click_login()
            try:
                page.wait_for_selector(login_page.locators.ERROR_NOTIFICATION, timeout=5000)
                error_text = login_page.get_error_message()
                assert "заполните все поля" in error_text.lower(), f"Неожиданный текст ошибки: {error_text}"
            except Exception as e:
                screenshot_utils.save_error_screenshot("validation_error")
                pytest.fail(f"Ошибка при проверке валидации: {str(e)}")

    @allure.story("Проверка XSS-уязвимости")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_xss_vulnerability(self, page: Page, config, screenshot_utils):
        """Тест демонстрирует потенциальную XSS-уязвимость"""
        login_page = LoginPage(page)
        
        with allure.step("Открытие страницы авторизации"):
            page.goto(config["baseUrl"])
        
        with allure.step("Ввод XSS-пейлоада"):
            xss_payload = "<script>alert('XSS')</script>"
            login_page.enter_username(xss_payload)
            login_page.enter_password("password")
        
        with allure.step("Проверка обработки XSS"):
            try:
                login_page.click_login()
                # Проверяем, не был ли выполнен скрипт
                alert = page.get_by_role("alert")
                if alert:
                    screenshot_utils.save_error_screenshot("xss_vulnerability")
                    pytest.fail("Обнаружена XSS-уязвимость: скрипт был выполнен")
            except Exception as e:
                logging.info("XSS-пейлоад был корректно обработан")