import pytest
from pages.login_page import LoginPage
import allure

# Параметризация для разных браузеров
@pytest.mark.parametrize("browser_page", ["chromium", "firefox", "webkit"], indirect=True)
@allure.feature("Аутентификация")
class TestAuthentication:
    @allure.story("Успешный вход")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_successful_login(self, browser_page, config):
        page, browser_name = browser_page
        login_page = LoginPage(page, config["baseUrl"])
        creds = config["credentials"]["valid_user"]
        
        with allure.step(f"Вход в систему в браузере {browser_name}"):
            login_page.login(creds["email"], creds["password"])
        
        current_url = page.url
        if "/office/" not in current_url:
            if login_page.is_error_message_displayed():
                allure.attach(page.screenshot(path=f"login_error_{browser_name}.png"), f"Ошибка при входе в {browser_name}", allure.attachment_type.PNG)
                pytest.fail(f"Login failed in {browser_name}: error message displayed on {current_url}")
            allure.attach(page.screenshot(path=f"login_no_redirect_{browser_name}.png"), f"Нет редиректа в {browser_name}", allure.attachment_type.PNG)
            pytest.fail(f"Expected redirect to /office/ in {browser_name}, got {current_url}")
        
        assert login_page.profile_dropdown.is_visible(timeout=10000), f"Profile dropdown not visible after login in {browser_name}"
        allure.attach(page.screenshot(path=f"login_success_{browser_name}.png"), f"Успешный вход в {browser_name}", allure.attachment_type.PNG)

    @allure.story("Неверный вход")
    @allure.severity(allure.severity_level.NORMAL)
    def test_invalid_login(self, browser_page, config):
        page, browser_name = browser_page
        login_page = LoginPage(page, config["baseUrl"])
        creds = config["credentials"]["invalid_user"]
    
        with allure.step(f"Попытка входа с неверными данными в браузере {browser_name}"):
            login_page.login(creds["email"], creds["password"])
    
        # Проверяем наличие сообщения об ошибке
        if not login_page.is_error_message_displayed():
            allure.attach(page.screenshot(path=f"invalid_login_no_error_{browser_name}.png"), f"Нет сообщения об ошибке в {browser_name}", allure.attachment_type.PNG)
            pytest.fail(f"Error message not displayed in {browser_name}")
    
        # Проверяем, что остались на странице авторизации
        current_url = page.url
        if not current_url.startswith(config["baseUrl"]):
            allure.attach(page.screenshot(path=f"invalid_login_redirect_{browser_name}.png"), f"Неожиданный редирект в {browser_name}", allure.attachment_type.PNG)
            pytest.fail(f"Unexpected redirect in {browser_name}, got {current_url}")
    
        allure.attach(page.screenshot(path=f"invalid_login_success_{browser_name}.png"), f"Неверный вход в {browser_name}", allure.attachment_type.PNG)

    @allure.story("Успешный выход")
    @allure.severity(allure.severity_level.NORMAL)
    def test_successful_logout(self, browser_page, config):
        page, browser_name = browser_page
        
        # Сначала входим в систему
        login_page = LoginPage(page, config["baseUrl"])
        creds = config["credentials"]["valid_user"]
        
        with allure.step(f"Вход в систему в браузере {browser_name}"):
            login_page.login(creds["email"], creds["password"])
            
            # Ждем редиректа на /office/
            try:
                page.wait_for_url("**/office/**", timeout=10000)
            except:
                allure.attach(page.screenshot(path=f"login_failed_{browser_name}.png"), f"Ошибка входа в {browser_name}", allure.attachment_type.PNG)
                pytest.skip(f"Не удалось войти в систему в {browser_name}, пропуск теста выхода")
        
        with allure.step(f"Выход из системы в браузере {browser_name}"):
            login_page.logout()
        
        current_url = page.url
        if not current_url.startswith(config["baseUrl"]):
            allure.attach(page.screenshot(path=f"logout_failed_{browser_name}.png"), f"Ошибка выхода в {browser_name}", allure.attachment_type.PNG)
            pytest.fail(f"Expected redirect to /auth/ in {browser_name}, got {current_url}")
        
        assert not login_page.profile_dropdown.is_visible(timeout=5000), f"Profile dropdown still visible after logout in {browser_name}"
        allure.attach(page.screenshot(path=f"logout_success_{browser_name}.png"), f"Успешный выход в {browser_name}", allure.attachment_type.PNG)

    @allure.story("Запрос восстановления пароля")
    @allure.severity(allure.severity_level.NORMAL)
    def test_password_recovery(self, browser_page, config):
        page, browser_name = browser_page
        login_page = LoginPage(page, config["baseUrl"])
        creds = config["credentials"]["valid_user"]
    
        with allure.step(f"Запрос восстановления пароля в браузере {browser_name}"):
            login_page.request_password_reset(creds["email"])
    
        # Проверяем наличие сообщения об успехе
        if not login_page.is_success_message_displayed():
            allure.attach(page.screenshot(path=f"recovery_no_success_{browser_name}.png"), f"Нет сообщения об успехе в {browser_name}", allure.attachment_type.PNG)
            pytest.fail(f"Success message not displayed in {browser_name}")
    
        allure.attach(page.screenshot(path=f"recovery_success_{browser_name}.png"), f"Успешный запрос восстановления в {browser_name}", allure.attachment_type.PNG)