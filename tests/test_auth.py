import pytest
from pages.login_page import LoginPage
import allure

@allure.feature("Authentication")
class TestAuthentication:
    
    @allure.story("Successful login")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_successful_login(self, driver, config):
        """Проверка успешной авторизации с правильными учетными данными"""
        login_page = LoginPage(driver)
        
        with allure.step("Переход на страницу логина"):
            login_page.navigate()
        
        with allure.step("Ввод учетных данных и вход"):
            valid_credentials = config['credentials']['valid_user']
            login_page.login(valid_credentials['email'], valid_credentials['password'])
        
        with allure.step("Проверка успешной авторизации"):
            # Здесь нужно заменить на реальное условие, показывающее успешный вход
            # Например, проверка URL или наличие элемента на странице дашборда
            # assert "dashboard" in driver.current_url
            # Временно используем просто проверку, что URL изменился
            assert login_page.get_current_url() != config['baseUrl']
            
    @allure.story("Invalid login")
    @allure.severity(allure.severity_level.NORMAL)
    def test_invalid_login(self, driver, config):
        """Проверка отказа в авторизации с неправильными учетными данными"""
        login_page = LoginPage(driver)
        
        with allure.step("Переход на страницу логина"):
            login_page.navigate()
        
        with allure.step("Ввод неверных учетных данных"):
            invalid_credentials = config['credentials']['invalid_user']
            login_page.login(invalid_credentials['email'], invalid_credentials['password'])
        
        with allure.step("Проверка сообщения об ошибке"):
            assert login_page.is_error_message_displayed()