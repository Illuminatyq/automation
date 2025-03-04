from playwright.sync_api import Page, expect

class LoginPage:
    def __init__(self, page: Page):
        self.page = page
        self.base_url = "https://liner.dstepanyuk.dev.smte.am/auth/"
        
        # Локаторы для элементов авторизации
        self.email_field = page.locator("input[name='login']")
        self.password_field = page.locator("input[name='password']")
        self.login_button = page.locator("button.btn-lg.btn-primary[type='submit']")
        self.remember_me_checkbox = page.locator("input[name='remember']")
        self.forgot_password_link = page.locator("a[href='/auth/forgot/']")
        self.error_notification = page.locator(".toast-error")  # Локатор сообщения об ошибке (из скрипта)
        
    def navigate(self):
        self.page.goto(self.base_url)
        return self
        
    def enter_email(self, email):
        self.email_field.fill(email)
        return self
        
    def enter_password(self, password):
        self.password_field.fill(password)
        return self
        
    def click_login_button(self):
        self.login_button.click()
        
    def check_remember_me(self, check=True):
        checkbox = self.remember_me_checkbox
        if check and not checkbox.is_checked():
            checkbox.check()
        elif not check and checkbox.is_checked():
            checkbox.uncheck()
        return self
        
    def click_forgot_password(self):
        self.forgot_password_link.click()
        
    def login(self, email, password, remember_me=True):
        self.navigate()
        self.enter_email(email)
        self.enter_password(password)
        self.check_remember_me(remember_me)
        self.click_login_button()
        
    def is_error_message_displayed(self, timeout=10000):
        """Проверяет, отображается ли сообщение об ошибке авторизации"""
        return self.error_notification.is_visible(timeout=timeout)
    
    def is_login_successful(self):
        """Проверяет, успешна ли авторизация (например, по URL или элементу дашборда)"""
        try:
            self.page.wait_for_url("**/*dashboard*", timeout=10000)  # Замени на реальный URL после логина
            return True
        except:
            return False