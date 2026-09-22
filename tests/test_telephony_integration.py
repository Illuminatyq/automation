# import pytest
# import allure
# import json
# import logging
# import os
# import requests

# logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# def load_telephony_config():
# #     """Загрузка конфигурации телефонии"""
# #     config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'telephony_test_config.json')
# #     try:
# #         with open(config_path, 'r', encoding='utf-8') as f:
# #             return json.load(f)
# #     except Exception as e:
# #         logging.warning(f"Не удалось загрузить конфигурацию телефонии: {e}")
# #         # Fallback на dev окружение
# #         return {
# #             "telephony": {
# #                 "api": {
# #                     "base_url": "https://liner.dstepanyuk.dev.smte.am",
# #                     "timeout": 30,
# #                     "retry_attempts": 3
# #                 }
# #             }
# #         }

# # @pytest.fixture
# # def telephony_api_client():
# #     """Клиент для работы с API телефонии"""
# #     config = load_telephony_config()
# #     base_url = config["telephony"]["api"]["base_url"]
# #     class TelephonyAPIClient:
# #         def __init__(self, base_url=base_url):
# #             self.base_url = base_url
# #             self.session = requests.Session()
# #             self.session.verify = False
# #         def change_operator_status(self, operator_id, status):
# #             url = f"{self.base_url}/api/?controller=Vats&method=changeEmployeeStatusAction"
# #             data = {
# #                 'status_id': self._get_status_id_by_name(status),
# #                 'operator_id': operator_id
# #             }
# #             return self.session.post(url, data=data)
# #         def get_operator_status(self, operator_id):
# #             url = f"{self.base_url}/api/?controller=Vats&method=getEmployeeStatus"
# #             params = {'operator_id': operator_id}
# #             return self.session.get(url, params=params)
# #         def get_online_operators(self):
# #             url = f"{self.base_url}/api/?controller=Vats&method=getOnlineReadyEmployees"
# #             return self.session.get(url)
# #         def start_predictive_call(self, lead_data, phone_data):
# #             url = f"{self.base_url}/api/?controller=Vats&method=startPredictiveCall"
# #             data = {
# #                 'lead_data': json.dumps(lead_data),
# #                 'phone_data': json.dumps(phone_data)
# #             }
# #             return self.session.post(url, data=data)
# #         def get_dialer_queue(self):
# #             url = f"{self.base_url}/api/?controller=Vats&method=getDialerQueue"
# #             return self.session.get(url)
# #         def _get_status_id_by_name(self, status_name):
# #             status_map = {
# #                 'available': 1,
# #                 'busy': 2,
# #                 'break': 3,
# #                 'offline': 4,
# #                 'post_call': 5
# #             }
# #             return status_map.get(status_name, 4)
# #     return TelephonyAPIClient()

# # @pytest.fixture
# # def test_data():
# #     return {
# #         "operator": {
# #             "id": 123,  # users.ID
# #             "vox_user_name": "vasya_operator",  # users.UF_VOX_USER_NAME
# #             "display_name": "Василий Петров"   # users.NAME + " " + users.LAST_NAME
# #         },
# #         "lead": {
# #             "id": 456,  # leads.ID
# #             "phone": "+79991234567",  # leads.UF_PHONE
# #             "name": "Иван Клиент",    # leads.UF_NAME
# #             "order_id": 789           # leads.UF_ORDER
# #         },
# #         "phone": {
# #             "connection_type": "webrtc",
# #             "params": {
# #                 "user_name": "vasya_operator",
# #                 "display_name": "Василий Петров"
# #             }
# #         }
# #     }

# # # =============================
# # # Интеграционные тесты телефонии
# # # =============================

# # @allure.epic("Телефония")
# # @allure.feature("Интеграция: оператор и звонок")
# # class TestTelephonyMinimal:
# #     """
# #     Минимальные интеграционные тесты телефонии.
# #     Для запуска с моками: TELEPHONY_USE_MOCKS=1 pytest ...
# #     Для запуска с реальным API: TELEPHONY_USE_MOCKS=0 pytest ...
# #     """

# #     @allure.story("Смена статуса оператора")
# #     @allure.severity('critical')
# #     def test_operator_status_change(self, telephony_api_client, voximplant_mock, test_data):
# #         """Оператор становится 'доступен', проверяем статус через API"""
# #         operator_id = test_data["operator"]["id"]
# #         response = telephony_api_client.change_operator_status(operator_id, "available")
# #         assert response.status_code == 200
# #         # Проверяем статус
# #         status_response = telephony_api_client.get_operator_status(operator_id)
# #         assert status_response.status_code == 200
# #         status_data = status_response.json()
# #         assert status_data.get("status") == "available"
# #         allure.attach(
# #             f"Оператор ID: {operator_id}\nAPI ответ: {response.json()}\nСтатус: {status_data}",
# #             "Результаты теста статуса",
# #             allure.attachment_type.TEXT
# #         )

# #     @allure.story("Запуск звонка оператору")
# #     @allure.severity('critical')
# #     def test_predictive_call(self, telephony_api_client, voximplant_mock, test_data):
# #         """Запуск звонка по лиду, проверяем, что звонок появился в очереди"""
# #         lead_data = test_data["lead"]
# #         phone_data = test_data["phone"]
# #         # Запускаем звонок
# #         call_response = telephony_api_client.start_predictive_call(lead_data, phone_data)
# #         assert call_response.status_code == 200
# #         call_data = call_response.json()
# #         assert call_data.get("success") is True or call_data.get("call_session_id")
# #         # Проверяем, что звонок появился в очереди
# #         queue_response = telephony_api_client.get_dialer_queue()
# #         assert queue_response.status_code == 200
# #         queue_data = queue_response.json()
# #         lead_in_queue = any(
# #             item.get("lead_id") == lead_data["id"]
# #             for item in queue_data.get("queue", [])
# #         )
# #         assert lead_in_queue
# #         allure.attach(
# #             f"Лид ID: {lead_data['id']}\nCall Session: {call_data}\nВ очереди: {lead_in_queue}",
# #             "Результаты теста звонка",
# #             allure.attachment_type.TEXT
# #         ) 