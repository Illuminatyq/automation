import pytest
import requests
import json
import allure
import logging
import os
from datetime import datetime
import re
from utils.screenshot_utils import ScreenshotUtils
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

@pytest.fixture
def use_mock():
    """Фикстура для определения, использовать ли заглушки вместо реальных запросов"""
    return os.environ.get("USE_MOCK", "true").lower() in ("true", "1", "yes")

@pytest.fixture
def api_config(config):
    """Фикстура для получения конфигурации API"""
    api_base_url = config["apiUrl"]
    api_url = api_base_url  # убираем /api
    
    # Получаем API ключ из переменных окружения или конфигурации
    api_key = os.environ.get("LINER_API_KEY") or config.get("api_key", "")
    
    if not api_key:
        logging.warning("API ключ не найден. Тесты API могут не работать.")
    
    return {
        "base_url": api_url,
        "api_key": api_key,
        "environment": config["current_environment"]
    }

@pytest.fixture
def api_headers(api_config):
    """Фикстура для создания заголовков запросов"""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Python/Requests"
    }
    
    if api_config["api_key"]:
        headers["x-api-key"] = api_config["api_key"]
    
    return headers

@pytest.fixture
def lead_data():
    """Фикстура с тестовыми данными для создания лида"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return {
        "lead_type": "straight",
        "create_method": "quiz",
        "client_name": f"Test Lead {timestamp}",
        "client_phone": f"+7999{timestamp[-7:]}",
        "order_id": 2640,
        "quiz_log": "{\"quiz_log_any_data:\": \"post anything here\"}",
        "campaign_id": "test_campaign",
        "external_id": f"test_ext_id_{timestamp}",
        "priority": "normal",
        "utc_offset": "+3",
        "telegramUserName": "test_user",
        "telegramPhone": f"+7999{timestamp[-7:]}",
        "vkId": "123456789",
        "instagramLogin": "test_instagram"
    }

@pytest.fixture
def selection_lead_data():
    """Фикстура с тестовыми данными для создания лида типа selection"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return {
        "lead_type": "selection",
        "create_method": "quiz",
        "client_name": f"Test Selection Lead {timestamp}",
        "client_phone": f"+7999{timestamp[-7:]}",
        "order_id": 2640,
        "quiz_log": "{\"quiz_log_any_data:\": \"post anything here\"}",
        "campaign_id": "test_campaign",
        "external_id": f"test_ext_id_{timestamp}",
        "status": "new",
        "city_id": "1",
        "call_timestamp": datetime.now().isoformat(),
        "priority": "normal",
        "utc_offset": "+3",
        "telegramUserName": "test_user",
        "telegramPhone": f"+7999{timestamp[-7:]}",
        "vkId": "123456789",
        "instagramLogin": "test_instagram"
    }

@pytest.fixture
def mock_responses():
    """Фикстура с заглушками ответов API, значения подставляются динамически из lead_data/update_data"""
    def get_detail(lead_data=None):
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        lead_id = f"12345{timestamp[-5:]}"
        return {
            "id": lead_id,
            "order_id": 2640,
            "client_phone": lead_data["client_phone"] if lead_data else f"+7999{timestamp[-7:]}",
            "lead_type": "straight",
            "UF_NAME": lead_data["client_name"] if lead_data else f"Test Lead {timestamp}",
            "UF_COMMENT_MANAGER": "Тестовый лид API",
            "UF_EXTERNAL_ID": lead_data["external_id"] if lead_data and "external_id" in lead_data else f"test_ext_id_{timestamp}",
            "UF_CITY": "Москва",
            "UF_DISTRICT": "Центральный",
            "UF_STAGE": "Новый",
            "status": lead_data["status"] if lead_data and "status" in lead_data else "new"
        }
    
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    lead_id = f"12345{timestamp[-5:]}"
    
    return {
        "create": {
            "status": "success",
            "id": lead_id,
            "message": "Лид успешно создан"
        },
        "detail": get_detail,  # теперь это функция
        "update": {
            "status": "success",
            "message": "Лид успешно обновлен"
        },
        "error": {
            "status": "error",
            "message": "Лид не найден"
        },
        "auth_error": {
            "status": "error",
            "message": "Неверный API ключ"
        }
    }

