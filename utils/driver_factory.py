from selenium import webdriver
import json
import os
import platform

class DriverFactory:
    @staticmethod
    def get_driver(browser_name=None):
        # Загрузка конфигурации
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'config.json')
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        browser = browser_name or config.get('browser', 'chrome').lower()
        
        if browser == 'chrome':
            options = webdriver.ChromeOptions()
            options.add_argument('--start-maximized')
            
            # Используем встроенный драйвер Chrome
            # Это работает с Selenium 4.x
            driver = webdriver.Chrome(options=options)
            
        elif browser == 'firefox':
            options = webdriver.FirefoxOptions()
            options.add_argument('--start-maximized')
            driver = webdriver.Firefox(options=options)
        else:
            raise Exception(f"Browser {browser} is not supported")
        
        driver.implicitly_wait(config.get('timeout', 10))
        return driver