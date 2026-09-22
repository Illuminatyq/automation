from playwright.sync_api import sync_playwright, expect, Page
from pages.login_page import LoginPage
from utils.api_client import APIClient
import allure
import time

@allure.epic("Оператор")
@allure.feature("Звонок и удаление лида")
def test_operator_call_and_lead_delete(page: Page, config, api_config):
    api_client = APIClient(api_config["base_url"], api_config["api_key"])

    # Шаг 1: Создаём лид
    with allure.step("Импортируем лида через API"):
        lead_data = {
            "lead_type": "straight",
            "create_method": "quiz",
            "client_name": "Test Operator Lead",
            "client_phone": "+79122093591",  # Твой номер или тестовый
            "order_id": 2640,
            "quiz_log": "{\"quiz_log_any_data:\": \"post anything here\"}",
            "campaign_id": "test_campaign",
            "external_id": f"test_ext_id_{int(time.time())}",
            "priority": "normal",
            "utc_offset": "+3",
            "telegramUserName": "test_user",
            "telegramPhone": "+79122093591",
            "vkId": "123456789",
            "instagramLogin": "test_instagram"
        }
        response = api_client.post("v1/lead/create/", json=lead_data)
        allure.attach(str(response.text), name="Ответ API на создание лида", attachment_type=allure.attachment_type.JSON)
        assert response.status_code == 200, f"Ошибка создания лида: {response.status_code}, {response.text}"
        resp_json = response.json()
        # lead_id = resp_json.get("lead_id") or resp_json.get("id") or (resp_json.get("data") or {}).get("id")
        # assert lead_id, f"Нет lead_id в ответе: {resp_json}"

    # Шаг 2: Логинимся под оператором
    with allure.step("Логинимся под оператором"):
        login_page = LoginPage(page, config["baseUrl"])
        operator_creds = config["credentials"]["operator"]
        # Явно переходим на страницу логина после API-запроса
        page.goto(f"{config['baseUrl'].rstrip('/')}/auth/login/")
        page.wait_for_load_state("domcontentloaded")
        allure.attach(page.screenshot(), name="after_goto_login", attachment_type=allure.attachment_type.PNG)
        allure.attach(page.content(), name="after_goto_login_html", attachment_type=allure.attachment_type.HTML)
        login_page.force_navigate_to_login()
        assert login_page.is_login_form_ready(), "Форма авторизации должна быть готова"
        assert login_page.login(operator_creds["email"], operator_creds["password"]), "Не удалось авторизоваться"
        allure.attach(page.screenshot(), name="После логина оператора", attachment_type=allure.attachment_type.PNG)

    # Шаг 3: Ставим статус "Доступен"
    with allure.step("Ставим статус 'Доступен'"):
        status_menu = page.locator("#employee-status-menu")
        if status_menu.count() > 0 and status_menu.is_visible():
            status_menu.click()
            available_status = page.locator("a[data-status-name='Доступен']")
            if available_status.count() > 0:
                available_status.click()
                expect(page.locator("#employee-status-menu")).to_contain_text("Доступен", timeout=5000)
            else:
                logging.warning("Статус 'Доступен' не найден в меню")
        else:
            logging.warning("Меню статуса сотрудника не найдено")
        allure.attach(page.screenshot(), name="Статус 'Доступен' выбран", attachment_type=allure.attachment_type.PNG)

    # Шаг 4: Ждём 10 секунд
    with allure.step("Ждем 10 секунд для выхода на линию"):
        time.sleep(10)

    # Шаг 5: Ждём ещё 5 секунд и вызываем dialer в фоне
    with allure.step("Вызываем dialer через API в фоне"):
        time.sleep(5)  # Дополнительная задержка для надёжности
        import threading
        def call_dialer():
            dialer_resp = api_client.get("?controller=vats&method=dialer")
            try:
                import allure
                allure.attach(str(dialer_resp.text), name="Ответ API dialer (background)", attachment_type=allure.attachment_type.JSON)
            except Exception:
                pass
        threading.Thread(target=call_dialer, daemon=True).start()

    # Шаг 6: Ждём поступления звонка и принимаем его
    with allure.step("Ждем поступления звонка и принимаем его"):
        expect(page.locator(".call-accept-btn")).to_be_visible(timeout=60000)
        page.click(".call-accept-btn")
        allure.attach(page.screenshot(), name="Звонок принят", attachment_type=allure.attachment_type.PNG)

    # Шаг 7: Проверяем успешность звонка через API (пока закомментировано)
    # with allure.step("Проверяем статус звонка через API"):
    #     response = api_client.get(f"?controller=Vats&method=getCallStatusEntity&callSessionId={call_session_id}")
    #     assert response.status_code == 200, f"Ошибка статуса звонка: {response.status_code}, {response.text}"
    #     status_data = response.json()
    #     assert status_data.get("UF_CLIENT_LEG_ID"), f"Звонок не подключён: {status_data}"
    #     allure.attach(str(status_data), name="Статус звонка", attachment_type=allure.attachment_type.JSON)

    # Шаг 8: Ждём 30 секунд и сбрасываем
    with allure.step("Ждем 30 секунд во время звонка"):
        time.sleep(30)
    with allure.step("Сбрасываем вызов"):
        page.click(".call-hangup-btn")
        allure.attach(page.screenshot(), name="Вызов сброшен", attachment_type=allure.attachment_type.PNG)

    # Шаг 9: Ставим статус "Нет на работе"
    with allure.step("Ставим статус 'Нет на работе'"):
        page.click("#employee-status-menu")
        page.click("a[data-status-name='Нет на работе']")
        expect(page.locator("#employee-status-menu")).to_contain_text("Нет на работе", timeout=5000)
        allure.attach(page.screenshot(), name="Статус 'Нет на работе' выбран", attachment_type=allure.attachment_type.PNG)

    # Шаг 10: Выходим
    with allure.step("Выходим из аккаунта оператора"):
        login_page.logout()
        allure.attach(page.screenshot(), name="После логаута оператора", attachment_type=allure.attachment_type.PNG)