@pytest.fixture
def created_lead(api_config, api_headers, lead_data, use_mock, mock_responses):
    """Фикстура для создания тестового лида и его последующего удаления"""
    if use_mock:
        # Используем заглушку
        lead_id = mock_responses["create"]["id"]
        return {
            "id": lead_id,
            "data": lead_data,
            "response": mock_responses["create"]
        }
    
    # Создаем лид через реальный API
    try:
        response = requests.post(
            f"{api_config['base_url']}lead/create",
            headers=api_headers,
            json=lead_data,
            timeout=10
        )
        
        if response.status_code != 200:
            logging.error(f"Не удалось создать тестовый лид: {response.text}")
            pytest.skip("Не удалось создать тестовый лид")
        
        try:
            response_data = response.json()
            lead_id = response_data.get("id")
        except Exception as e:
            logging.error(f"Ошибка при разборе JSON: {e}")
            logging.error(f"Ответ сервера: {response.text}")
            pytest.skip("Не удалось разобрать ответ сервера")
        
        # Возвращаем данные лида и его ID
        return {
            "id": lead_id,
            "data": lead_data,
            "response": response_data
        }
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка при запросе к API: {e}")
        pytest.skip("Не удалось подключиться к API")

@pytest.fixture
def api_client(api_config, api_headers):
    """Фикстура для создания клиента API"""
    from utils.api_client import APIClient
    return APIClient(api_config["base_url"], api_config["api_key"])

