import requests
import logging
from typing import Dict, Any, Optional
import allure

class APIClient:
    """Клиент для работы с API"""
    
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.logger = logging.getLogger(__name__)
        
    def _get_headers(self) -> Dict[str, str]:
        """Получение заголовков для запросов"""
        return {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "*/*",
            "User-Agent": "Python/Requests"
        }
        
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Выполнение HTTP запроса"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = self._get_headers()
        
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))
        
        self.logger.info(f"Выполнение {method} запроса к {url}")
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                **kwargs
            )
            
            self.logger.info(f"Получен ответ: {response.status_code}")
            if response.text:
                self.logger.debug(f"Тело ответа: {response.text[:1000]}")
                
            return response
            
        except Exception as e:
            self.logger.error(f"Ошибка при выполнении запроса: {str(e)}")
            raise
            
    def get(self, endpoint: str, **kwargs) -> requests.Response:
        """Выполнение GET запроса"""
        return self._make_request("GET", endpoint, **kwargs)
        
    def post(self, endpoint: str, **kwargs) -> requests.Response:
        """Выполнение POST запроса"""
        return self._make_request("POST", endpoint, **kwargs)
        
    def put(self, endpoint: str, **kwargs) -> requests.Response:
        """Выполнение PUT запроса"""
        return self._make_request("PUT", endpoint, **kwargs)
        
    def delete(self, endpoint: str, **kwargs) -> requests.Response:
        """Выполнение DELETE запроса"""
        return self._make_request("DELETE", endpoint, **kwargs)

    def search_leads(self, query_params: Dict[str, Any]) -> Dict[str, Any]:
        """Поиск лидов по параметрам"""
        try:
            response = self._make_request('GET', '/leads/search', params=query_params)
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Ошибка при поиске лидов: {str(e)}")
            return {"status": "error", "message": str(e)}

    def get_lead(self, lead_id: int) -> Dict[str, Any]:
        """Получение информации о лиде"""
        try:
            response = self._make_request('GET', f'/leads/{lead_id}')
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Ошибка при получении лида {lead_id}: {str(e)}")
            return {"status": "error", "message": str(e)}

    def create_lead(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """Создание нового лида"""
        try:
            response = self._make_request('POST', '/leads', json=lead_data)
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Ошибка при создании лида: {str(e)}")
            return {"status": "error", "message": str(e)}

    def update_lead(self, lead_id: int, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """Обновление информации о лиде"""
        return self._make_request('PUT', f'/leads/{lead_id}', json=lead_data).json()

    def delete_lead(self, lead_id: int) -> Dict[str, Any]:
        """Удаление лида"""
        return self._make_request('DELETE', f'/leads/{lead_id}').json()

    def get_telegram_info(self, lead_id: int) -> Dict[str, Any]:
        """Получение информации о Telegram лида"""
        return self._make_request('GET', f'/leads/{lead_id}/telegram').json()

    def update_telegram_info(self, lead_id: int, telegram_data: Dict[str, Any]) -> Dict[str, Any]:
        """Обновление информации о Telegram лида"""
        return self._make_request('PUT', f'/leads/{lead_id}/telegram', json=telegram_data).json() 