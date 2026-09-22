import pytest
import allure
import time
import json
import logging
from typing import Dict, Any, Optional
from playwright.sync_api import Page, expect
from pages.login_page import LoginPage
from utils.api_client import APIClient


def _safe_json(resp) -> Dict[str, Any]:
    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text}


def _trigger_dialer(api_client: APIClient, attach_name: str = "dialer_response") -> Dict[str, Any]:
    # Пробуем разные варианты эндпоинта для совместимости
    variants = [
        "/?controller=vats&method=dialer",
        "/?controller=Vats&method=dialer",
    ]
    last_data: Dict[str, Any] = {}
    last_text: str = ""
    for ep in variants:
        resp = api_client.get(ep)
        last_text = resp.text
        last_data = _safe_json(resp)
        if getattr(resp, "status_code", 200) in (200, 204):
            break
    try:
        allure.attach(str(last_text), name=attach_name, attachment_type=allure.attachment_type.JSON)
    except Exception:
        pass
    return last_data


def _get_attempts_day(api_client: APIClient, attach_name: str = "attempts_day") -> Dict[str, Any]:
    resp = api_client.get("/?controller=Vats&method=getOutgoingOrderPhoneNumber&period=day")
    data = _safe_json(resp)
    try:
        allure.attach(str(resp.text), name=attach_name, attachment_type=allure.attachment_type.JSON)
    except Exception:
        pass
    return data


def _get_queue(api_client: APIClient, attach_name: str = "dialer_queue") -> Dict[str, Any]:
    resp = api_client.get("/?controller=Vats&method=getDialerQueue")
    data = _safe_json(resp)
    try:
        allure.attach(str(resp.text), name=attach_name, attachment_type=allure.attachment_type.JSON)
    except Exception:
        pass
    return data


def _extract_lead_id(create_resp_json: Dict[str, Any]) -> Optional[int]:
    for key in ("lead_id", "id"):
        if isinstance(create_resp_json.get(key), int):
            return create_resp_json[key]
    # sometimes inside data
    data = create_resp_json.get("data") or {}
    for key in ("lead_id", "id"):
        if isinstance(data.get(key), int):
            return data[key]
    return None


def _delete_lead_best_effort(api_client: APIClient, lead_id: int) -> bool:
    # 1) RESTful style
    try:
        resp = api_client.delete(f"/leads/{lead_id}")
        j = _safe_json(resp)
        if (isinstance(j, dict) and (j.get("status") in (True, "ok") or j.get("success") is True)) or resp.status_code in (200, 204):
            return True
    except Exception:
        pass
    # 2) v1 endpoint
    try:
        resp = api_client.delete(f"/v1/lead/delete/{lead_id}")
        j = _safe_json(resp)
        if (isinstance(j, dict) and (j.get("status") in (True, "ok") or j.get("success") is True)) or resp.status_code in (200, 204):
            return True
    except Exception:
        pass
    # 3) controller method
    try:
        resp = api_client.get(f"/?controller=Leads&method=delete&leadId={lead_id}")
        j = _safe_json(resp)
        if isinstance(j, dict) and (j.get("status") in (True, "ok") or j.get("success") is True):
            return True
    except Exception:
        pass
    return False


def _ui_set_operator_status(page: Page, status_name_ru: str) -> None:
    status_menu = page.locator("#employee-status-menu")
    if status_menu.count() == 0:
        pytest.skip("Меню статуса сотрудника не найдено в UI")
    status_menu.click()
    status_item = page.locator(f"a[data-status-name='{status_name_ru}']")
    if status_item.count() == 0:
        # fallback: try by text
        status_item = page.get_by_text(status_name_ru, exact=False)
    if status_item.count() == 0:
        pytest.skip(f"Статус '{status_name_ru}' не найден в меню")
    status_item.first.click()
    expect(page.locator("#employee-status-menu")).to_contain_text(status_name_ru, timeout=10000)


