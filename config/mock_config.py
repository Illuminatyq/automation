"""
Конфигурация для управления моками в тестах телефонии
"""

import os
from typing import Dict, Any

class MockConfig:
    """Конфигурация моков для тестов телефонии"""
    
    def __init__(self):
        # Читаем настройки из переменных окружения
        self.use_mocks = self._get_env_bool('USE_MOCKS', default=True)
        self.use_voximplant_mock = self._get_env_bool('USE_VOXIMPLANT_MOCK', default=True)
        self.fail_on_api_error = self._get_env_bool('FAIL_ON_API_ERROR', default=False)
        self.api_timeout = int(os.getenv('API_TIMEOUT', '10'))
        
    def _get_env_bool(self, key: str, default: bool = True) -> bool:
        """Получение булевого значения из переменной окружения"""
        value = os.getenv(key, str(default)).lower()
        return value in ('true', '1', 'yes', 'on')
    
    @property
    def is_mock_enabled(self) -> bool:
        """Включены ли моки"""
        return self.use_mocks
    
    @property
    def is_voximplant_mock_enabled(self) -> bool:
        """Включен ли мок Voximplant"""
        return self.use_mocks and self.use_voximplant_mock
    
    def get_mock_settings(self) -> Dict[str, Any]:
        """Получение настроек моков"""
        return {
            'use_mocks': self.use_mocks,
            'use_voximplant_mock': self.use_voximplant_mock,
            'fail_on_api_error': self.fail_on_api_error,
            'api_timeout': self.api_timeout
        }

# Глобальный экземпляр конфигурации
mock_config = MockConfig()

# Функции-помощники для тестов
def should_use_mocks() -> bool:
    """Должны ли тесты использовать моки"""
    return mock_config.is_mock_enabled

def should_use_voximplant_mock() -> bool:
    """Должен ли использоваться мок Voximplant"""
    return mock_config.is_voximplant_mock_enabled

def get_api_timeout() -> int:
    """Получение таймаута для API запросов"""
    return mock_config.api_timeout

def should_fail_on_api_error() -> bool:
    """Должны ли тесты падать при ошибках API"""
    return mock_config.fail_on_api_error

# Константы для разных режимов тестирования
MOCK_MODES = {
    'FULL_MOCK': {
        'USE_MOCKS': True,
        'USE_VOXIMPLANT_MOCK': True,
        'FAIL_ON_API_ERROR': False
    },
    'PARTIAL_MOCK': {
        'USE_MOCKS': True,
        'USE_VOXIMPLANT_MOCK': False,
        'FAIL_ON_API_ERROR': False
    },
    'NO_MOCK': {
        'USE_MOCKS': False,
        'USE_VOXIMPLANT_MOCK': False,
        'FAIL_ON_API_ERROR': True
    },
    'STRICT_NO_MOCK': {
        'USE_MOCKS': False,
        'USE_VOXIMPLANT_MOCK': False,
        'FAIL_ON_API_ERROR': True
    }
}

def set_mock_mode(mode: str):
    """Установка режима моков"""
    if mode not in MOCK_MODES:
        raise ValueError(f"Неизвестный режим моков: {mode}. Доступные: {list(MOCK_MODES.keys())}")
    
    settings = MOCK_MODES[mode]
    for key, value in settings.items():
        os.environ[key] = str(value)
    
    # Пересоздаем конфигурацию
    global mock_config
    mock_config = MockConfig() 