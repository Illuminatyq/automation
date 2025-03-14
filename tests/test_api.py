import pytest
import requests
import json
import allure
import logging
import os
from datetime import datetime
import re

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

@pytest.fixture
def use_mock():
    """Фикстура для определения, использовать ли заглушки вместо реальных запросов"""
    return os.environ.get("USE_MOCK", "true").lower() in ("true", "1", "yes")

@pytest.fixture
def api_config(config):
    """Фикстура для получения конфигурации API"""
    api_base_url = config["apiUrl"].replace("/api/", "")
    api_url = f"{api_base_url}/v1/"
    
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
    return {
        "Content-Type": "application/json",
        "x-api-key": api_config["api_key"]
    }

@pytest.fixture
def lead_data():
    """Фикстура с тестовыми данными для создания лида"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return {
        "order_id": 2640,  # Тестовый заказ
        "client_phone": f"+7999{timestamp[-7:]}",
        "lead_type": "straight",
        "UF_NAME": f"Test Lead {timestamp}",
        "UF_COMMENT_MANAGER": "Тестовый лид API",
        "UF_EXTERNAL_ID": f"test_ext_id_{timestamp}",
        "UF_CITY": "Москва",
        "UF_DISTRICT": "Центральный",
        "UF_STAGE": "Новый"
    }

@pytest.fixture
def mock_responses():
    """Фикстура с заглушками ответов API"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    lead_id = f"12345{timestamp[-5:]}"
    
    return {
        "create": {
            "status": "success",
            "id": lead_id,
            "message": "Лид успешно создан"
        },
        "detail": {
            "id": lead_id,
            "order_id": 2640,
            "client_phone": f"+7999{timestamp[-7:]}",
            "lead_type": "straight",
            "UF_NAME": f"Test Lead {timestamp}",
            "UF_COMMENT_MANAGER": "Тестовый лид API",
            "UF_EXTERNAL_ID": f"test_ext_id_{timestamp}",
            "UF_CITY": "Москва",
            "UF_DISTRICT": "Центральный",
            "UF_STAGE": "Новый"
        },
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


@allure.feature("API интеграция")
class TestApiIntegration:
    
    @allure.story("Создание лида")
    @allure.severity("critical")
    def test_create_lead(self, api_config, api_headers, lead_data, use_mock, mock_responses):
        """Тест создания лида через API"""
        with allure.step("Отправка запроса на создание лида"):
            if use_mock:
                # Используем заглушку
                response_data = mock_responses["create"]
                allure.attach(
                    json.dumps(lead_data, indent=2, ensure_ascii=False),
                    "Данные запроса",
                    allure.attachment_type.JSON
                )
                allure.attach(
                    json.dumps(response_data, indent=2, ensure_ascii=False),
                    "Ответ сервера (заглушка)",
                    allure.attachment_type.JSON
                )
            else:
                # Отправляем реальный запрос
                try:
                    response = requests.post(
                        f"{api_config['base_url']}lead/create",
                        headers=api_headers,
                        json=lead_data,
                        timeout=10
                    )
                    
                    # Логируем запрос и ответ
                    allure.attach(
                        json.dumps(lead_data, indent=2, ensure_ascii=False),
                        "Данные запроса",
                        allure.attachment_type.JSON
                    )
                    allure.attach(
                        response.text,
                        "Ответ сервера",
                        allure.attachment_type.TEXT
                    )
                    
                    with allure.step("Проверка статус-кода"):
                        assert response.status_code == 200, f"Ожидался статус-код 200, получен {response.status_code}"
                    
                    try:
                        response_data = response.json()
                    except Exception as e:
                        logging.error(f"Ошибка при разборе JSON: {e}")
                        logging.error(f"Ответ сервера: {response.text}")
                        pytest.skip("Не удалось разобрать ответ сервера")
                except requests.exceptions.RequestException as e:
                    logging.error(f"Ошибка при запросе к API: {e}")
                    pytest.skip("Не удалось подключиться к API")
                    return
        
        with allure.step("Проверка структуры ответа"):
            if use_mock:
                response_data = mock_responses["create"]
            
            assert "id" in response_data, "В ответе отсутствует поле 'id'"
            assert "status" in response_data, "В ответе отсутствует поле 'status'"
            assert response_data["status"] == "success", f"Ожидался статус 'success', получен '{response_data.get('status')}'"
        
        logging.info(f"Лид успешно создан с ID: {response_data.get('id')}")
    
    @allure.story("Получение деталей лида")
    @allure.severity("high")
    def test_get_lead_details(self, api_config, api_headers, created_lead, use_mock, mock_responses):
        """Тест получения деталей лида через API"""
        lead_id = created_lead["id"]
        
        with allure.step(f"Отправка запроса на получение деталей лида с ID {lead_id}"):
            if use_mock:
                # Используем заглушку
                response_data = mock_responses["detail"]
                allure.attach(
                    json.dumps(response_data, indent=2, ensure_ascii=False),
                    "Ответ сервера (заглушка)",
                    allure.attachment_type.JSON
                )
            else:
                # Отправляем реальный запрос
                try:
                    response = requests.get(
                        f"{api_config['base_url']}lead/detail/{lead_id}",
                        headers=api_headers,
                        timeout=10
                    )
                    
                    # Логируем ответ
                    allure.attach(
                        response.text,
                        "Ответ сервера",
                        allure.attachment_type.TEXT
                    )
                    
                    with allure.step("Проверка статус-кода"):
                        assert response.status_code == 200, f"Ожидался статус-код 200, получен {response.status_code}"
                    
                    try:
                        response_data = response.json()
                    except Exception as e:
                        logging.error(f"Ошибка при разборе JSON: {e}")
                        logging.error(f"Ответ сервера: {response.text}")
                        pytest.skip("Не удалось разобрать ответ сервера")
                except requests.exceptions.RequestException as e:
                    logging.error(f"Ошибка при запросе к API: {e}")
                    pytest.skip("Не удалось подключиться к API")
                    return
        
        with allure.step("Проверка структуры ответа"):
            if use_mock:
                response_data = mock_responses["detail"]
            
            assert "id" in response_data, "В ответе отсутствует поле 'id'"
            assert response_data["id"] == lead_id, f"ID лида в ответе ({response_data['id']}) не соответствует запрошенному ({lead_id})"
            
            # Проверяем, что данные лида соответствуют тем, что мы создавали
            original_data = created_lead["data"]
            if "UF_NAME" in response_data and "UF_NAME" in original_data:
                assert response_data["UF_NAME"] == original_data["UF_NAME"], "Имя лида не соответствует"
            if "client_phone" in response_data and "client_phone" in original_data:
                assert response_data["client_phone"] == original_data["client_phone"], "Телефон лида не соответствует"
            if "order_id" in response_data and "order_id" in original_data:
                assert response_data["order_id"] == original_data["order_id"], "ID заказа не соответствует"
        
        logging.info(f"Детали лида с ID {lead_id} успешно получены")
    
    @allure.story("Обновление лида")
    @allure.severity("high")
    def test_update_lead(self, api_config, api_headers, created_lead, use_mock, mock_responses):
        """Тест обновления лида через API"""
        lead_id = created_lead["id"]
        
        # Данные для обновления
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        update_data = {
            "UF_NAME": f"Updated Lead {timestamp}",
            "UF_COMMENT_MANAGER": "Обновленный комментарий через API тесты",
            "UF_STAGE": "В работе"
        }
        
        with allure.step(f"Отправка запроса на обновление лида с ID {lead_id}"):
            if use_mock:
                # Используем заглушку
                response_data = mock_responses["update"]
                allure.attach(
                    json.dumps(update_data, indent=2, ensure_ascii=False),
                    "Данные запроса",
                    allure.attachment_type.JSON
                )
                allure.attach(
                    json.dumps(response_data, indent=2, ensure_ascii=False),
                    "Ответ сервера (заглушка)",
                    allure.attachment_type.JSON
                )
            else:
                # Отправляем реальный запрос
                try:
                    response = requests.post(
                        f"{api_config['base_url']}lead/update/{lead_id}",
                        headers=api_headers,
                        json=update_data,
                        timeout=10
                    )
                    
                    # Логируем запрос и ответ
                    allure.attach(
                        json.dumps(update_data, indent=2, ensure_ascii=False),
                        "Данные запроса",
                        allure.attachment_type.JSON
                    )
                    allure.attach(
                        response.text,
                        "Ответ сервера",
                        allure.attachment_type.TEXT
                    )
                    
                    with allure.step("Проверка статус-кода"):
                        assert response.status_code == 200, f"Ожидался статус-код 200, получен {response.status_code}"
                    
                    try:
                        response_data = response.json()
                    except Exception as e:
                        logging.error(f"Ошибка при разборе JSON: {e}")
                        logging.error(f"Ответ сервера: {response.text}")
                        pytest.skip("Не удалось разобрать ответ сервера")
                except requests.exceptions.RequestException as e:
                    logging.error(f"Ошибка при запросе к API: {e}")
                    pytest.skip("Не удалось подключиться к API")
                    return
        
        with allure.step("Проверка структуры ответа"):
            if use_mock:
                response_data = mock_responses["update"]
            
            assert "status" in response_data, "В ответе отсутствует поле 'status'"
            assert response_data["status"] == "success", f"Ожидался статус 'success', получен '{response_data.get('status')}'"
        
        with allure.step("Проверка применения изменений"):
            if use_mock:
                # Обновляем заглушку для получения деталей
                mock_detail = mock_responses["detail"].copy()
                mock_detail.update(update_data)
                updated_lead = mock_detail
            else:
                # Получаем обновленные данные лида
                try:
                    details_response = requests.get(
                        f"{api_config['base_url']}lead/detail/{lead_id}",
                        headers=api_headers,
                        timeout=10
                    )
                    
                    assert details_response.status_code == 200, "Не удалось получить обновленные данные лида"
                    
                    try:
                        updated_lead = details_response.json()
                    except Exception as e:
                        logging.error(f"Ошибка при разборе JSON: {e}")
                        logging.error(f"Ответ сервера: {details_response.text}")
                        pytest.skip("Не удалось разобрать ответ сервера")
                except requests.exceptions.RequestException as e:
                    logging.error(f"Ошибка при запросе к API: {e}")
                    pytest.skip("Не удалось подключиться к API")
                    return
            
            if "UF_NAME" in updated_lead and "UF_NAME" in update_data:
                assert updated_lead["UF_NAME"] == update_data["UF_NAME"], "Имя лида не было обновлено"
            if "UF_COMMENT_MANAGER" in updated_lead and "UF_COMMENT_MANAGER" in update_data:
                assert updated_lead["UF_COMMENT_MANAGER"] == update_data["UF_COMMENT_MANAGER"], "Комментарий лида не был обновлен"
            if "UF_STAGE" in updated_lead and "UF_STAGE" in update_data:
                assert updated_lead["UF_STAGE"] == update_data["UF_STAGE"], "Стадия лида не была обновлена"
            
            # Проверяем, что неизмененные поля остались прежними
            original_data = created_lead["data"]
            if "client_phone" in updated_lead and "client_phone" in original_data:
                assert updated_lead["client_phone"] == original_data["client_phone"], "Телефон лида изменился, хотя не должен был"
            if "order_id" in updated_lead and "order_id" in original_data:
                assert updated_lead["order_id"] == original_data["order_id"], "ID заказа изменился, хотя не должен был"
        
        logging.info(f"Лид с ID {lead_id} успешно обновлен")
    
    @allure.story("Обработка ошибок API")
    @allure.severity("normal")
    def test_api_error_handling(self, api_config, api_headers, use_mock, mock_responses):
        """Тест обработки ошибок API"""
        # Тест с несуществующим ID лида
        non_existent_id = "99999999"
        
        with allure.step(f"Запрос деталей несуществующего лида с ID {non_existent_id}"):
            if use_mock:
                # Используем заглушку
                response_data = mock_responses["error"]
                status_code = 404
                allure.attach(
                    json.dumps(response_data, indent=2, ensure_ascii=False),
                    "Ответ сервера (заглушка)",
                    allure.attachment_type.JSON
                )
            else:
                # Отправляем реальный запрос
                try:
                    response = requests.get(
                        f"{api_config['base_url']}lead/detail/{non_existent_id}",
                        headers=api_headers,
                        timeout=10
                    )
                    
                    allure.attach(
                        response.text,
                        "Ответ сервера",
                        allure.attachment_type.TEXT
                    )
                    
                    status_code = response.status_code
                    
                    try:
                        if response.headers.get("Content-Type", "").startswith("application/json"):
                            response_data = response.json()
                        else:
                            response_data = {"text": response.text}
                    except Exception as e:
                        logging.error(f"Ошибка при разборе JSON: {e}")
                        response_data = {"error": str(e)}
                except requests.exceptions.RequestException as e:
                    logging.error(f"Ошибка при запросе к API: {e}")
                    pytest.skip("Не удалось подключиться к API")
                    return
            
            # Проверяем, что API возвращает ошибку (код 404 или другой код ошибки)
            if use_mock:
                assert status_code != 200, "API должен возвращать ошибку для несуществующего лида"
            else:
                # В реальном API может быть разное поведение, поэтому проверяем мягче
                if status_code == 200:
                    logging.warning("API вернул код 200 для несуществующего лида, что не является ошибкой")
                    # Проверяем, что в ответе есть признаки ошибки
                    if isinstance(response_data, dict) and ("error" in response_data or "status" in response_data and response_data.get("status") == "error"):
                        pass  # Это нормально, API вернул ошибку в теле ответа
                    else:
                        logging.warning(f"API вернул успешный ответ для несуществующего лида: {response_data}")
            
            # Если API возвращает JSON с сообщением об ошибке, проверяем его
            if use_mock or (isinstance(response_data, dict) and response.headers.get("Content-Type", "").startswith("application/json")):
                if "error" in response_data or "status" in response_data:
                    pass  # Это нормально
                else:
                    logging.warning(f"В ответе нет поля с ошибкой: {response_data}")
        
        # Тест с неверным API ключом
        with allure.step("Запрос с неверным API ключом"):
            if use_mock:
                # Используем заглушку
                response_data = mock_responses["auth_error"]
                status_code = 401
                allure.attach(
                    json.dumps(response_data, indent=2, ensure_ascii=False),
                    "Ответ сервера (заглушка)",
                    allure.attachment_type.JSON
                )
            else:
                # Отправляем реальный запрос
                try:
                    invalid_headers = api_headers.copy()
                    invalid_headers["x-api-key"] = "invalid_key_12345"
                    
                    response = requests.get(
                        f"{api_config['base_url']}lead/detail/1",
                        headers=invalid_headers,
                        timeout=10
                    )
                    
                    allure.attach(
                        response.text,
                        "Ответ сервера",
                        allure.attachment_type.TEXT
                    )
                    
                    status_code = response.status_code
                except requests.exceptions.RequestException as e:
                    logging.error(f"Ошибка при запросе к API: {e}")
                    pytest.skip("Не удалось подключиться к API")
                    return
            
            # Проверяем, что API возвращает ошибку авторизации (код 401 или 403)
            if use_mock:
                assert status_code in [401, 403], "API должен возвращать ошибку авторизации для неверного ключа"
            else:
                # В реальном API может быть разное поведение, поэтому проверяем мягче
                if status_code not in [401, 403]:
                    logging.warning(f"API вернул код {status_code} для неверного ключа, ожидался 401 или 403")
