import pytest
import allure
import json
from unittest.mock import patch, MagicMock
import requests

@pytest.fixture
def voximplant_mock():
    """Фикстура для мока Voximplant API"""
    with patch('requests.post') as mock_post:
        # Настраиваем мок для успешного ответа
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": 1,
            "call_id": "test_call_123",
            "status": "success"
        }
        mock_post.return_value = mock_response
        yield mock_post

@pytest.fixture
def voximplant_config():
    """Фикстура с конфигурацией Voximplant"""
    return {
        "api_url": "https://api.voximplant.com/platform_api/",
        "account_id": "test_account",
        "api_key": "test_key",
        "scenario_id": "test_scenario"
    }

@allure.epic("Телефония")
@allure.feature("Voximplant интеграция")
class TestTelephony:
    
    @allure.title("Проверка успешного звонка через Voximplant")
    @allure.story("Базовый функционал")
    @allure.severity('critical')
    def test_successful_call(self, voximplant_mock, voximplant_config):
        """Тест проверяет успешное выполнение звонка через Voximplant"""
        # Подготавливаем данные для звонка
        call_data = {
            "phone_number": "+79991234567",
            "scenario_id": voximplant_config["scenario_id"],
            "variables": {
                "lead_id": "12345",
                "client_name": "Test Client"
            }
        }
        
        # Выполняем запрос к API
        response = requests.post(
            f"{voximplant_config['api_url']}StartScenarios",
            headers={
                "Authorization": f"Bearer {voximplant_config['api_key']}",
                "Content-Type": "application/json"
            },
            json=call_data
        )
        
        # Проверяем результат
        assert response.status_code == 200, "Запрос должен быть успешным"
        response_data = response.json()
        assert response_data["result"] == 1, "Результат должен быть успешным"
        assert "call_id" in response_data, "В ответе должен быть ID звонка"
        
        # Проверяем, что мок был вызван с правильными параметрами
        voximplant_mock.assert_called_once()
        call_args = voximplant_mock.call_args[1]
        assert call_args["json"] == call_data, "Данные запроса не соответствуют ожидаемым"
    
    @allure.title("Проверка обработки ошибок при звонке")
    @allure.story("Обработка ошибок")
    @allure.severity('high')
    def test_call_error_handling(self, voximplant_mock, voximplant_config):
        """Тест проверяет корректную обработку ошибок при звонке"""
        # Настраиваем мок для возврата ошибки
        error_response = MagicMock()
        error_response.status_code = 400
        error_response.json.return_value = {
            "result": 0,
            "error": "Invalid phone number"
        }
        voximplant_mock.return_value = error_response
        
        # Подготавливаем данные для звонка с неверным номером
        call_data = {
            "phone_number": "invalid_number",
            "scenario_id": voximplant_config["scenario_id"],
            "variables": {
                "lead_id": "12345",
                "client_name": "Test Client"
            }
        }
        
        # Выполняем запрос к API
        response = requests.post(
            f"{voximplant_config['api_url']}StartScenarios",
            headers={
                "Authorization": f"Bearer {voximplant_config['api_key']}",
                "Content-Type": "application/json"
            },
            json=call_data
        )
        
        # Проверяем результат
        assert response.status_code == 400, "Должен быть получен код ошибки"
        response_data = response.json()
        assert response_data["result"] == 0, "Результат должен быть неуспешным"
        assert "error" in response_data, "В ответе должно быть сообщение об ошибке"
    
    @allure.title("Проверка статуса звонка")
    @allure.story("Мониторинг звонков")
    @allure.severity('high')
    def test_call_status(self, voximplant_mock, voximplant_config):
        """Тест проверяет получение статуса звонка"""
        # Настраиваем мок для возврата статуса звонка
        status_response = MagicMock()
        status_response.status_code = 200
        status_response.json.return_value = {
            "result": 1,
            "call_status": "completed",
            "duration": 120,
            "hangup_reason": "normal_clearing"
        }
        voximplant_mock.return_value = status_response
        
        # Запрашиваем статус звонка
        call_id = "test_call_123"
        response = requests.post(
            f"{voximplant_config['api_url']}GetCallHistory",
            headers={
                "Authorization": f"Bearer {voximplant_config['api_key']}",
                "Content-Type": "application/json"
            },
            json={"call_id": call_id}
        )
        
        # Проверяем результат
        assert response.status_code == 200, "Запрос должен быть успешным"
        response_data = response.json()
        assert response_data["result"] == 1, "Результат должен быть успешным"
        assert "call_status" in response_data, "В ответе должен быть статус звонка"
        assert response_data["call_status"] == "completed", "Статус звонка должен быть 'completed'" 