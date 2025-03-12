import pytest
from pages.login_page import LoginPage
import allure

@allure.feature("Authentication")
@pytest.mark.usefixtures("page")
class TestAuthentication:
    @allure.story("Successful login")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_successful_login(self, page, config):
        login_page = LoginPage(page, config["baseUrl"])
        creds = config["credentials"]["valid_user"]
        login_page.login(creds["email"], creds["password"])
        assert "office" in page.url, f"Expected '/office/' in URL, got {page.url}"

    @allure.story("Successful logout")
    @allure.severity(allure.severity_level.NORMAL)
    def test_successful_logout(self, authenticated_page):
        login_page = LoginPage(authenticated_page)
        assert login_page.logout(), "Logout failed"
        assert "/auth/" in authenticated_page.url, "Not redirected to login page"

    @allure.story("Invalid login")
    @allure.severity(allure.severity_level.NORMAL)
    def test_invalid_login(self, page, config):
        login_page = LoginPage(page, config["baseUrl"])
        creds = config["credentials"]["invalid_user"]
        login_page.login(creds["email"], creds["password"])
        assert login_page.is_error_message_displayed(), "Error message not displayed"
        assert page.url.startswith(config["baseUrl"]), "Unexpected redirect"

    @allure.story("Password recovery request")
    @allure.severity(allure.severity_level.NORMAL)
    def test_password_recovery(self, page, config):
        login_page = LoginPage(page, config["baseUrl"])
        login_page.navigate().click_forgot_password()
        recovery_email_field = page.locator("input[name='login'].form-control.form-control-lg")
        recovery_email_field.fill(config["credentials"]["valid_user"]["email"])
        page.locator("button[type='submit']").click()
        success_message = page.locator(".toast-success")
        assert success_message.is_visible(timeout=10000), "Success message not shown"