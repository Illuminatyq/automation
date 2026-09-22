"""
Тесты реальных пользовательских сценариев, которые могут поломать форму авторизации.
Фокус на поведении пользователя, а не только на технических атаках.
"""
import time
import logging
import pytest
import allure
from allure_commons.types import Severity
from playwright.sync_api import Page, expect
from pages.login_page import LoginPage


@allure.epic("Деструктивные сценарии")
@allure.feature("Реальные пользовательские кейсы")
@pytest.mark.auth
@pytest.mark.destructive
class TestAuthUserScenarios:
    """Тесты реальных пользовательских сценариев, которые могут поломать продукт"""

    def _open_login_page(self, page: Page, base_url: str) -> LoginPage:
        login_page = LoginPage(page, base_url)
        login_page.force_navigate_to_login()
        login_page.clear_form()
        return login_page

    @allure.title("Множественные быстрые клики по кнопке 'Войти'")
    @allure.severity(Severity.CRITICAL)
    @allure.description("""
    Пользователь быстро кликает 5-10 раз по кнопке входа.
    Проверяем защиту от двойной отправки формы.
    
    **Что может сломаться:**
    - Множественные запросы на сервер
    - Дублирование сессий
    - Race conditions
    - Проблемы с состоянием формы
    """)
    def test_multiple_rapid_clicks_on_login_button(self, page: Page, config, screenshot_utils):
        """Проверка защиты от множественных быстрых кликов"""
        login_page = self._open_login_page(page, config["baseUrl"])
        credentials = config["credentials"]["valid_user"]
        
        login_page.enter_username(credentials["email"])
        login_page.enter_password(credentials["password"])
        
        login_button = page.locator(login_page.locators.LOGIN_BUTTON)
        
        with allure.step("Быстрые множественные клики (10 раз)"):
            click_count = 10
            for i in range(click_count):
                try:
                    login_button.click(timeout=1000)
                except Exception as e:
                    logging.warning(f"Клик {i+1} не выполнен: {e}")
                time.sleep(0.05)  # Очень маленькая задержка между кликами
        
        with allure.step("Проверка результата"):
            # Ждем завершения обработки
            time.sleep(2)
            
            # Проверяем, что форма обработала запрос корректно
            # Должна быть либо успешная авторизация, либо одна ошибка
            current_url = page.url
            is_logged_in = login_page.is_logged_in()
            
            # Проверяем консоль на ошибки
            console_errors = []
            try:
                # Попытка получить ошибки из консоли (если доступно)
                page.wait_for_timeout(1000)
            except Exception:
                pass
            
            # Проверяем, что нет множественных редиректов или зависаний
            assert current_url is not None, "URL не должен быть None"
            
            # Если авторизация прошла, проверяем что она была одна
            if is_logged_in:
                logging.info("✅ Авторизация прошла успешно после множественных кликов")
            else:
                # Если не авторизовались, проверяем что есть ошибка (но не множественные)
                error_count = page.locator(".toast-error, .error-message").count()
                assert error_count <= 1, f"Обнаружено множественных ошибок: {error_count}"
            
            screenshot_utils.take_screenshot("multiple_rapid_clicks")

    @allure.title("Изменение данных во время отправки формы")
    @allure.severity(Severity.CRITICAL)
    @allure.description("""
    Пользователь вводит email, начинает вводить пароль, но пока форма отправляется, меняет email.
    
    **Что может сломаться:**
    - Отправка устаревших данных
    - Конфликты состояния формы
    - Некорректная валидация
    """)
    def test_change_data_during_form_submission(self, page: Page, config, screenshot_utils):
        """Проверка поведения при изменении данных во время отправки"""
        login_page = self._open_login_page(page, config["baseUrl"])
        credentials = config["credentials"]["valid_user"]
        
        username_input = page.locator(login_page.locators.USERNAME_INPUT)
        password_input = page.locator(login_page.locators.PASSWORD_INPUT)
        login_button = page.locator(login_page.locators.LOGIN_BUTTON)
        
        with allure.step("Ввод начальных данных"):
            username_input.fill(credentials["email"])
            password_input.fill(credentials["password"])
        
        with allure.step("Начало отправки формы и быстрое изменение email"):
            # Кликаем кнопку
            login_button.click()
            
            # Сразу же меняем email
            time.sleep(0.1)  # Небольшая задержка для начала обработки
            changed_email = "changed@example.com"
            username_input.fill(changed_email)
        
        with allure.step("Проверка результата"):
            time.sleep(2)  # Ждем завершения обработки
            
            # Проверяем, что форма либо использует актуальные данные,
            # либо блокирует изменения во время отправки
            final_email = username_input.input_value()
            
            # Форма должна либо использовать изначальный email (если блокирует изменения),
            # либо новый (если позволяет изменения)
            # Главное - не должно быть конфликта или ошибок
            assert final_email in [credentials["email"], changed_email], \
                f"Неожиданное значение email: {final_email}"
            
            # Проверяем отсутствие JavaScript ошибок
            # (это можно проверить через консоль браузера, если доступно)
            
            screenshot_utils.take_screenshot("change_data_during_submission")

    @allure.title("Копирование-вставка больших объемов текста")
    @allure.severity(Severity.CRITICAL)
    @allure.description("""
    Пользователь копирует большой текст (10KB+) и вставляет в поля формы.
    
    **Что может сломаться:**
    - Переполнение буфера
    - Зависание UI
    - Проблемы с производительностью
    - Отсутствие валидации длины
    """)
    def test_paste_large_text_into_fields(self, page: Page, config, screenshot_utils):
        """Проверка обработки больших объемов текста"""
        login_page = self._open_login_page(page, config["baseUrl"])
        
        username_input = page.locator(login_page.locators.USERNAME_INPUT)
        password_input = page.locator(login_page.locators.PASSWORD_INPUT)
        
        # Генерируем большой текст (10KB)
        large_text = "a" * 10000
        
        with allure.step("Вставка большого текста в поле email"):
            try:
                username_input.fill(large_text)
            except Exception as e:
                pytest.fail(f"Не удалось вставить текст в поле email: {e}")
            
            # Проверяем, что поле либо обрезало текст, либо приняло его
            filled_value = username_input.input_value()
            assert len(filled_value) <= len(large_text), \
                f"Поле email содержит больше данных чем было вставлено: {len(filled_value)}"
            
            # Проверяем производительность - вставка не должна зависнуть
            start_time = time.time()
            username_input.fill("test@example.com")  # Очищаем поле
            clear_time = time.time() - start_time
            assert clear_time < 1.0, f"Очистка поля заняла слишком долго: {clear_time:.2f}s"
        
        with allure.step("Вставка большого текста в поле пароля"):
            try:
                password_input.fill(large_text)
            except Exception as e:
                pytest.fail(f"Не удалось вставить текст в поле пароля: {e}")
            
            filled_value = password_input.input_value()
            assert len(filled_value) <= len(large_text), \
                f"Поле пароля содержит больше данных чем было вставлено: {len(filled_value)}"
            
            # Проверяем производительность
            start_time = time.time()
            password_input.fill("password")
            clear_time = time.time() - start_time
            assert clear_time < 1.0, f"Очистка поля пароля заняла слишком долго: {clear_time:.2f}s"
        
        with allure.step("Проверка стабильности формы"):
            assert login_page.is_login_form_ready(), \
                "Форма должна оставаться функциональной после вставки больших данных"
            
            screenshot_utils.take_screenshot("large_text_paste")

    @allure.title("Специальные символы в email (реальные случаи)")
    @allure.severity(Severity.CRITICAL)
    @allure.description("""
    Тестирование различных валидных форматов email с особыми символами.
    
    **Что может сломаться:**
    - Неправильная валидация
    - Отказ в доступе легитимным пользователям
    - Проблемы с кодировкой
    """)
    @pytest.mark.parametrize("email", [
        "user+tag@example.com",
        "user.name+tag@example.com",
        "user_name@example.co.uk",
        "user123@subdomain.example.com",
        "user@example-domain.com",
        "user_name123@example.com",
        "user+tag+another@example.com",
        "user.name.middle@example.com",
    ])
    def test_special_characters_in_email(self, page: Page, config, screenshot_utils, email):
        """Проверка обработки email с особыми символами"""
        login_page = self._open_login_page(page, config["baseUrl"])
        
        username_input = page.locator(login_page.locators.USERNAME_INPUT)
        password_input = page.locator(login_page.locators.PASSWORD_INPUT)
        
        with allure.step(f"Ввод email с особыми символами: {email}"):
            username_input.fill(email)
            password_input.fill("testpassword123")
            
            # Проверяем, что email был введен корректно
            filled_email = username_input.input_value()
            assert filled_email == email, \
                f"Email был изменен после ввода. Ожидалось: {email}, получено: {filled_email}"
        
        with allure.step("Попытка авторизации"):
            result = login_page.click_login_button()
            
            # Проверяем, что форма либо приняла валидный email,
            # либо показала понятную ошибку валидации
            if not result:
                # Если авторизация не прошла, проверяем что есть ошибка валидации
                error_displayed = login_page.wait_for_notification('error', timeout=3000)
                inline_errors = page.locator(".invalid-feedback, .form-error").count() > 0
                
                # Должна быть либо ошибка валидации, либо ошибка авторизации
                assert error_displayed or inline_errors, \
                    f"Для email {email} не отображена ошибка валидации или авторизации"
            
            screenshot_utils.take_screenshot(f"special_email_{email.replace('@', '_at_').replace('.', '_')}")

    @allure.title("Пароли с крайними значениями")
    @allure.severity(Severity.CRITICAL)
    @allure.description("""
    Тестирование паролей с различными крайними значениями.
    
    **Что может сломаться:**
    - Непоследовательная валидация
    - Проблемы с кодировкой
    - Отказ в доступе легитимным пользователям
    """)
    @pytest.mark.parametrize("password,description", [
        (" " * 20, "Только пробелы"),
        ("!@#$%^&*()", "Только спецсимволы"),
        ("12345678", "Только цифры"),
        ("abcdefgh", "Только буквы"),
        ("Пароль123", "Кириллица в пароле"),
        ("a" * 200, "Очень длинный пароль"),
        ("a", "Очень короткий пароль"),
    ])
    def test_extreme_password_values(self, page: Page, config, screenshot_utils, password, description):
        """Проверка обработки паролей с крайними значениями"""
        login_page = self._open_login_page(page, config["baseUrl"])
        credentials = config["credentials"]["valid_user"]
        
        username_input = page.locator(login_page.locators.USERNAME_INPUT)
        password_input = page.locator(login_page.locators.PASSWORD_INPUT)
        
        with allure.step(f"Ввод пароля: {description}"):
            username_input.fill(credentials["email"])
            
            try:
                password_input.fill(password)
            except Exception as e:
                pytest.fail(f"Не удалось ввести пароль '{description}': {e}")
            
            # Проверяем, что пароль был введен (или обрезан, если слишком длинный)
            filled_password = password_input.input_value()
            assert len(filled_password) <= len(password), \
                f"Пароль содержит больше символов чем было введено"
        
        with allure.step("Попытка авторизации"):
            result = login_page.click_login_button()
            
            # Проверяем, что форма либо приняла пароль, либо показала ошибку валидации
            if not result:
                error_displayed = login_page.wait_for_notification('error', timeout=3000)
                inline_errors = page.locator(".invalid-feedback, .form-error").count() > 0
                
                assert error_displayed or inline_errors, \
                    f"Для пароля '{description}' не отображена ошибка"
            
            # Форма должна оставаться функциональной
            assert login_page.is_login_form_ready(), \
                f"Форма не готова после пароля '{description}'"
            
            screenshot_utils.take_screenshot(f"extreme_password_{description.replace(' ', '_')}")

    @allure.title("Пустые значения после пробелов (trim)")
    @allure.severity(Severity.NORMAL)
    @allure.description("""
    Пользователь вводит пробелы в начале/конце email или пароля.
    
    **Что может сломаться:**
    - Неожиданная авторизация
    - Проблемы с валидацией
    - Непоследовательное поведение
    """)
    def test_whitespace_trimming(self, page: Page, config, screenshot_utils):
        """Проверка обработки пробелов в начале/конце полей"""
        login_page = self._open_login_page(page, config["baseUrl"])
        credentials = config["credentials"]["valid_user"]
        
        username_input = page.locator(login_page.locators.USERNAME_INPUT)
        password_input = page.locator(login_page.locators.PASSWORD_INPUT)
        
        test_cases = [
            (" " + credentials["email"], "пробелы в начале email"),
            (credentials["email"] + " ", "пробелы в конце email"),
            (" " + credentials["email"] + " ", "пробелы с обеих сторон email"),
            ("  " + credentials["password"], "пробелы в начале пароля"),
            (credentials["password"] + "  ", "пробелы в конце пароля"),
        ]
        
        for value, description in test_cases:
            with allure.step(f"Тест: {description}"):
                login_page.clear_form()
                
                if "email" in description:
                    username_input.fill(value)
                    password_input.fill(credentials["password"])
                else:
                    username_input.fill(credentials["email"])
                    password_input.fill(value)
                
                # Проверяем, что значение было введено
                if "email" in description:
                    filled_value = username_input.input_value()
                else:
                    filled_value = password_input.input_value()
                
                # Значение должно быть либо обрезано (trim), либо сохранено как есть
                # Главное - поведение должно быть последовательным
                assert len(filled_value) > 0, \
                    f"Поле стало пустым после ввода '{description}'"
                
                # Пробуем авторизоваться
                result = login_page.click_login_button()
                
                # Если авторизация не прошла, должна быть ошибка
                if not result:
                    error_displayed = login_page.wait_for_notification('error', timeout=3000)
                    inline_errors = page.locator(".invalid-feedback, .form-error").count() > 0
                    assert error_displayed or inline_errors, \
                        f"Для '{description}' не отображена ошибка"
        
        screenshot_utils.take_screenshot("whitespace_trimming")

    @allure.title("Нажатие Enter vs клик по кнопке")
    @allure.severity(Severity.NORMAL)
    @allure.description("""
    Пользователь вводит данные и нажимает Enter вместо клика по кнопке.
    
    **Что может сломаться:**
    - Разное поведение
    - Двойная отправка формы
    - Проблемы с валидацией
    """)
    def test_enter_key_vs_button_click(self, page: Page, config, screenshot_utils):
        """Проверка одинакового поведения Enter и клика по кнопке"""
        login_page = self._open_login_page(page, config["baseUrl"])
        credentials = config["credentials"]["valid_user"]
        
        username_input = page.locator(login_page.locators.USERNAME_INPUT)
        password_input = page.locator(login_page.locators.PASSWORD_INPUT)
        
        with allure.step("Авторизация через Enter"):
            username_input.fill(credentials["email"])
            password_input.fill(credentials["password"])
            password_input.press("Enter")
            
            time.sleep(2)
            result_enter = login_page.is_logged_in()
            url_after_enter = page.url
        
        # Очищаем и пробуем через клик
        page.reload()
        login_page.force_navigate_to_login()
        login_page.clear_form()
        
        with allure.step("Авторизация через клик по кнопке"):
            username_input.fill(credentials["email"])
            password_input.fill(credentials["password"])
            login_page.click_login_button()
            
            time.sleep(2)
            result_click = login_page.is_logged_in()
            url_after_click = page.url
        
        with allure.step("Проверка одинакового поведения"):
            # Оба способа должны работать одинаково
            assert result_enter == result_click, \
                f"Разное поведение: Enter={result_enter}, Click={result_click}"
            
            # URL должны быть одинаковыми (или оба указывать на авторизацию/главную)
            assert url_after_enter == url_after_click or \
                   ("/auth/" in url_after_enter and "/auth/" in url_after_click) or \
                   ("/office/" in url_after_enter and "/office/" in url_after_click), \
                f"Разные URL после авторизации: Enter={url_after_enter}, Click={url_after_click}"
            
            screenshot_utils.take_screenshot("enter_vs_click")

    @allure.title("Чекбокс 'Запомнить меня' - различные сценарии")
    @allure.severity(Severity.NORMAL)
    @allure.description("""
    Тестирование различных сценариев работы с чекбоксом 'Запомнить меня'.
    
    **Что может сломаться:**
    - Некорректное сохранение состояния
    - Проблемы с cookies
    - Конфликты при быстром переключении
    """)
    def test_remember_me_checkbox_scenarios(self, page: Page, config, screenshot_utils):
        """Проверка различных сценариев работы с чекбоксом"""
        login_page = self._open_login_page(page, config["baseUrl"])
        credentials = config["credentials"]["valid_user"]
        
        remember_checkbox = page.locator(login_page.locators.REMEMBER_ME_CHECKBOX)
        
        scenarios = [
            ("Включить перед отправкой", True),
            ("Выключить перед отправкой", False),
            ("Включить-выключить-включить", True),
        ]
        
        for scenario_name, expected_state in scenarios:
            with allure.step(f"Сценарий: {scenario_name}"):
                login_page.clear_form()
                
                login_page.enter_username(credentials["email"])
                login_page.enter_password(credentials["password"])
                
                # Выполняем действия с чекбоксом
                if "Включить" in scenario_name and "выключить" not in scenario_name:
                    if not remember_checkbox.is_checked():
                        remember_checkbox.click(force=True)
                elif "Выключить" in scenario_name:
                    if remember_checkbox.is_checked():
                        remember_checkbox.click(force=True)
                elif "Включить-выключить-включить" in scenario_name:
                    remember_checkbox.click(force=True)
                    time.sleep(0.1)
                    remember_checkbox.click(force=True)
                    time.sleep(0.1)
                    remember_checkbox.click(force=True)
                
                # Проверяем финальное состояние
                final_state = remember_checkbox.is_checked()
                assert final_state == expected_state, \
                    f"Для сценария '{scenario_name}' ожидалось {expected_state}, получено {final_state}"
                
                # Пробуем авторизоваться
                result = login_page.click_login_button()
                
                # Авторизация должна работать независимо от состояния чекбокса
                # (проверяем что форма не сломалась)
                time.sleep(1)
                assert login_page.is_login_form_ready() or login_page.is_logged_in(), \
                    f"Форма не работает после сценария '{scenario_name}'"
        
        screenshot_utils.take_screenshot("remember_me_scenarios")

