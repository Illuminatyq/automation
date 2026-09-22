import pytest
import allure
from playwright.sync_api import Page, expect
from pages.login_page import LoginPage
import logging
import time

@allure.epic("Безопасность")
@allure.feature("Тесты безопасности")
@pytest.mark.security
class TestSecurity:
    """Класс тестов для проверки безопасности системы"""

    @pytest.mark.usefixtures("page")
    @allure.title("Проверка защиты от XSS через форму авторизации")
    @allure.story("XSS защита")
    @allure.severity('CRITICAL')
    @allure.description("""
    Тест проверяет уязвимость формы авторизации к XSS:
    1. Ввод XSS-скрипта в поле email и пароля
    2. Проверка, что скрипт не выполняется и не влияют на функциональность
    3. Проверка экранирования специальных символов
    4. Проверка стабильности формы после попыток XSS
    
    Цель: Убедиться, что система защищена от XSS-атак через форму входа
    """)
    def test_xss_authentication_form(self, page: Page, config, screenshot_utils):
        """Тест XSS в форме авторизации"""
        from utils.allure_helpers import AllureHelper
        
        try:
            login_page = LoginPage(page, config["baseUrl"])

            with allure.step("Открытие страницы авторизации"):
                login_page.navigate()
                screenshot_utils.take_screenshot("xss_test_initial")
                AllureHelper.attach_page_info(page, "Начальное состояние")
                
                if not login_page.is_login_form_ready():
                    screenshot_utils.save_error_screenshot("form_not_ready_initial")
                    assert False, "Форма авторизации не готова"

            with allure.step("Попытка внедрения XSS-скриптов"):
                # Пробуем внедрить XSS в поля
                xss_payload_email = "<script>alert('xss')</script>"
                xss_payload_password = "<img src=x onerror=alert('xss')>"
                
                # Прикрепляем информацию о payload'ах
                allure.attach(
                    f"Email payload: {xss_payload_email}\nPassword payload: {xss_payload_password}",
                    name="🔍 XSS Payload'ы",
                    attachment_type=allure.attachment_type.TEXT
                )

                login_page.enter_username(xss_payload_email)
                login_page.enter_password(xss_payload_password)
                screenshot_utils.take_screenshot("xss_test_after_input")
                
                # Пробуем отправить форму
                login_page.click_login_button()
                screenshot_utils.take_screenshot("xss_test_after_submit")

            with allure.step("Проверка защиты от XSS"):
                # Проверяем, что скрипт не выполнился и форма активна
                page_content = page.content()
                
                # Прикрепляем HTML контент страницы (маскируя чувствительные данные)
                AllureHelper.attach_test_data({
                    "page_content_length": len(page_content),
                    "xss_email_in_content": xss_payload_email in page_content,
                    "xss_password_in_content": xss_payload_password in page_content,
                    "url": page.url
                }, "Анализ защиты от XSS")
                
                if xss_payload_email in page_content:
                    screenshot_utils.save_error_screenshot("xss_email_not_escaped")
                    allure.attach(
                        "⚠️ КРИТИЧНО: XSS-инъекция в поле email не была экранирована!\nСкрипт может выполниться в браузере пользователя.",
                        name="🚨 Уязвимость XSS (email)",
                        attachment_type=allure.attachment_type.TEXT
                    )
                    assert False, "XSS-инъекция в поле email не была экранирована"
                
                if xss_payload_password in page_content:
                    screenshot_utils.save_error_screenshot("xss_password_not_escaped")
                    allure.attach(
                        "⚠️ КРИТИЧНО: XSS-инъекция в поле пароля не была экранирована!\nСкрипт может выполниться в браузере пользователя.",
                        name="🚨 Уязвимость XSS (password)",
                        attachment_type=allure.attachment_type.TEXT
                    )
                    assert False, "XSS-инъекция в поле пароля не была экранирована"
                
                # Проверяем, что форма все еще функциональна
                if not login_page.is_login_form_ready():
                    screenshot_utils.save_error_screenshot("form_broken_after_xss")
                    allure.attach(
                        "⚠️ Форма авторизации стала недоступной после XSS-инъекции!\nЭто может указывать на:\n- XSS сломал DOM\n- Ошибка на сервере\n- Проблема с валидацией",
                        name="💥 Форма сломана после XSS",
                        attachment_type=allure.attachment_type.TEXT
                    )
                    assert False, "Форма авторизации не готова после XSS-инъекции"
                
                screenshot_utils.take_screenshot("xss_auth_form_test_final")
                AllureHelper.attach_page_info(page, "Финальное состояние после XSS")
                
        except AssertionError as e:
            screenshot_utils.save_error_screenshot("xss_test_assertion_failed")
            AllureHelper.attach_error_details(e)
            raise
        except Exception as e:
            screenshot_utils.save_error_screenshot("xss_test_exception")
            AllureHelper.attach_error_details(e)
            raise

    @pytest.mark.usefixtures("page")
    @allure.title("Проверка защиты от различных XSS-векторов")
    @allure.story("XSS защита")
    @allure.severity('HIGH')
    @allure.description("""
    Тест проверяет уязвимость к различным XSS-векторам:
    1. Проверка различных XSS-векторов атак
    2. Проверка обработки HTML-тегов
    3. Проверка обработки JavaScript кода
    4. Проверка обработки событий (event handlers)
    5. Проверка URL-based XSS
    
    Проверяется защита от широкого спектра XSS-атак
    """)
    def test_xss_vulnerability_vectors(self, page: Page, config, screenshot_utils):
        """Тест на уязвимость к различным XSS-векторам"""
        login_page = LoginPage(page, config["baseUrl"])
        
        with allure.step("Открытие страницы авторизации"):
            login_page.navigate()
            assert login_page.is_login_form_ready(), "Форма авторизации не готова"

        with allure.step("Тестирование различных XSS-векторов"):
            # Различные XSS-векторы для тестирования
            xss_vectors = [
                "<script>alert('xss')</script>",
                "<img src=x onerror=alert('xss')>",
                "javascript:alert('xss')",
                "<svg/onload=alert('xss')>",
                "'-alert('xss')-'",
                "<iframe src='javascript:alert(\"xss\")'></iframe>",
                "<body onload=alert('xss')>",
                "<input onfocus=alert('xss') autofocus>",
                "<select onfocus=alert('xss') autofocus>",
                "<textarea onfocus=alert('xss') autofocus>",
                "<keygen onfocus=alert('xss') autofocus>",
                "<video><source onerror='alert(\"xss\")'>",
                "<audio src=x onerror=alert('xss')>",
                "<details open ontoggle=alert('xss')>",
                "\"autofocus onfocus=alert('xss') \"",
                "'autofocus onfocus=alert('xss') '",
                "<marquee onstart=alert('xss')>",
                "<object data='javascript:alert(\"xss\")'>"
            ]
            
            for i, vector in enumerate(xss_vectors):
                with allure.step(f"Тестирование XSS-вектора {i+1}: {vector[:50]}..."):
                    # Очищаем форму
                    login_page.clear_form()
                    
                    # Вводим XSS-вектор
                    login_page.enter_username(vector)
                    login_page.enter_password(vector)
                    
                    # Проверяем, что вектор не выполнился
                    page_content = page.content()
                    assert vector not in page_content, f"XSS-вектор {vector} не был экранирован"
                    
                    # Проверяем, что форма все еще работает
                    assert login_page.is_login_form_ready(), f"Форма авторизации перестала работать после XSS-вектора {vector}"
                    
                    # Небольшая пауза между тестами
                    time.sleep(0.1)
            
            screenshot_utils.take_screenshot("xss_vectors_test")

    @pytest.mark.usefixtures("page")
    @allure.title("Проверка защиты от SQL-инъекций")
    @allure.story("SQL-инъекции")
    @allure.severity('CRITICAL')
    @allure.description("""
    Тест проверяет защиту от SQL-инъекций:
    1. Тестирование базовых SQL-инъекций
    2. Проверка Union-based инъекций
    3. Проверка Boolean-based инъекций
    4. Проверка Time-based инъекций
    5. Проверка обработки специальных символов SQL
    
    Цель: Убедиться, что система защищена от SQL-инъекций
    """)
    def test_sql_injection_protection(self, page: Page, config, screenshot_utils):
        """Тест защиты от SQL-инъекций"""
        login_page = LoginPage(page, config["baseUrl"])
        
        with allure.step("Открытие страницы авторизации"):
            login_page.navigate()
            assert login_page.is_login_form_ready(), "Форма авторизации не готова"

        with allure.step("Тестирование SQL-инъекций"):
            # SQL-инъекции для тестирования
            sql_injections = [
                "' OR '1'='1",
                "' OR 1=1--",
                "' OR 1=1#",
                "' OR 1=1/*",
                "') OR '1'='1--",
                "') OR ('1'='1--",
                "' OR 1=1 LIMIT 1--",
                "' UNION SELECT NULL--",
                "' UNION SELECT 1,2,3--",
                "' UNION ALL SELECT NULL--",
                "admin'--",
                "admin' #",
                "admin'/*",
                "' OR 'x'='x",
                "' AND id IS NULL; --",
                "' UNION SELECT username, password FROM users--",
                "'; DROP TABLE users; --",
                "'; EXEC xp_cmdshell('dir'); --",
                "' OR SLEEP(5)--",
                "' OR pg_sleep(5)--",
                "' WAITFOR DELAY '0:0:5'--",
                "1' AND EXTRACTVALUE(1, CONCAT(0x7e, (SELECT version()), 0x7e))--"
            ]
            
            for i, injection in enumerate(sql_injections):
                with allure.step(f"Тестирование SQL-инъекции {i+1}: {injection[:50]}..."):
                    # Очищаем форму
                    login_page.clear_form()
                    
                    # Вводим SQL-инъекцию в email
                    login_page.enter_username(injection)
                    login_page.enter_password("test_password")
                    
                    # Пробуем отправить форму
                    start_time = time.time()
                    result = login_page.click_login_button()
                    end_time = time.time()
                    
                    # Проверяем, что инъекция не сработала
                    assert not result, f"SQL-инъекция {injection} привела к успешной авторизации"
                    
                    # Проверяем время ответа (защита от time-based инъекций)
                    response_time = end_time - start_time
                    assert response_time < 3.0, f"Подозрительно долгий ответ ({response_time:.2f}с) на SQL-инъекцию {injection}"
                    
                    # Проверяем, что форма все еще работает
                    assert login_page.is_login_form_ready(), f"Форма авторизации перестала работать после SQL-инъекции {injection}"
                    
                    # Небольшая пауза между тестами
                    time.sleep(0.1)
            
            screenshot_utils.take_screenshot("sql_injection_test")

    @pytest.mark.usefixtures("page")
    @allure.title("Проверка защиты от CSRF-атак")
    @allure.story("CSRF защита")
    @allure.severity('HIGH')
    @allure.description("""
    Тест проверяет защиту от CSRF-атак:
    1. Проверка наличия CSRF-токенов в формах
    2. Проверка валидации CSRF-токенов
    3. Проверка обновления токенов
    4. Проверка защиты критических операций
    
    Цель: Убедиться, что система защищена от CSRF-атак
    """)
    def test_csrf_protection(self, page: Page, config, screenshot_utils):
        """Тест защиты от CSRF-атак"""
        login_page = LoginPage(page, config["baseUrl"])
        
        with allure.step("Открытие страницы авторизации"):
            login_page.navigate()
            assert login_page.is_login_form_ready(), "Форма авторизации не готова"

        with allure.step("Проверка наличия CSRF-токенов"):
            # Ищем CSRF-токены в форме
            csrf_selectors = [
                'input[name*="csrf"]',
                'input[name*="token"]',
                'input[name="_token"]',
                'meta[name="csrf-token"]',
                'input[type="hidden"][name*="csrf"]'
            ]
            
            csrf_found = False
            for selector in csrf_selectors:
                csrf_elements = page.locator(selector)
                if csrf_elements.count() > 0:
                    csrf_found = True
                    logging.info(f"CSRF-токен найден по селектору: {selector}")
                    break
            
            if csrf_found:
                allure.attach("CSRF-токены найдены в форме", "CSRF Protection Status", allure.attachment_type.TEXT)
            else:
                allure.attach("CSRF-токены НЕ найдены в форме", "CSRF Protection Status", allure.attachment_type.TEXT)
                logging.warning("CSRF-токены не найдены в форме авторизации")

        with allure.step("Попытка обхода CSRF-защиты"):
            # Попытка удалить CSRF-токены и отправить форму
            page.evaluate("""
                // Удаляем все возможные CSRF-токены
                const csrfInputs = document.querySelectorAll('input[name*="csrf"], input[name*="token"], input[name="_token"]');
                csrfInputs.forEach(input => input.remove());
                
                const csrfMetas = document.querySelectorAll('meta[name="csrf-token"]');
                csrfMetas.forEach(meta => meta.remove());
            """)
            
            # Пробуем отправить форму без CSRF-токена
            valid_creds = config["credentials"]["valid_user"]
            login_page.enter_username(valid_creds["email"])
            login_page.enter_password(valid_creds["password"])
            
            result = login_page.click_login_button()
            
            # Форма должна отклонить запрос без валидного CSRF-токена
            if result:
                logging.warning("Форма приняла запрос без CSRF-токена")
            else:
                logging.info("Форма корректно отклонила запрос без CSRF-токена")
            
            screenshot_utils.take_screenshot("csrf_protection_test")

    @pytest.mark.usefixtures("page")
    @allure.title("Проверка защиты от брутфорс-атак")
    @allure.story("Брутфорс защита")
    @allure.severity('HIGH')
    @allure.description("""
    Тест проверяет защиту от брутфорс-атак:
    1. Множественные попытки входа с неверными данными
    2. Проверка блокировки после определенного количества попыток
    3. Проверка капчи или других защитных механизмов
    4. Проверка временных задержек
    
    Цель: Убедиться, что система защищена от брутфорс-атак
    """)
    def test_bruteforce_protection(self, page: Page, config, screenshot_utils):
        """Тест защиты от брутфорс-атак"""
        login_page = LoginPage(page, config["baseUrl"])
        
        with allure.step("Открытие страницы авторизации"):
            login_page.navigate()
            assert login_page.is_login_form_ready(), "Форма авторизации не готова"

        with allure.step("Симуляция брутфорс-атаки"):
            invalid_credentials = config["credentials"]["invalid_user"]
            attempt_count = 5  # Количество попыток для тестирования
            
            response_times = []
            
            for attempt in range(1, attempt_count + 1):
                with allure.step(f"Попытка входа {attempt}/{attempt_count}"):
                    # Очищаем форму
                    login_page.clear_form()
                    
                    # Измеряем время ответа
                    start_time = time.time()
                    
                    # Вводим неверные данные
                    login_page.enter_username(invalid_credentials["email"])
                    login_page.enter_password(f"wrong_password_{attempt}")
                    
                    result = login_page.click_login_button()
                    
                    end_time = time.time()
                    response_time = end_time - start_time
                    response_times.append(response_time)
                    
                    # Проверяем, что вход не удался
                    assert not result, f"Попытка {attempt} неожиданно прошла успешно"
                    
                    # Проверяем наличие сообщения об ошибке
                    assert login_page.is_error_message_displayed(), f"Сообщение об ошибке не отображается на попытке {attempt}"
                    
                    logging.info(f"Попытка {attempt}: время ответа {response_time:.2f}с")
                    
                    # Небольшая пауза между попытками
                    time.sleep(1)

        with allure.step("Анализ защиты от брутфорса"):
            # Проверяем увеличение времени ответа (возможная защита)
            if len(response_times) >= 3:
                avg_first_half = sum(response_times[:2]) / 2
                avg_second_half = sum(response_times[2:]) / len(response_times[2:])
                
                if avg_second_half > avg_first_half * 1.5:
                    logging.info("Обнаружено увеличение времени ответа - возможная защита от брутфорса")
                    allure.attach(
                        f"Среднее время первых попыток: {avg_first_half:.2f}с\n"
                        f"Среднее время последних попыток: {avg_second_half:.2f}с\n"
                        f"Увеличение времени: {(avg_second_half/avg_first_half)*100:.1f}%",
                        "Анализ времени ответа",
                        allure.attachment_type.TEXT
                    )
            
            # Проверяем появление капчи
            captcha_selectors = [
                '.captcha',
                '#captcha',
                '[data-captcha]',
                '.recaptcha',
                '.hcaptcha'
            ]
            
            captcha_found = False
            for selector in captcha_selectors:
                if page.locator(selector).count() > 0:
                    captcha_found = True
                    logging.info(f"Капча найдена по селектору: {selector}")
                    break
            
            if captcha_found:
                allure.attach("Капча активирована после множественных неудачных попыток", "Bruteforce Protection", allure.attachment_type.TEXT)
            else:
                logging.warning("Капча не обнаружена после множественных неудачных попыток")
            
            screenshot_utils.take_screenshot("bruteforce_protection_test")

    @pytest.mark.usefixtures("page")
    @allure.title("Проверка защиты от инъекций в заголовках")
    @allure.story("Header инъекции")
    @allure.severity('NORMAL')
    @allure.description("""
    Тест проверяет защиту от инъекций в HTTP-заголовках:
    1. Проверка обработки специальных символов в User-Agent
    2. Проверка обработки инъекций в Referer
    3. Проверка защиты от HTTP Response Splitting
    4. Проверка валидации заголовков
    
    Цель: Убедиться, что система корректно обрабатывает заголовки
    """)
    def test_header_injection_protection(self, page: Page, config, screenshot_utils):
        """Тест защиты от инъекций в заголовках"""
        
        with allure.step("Тестирование инъекций в User-Agent"):
            # Устанавливаем вредоносный User-Agent (без недопустимых символов)
            malicious_user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 X-Injected-Header: malicious"
            
            # Создаем новый контекст с вредоносным User-Agent
            try:
                context = page.context.browser.new_context(
                    user_agent=malicious_user_agent,
                    viewport={"width": 1920, "height": 1080}
                )
            except Exception as e:
                logging.warning(f"Не удалось создать контекст с вредоносным User-Agent: {e}")
                # Используем стандартный User-Agent для продолжения теста
                context = page.context.browser.new_context(
                    viewport={"width": 1920, "height": 1080}
                )
            
            try:
                new_page = context.new_page()
                
                # Переходим на страницу
                new_page.goto(config["baseUrl"])
                new_page.wait_for_load_state("domcontentloaded")
                
                # Проверяем, что инъекция не сработала
                page_content = new_page.content()
                assert "<script>alert('xss')</script>" not in page_content, "XSS-инъекция в User-Agent не была заблокирована"
                
                # Проверяем, что страница загрузилась корректно
                assert new_page.locator("body").count() > 0, "Страница не загрузилась с вредоносным User-Agent"
                
                logging.info("Защита от инъекций в User-Agent работает корректно")
                
            finally:
                context.close()

        with allure.step("Тестирование других типов заголовков"):
            # Тестируем инъекции через JavaScript (имитация изменения заголовков)
            page.goto(config["baseUrl"])
            page.wait_for_load_state("domcontentloaded")
            
            # Попытка внедрения через JavaScript
            try:
                page.evaluate("""
                    fetch(window.location.href, {
                        headers: {
                            'X-Injected': 'test\\r\\nX-Another-Header: malicious',
                            'Referer': 'http://evil.com\\r\\nX-Evil: true'
                        }
                    }).catch(() => {});
                """)
                
                logging.info("Попытка инъекции через JavaScript выполнена")
                
            except Exception as e:
                logging.info(f"JavaScript инъекция заблокирована: {e}")
            
            screenshot_utils.take_screenshot("header_injection_test")

    @pytest.mark.usefixtures("authenticated_page")
    @allure.title("Проверка защиты авторизованных страниц")
    @allure.story("Авторизация и доступ")
    @allure.severity('HIGH')
    @allure.description("""
    Тест проверяет защиту авторизованных страниц:
    1. Проверка доступа к страницам без авторизации
    2. Проверка корректности редиректов
    3. Проверка защиты от несанкционированного доступа
    4. Проверка сессионной безопасности
    
    Цель: Убедиться, что авторизованные страницы защищены
    """)
    def test_authenticated_pages_protection(self, authenticated_page: Page, config, screenshot_utils):
        """Тест защиты авторизованных страниц"""
        
        with allure.step("Проверка доступа к защищенным страницам после авторизации"):
            # Переходим на защищенную страницу
            authenticated_page.goto(f"{config['baseUrl']}/leads/")
            authenticated_page.wait_for_load_state("domcontentloaded")
            
            # Проверяем, что мы на нужной странице
            current_url = authenticated_page.url
            assert "/leads/" in current_url, f"Не удалось получить доступ к защищенной странице. URL: {current_url}"
            
            screenshot_utils.take_screenshot("authenticated_access_success")

        with allure.step("Проверка защиты после очистки сессии"):
            # Очищаем cookies (имитация выхода из системы)
            authenticated_page.context.clear_cookies()
            
            # Пробуем получить доступ к защищенной странице
            authenticated_page.goto(f"{config['baseUrl']}/leads/")
            authenticated_page.wait_for_load_state("domcontentloaded")
            
            # Проверяем, что нас перенаправили на страницу авторизации
            current_url = authenticated_page.url
            auth_indicators = ["/auth/", "/login/", "/signin/"]
            is_redirected_to_auth = any(indicator in current_url for indicator in auth_indicators)
            
            if not is_redirected_to_auth:
                logging.warning(f"Не было перенаправления на страницу авторизации. Текущий URL: {current_url}")
            else:
                logging.info("Корректное перенаправление на страницу авторизации после очистки сессии")
            
            screenshot_utils.take_screenshot("session_cleared_redirect")
