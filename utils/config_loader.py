import os
import json
from dotenv import load_dotenv
from typing import Dict, Any

class ConfigLoader:
    def __init__(self, config_path: str = "config/config.json"):
        load_dotenv()  # Загружаем переменные окружения из .env файла
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Загружает конфигурацию из JSON файла и подставляет переменные окружения"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Рекурсивно обрабатываем все значения в конфигурации
        self._process_env_variables(config)
        return config

    def _process_env_variables(self, config: Dict[str, Any]) -> None:
        """Рекурсивно обрабатывает словарь и подставляет переменные окружения"""
        for key, value in config.items():
            if isinstance(value, dict):
                self._process_env_variables(value)
            elif isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                env_var = value[2:-1]  # Убираем ${ и }
                config[key] = os.getenv(env_var, "")

    def get_environment_config(self, env_name: str = None) -> Dict[str, Any]:
        """Получает конфигурацию для указанного окружения"""
        env_name = env_name or self.config.get("defaultEnvironment", "dev")
        return self.config["environments"].get(env_name, {})

    def get_api_key(self, env_name: str = None) -> str:
        """Получает API ключ для указанного окружения"""
        env_config = self.get_environment_config(env_name)
        return env_config.get("api_key", "")

    def get_base_url(self, env_name: str = None) -> str:
        """Получает базовый URL для указанного окружения"""
        env_config = self.get_environment_config(env_name)
        return env_config.get("baseUrl", "")

    def get_api_url(self, env_name: str = None) -> str:
        """Получает API URL для указанного окружения"""
        env_config = self.get_environment_config(env_name)
        return env_config.get("apiUrl", "")

# Пример использования:
if __name__ == "__main__":
    config_loader = ConfigLoader()
    
    # Получение конфигурации для dev окружения
    dev_config = config_loader.get_environment_config("dev")
    print(f"Dev API Key: {dev_config['api_key']}")
    
    # Получение конфигурации для SM окружения
    sm_config = config_loader.get_environment_config("sm")
    print(f"SM API Key: {sm_config['api_key']}") 