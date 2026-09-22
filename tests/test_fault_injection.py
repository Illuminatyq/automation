import time
import logging

import allure
import pytest
from allure_commons.types import Severity
from playwright.sync_api import Page

from pages.login_page import LoginPage


MALICIOUS_PAYLOADS = [
    {"id": "xss_script", "value": "<script>alert('break')</script>"},
    {"id": "xss_img_onerror", "value": "<img src=x onerror=alert('break')>"},
    {"id": "sql_union", "value": "' UNION SELECT NULL--"},
    {"id": "sql_tautology", "value": "' OR '1'='1"},
    {"id": "nosql", "value": "{ \"$ne\": null }"},
    {"id": "command_injection", "value": "test@example.com; rm -rf /"},
    {"id": "template_injection", "value": "{{7*7}}"},
    {"id": "path_traversal", "value": "../../etc/passwd"},
    {"id": "format_string", "value": "%x%x%x%x"},
    {"id": "json_array", "value": "[1,2,3]"},
]


EXTREME_INPUT_SETS = [
    {
        "id": "long_ascii",
        "email": "user+" + "a" * 512 + "@example.com",
        "password": "P4ssW0rd!" * 128,
    },
    {
        "id": "null_byte",
        "email": "null\x00byte@example.com",
        "password": "pass\x00word",
    },
    {
        "id": "whitespace_spam",
        "email": " \t\n\r",
        "password": " \t\n\r",
    },
    {
        "id": "rtl_override",
        "email": "normal\u202Eevil@example.com",
        "password": "password\u202E321",
    },
    {
        "id": "emoji_payload",
        "email": "break\u2603er@example.com",
        "password": "\U0001F525" * 32,
    },
]


