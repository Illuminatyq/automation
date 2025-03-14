from playwright.sync_api import Page, TimeoutError
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class LoginPage:
    def __init__(self, page: Page, base_url: str = None, timeout: int = 10000):
        self.page = page
        self.base_url = base_url.rstrip('/')
        self.default_timeout = timeout
        
        # Локаторы
        self.email_field = page.locator("input[name='login']")
        self.password_field = page.locator("input[name='password']")
        self.login_button = page.locator("button.btn-lg.btn-primary[type='submit']")
        self.forgot_password_link = page.locator("a[href='/auth/forgot/']")
        self.error_notification = page.locator("#toast-container .toast-error")
        self.success_notification = page.locator("#toast-container .toast-success")
        self.profile_dropdown = page.locator("a.nav-link.dropdown-toggle")
        self.logout_button = page.locator("a.dropdown-item[href='/auth/logout/']")

    def navigate(self) -> "LoginPage":
        self.page.goto(f"{self.base_url}/")
        self.page.wait_for_load_state("networkidle", timeout=self.default_timeout)
        logging.info(f"Navigated to {self.base_url}")
        return self

    def enter_email(self, email: str) -> "LoginPage":
        self.email_field.wait_for(state="visible", timeout=self.default_timeout)
        self.email_field.clear(timeout=self.default_timeout)
        self.email_field.fill(email, timeout=self.default_timeout)
        logging.info(f"Entered email: {email}")
        return self

    def enter_password(self, password: str) -> "LoginPage":
        self.password_field.wait_for(state="visible", timeout=self.default_timeout)
        self.password_field.clear(timeout=self.default_timeout)
        self.password_field.fill(password, timeout=self.default_timeout)
        logging.info("Entered password")
        return self

    def click_login(self) -> "LoginPage":
        self.login_button.wait_for(state="visible", timeout=self.default_timeout)
        self.page.evaluate("document.querySelector('form').submit()")
        self.page.wait_for_load_state("networkidle", timeout=self.default_timeout)
        logging.info("Form submitted and page loaded")
        
        # Проверяем результат
        if "/office/" in self.page.url:
            logging.info(f"Redirected to {self.page.url}")
        else:
            try:
                self.error_notification.wait_for(state="visible", timeout=10000)  # Увеличили таймаут
                logging.info("Error notification appeared")
            except TimeoutError:
                logging.warning("No error notification appeared")
                self._screenshot_on_error("login_no_error")
        return self

    def login(self, email: str, password: str) -> "LoginPage":
        self.navigate()
        self.enter_email(email)
        self.enter_password(password)
        self.click_login()
        logging.info(f"Login attempted with email: {email}")
        return self

    def click_forgot_password(self) -> "LoginPage":
        self.forgot_password_link.wait_for(state="visible", timeout=self.default_timeout)
        self.forgot_password_link.click()
        self.page.wait_for_load_state("networkidle", timeout=self.default_timeout)
        logging.info("Clicked forgot password link")
        return self

    def request_password_reset(self, email: str) -> "LoginPage":
        self.navigate()
        self.click_forgot_password()
        self.enter_email(email)
        self.page.locator("button[type='submit']").click()
        self.page.wait_for_load_state("networkidle", timeout=self.default_timeout)
        try:
            self.success_notification.wait_for(state="visible", timeout=10000)  # Увеличили таймаут
            logging.info("Success notification appeared")
        except TimeoutError:
            logging.warning("No success notification appeared")
            self._screenshot_on_error("recovery_no_success")
        return self

    def logout(self) -> "LoginPage":
        self.profile_dropdown.wait_for(state="visible", timeout=self.default_timeout)
        self.profile_dropdown.click()
        self.logout_button.wait_for(state="visible", timeout=self.default_timeout)
        self.logout_button.click()
        self.page.wait_for_url("**/auth/**", timeout=self.default_timeout)
        logging.info("Logged out")
        return self

    def _screenshot_on_error(self, action: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        path = f"screenshots/{action}_{timestamp}.png"
        self.page.screenshot(path=path)
        logging.info(f"Screenshot saved: {path}")

    def is_error_message_displayed(self) -> bool:
        try:
            self.error_notification.wait_for(state="visible", timeout=10000)
            is_visible = self.error_notification.is_visible()
            text = self.error_notification.text_content()
            logging.info(f"Error message visibility: {is_visible}, text: {text}")
            return is_visible
        except TimeoutError:
            logging.warning("Error message not visible within timeout")
            return False

    def is_success_message_displayed(self) -> bool:
        try:
            self.success_notification.wait_for(state="visible", timeout=10000)
            is_visible = self.success_notification.is_visible()
            text = self.success_notification.text_content()
            logging.info(f"Success message visibility: {is_visible}, text: {text}")
            return is_visible
        except TimeoutError:
            logging.warning("Success message not visible within timeout")
            return False