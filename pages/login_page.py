from playwright.sync_api import Page

class LoginPage:
    def __init__(self, page: Page, base_url: str = "https://liner.dstepanyuk.dev.smte.am/auth/"):
        self.page = page
        self.base_url = base_url
        self.email_field = page.locator("input[name='login']")
        self.password_field = page.locator("input[name='password']")
        self.login_button = page.locator("button.btn-lg.btn-primary[type='submit']")
        self.forgot_password_link = page.locator("a[href='/auth/forgot/']")
        self.error_notification = page.locator(".toast-error")
        self.profile_dropdown = page.locator("a.nav-link.dropdown-toggle")
        self.logout_button = page.locator("a.dropdown-item[href='/auth/logout/']")

    def navigate(self):
        self.page.goto(self.base_url)
        self.page.wait_for_load_state("networkidle")
        return self

    def enter_email(self, email):
        self.email_field.fill(email)
        return self

    def enter_password(self, password):
        self.password_field.fill(password)
        return self

    def click_login(self):
        self.login_button.click()
        return self

    def login(self, email, password):
        return self.navigate().enter_email(email).enter_password(password).click_login()

    def logout(self):
        try:
            self.profile_dropdown.click()
            self.page.wait_for_timeout(500)  # Дать время на анимацию
            self.logout_button.click()
            self.page.wait_for_url("**/auth/**", timeout=10000)
            return True
        except Exception as e:
            self.page.screenshot(path="logout_error.png")
            print(f"Logout failed: {e}")
            return False

    def click_forgot_password(self):
        self.forgot_password_link.click()
        self.page.wait_for_load_state("networkidle")

    def is_error_message_displayed(self):
        return self.error_notification.is_visible(timeout=5000)