@allure.epic("Деструктивные сценарии")
@allure.feature("Форма авторизации")
@pytest.mark.auth
@pytest.mark.destructive
class TestAuthFaultInjection:
    """Намеренно деструктивные сценарии для формы авторизации."""

    def _open_login_page(self, page: Page, base_url: str) -> LoginPage:
        login_page = LoginPage(page, base_url)
        login_page.force_navigate_to_login()
        login_page.clear_form()
        return login_page

    @pytest.mark.parametrize("payload", MALICIOUS_PAYLOADS, ids=lambda p: p["id"])
    @allure.title("Отрицательный сценарий: вредоносные payload'ы")
    @allure.severity(Severity.CRITICAL)
    def test_login_rejects_malicious_payloads(self, page: Page, config, screenshot_utils, payload):
        """Проверяет, что типичные вредоносные полезные нагрузки не проходят авторизацию."""
        from utils.allure_helpers import AllureHelper
        
        try:
            login_page = self._open_login_page(page, config["baseUrl"])

            # Прикрепляем информацию о payload
            allure.attach(
                f"Payload ID: {payload['id']}\nPayload Value: {payload['value']}\nPayload Type: {type(payload['value']).__name__}",
                name=f"🔍 Payload '{payload['id']}'",
                attachment_type=allure.attachment_type.TEXT
            )

            with allure.step(f"Ввод вредоносного payload '{payload['id']}'"):
                login_page.enter_username(payload["value"])
                login_page.enter_password(payload["value"])
                screenshot_utils.take_screenshot(f"before_submit_{payload['id']}")

            with allure.step("Запрос авторизации и ожидание результата"):
                start_time = time.time()
                result = login_page.click_login_button()
                duration = time.time() - start_time
                
                # Прикрепляем метрики производительности
                AllureHelper.attach_performance_metrics({
                    "Длительность обработки (сек)": round(duration, 2),
                    "Payload ID": payload['id'],
                    "Результат авторизации": "Успешно" if result else "Отклонено"
                })

            with allure.step("Проверки отказа в авторизации"):
                # Скриншот после попытки авторизации
                screenshot_utils.take_screenshot(f"after_submit_{payload['id']}")
                
                # Прикрепляем информацию о странице
                AllureHelper.attach_page_info(page, f"Состояние после payload '{payload['id']}'")
                
                if result:
                    screenshot_utils.save_error_screenshot(f"unexpected_success_{payload['id']}")
                    allure.attach(
                        f"⚠️ ВНИМАНИЕ: Payload '{payload['id']}' привёл к успешной авторизации!\nЭто может быть уязвимостью безопасности!",
                        name="🚨 Критическая проблема",
                        attachment_type=allure.attachment_type.TEXT
                    )
                    assert False, f"Payload '{payload['id']}' неожиданно привёл к успешной авторизации"
                
                if duration >= 5:
                    screenshot_utils.save_error_screenshot(f"slow_response_{payload['id']}")
                    allure.attach(
                        f"⚠️ Подозрительно долгая обработка: {duration:.2f}s\nЭто может указывать на:\n- Time-based SQL инъекцию\n- Проблемы производительности\n- Блокировку/задержку защиты",
                        name="⏱️ Проблема производительности",
                        attachment_type=allure.attachment_type.TEXT
                    )
                    # Не падаем, но фиксируем проблему
                    logging.warning(f"Обработка payload '{payload['id']}' заняла подозрительно долго: {duration:.2f}s")
                
                if not login_page.is_login_form_ready():
                    screenshot_utils.save_error_screenshot(f"form_broken_{payload['id']}")
                    allure.attach(
                        f"⚠️ Форма авторизации стала недоступной после payload '{payload['id']}'\nЭто может указывать на:\n- XSS инъекцию, сломавшую DOM\n- Ошибку на сервере\n- Проблему с валидацией",
                        name="💥 Форма сломана",
                        attachment_type=allure.attachment_type.TEXT
                    )
                    assert False, "Форма авторизации должна оставаться доступной"

                error_displayed = login_page.wait_for_notification('error', timeout=3000)
                inline_errors = page.locator(".invalid-feedback, .form-error, .error-message").count() > 0
                
                if not (error_displayed or inline_errors):
                    screenshot_utils.save_error_screenshot(f"no_error_message_{payload['id']}")
                    allure.attach(
                        f"⚠️ Не отображено сообщение об ошибке после payload '{payload['id']}'\nПользователь не получит обратную связь о проблеме",
                        name="📢 Отсутствует обратная связь",
                        attachment_type=allure.attachment_type.TEXT
                    )
                    assert False, f"Не отображена ошибка после payload '{payload['id']}'"

                if page.is_closed():
                    screenshot_utils.save_error_screenshot(f"page_closed_{payload['id']}")
                    allure.attach(
                        f"⚠️ Страница закрылась после payload '{payload['id']}'\nЭто может указывать на критическую ошибку",
                        name="🔴 Страница закрыта",
                        attachment_type=allure.attachment_type.TEXT
                    )
                    assert False, "Страница не должна закрываться после некорректных данных"

            screenshot_utils.take_screenshot(f"malicious_payload_{payload['id']}_final")
            
        except AssertionError as e:
            screenshot_utils.save_error_screenshot(f"assertion_failed_{payload['id']}")
            AllureHelper.attach_error_details(e, {"payload": payload})
            raise
        except Exception as e:
            screenshot_utils.save_error_screenshot(f"exception_{payload['id']}")
            AllureHelper.attach_error_details(e, {"payload": payload})
            raise

    @pytest.mark.parametrize("payload", EXTREME_INPUT_SETS, ids=lambda p: p["id"])
    @allure.title("Отрицательный сценарий: экстремальные наборы данных")
    @allure.severity(Severity.BLOCKER)
    def test_login_with_extreme_inputs(self, page: Page, config, screenshot_utils, payload):
        """Проверяет реакцию формы авторизации на экстремальные по длине и содержанию значения."""
        login_page = self._open_login_page(page, config["baseUrl"])

        username_input = page.locator(login_page.locators.USERNAME_INPUT)
        password_input = page.locator(login_page.locators.PASSWORD_INPUT)

        with allure.step(f"Ввод экстремальных данных '{payload['id']}'"):
            try:
                username_input.fill(payload["email"])
                password_input.fill(payload["password"])
            except Exception as exc:
                pytest.fail(f"Не удалось ввести данные payload '{payload['id']}': {exc}")

        filled_email = username_input.input_value()
        filled_password = password_input.input_value()

        with allure.step("Валидация фактического значения полей"):
            assert filled_email == payload["email"], (
                f"Поле email было изменено/усечено для payload '{payload['id']}'. "
                f"Ожидалось {len(payload['email'])} символов, получено {len(filled_email)}"
            )
            assert filled_password == payload["password"], (
                f"Поле password было изменено/усечено для payload '{payload['id']}'. "
                f"Ожидалось {len(payload['password'])} символов, получено {len(filled_password)}"
            )

        with allure.step("Попытка авторизации"):
            result = login_page.click_login_button()

        with allure.step("Проверки устойчивости интерфейса"):
            assert not result, f"Экстремальные данные '{payload['id']}' неожиданно прошли авторизацию"
            ui_still_ready = login_page.is_login_form_ready()
            assert ui_still_ready, "Форма авторизации должна оставаться доступной после экстремальных данных"

            error_displayed = login_page.wait_for_notification('error', timeout=3000)
            inline_errors = page.locator(".invalid-feedback, .form-error, .error-message").count() > 0
            assert error_displayed or inline_errors, f"Ожидалась ошибка или валидация для payload '{payload['id']}'"

            assert not page.is_closed(), "Страница не должна закрываться после экстремальных данных"

        screenshot_utils.take_screenshot(f"extreme_payload_{payload['id']}")

    @allure.title("Отрицательный сценарий: смешанные хаотичные вводы по шагам")
    @allure.severity(Severity.CRITICAL)
    def test_stepwise_faulty_sequence(self, page: Page, config, screenshot_utils):
        """
        Проверяет поведение формы при последовательном вводе различных типов данных,
        имитируя непредсказуемые действия пользователя.
        """
        login_page = self._open_login_page(page, config["baseUrl"])
        username_input = page.locator(login_page.locators.USERNAME_INPUT)
        password_input = page.locator(login_page.locators.PASSWORD_INPUT)

        chaotic_sequence = [
            ("<svg/onload=alert('1')>", "xss_stage"),
            ("' OR 'x'='x", "sql_stage"),
            ("  ", "whitespace_stage"),
            ("../../../../etc/passwd", "path_stage"),
            ("{{7*7}}", "template_stage"),
            ("break\u202Eflow@example.com", "rtl_stage"),
        ]

        for value, stage in chaotic_sequence:
            with allure.step(f"Стадия {stage}: ввод '{value}'"):
                try:
                    username_input.fill(value)
                    password_input.fill(value)
                except Exception as exc:
                    pytest.fail(f"Stage '{stage}': заполнение полей завершилось ошибкой: {exc}")

                # Проверяем, что значение действительно выставлено (или становится пустым)
                current_email = username_input.input_value()
                current_password = password_input.input_value()
                if current_email != value or current_password != value:
                    logging.warning(
                        "Stage '%s': значение поля было модифицировано браузером или фронтендом. "
                        "email='%s', password='%s'",
                        stage,
                        current_email,
                        current_password,
                    )

                result = login_page.click_login_button()
                assert not result, f"Стадия '{stage}' неожиданно прошла авторизацию"

                still_ready = login_page.is_login_form_ready()
                assert still_ready, f"Форма авторизации не готова после стадии '{stage}'"

                login_page.clear_form()

        screenshot_utils.take_screenshot("stepwise_faulty_sequence")

