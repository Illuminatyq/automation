"""
Утилиты для улучшения Allure отчетов
"""
import allure
import logging
import json
import os
from datetime import datetime
from typing import Any, Dict, Optional, List
from playwright.sync_api import Page
import traceback

logger = logging.getLogger(__name__)


class AllureHelper:
    """Класс-хелпер для работы с Allure отчетами"""
    
    @staticmethod
    def attach_environment_info(config: Dict[str, Any]):
        """Прикрепляет информацию об окружении к отчету"""
        env_info = {
            "Окружение": config.get("current_environment", "unknown"),
            "Base URL": config.get("baseUrl", "unknown"),
            "API URL": config.get("apiUrl", "unknown"),
            "Браузер": config.get("browser", "unknown"),
            "Таймаут": config.get("timeout", "unknown"),
            "Время запуска": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        
        allure.dynamic.label("environment", env_info["Окружение"])
        allure.attach(
            json.dumps(env_info, indent=2, ensure_ascii=False),
            name="🌍 Информация об окружении",
            attachment_type=allure.attachment_type.JSON
        )
    
    @staticmethod
    def attach_page_info(page: Page, step_name: str = "Информация о странице"):
        """Прикрепляет информацию о текущей странице"""
        try:
            page_info = {
                "URL": page.url,
                "Заголовок": page.title(),
                "Время": datetime.now().isoformat(),
                "Viewport": str(page.viewport_size) if page.viewport_size else "N/A",
            }
            
            allure.attach(
                json.dumps(page_info, indent=2, ensure_ascii=False),
                name=f"📄 {step_name}",
                attachment_type=allure.attachment_type.JSON
            )
        except Exception as e:
            logger.warning(f"Не удалось получить информацию о странице: {str(e)}")
    
    @staticmethod
    def attach_request_response(request_data: Dict[str, Any], response_data: Dict[str, Any]):
        """Прикрепляет информацию о HTTP запросе и ответе"""
        request_info = {
            "Метод": request_data.get("method", "N/A"),
            "URL": request_data.get("url", "N/A"),
            "Заголовки": request_data.get("headers", {}),
            "Тело запроса": request_data.get("body", "N/A"),
        }
        
        response_info = {
            "Статус": response_data.get("status", "N/A"),
            "Заголовки": response_data.get("headers", {}),
            "Тело ответа": response_data.get("body", "N/A"),
            "Время ответа (мс)": response_data.get("duration", "N/A"),
        }
        
        allure.attach(
            json.dumps(request_info, indent=2, ensure_ascii=False),
            name="📤 HTTP Запрос",
            attachment_type=allure.attachment_type.JSON
        )
        
        allure.attach(
            json.dumps(response_info, indent=2, ensure_ascii=False),
            name="📥 HTTP Ответ",
            attachment_type=allure.attachment_type.JSON
        )
    
    @staticmethod
    def attach_error_details(exception: Exception, context: Optional[Dict[str, Any]] = None):
        """Прикрепляет детальную информацию об ошибке"""
        error_info = {
            "Тип ошибки": type(exception).__name__,
            "Сообщение": str(exception),
            "Трассировка": traceback.format_exc(),
            "Время": datetime.now().isoformat(),
        }
        
        if context:
            error_info["Контекст"] = context
        
        allure.attach(
            json.dumps(error_info, indent=2, ensure_ascii=False),
            name="🚨 Детали ошибки",
            attachment_type=allure.attachment_type.JSON
        )
    
    @staticmethod
    def attach_test_data(test_data: Dict[str, Any], name: str = "Тестовые данные"):
        """Прикрепляет тестовые данные к отчету"""
        # Маскируем чувствительные данные
        masked_data = AllureHelper._mask_sensitive_data(test_data)
        
        allure.attach(
            json.dumps(masked_data, indent=2, ensure_ascii=False),
            name=f"📊 {name}",
            attachment_type=allure.attachment_type.JSON
        )
    
    @staticmethod
    def _mask_sensitive_data(data: Any) -> Any:
        """Маскирует чувствительные данные (пароли, токены и т.д.)"""
        sensitive_keys = ["password", "token", "api_key", "secret", "auth", "credential"]
        
        if isinstance(data, dict):
            masked = {}
            for key, value in data.items():
                if any(sensitive in key.lower() for sensitive in sensitive_keys):
                    masked[key] = "***MASKED***"
                elif isinstance(value, (dict, list)):
                    masked[key] = AllureHelper._mask_sensitive_data(value)
                else:
                    masked[key] = value
            return masked
        elif isinstance(data, list):
            return [AllureHelper._mask_sensitive_data(item) for item in data]
        else:
            return data
    
    @staticmethod
    def attach_console_logs(logs: List[Dict[str, Any]]):
        """Прикрепляет логи консоли браузера"""
        if not logs:
            return
        
        log_text = "\n".join([
            f"[{log.get('level', 'INFO')}] {log.get('text', '')}"
            for log in logs
        ])
        
        allure.attach(
            log_text,
            name="📝 Логи консоли браузера",
            attachment_type=allure.attachment_type.TEXT
        )
    
    @staticmethod
    def attach_network_logs(requests: List[Dict[str, Any]]):
        """Прикрепляет логи сетевых запросов"""
        if not requests:
            return
        
        network_info = []
        for req in requests:
            network_info.append({
                "URL": req.get("url", "N/A"),
                "Метод": req.get("method", "N/A"),
                "Статус": req.get("response", {}).get("status", "N/A"),
                "Время (мс)": req.get("response", {}).get("time", "N/A"),
            })
        
        allure.attach(
            json.dumps(network_info, indent=2, ensure_ascii=False),
            name="🌐 Сетевые запросы",
            attachment_type=allure.attachment_type.JSON
        )
    
    @staticmethod
    def set_test_parameters(**kwargs):
        """Устанавливает параметры теста для отображения в Allure"""
        for key, value in kwargs.items():
            allure.dynamic.parameter(key, value)
    
    @staticmethod
    def set_test_links(**links):
        """Устанавливает ссылки для теста (issue, tms и т.д.)"""
        for link_type, link_value in links.items():
            if link_type == "issue":
                allure.dynamic.link(link_value, name="Issue", link_type=allure.link_type.ISSUE)
            elif link_type == "tms":
                allure.dynamic.link(link_value, name="TMS", link_type=allure.link_type.TMS)
            elif link_type == "link":
                allure.dynamic.link(link_value, name="Ссылка")
    
    @staticmethod
    def attach_performance_metrics(metrics: Dict[str, Any]):
        """Прикрепляет метрики производительности"""
        allure.attach(
            json.dumps(metrics, indent=2, ensure_ascii=False),
            name="⚡ Метрики производительности",
            attachment_type=allure.attachment_type.JSON
        )
    
    @staticmethod
    def attach_sql_query(query: str, params: Optional[Dict[str, Any]] = None):
        """Прикрепляет SQL запрос (для отладки)"""
        query_info = {
            "Запрос": query,
            "Параметры": params or {},
            "Время": datetime.now().isoformat(),
        }
        
        allure.attach(
            json.dumps(query_info, indent=2, ensure_ascii=False),
            name="🗄️ SQL Запрос",
            attachment_type=allure.attachment_type.JSON
        )


def allure_step(step_name: str):
    """Декоратор для создания Allure шагов"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            with allure.step(step_name):
                return func(*args, **kwargs)
        return wrapper
    return decorator

