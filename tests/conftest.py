import pytest
import os
import json
from playwright.sync_api import sync_playwright, TimeoutError
import logging
from config.viewport_config import VIEWPORT_CONFIGS
import allure
from utils.screenshot_utils import ScreenshotUtils

def pytest_addoption(parser):
    parser.addoption("--env", action="store", default=None, help="Environment to run tests against")
    parser.addoption("--api-key", action="store", default=None, help="API key for API tests")
    parser.addoption("--headless", action="store_true", default=False, help="Run browsers in headless mode")
    parser.addoption("--browser-type", action="store", default=None, help="Browser to run tests in (chromium, firefox, webkit)")

def pytest_configure(config):
    config.addinivalue_line("markers", "visual: mark test as visual regression test")
    config.addinivalue_line("markers", "api: mark test as API test")
    config.addinivalue_line("markers", "browser: mark test to run in specific browser")

@pytest.fixture(scope="session")
def config(request):
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "config.json")
    with open(config_path, "r") as f:
        config = json.load(f)

    env_name = request.config.getoption("--env") or os.environ.get("TEST_ENV") or config.get("defaultEnvironment", "dev")
    if env_name not in config.get("environments", {}):
        available_envs = ", ".join(config["environments"].keys())
        pytest.fail(f"Environment '{env_name}' not found. Available: {available_envs}")

    config.update(config["environments"][env_name])
    config["current_environment"] = env_name
    
    # Получаем API ключ из разных источников в порядке приоритета:
    # 1. Параметр командной строки
    # 2. Переменная окружения LINER_API_KEY
    # 3. Переменная окружения с префиксом окружения (например, DEV_LINER_API_KEY)
    # 4. Значение из конфигурационного файла
    api_key = (
        request.config.getoption("--api-key") or 
        os.environ.get("LINER_API_KEY") or 
        os.environ.get(f"{env_name.upper()}_LINER_API_KEY") or
        config.get("api_key", "")
    )
    
    if api_key:
        config["api_key"] = api_key
    else:
        logging.warning(f"API ключ не найден для окружения {env_name}. API тесты могут не работать.")
    
    return config

@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        yield browser
        browser.close()

@pytest.fixture(scope="session", autouse=True)
def cleanup_old_screenshots():
    """Очищает старые скриншоты перед запуском тестов"""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        screenshot_utils = ScreenshotUtils(page)
        screenshot_utils.cleanup_old_screenshots(days=7)  # Удаляем скриншоты старше 7 дней
        browser.close()

@pytest.fixture
def page(browser):
    """Фикстура для создания новой страницы"""
    page = browser.new_page()
    yield page
    page.close()

@pytest.fixture
def browser_page(request, config):
    """Фикстура для создания страницы в указанном браузере с заданным разрешением экрана"""
    browser_type = request.param[0] if isinstance(request.param, tuple) else request.param
    viewport = request.param[1] if isinstance(request.param, tuple) else ("desktop", "medium")
    device_type, viewport_type = viewport
    
    headless = request.config.getoption("--headless") or os.environ.get("HEADLESS", "false").lower() in ("true", "1", "yes")
    
    # Получаем размеры экрана из конфигурации
    viewport_size = VIEWPORT_CONFIGS[device_type][viewport_type]
    
    with sync_playwright() as p:
        if browser_type == "chromium":
            browser_instance = p.chromium.launch(headless=headless)
            browser_name = "Chrome"
        elif browser_type == "firefox":
            browser_instance = p.firefox.launch(headless=headless)
            browser_name = "Firefox"
        elif browser_type == "webkit":
            browser_instance = p.webkit.launch(headless=headless)
            browser_name = "Safari"
        else:
            browser_instance = p.chromium.launch(headless=headless)
            browser_name = "Chrome"
        
        context = browser_instance.new_context(viewport=viewport_size)
        page = context.new_page()
        
        try:
            yield (page, browser_name)
        finally:
            page.close()
            context.close()
            browser_instance.close()

@pytest.fixture
def authenticated_page(page, config):
    from pages.login_page import LoginPage
    login_page = LoginPage(page, config["baseUrl"])
    creds = config["credentials"]["valid_user"]
    
    login_page.login(creds["email"], creds["password"])
    
    # Ждем редиректа на /office/
    try:
        page.wait_for_url("**/office/**", timeout=10000)
    except TimeoutError:
        page.screenshot(path="auth_failed.png")
        pytest.fail(f"Failed to authenticate: expected redirect to /office/, got {page.url}")
    return page

@pytest.fixture(scope="function")
def screenshot_utils(page):
    """Фикстура для работы со скриншотами"""
    return ScreenshotUtils(page)