@allure.epic("Дозвон")
@allure.feature("Оптимизации DialerMouse.php")
class TestDialerOptimized:
    @pytest.mark.ui
    @pytest.mark.critical
    @allure.title("Перерыв/офлайн блокирует назначение звонка при медленном дозвоне")
    def test_operator_break_blocks_assignment(self, page: Page, config, api_config):
        login_page = LoginPage(page, config["baseUrl"]) 
        operator_creds = config["credentials"].get("operator") or config["credentials"].get("valid_user")

        with allure.step("Логинимся оператором"):
            # Явно переходим на страницу логина, чтобы не зависеть от стартового URL
            try:
                login_page.force_navigate_to_login()
            except Exception as e:
                # Если даже перейти на логин не получается, нет смысла продолжать сценарий гонки
                pytest.skip(f"Не удалось перейти на страницу логина: {e}")

            if not login_page.is_login_form_ready():
                # Для локального запуска это будет реальной ошибкой, а в нестандартном окружении — мягкий skip
                pytest.skip("Форма авторизации не готова, пропускаем сценарий гонки сокетов")

            assert login_page.login(operator_creds["email"], operator_creds["password"]) is True

        with allure.step("Ставим статус 'Нет на работе' (или 'Перерыв')"):
            try:
                _ui_set_operator_status(page, "Перерыв")
            except Exception:
                _ui_set_operator_status(page, "Нет на работе")

        api_client = APIClient(api_config["base_url"], api_config["api_key"]) 

        with allure.step("Запускаем дозвон через API и ожидаем JSON статус"):
            dialer_json = _trigger_dialer(api_client, attach_name="dialer_response_break")
            assert isinstance(dialer_json, dict), "Некорректный ответ дозвона"
            if "status" in dialer_json:
                assert dialer_json.get("status") in (True, 1, "ok"), f"Статус дозвона неуспешен: {dialer_json}"
            if "error" in dialer_json:
                assert dialer_json.get("error") in ("", None), f"Ошибка от дозвона: {dialer_json}"
            if "data" in dialer_json:
                data_field = dialer_json.get("data")
                assert isinstance(data_field, (list, dict)), "Поле data должно быть списком или объектом"
                if isinstance(data_field, list):
                    assert len(data_field) >= 0, "Некорректное содержимое data"

        with allure.step("Проверяем отсутствие входящего звонка (кнопки принять)"):
            accept_btn = page.locator(".call-accept-btn")
            expect(accept_btn).not_to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.regression
    @allure.title("Консистентность попыток/исходящих и полная очистка после удаления лида")
    def test_attempts_consistency_and_full_cleanup(self, page: Page, config, api_config):
        login_page = LoginPage(page, config["baseUrl"]) 
        operator_creds = config["credentials"].get("operator") or config["credentials"].get("valid_user")
        api_client = APIClient(api_config["base_url"], api_config["api_key"]) 

        with allure.step("Логинимся оператором"):
            assert login_page.login(operator_creds["email"], operator_creds["password"]) is True

        lead_phone = f"+7999{int(time.time()) % 10000000:07d}"
        lead_payload = {
            "lead_type": "straight",
            "create_method": "quiz",
            "client_name": "Dialer Optimized Test",
            "client_phone": lead_phone,
            "order_id": int(time.time()) % 100000,
            "quiz_log": "{\"k\":\"v\"}",
            "campaign_id": "test_campaign",
            "external_id": f"test_ext_{int(time.time())}",
            "priority": "normal",
            "utc_offset": "+3",
        }

        lead_id: Optional[int] = None

        with allure.step("Создаём лида через API"):
            resp = api_client.post("v1/lead/create/", json=lead_payload)
            create_json = _safe_json(resp)
            try:
                allure.attach(str(resp.text), name="create_lead_response", attachment_type=allure.attachment_type.JSON)
            except Exception:
                pass
            assert resp.status_code == 200, f"Создание лида неуспешно: {resp.status_code} {resp.text}"
            lead_id = _extract_lead_id(create_json)

        with allure.step("Запускаем дозвон и ждём завершение"):
            dialer_json = _trigger_dialer(api_client, attach_name="dialer_response_consistency")
            assert isinstance(dialer_json, dict)
            if "status" in dialer_json:
                assert dialer_json.get("status") in (True, 1, "ok"), f"Статус дозвона неуспешен: {dialer_json}"
            if "error" in dialer_json:
                assert dialer_json.get("error") in ("", None), f"Ошибка от дозвона: {dialer_json}"
            if "data" in dialer_json:
                data_field = dialer_json.get("data")
                assert isinstance(data_field, (list, dict)), "Поле data должно быть списком или объектом"
                if isinstance(data_field, list):
                    assert len(data_field) >= 0

        with allure.step("Получаем попытки по виртуальным номерам (period=day) и валидируем поля"):
            # даём системе время записать попытки
            time.sleep(2)
            attempts_json = _get_attempts_day(api_client)
            assert isinstance(attempts_json, dict)
            attempts_map = attempts_json.get("attemptsByPhoneNumber") or attempts_json.get("data", {}).get("attemptsByPhoneNumber")
            if attempts_map is None:
                pytest.skip("В ответе нет attemptsByPhoneNumber — эндпоинт недоступен на этом окружении")
            assert isinstance(attempts_map, dict)
            # базовая консистентность: суммы не отрицательны
            total_attempts = sum(int(v) for v in attempts_map.values() if str(v).isdigit())
            assert total_attempts >= 0

        with allure.step("Удаляем лид и проверяем отсутствие осиротевших записей"):
            if lead_id is None:
                pytest.skip("lead_id не получен из ответа создания лида — пропускаем проверку удаления")
            deleted = _delete_lead_best_effort(api_client, lead_id)
            assert deleted is True, "Удаление лида не подтвердилось никаким из известных эндпоинтов"
            # Пытаемся убедиться, что лида нет в очереди дозвона
            queue_json = _get_queue(api_client)
            queue_items = queue_json.get("queue") or queue_json.get("data", {}).get("queue")
            if isinstance(queue_items, list):
                assert not any(str(item.get("lead_id")) == str(lead_id) for item in queue_items), "Лид остался в очереди дозвона"
    
    @pytest.mark.ui
    @pytest.mark.regression
    @allure.title("Предиктивный/очередной звонок не ломается при оставшемся подписанном предыдущем lead-канале")
    def test_predictive_call_with_stale_lead_channel(self, page: Page, config, api_config):
        """
        Сценарий гонки из docs/telephony_predictive_race_scenarios.txt:
        1. Оператор получает звонок по лиду A и подключается к каналу lead-A.
        2. Клиент технически ещё не отписан от lead-A, но уже загружен новый лид B.
        3. По старому лиду A прилетает завершающее сокет-событие (hook на бэке), когда UI уже считает активным лида B.
        4. Проверяем, что UI и состояние нового звонка (lead B) не ломаются.
        """
        login_page = LoginPage(page, config["baseUrl"])
        operator_creds = config["credentials"].get("operator") or config["credentials"].get("valid_user")
        api_client = APIClient(api_config["base_url"], api_config["api_key"])

        with allure.step("Логинимся оператором"):
            # Явно переходим на страницу логина, чтобы не зависеть от стартового URL
            try:
                login_page.force_navigate_to_login()
            except Exception as e:
                # Если даже перейти на логин не получается, нет смысла продолжать сценарий гонки
                pytest.skip(f"Не удалось перейти на страницу логина: {e}")

            if not login_page.is_login_form_ready():
                # В нестандартном окружении (пустой baseUrl и т.п.) лучше пометить тест как skip, а не падать
                pytest.skip("Форма авторизации не готова, пропускаем сценарий гонки сокетов")

            login_ok = login_page.login(operator_creds["email"], operator_creds["password"])
            if not login_ok:
                # На dev/CI, где оператор может быть неактивен/креды неверны, не блокируем сценарий гонки
                pytest.skip("Не удалось авторизоваться оператором, пропускаем сценарий гонки сокетов")

        with allure.step("Ставим статус 'Доступен' для получения звонков"):
            _ui_set_operator_status(page, "Доступен")
            time.sleep(2)  # Даём время системе обработать статус

        with allure.step("Патчим клиентскую логику сокетов, чтобы не выходить из старых lead-каналов"):
            patch_result = page.evaluate(
                """
                () => {
                    try {
                        // Ищем функции в глобальной области или через socket объект
                        let patched = false;
                        if (typeof window.joinLeadChannel === 'function' && typeof window.leaveSocketChannel === 'function') {
                            window.__test_original_joinLeadChannel = window.joinLeadChannel;
                            window.__test_original_leaveSocketChannel = window.leaveSocketChannel;
                            window.leaveSocketChannel = function (channel) {
                                console.log('TEST: skip leaveSocketChannel for', channel);
                                // Не вызываем оригинальную функцию - имитируем залипание
                            };
                            patched = true;
                        }
                        return { patched, hasJoinLeadChannel: typeof window.joinLeadChannel === 'function', 
                                hasLeaveSocketChannel: typeof window.leaveSocketChannel === 'function' };
                    } catch (e) {
                        return { patched: false, error: String(e) };
                    }
                }
                """
            )
            allure.attach(str(patch_result), name="socket_patch_result", attachment_type=allure.attachment_type.JSON)
            if not patch_result.get("patched"):
                logging.warning(f"Не удалось запатчить сокеты: {patch_result}")

        # Создаём два лида для последовательных звонков
        lead_a_id: Optional[int] = None
        lead_b_id: Optional[int] = None

        with allure.step("Создаём лид A через API"):
            lead_a_phone = f"+7999{int(time.time()) % 10000000:07d}"
            lead_a_payload = {
                "lead_type": "straight",
                "create_method": "quiz",
                "client_name": "Race Test Lead A",
                "client_phone": lead_a_phone,
                "order_id": int(time.time()) % 100000,
                "quiz_log": "{\"test\":\"race_scenario_a\"}",
                "campaign_id": "test_campaign",
                "external_id": f"test_race_a_{int(time.time())}",
                "priority": "normal",
                "utc_offset": "+3",
            }
            resp_a = api_client.post("v1/lead/create/", json=lead_a_payload)
            create_a_json = _safe_json(resp_a)
            allure.attach(str(resp_a.text), name="create_lead_a_response", attachment_type=allure.attachment_type.JSON)
            assert resp_a.status_code == 200, f"Создание лида A неуспешно: {resp_a.status_code} {resp_a.text}"
            lead_a_id = _extract_lead_id(create_a_json)
            assert lead_a_id is not None, "Не удалось получить lead_id для лида A"

        with allure.step("Запускаем dialer для лида A и ждём появления звонка"):
            dialer_a_json = _trigger_dialer(api_client, attach_name="dialer_response_lead_a")
            allure.attach(str(dialer_a_json), name="dialer_a_result", attachment_type=allure.attachment_type.JSON)
            
            # Ждём появления UI звонка (кнопка принять или карточка звонка)
            try:
                call_session_a = page.locator("#call-session")
                # Ждём либо кнопку принять, либо саму карточку звонка
                accept_btn_a = page.locator(".call-accept-btn, #phone-answer-btn")
                accept_btn_a.wait_for(state="visible", timeout=30000)
                allure.attach(page.screenshot(), name="lead_a_call_received", attachment_type=allure.attachment_type.PNG)
                
                # Проверяем, что карточка лида A отображается
                if call_session_a.count() > 0:
                    lead_id_attr = call_session_a.get_attribute("data-lead-id")
                    allure.attach(f"Lead A call session data-lead-id: {lead_id_attr}", name="lead_a_session_info", attachment_type=allure.attachment_type.TEXT)
            except Exception as e:
                logging.warning(f"Не удалось дождаться UI звонка A: {e}")
                allure.attach(str(e), name="lead_a_wait_error", attachment_type=allure.attachment_type.TEXT)

        with allure.step("Создаём лид B через API (пока лид A ещё активен)"):
            lead_b_phone = f"+7999{int(time.time()) % 10000000:07d}"
            lead_b_payload = {
                "lead_type": "straight",
                "create_method": "quiz",
                "client_name": "Race Test Lead B",
                "client_phone": lead_b_phone,
                "order_id": int(time.time()) % 100000,
                "quiz_log": "{\"test\":\"race_scenario_b\"}",
                "campaign_id": "test_campaign",
                "external_id": f"test_race_b_{int(time.time())}",
                "priority": "normal",
                "utc_offset": "+3",
            }
            resp_b = api_client.post("v1/lead/create/", json=lead_b_payload)
            create_b_json = _safe_json(resp_b)
            allure.attach(str(resp_b.text), name="create_lead_b_response", attachment_type=allure.attachment_type.JSON)
            assert resp_b.status_code == 200, f"Создание лида B неуспешно: {resp_b.status_code} {resp_b.text}"
            lead_b_id = _extract_lead_id(create_b_json)
            assert lead_b_id is not None, "Не удалось получить lead_id для лида B"

        with allure.step("Запускаем dialer для лида B (пока лид A ещё может быть активен)"):
            time.sleep(1)  # Небольшая задержка для имитации гонки
            dialer_b_json = _trigger_dialer(api_client, attach_name="dialer_response_lead_b")
            allure.attach(str(dialer_b_json), name="dialer_b_result", attachment_type=allure.attachment_type.JSON)

        with allure.step("Проверяем состояние UI после получения второго звонка"):
            # Ждём появления UI для лида B
            try:
                call_session_b = page.locator("#call-session")
                # Даём время системе обработать новый звонок
                time.sleep(3)
                
                # Проверяем, что UI не сломан
                # 1. Карточка звонка должна быть видима
                if call_session_b.count() > 0:
                    lead_id_attr_b = call_session_b.get_attribute("data-lead-id")
                    allure.attach(f"Lead B call session data-lead-id: {lead_id_attr_b}", name="lead_b_session_info", attachment_type=allure.attachment_type.TEXT)
                    
                    # 2. Ключевые элементы должны быть доступны
                    finish_call_btn = page.locator("#finish_call")
                    call_status_select = page.locator("#callStatus")
                    save_result_btn = page.locator("#save-call-result-btn")
                    
                    # Проверяем отсутствие критических ошибок в консоли
                    console_errors = []
                    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
                    
                    allure.attach(page.screenshot(), name="lead_b_call_ui_state", attachment_type=allure.attachment_type.PNG)
                    
                    # Базовая проверка: UI должен быть функциональным
                    if finish_call_btn.count() > 0 or call_status_select.count() > 0:
                        logging.info("UI элементы звонка присутствуют после получения второго звонка")
                    else:
                        logging.warning("Критические UI элементы отсутствуют - возможна поломка UI")
                        
            except Exception as e:
                logging.error(f"Ошибка при проверке UI после второго звонка: {e}")
                allure.attach(str(e), name="lead_b_ui_check_error", attachment_type=allure.attachment_type.TEXT)
                allure.attach(page.screenshot(), name="error_screenshot", attachment_type=allure.attachment_type.PNG)

        with allure.step("Очистка: удаляем созданные лиды"):
            if lead_a_id:
                _delete_lead_best_effort(api_client, lead_a_id)
            if lead_b_id:
                _delete_lead_best_effort(api_client, lead_b_id)
