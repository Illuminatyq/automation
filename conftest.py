import pytest
from utils.driver_factory import DriverFactory
import os
import json

@pytest.fixture(scope="function")
def driver(request):
    driver = DriverFactory.get_driver()
    yield driver
    driver.quit()
    
@pytest.fixture(scope="session")
def config():
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.json')
    with open(config_path, 'r') as f:
        config = json.load(f)
    return config