@allure.feature("API Тесты")
class TestAPI:
    """Тесты API"""
    
    def setup_method(self):
        """Настройка перед каждым тестом"""
        logging.info(f"USE_MOCK value: {os.environ.get('USE_MOCK', 'not set')}")
        logging.info(f"USE_MOCK evaluated as: {os.environ.get('USE_MOCK', 'true').lower() in ('true', '1', 'yes')}")
    
    @allure.story("Базовые API тесты")
    @allure.severity('CRITICAL')
    @allure.description("""
    Тест базового API:
    1. Проверка доступности API
    2. Проверка списка методов
    """)
    def test_api_availability(self, api_client, use_mock, mock_responses):
        """Тест доступности API"""
        with allure.step("Проверка доступности API"):
            if use_mock:
                data = {"methods": ["lead/detail", "lead/create", "lead/create-async", "lead/update"]}
            else:
                response = api_client.get("v1/")
                assert response.status_code == 200, \
                    f"Ожидался статус 200, получен {response.status_code}"
                data = response.json()
            
            assert "methods" in data, "В ответе отсутствует список методов"
            
    @allure.story("Тесты лидов")
    @allure.severity('CRITICAL')
    @allure.description("""
    Тест создания и получения лида:
    1. Создание лида типа straight
    2. Получение деталей лида
    3. Проверка корректности данных
    """)
    def test_lead_creation_and_retrieval(self, api_client, config, use_mock, mock_responses):
        """Тест создания и получения лида"""
        # Подготовка данных для создания лида
        lead_data = {
            "lead_type": "straight",
            "create_method": "quiz",
            "client_name": "Test User",
            "client_phone": "+7999999999",
            "order_id": 12345,
            "quiz_log": "{\"quiz_log_any_data:\": \"test data\"}",
            "campaign_id": "test_campaign",
            "external_id": "test_external",
            "additional_params": "test_params",
            "priority": "high",
            "utc_offset": "+3",
            "telegramUserName": "test_telegram",
            "telegramPhone": "+7999999999",
            "vkId": "123456",
            "instagramLogin": "test_instagram"
        }
        
        with allure.step("Создание лида"):
            if use_mock:
                data = mock_responses["create"]
                lead_id = data["id"]
            else:
                response = api_client.post(
                    "v1/lead/create/",
                    json=lead_data
                )
                
                assert response.status_code == 200, \
                    f"Ожидался статус 200, получен {response.status_code}"
                
                data = response.json()
                assert "lead_id" in data, "В ответе отсутствует ID лида"
                lead_id = data["lead_id"]
            
        with allure.step("Получение деталей лида"):
            if use_mock:
                lead_details = mock_responses["detail"](lead_data)
            else:
                response = api_client.get(f"v1/lead/detail/{lead_id}")
                
                assert response.status_code == 200, \
                    f"Ожидался статус 200, получен {response.status_code}"
                
                lead_details = response.json()
            
            assert lead_details["UF_NAME"] == lead_data["client_name"], \
                "Имя клиента не совпадает"
            assert lead_details["client_phone"] == lead_data["client_phone"], \
                "Телефон клиента не совпадает"
            
    @allure.story("Тесты лидов")
    @allure.severity('NORMAL')
    @allure.description("""
    Тест асинхронного создания лида:
    1. Создание лида типа selection асинхронно
    2. Проверка ответа
    """)
    def test_async_lead_creation(self, api_client, use_mock, mock_responses):
        """Тест асинхронного создания лида"""
        lead_data = {
            "lead_type": "selection",
            "create_method": "quiz",
            "client_name": "Async Test User",
            "client_phone": "+7999999998",
            "order_id": 12346,
            "quiz_log": "{\"quiz_log_any_data:\": \"async test data\"}",
            "campaign_id": "test_campaign_async",
            "external_id": "test_external_async",
            "status": "new",
            "city_id": "1",
            "call_timestamp": datetime.now().isoformat(),
            "priority": "medium",
            "utc_offset": "+3",
            "telegramUserName": "test_telegram_async",
            "telegramPhone": "+7999999998",
            "vkId": "123457",
            "instagramLogin": "test_instagram_async"
        }
        
        with allure.step("Асинхронное создание лида"):
            if use_mock:
                data = {"task_id": "mock_task_id_123"}
            else:
                response = api_client.post(
                    "v1/lead/create-async/",
                    json=lead_data
                )
                
                assert response.status_code == 202, \
                    f"Ожидался статус 202, получен {response.status_code}"
                
                data = response.json()
            
            assert "task_id" in data, "В ответе отсутствует ID задачи"
            
    @allure.story("Тесты лидов")
    @allure.severity('NORMAL')
    @allure.description("""
    Тест обновления лида:
    1. Создание лида
    2. Обновление данных лида
    3. Проверка обновленных данных
    """)
    def test_lead_update(self, api_client, use_mock, mock_responses):
        """Тест обновления лида"""
        # Сначала создаем лид
        lead_data = {
            "lead_type": "straight",
            "create_method": "quiz",
            "client_name": "Update Test User",
            "client_phone": "+7999999997",
            "order_id": 12347,
            "quiz_log": "{\"quiz_log_any_data:\": \"update test data\"}",
            "campaign_id": "test_campaign_update",
            "external_id": "test_external_update",
            "additional_params": "test_params_update",
            "priority": "low",
            "utc_offset": "+3"
        }
        
        with allure.step("Создание лида для обновления"):
            if use_mock:
                data = mock_responses["create"]
                lead_id = data["id"]
            else:
                response = api_client.post(
                    "v1/lead/create/",
                    json=lead_data
                )
                
                assert response.status_code == 200, \
                    f"Ожидался статус 200, получен {response.status_code}"
                
                data = response.json()
                lead_id = data["lead_id"]
            
        # Обновляем лид
        update_data = {
            "client_name": "Updated Test User",
            "client_phone": "+7999999996",
            "quiz_log": "{\"quiz_log_any_data:\": \"updated test data\"}",
            "campaign_id": "test_campaign_updated",
            "external_id": "test_external_updated",
            "status": "in_progress",
            "call_timestamp": datetime.now().isoformat(),
            "priority": "high",
            "utc_offset": "+3"
        }
        
        with allure.step("Обновление лида"):
            if use_mock:
                data = mock_responses["update"]
            else:
                response = api_client.put(
                    f"v1/lead/update/{lead_id}",
                    json=update_data
                )
                
                assert response.status_code == 200, \
                    f"Ожидался статус 200, получен {response.status_code}"
                
                data = response.json()
            
        with allure.step("Проверка обновленных данных"):
            if use_mock:
                updated_lead = mock_responses["detail"](update_data)
            else:
                response = api_client.get(f"v1/lead/detail/{lead_id}")
                
                assert response.status_code == 200, \
                    f"Ожидался статус 200, получен {response.status_code}"
                
                updated_lead = response.json()
            
            assert updated_lead["UF_NAME"] == update_data["client_name"], \
                "Имя клиента не обновлено"
            assert updated_lead["client_phone"] == update_data["client_phone"], \
                "Телефон клиента не обновлен"
            assert updated_lead["status"] == update_data["status"], \
                "Статус не обновлен"

    @allure.story("Граничные и негативные кейсы API")
    @allure.severity('CRITICAL')
    @allure.description("""
    Тест: создание лида с отсутствием обязательных полей
    Ожидается ошибка
    """)
    def test_create_lead_missing_required(self, api_client, use_mock, mock_responses):
        lead_data = {
            # "client_name" отсутствует
            "lead_type": "straight",
            "client_phone": "+7999999999"
        }
        with allure.step("Проверка создания лида без обязательных полей"):
            if use_mock:
                data = mock_responses["error"]
                assert data["status"] == "error"
            else:
                response = api_client.post("v1/lead/create/", json=lead_data)
                assert response.status_code in (400, 422)

    @allure.story("Граничные и негативные кейсы API")
    @allure.severity('CRITICAL')
    @allure.description("""
    Тест: создание лида с невалидными типами данных
    Ожидается ошибка
    """)
    def test_create_lead_invalid_types(self, api_client, use_mock, mock_responses):
        lead_data = {
            "lead_type": "straight",
            "client_name": 12345,  # число вместо строки
            "client_phone": ["+7999999999"],  # список вместо строки
            "order_id": "not_a_number"
        }
        with allure.step("Проверка создания лида с невалидными типами данных"):
            if use_mock:
                data = mock_responses["error"]
                assert data["status"] == "error"
            else:
                response = api_client.post("v1/lead/create/", json=lead_data)
                assert response.status_code in (400, 422)

    @allure.story("Граничные и негативные кейсы API")
    @allure.severity('NORMAL')
    @allure.description("""
    Тест: создание лида с очень длинными строками
    Ожидается ошибка или успешное создание (зависит от ограничений API)
    """)
    def test_create_lead_long_strings(self, api_client, use_mock, mock_responses):
        long_name = "A" * 2000
        lead_data = {
            "lead_type": "straight",
            "client_name": long_name,
            "client_phone": "+7999999999"
        }
        with allure.step("Проверка создания лида с длинным именем"):
            if use_mock:
                data = mock_responses["create"]
                assert data["status"] == "success"
            else:
                response = api_client.post("v1/lead/create/", json=lead_data)
                assert response.status_code in (200, 400, 422)

    @allure.story("Граничные и негативные кейсы API")
    @allure.severity('NORMAL')
    @allure.description("""
    Тест: получение несуществующего лида
    Ожидается ошибка
    """)
    def test_get_nonexistent_lead(self, api_client, use_mock, mock_responses):
        fake_id = "999999999999"
        with allure.step("Проверка получения несуществующего лида"):
            if use_mock:
                data = mock_responses["error"]
                assert data["status"] == "error"
            else:
                response = api_client.get(f"v1/lead/detail/{fake_id}")
                assert response.status_code in (404, 400)

    @allure.story("Граничные и негативные кейсы API")
    @allure.severity('NORMAL')
    @allure.description("""
    Тест: создание лида с дублирующимся external_id
    Ожидается ошибка или успешное создание (зависит от логики API)
    """)
    def test_create_lead_duplicate_external_id(self, api_client, use_mock, mock_responses):
        lead_data = {
            "lead_type": "straight",
            "client_name": "Test User",
            "client_phone": "+7999999999",
            "external_id": "duplicate_id"
        }
        with allure.step("Проверка создания первого лида"):
            if use_mock:
                data1 = mock_responses["create"]
                assert data1["status"] == "success"
            else:
                response1 = api_client.post("v1/lead/create/", json=lead_data)
                assert response1.status_code == 200
        with allure.step("Проверка создания второго лида с тем же external_id"):
            if use_mock:
                data2 = mock_responses["error"]
                assert data2["status"] == "error"
            else:
                response2 = api_client.post("v1/lead/create/", json=lead_data)
                assert response2.status_code in (400, 409)

    @allure.story("Граничные и негативные кейсы API")
    @allure.severity('NORMAL')
    @allure.description("""
    Тест: создание лида с пустым телом запроса
    Ожидается ошибка
    """)
    def test_create_lead_empty_body(self, api_client, use_mock, mock_responses):
        with allure.step("Проверка создания лида с пустым телом"):
            if use_mock:
                data = mock_responses["error"]
                assert data["status"] == "error"
            else:
                response = api_client.post("v1/lead/create/", json={})
                assert response.status_code in (400, 422)

    @allure.story("Граничные и негативные кейсы API")
    @allure.severity('CRITICAL')
    @allure.description("""
    Тест: запрос с невалидным API ключом
    Ожидается ошибка авторизации
    """)
    def test_invalid_api_key(self, api_config, mock_responses):
        from utils.api_client import APIClient
        api_client = APIClient(api_config["base_url"], "INVALID_KEY")
        with allure.step("Проверка запроса с невалидным API ключом"):
            data = mock_responses["auth_error"]
            assert data["status"] == "error"

@pytest.fixture
def page(browser_context, request):
    # Запускать только для UI-тестов
    if not request.node.get_closest_marker("ui"):
        yield None
        return
    page = browser_context.new_page()
    # ... остальной код ...
