from utils.config_loader import ConfigLoader

def test_config_loading():
    config = ConfigLoader()
    
    # Проверяем загрузку для всех окружений
    environments = ['dev', 'sm', 'ask-yug']
    
    for env in environments:
        env_config = config.get_environment_config(env)
        print(f"\nКонфигурация для {env}:")
        print(f"API Key: {env_config['api_key']}")
        print(f"Base URL: {env_config['baseUrl']}")
        print(f"API URL: {env_config['apiUrl']}")

if __name__ == "__main__":
    test_config_loading() 