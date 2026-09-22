"""
Интеграция с Graylog для отправки логов тестов
"""
import logging
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
import requests
from pathlib import Path

logger = logging.getLogger(__name__)


class GraylogIntegration:
    """Класс для интеграции с Graylog"""
    
    def __init__(
        self,
        graylog_url: Optional[str] = None,
        graylog_port: int = 12201,
        use_gelf: bool = True,
        enabled: bool = True
    ):
        """
        Инициализация интеграции с Graylog
        
        Args:
            graylog_url: URL сервера Graylog (или из переменной окружения GRAYLOG_URL)
            graylog_port: Порт Graylog (по умолчанию 12201 для GELF)
            use_gelf: Использовать GELF протокол (True) или HTTP API (False)
            enabled: Включена ли интеграция (можно отключить через переменную окружения)
        """
        self.enabled = enabled and os.getenv("GRAYLOG_ENABLED", "false").lower() in ["true", "1", "yes"]
        
        if not self.enabled:
            logger.info("Интеграция с Graylog отключена")
            return
        
        self.graylog_url = graylog_url or os.getenv("GRAYLOG_URL")
        self.graylog_port = int(os.getenv("GRAYLOG_PORT", graylog_port))
        self.use_gelf = use_gelf
        
        if not self.graylog_url:
            logger.warning("Graylog URL не указан. Интеграция будет отключена.")
            self.enabled = False
            return
        
        # Формируем endpoint
        if self.use_gelf:
            self.endpoint = f"http://{self.graylog_url}:{self.graylog_port}/gelf"
        else:
            self.endpoint = f"http://{self.graylog_url}/api/search/universal/relative"
        
        logger.info(f"Graylog интеграция инициализирована: {self.endpoint}")
    
    def send_test_start(
        self,
        test_name: str,
        test_class: Optional[str] = None,
        test_file: Optional[str] = None,
        environment: Optional[str] = None,
        **kwargs
    ):
        """Отправляет событие начала теста"""
        if not self.enabled:
            return
        
        message = {
            "version": "1.1",
            "host": os.getenv("HOSTNAME", "test-runner"),
            "short_message": f"Тест начат: {test_name}",
            "full_message": f"Начало выполнения теста {test_name}",
            "timestamp": datetime.now().timestamp(),
            "level": 6,  # INFO
            "_event_type": "test_start",
            "_test_name": test_name,
            "_test_class": test_class or "",
            "_test_file": test_file or "",
            "_environment": environment or "",
            **{f"_{k}": str(v) for k, v in kwargs.items()}
        }
        
        self._send_message(message)
    
    def send_test_finish(
        self,
        test_name: str,
        status: str,
        duration: float,
        error: Optional[str] = None,
        **kwargs
    ):
        """Отправляет событие завершения теста"""
        if not self.enabled:
            return
        
        level_map = {
            "passed": 6,  # INFO
            "failed": 3,  # ERROR
            "skipped": 4,  # WARNING
            "broken": 3,  # ERROR
        }
        
        message = {
            "version": "1.1",
            "host": os.getenv("HOSTNAME", "test-runner"),
            "short_message": f"Тест завершен: {test_name} - {status}",
            "full_message": f"Тест {test_name} завершен со статусом {status} за {duration:.2f}с",
            "timestamp": datetime.now().timestamp(),
            "level": level_map.get(status, 6),
            "_event_type": "test_finish",
            "_test_name": test_name,
            "_test_status": status,
            "_test_duration": str(duration),
            "_error": error or "",
            **{f"_{k}": str(v) for k, v in kwargs.items()}
        }
        
        self._send_message(message)
    
    def send_test_step(
        self,
        test_name: str,
        step_name: str,
        step_status: str = "info",
        **kwargs
    ):
        """Отправляет событие шага теста"""
        if not self.enabled:
            return
        
        level_map = {
            "info": 6,
            "success": 6,
            "warning": 4,
            "error": 3,
        }
        
        message = {
            "version": "1.1",
            "host": os.getenv("HOSTNAME", "test-runner"),
            "short_message": f"Шаг теста: {step_name}",
            "full_message": f"Тест {test_name}: шаг {step_name}",
            "timestamp": datetime.now().timestamp(),
            "level": level_map.get(step_status, 6),
            "_event_type": "test_step",
            "_test_name": test_name,
            "_step_name": step_name,
            "_step_status": step_status,
            **{f"_{k}": str(v) for k, v in kwargs.items()}
        }
        
        self._send_message(message)
    
    def send_session_start(
        self,
        total_tests: int,
        environment: Optional[str] = None,
        **kwargs
    ):
        """Отправляет событие начала сессии тестирования"""
        if not self.enabled:
            return
        
        message = {
            "version": "1.1",
            "host": os.getenv("HOSTNAME", "test-runner"),
            "short_message": f"Сессия тестирования начата: {total_tests} тестов",
            "full_message": f"Начало сессии тестирования с {total_tests} тестами",
            "timestamp": datetime.now().timestamp(),
            "level": 6,
            "_event_type": "session_start",
            "_total_tests": str(total_tests),
            "_environment": environment or "",
            **{f"_{k}": str(v) for k, v in kwargs.items()}
        }
        
        self._send_message(message)
    
    def send_session_finish(
        self,
        total_tests: int,
        passed: int,
        failed: int,
        skipped: int,
        duration: float,
        **kwargs
    ):
        """Отправляет событие завершения сессии тестирования"""
        if not self.enabled:
            return
        
        success_rate = (passed / total_tests * 100) if total_tests > 0 else 0
        level = 6 if failed == 0 else 3
        
        message = {
            "version": "1.1",
            "host": os.getenv("HOSTNAME", "test-runner"),
            "short_message": f"Сессия завершена: {passed}/{total_tests} успешно",
            "full_message": f"Сессия тестирования завершена: {passed} успешно, {failed} провалено, {skipped} пропущено",
            "timestamp": datetime.now().timestamp(),
            "level": level,
            "_event_type": "session_finish",
            "_total_tests": str(total_tests),
            "_passed": str(passed),
            "_failed": str(failed),
            "_skipped": str(skipped),
            "_duration": str(duration),
            "_success_rate": f"{success_rate:.2f}%",
            **{f"_{k}": str(v) for k, v in kwargs.items()}
        }
        
        self._send_message(message)
    
    def send_error(
        self,
        error_message: str,
        error_type: str,
        test_name: Optional[str] = None,
        traceback: Optional[str] = None,
        **kwargs
    ):
        """Отправляет событие ошибки"""
        if not self.enabled:
            return
        
        message = {
            "version": "1.1",
            "host": os.getenv("HOSTNAME", "test-runner"),
            "short_message": f"Ошибка: {error_message}",
            "full_message": traceback or error_message,
            "timestamp": datetime.now().timestamp(),
            "level": 3,  # ERROR
            "_event_type": "error",
            "_error_type": error_type,
            "_error_message": error_message,
            "_test_name": test_name or "",
            "_traceback": traceback or "",
            **{f"_{k}": str(v) for k, v in kwargs.items()}
        }
        
        self._send_message(message)
    
    def _send_message(self, message: Dict[str, Any]):
        """Отправляет сообщение в Graylog"""
        if not self.enabled:
            return
        
        try:
            if self.use_gelf:
                # GELF формат (JSON)
                response = requests.post(
                    self.endpoint,
                    json=message,
                    timeout=5,
                    headers={"Content-Type": "application/json"}
                )
            else:
                # HTTP API
                response = requests.post(
                    self.endpoint,
                    json=message,
                    timeout=5,
                    headers={"Content-Type": "application/json"}
                )
            
            if response.status_code not in [200, 202, 204]:
                logger.warning(f"Graylog вернул статус {response.status_code}: {response.text}")
            else:
                logger.debug(f"Сообщение отправлено в Graylog: {message.get('short_message')}")
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"Не удалось отправить сообщение в Graylog: {str(e)}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка при отправке в Graylog: {str(e)}")


# Глобальный экземпляр (можно использовать как singleton)
_graylog_instance: Optional[GraylogIntegration] = None


def get_graylog() -> Optional[GraylogIntegration]:
    """Получает глобальный экземпляр Graylog интеграции"""
    global _graylog_instance
    if _graylog_instance is None:
        _graylog_instance = GraylogIntegration()
    return _graylog_instance if _graylog_instance.enabled else None

