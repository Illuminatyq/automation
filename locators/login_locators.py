"""
Локаторы для страницы авторизации
"""

class LoginLocators:
    """Локаторы для страницы авторизации"""
    
    # Основные элементы формы
    LOGIN_FORM = "form[action*='login'], form[action*='auth']"
    USERNAME_INPUT = "input[type='text'], input[type='email'], input[name='login'], input[name='username']"
    PASSWORD_INPUT = "input[type='password'], input[name='password']"
    LOGIN_BUTTON = "button[type='submit'], input[type='submit'], button:has-text('Войти')"
    
    # Элементы после успешной авторизации
    PROFILE_DROPDOWN = ".user-settings-dropdown .dropdown-toggle"
    LOGOUT_BUTTON = "a[href='/auth/logout/'], a:has-text('Завершить сеанс')"
    
    # Уведомления
    ERROR_NOTIFICATION = ".error-message, .alert-error, .notification-error, .toast-error, .error"
    SUCCESS_NOTIFICATION = ".success-message, .alert-success, .notification-success, .toast-success, .success"
    
    # Дополнительные элементы
    FORGOT_PASSWORD_LINK = "a[href*='forgot'], a[href*='reset'], a:has-text('Забыли пароль')"
    REMEMBER_ME_CHECKBOX = "input[name='remember'], input[type='checkbox']"
    REGISTER_LINK = "a[href*='register'], a[href*='signup'], a:has-text('Регистрация')" 