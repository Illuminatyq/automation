class LoginLocators:
    """Локаторы для страницы авторизации"""
    
    # Основные элементы формы
    LOGIN_FORM = "form[action='/auth/login/'][data-skip='true']"
    USERNAME_INPUT = "input.form-control[name='login']"
    PASSWORD_INPUT = "input.form-control[name='password']"
    LOGIN_BUTTON = "form[action='/auth/login/'] button.btn-primary[type='submit']"
    REMEMBER_ME_CHECKBOX = "input.custom-control-input[name='remember']"
    
    # Дополнительные элементы
    FORGOT_PASSWORD_LINK = "a[href='/auth/forgot/']"
    ERROR_NOTIFICATION = "#toast-container > .toast-error"
    SUCCESS_NOTIFICATION = "#toast-container > .toast-success"
    
    # Элементы после авторизации
    PROFILE_DROPDOWN = ".user-settings-dropdown"
    PROFILE_DROPDOWN_OPEN = ".user-settings-dropdown.show"
    PROFILE_DROPDOWN_TOGGLE = ".user-settings-dropdown .dropdown-toggle"
    LOGOUT_BUTTON = ".user-settings-dropdown .dropdown-menu a[href='/auth/logout/']"
    
    # Элементы загрузки
    LOADING_SPINNER = ".loading, .spinner, .loader"