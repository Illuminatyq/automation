from dotenv import load_dotenv
load_dotenv()

import pytest
import os
import json
import logging
import allure
import sys
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError, Page
import requests
from allure_commons.types import AttachmentType
from urllib.parse import urljoin
from pages.login_page import LoginPage
import time
from unittest.mock import patch, MagicMock

from config.constants import TEST_RESULTS_DIR, LOGS_DIR, SCREENSHOTS_DIR
from config.viewport_config import VIEWPORT_CONFIGS
from utils.screenshot_utils import ScreenshotUtils
from utils.allure_helpers import AllureHelper
from utils.graylog_integration import get_graylog

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
for handler in logging.getLogger().handlers:
    handler.setStream(sys.stdout)
    try:
        handler.stream.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Настройка логирования
def setup_logging():
    """Настройка логирования для тестов"""
    log_file = LOGS_DIR / f"test_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)8s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    # Уменьшаем уровень логирования для Playwright
    logging.getLogger("playwright").setLevel(logging.WARNING)

# Настройка логирования при импорте
setup_logging()

def replace_placeholders(data):
    """Рекурсивно заменяет плейсхолдеры вида ${VAR_NAME} на значения из os.getenv"""
    if isinstance(data, dict):
        return {k: replace_placeholders(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [replace_placeholders(i) for i in data]
    elif isinstance(data, str) and data.startswith('${') and data.endswith('}'):
        var_name = data[2:-1]
        value = os.getenv(var_name)
        if value is None:
            raise ValueError(f"Переменная окружения '{var_name}' не найдена! Укажите её в .env или системных переменных.")
        return value
    return data

def pytest_addoption(parser):
    """Добавление параметров командной строки"""
    parser.addoption(
        "--env", 
        action="store", 
        default="dev", 
        help="Окружение для запуска тестов (dev, sm, ask-yug)"
    )
    parser.addoption(
        "--api-key", 
        action="store", 
        default=None, 
        help="API ключ для API тестов"
    )
    parser.addoption(
        "--headless", 
        action="store_true", 
        default=False, 
        help="Запуск в headless режиме"
    )
    parser.addoption(
        "--viewport", 
        action="store", 
        default="desktop", 
        help="Формат устройства: desktop, tablet, mobile"
    )
    parser.addoption(
        "--test-type", 
        action="store", 
        default="ui", 
        help="Тип тестов: ui, api, hybrid"
    )
    # Опция --browser уже определена плагином pytest-playwright
    # Не добавляем дублирующую опцию

def pytest_configure(config):
    """Конфигурация Pytest"""
    config.addinivalue_line("markers", "auth: тесты авторизации")
    config.addinivalue_line("markers", "smoke: smoke тесты")
    config.addinivalue_line("markers", "critical: критические тесты")
    config.addinivalue_line("markers", "visual: визуальные тесты")
    config.addinivalue_line("markers", "api: API тесты")
    config.addinivalue_line("markers", "leads: тесты лидов")
    config.addinivalue_line("markers", "slow: медленные тесты")
    config.addinivalue_line("markers", "destructive: деструктивные тесты, которые намеренно проверяют хрупкость системы")

@pytest.fixture(scope="session")
def config(request):
    """Загружает конфигурацию с учетом выбранного окружения"""
    # ЖЁСТКИЙ ПУТЬ — ГАРАНТИРОВАННО РАБОТАЕТ
    config_path = r"E:\automation\config\config.json"
    
    if not os.path.exists(config_path):
        pytest.fail(f"Файл конфигурации не найден: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    env_name = request.config.getoption("--env") or config.get("defaultEnvironment", "dev")
    
    if env_name not in config.get("environments", {}):
        available_envs = ", ".join(config.get("environments", {}).keys())
        pytest.fail(f"Окружение '{env_name}' не найдено в конфигурации. Доступные: {available_envs}")
    
    env_config = config["environments"][env_name]
    config.update(env_config)
    config["current_environment"] = env_name
    
    # Замена плейсхолдеров
    config = replace_placeholders(config)
    
    return config

@pytest.fixture(scope="session")
def browser(request):
    """Фикстура для создания браузера"""
    browser_name = request.config.getoption("--browser") or "chromium"
    # pytest-playwright может отдавать список браузеров (например ["chromium"])
    if isinstance(browser_name, (list, tuple)):
        browser_name = browser_name[0] if browser_name else "chromium"
    headless = request.config.getoption("--headless")
    with sync_playwright() as p:
        browser_launcher = getattr(p, browser_name, None)
        if browser_launcher is None:
            pytest.fail(f"Браузер '{browser_name}' не поддерживается. Доступны: chromium, firefox, webkit.")
        browser = browser_launcher.launch(headless=headless)
        yield browser
        browser.close()

@pytest.fixture
def browser_context(browser):
    """Фикстура для создания нового контекста браузера для каждого теста"""
    context = browser.new_context(viewport={'width': 1920, 'height': 1080})
    yield context
    context.close()

@pytest.fixture
def page(browser_context):
    """Фикстура для создания новой страницы для каждого теста"""
    page = browser_context.new_page()
    yield page
    page.close()

@pytest.fixture
def screenshot_utils(page):
    """Фикстура для работы со скриншотами"""
    return ScreenshotUtils(page)

@pytest.fixture
def authenticated_page(page, config):
    """Фикстура, возвращающая аутентифицированную страницу"""
    from pages.login_page import LoginPage
    
    login_page = LoginPage(page, config["baseUrl"])
    login_page.navigate()
    
    valid_credentials = config['credentials']['valid_user']
    login_page.login(valid_credentials['email'], valid_credentials['password'])
    
    # Ждем успешного входа
    page.wait_for_url("**/*office*", timeout=10000)
    
    return page

@pytest.fixture(scope="session")
def api_config(config, request):
    """Фикстура для API конфигурации"""
    api_key = request.config.getoption("--api-key") or config.get("api_key") or os.getenv("LINER_API_KEY")
    if not api_key:
        pytest.skip("API ключ не найден. Укажите через --api-key или в .env")
    
    api_base_url = config.get("apiUrl")
    
    return {
        "base_url": api_base_url,
        "apiUrl": api_base_url,
        "api_key": api_key,
        "apiKey": api_key,
    }

@pytest.fixture(scope="function")
def api_headers(api_config):
    return {
        'Authorization': f"Bearer {api_config['apiKey']}",
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

# Моки телефонии
@pytest.fixture(scope='session')
def use_mocks():
    return os.environ.get('TELEPHONY_USE_MOCKS', '').lower() in ['1', 'true', 'yes']

@pytest.fixture
def voximplant_mock(use_mocks):
    if not use_mocks:
        yield None
        return
    with patch('requests.post') as mock_post, patch('requests.get') as mock_get:
        def mock_user_ready_response(*args, **kwargs):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "result": [
                    {"user_name": "test_operator", "acd_status": "READY"}
                ]
            }
            return mock_response
        def mock_start_call_response(*args, **kwargs):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "success": True,
                "call_session_id": 789
            }
            return mock_response
        mock_get.side_effect = mock_user_ready_response
        mock_post.side_effect = mock_start_call_response
        yield {'post': mock_post, 'get': mock_get}

# Pytest хуки с улучшенной интеграцией Allure и Graylog
def pytest_runtest_setup(item):
    """Вызывается перед каждым тестом"""
    test_name = item.name
    test_class = item.cls.__name__ if item.cls else None
    test_file = item.fspath.basename if hasattr(item, 'fspath') else None
    
    # Отправляем в Graylog
    graylog = get_graylog()
    if graylog:
        graylog.send_test_start(
            test_name=test_name,
            test_class=test_class,
            test_file=test_file,
            environment=item.config.getoption("--env", default="dev")
        )
    
    # Добавляем метаданные в Allure
    if hasattr(item, 'callspec'):
        params = item.callspec.params if item.callspec else {}
        AllureHelper.set_test_parameters(**params)

def pytest_runtest_makereport(item, call):
    """Вызывается после каждого этапа теста (setup, call, teardown)"""
    if call.when == "call":
        test_name = item.name
        test_class = item.cls.__name__ if item.cls else None
        test_file = item.fspath.basename if hasattr(item, 'fspath') else None
        
        # Определяем статус теста
        if call.excinfo is not None:
            status = "failed"
            error = str(call.excinfo.value)
            traceback_text = None
            try:
                repr_obj = call.excinfo.getrepr(style="short")
                traceback_text = getattr(repr_obj, "text", None) or str(repr_obj)
            except Exception:
                traceback_text = error
            
            logging.error(f"❌ Тест {item.nodeid} завершился с ошибкой: {error}")
            
            # Прикрепляем детали ошибки к Allure
            AllureHelper.attach_error_details(
                call.excinfo.value,
                context={
                    "test_name": test_name,
                    "test_class": test_class,
                    "test_file": test_file
                }
            )
            
            # Отправляем в Graylog
            graylog = get_graylog()
            if graylog:
                graylog.send_error(
                    error_message=error,
                    error_type=type(call.excinfo.value).__name__,
                    test_name=test_name,
                    traceback=traceback_text
                )
        else:
            status = "passed"
            error = None
        
        # Отправляем завершение теста в Graylog
        graylog = get_graylog()
        if graylog and hasattr(call, 'duration'):
            graylog.send_test_finish(
                test_name=test_name,
                status=status,
                duration=call.duration,
                error=error
            )

def pytest_runtest_teardown(item, nextitem):
    """Вызывается после завершения теста"""
    # Можно добавить дополнительную логику очистки
    pass

def pytest_sessionstart(session):
    """Вызывается в начале сессии тестирования"""
    logging.info("=" * 80)
    logging.info("🧪 НАЧАЛО СЕССИИ ТЕСТИРОВАНИЯ")
    logging.info("=" * 80)
    
    # Подсчитываем количество тестов (если доступно)
    try:
        total_tests = len(session.items) if hasattr(session, 'items') else 0
    except AttributeError:
        total_tests = 0
    
    environment = session.config.getoption("--env", default="dev")
    
    # Отправляем в Graylog
    graylog = get_graylog()
    if graylog:
        graylog.send_session_start(
            total_tests=total_tests,
            environment=environment
        )
    
    # Добавляем информацию об окружении в Allure
    if hasattr(session.config, 'option') and hasattr(session.config.option, 'config'):
        # Получаем конфигурацию через фикстуру
        try:
            config_fixture = session.config._get_fixturevalue('config')
            if config_fixture:
                AllureHelper.attach_environment_info(config_fixture)
        except Exception as e:
            logging.warning(f"Не удалось получить конфигурацию для Allure: {str(e)}")

def pytest_sessionfinish(session, exitstatus):
    """Вызывается в конце сессии тестирования"""
    logging.info("=" * 80)
    logging.info(f"[ЗАВЕРШЕНИЕ] СЕССИИ ТЕСТИРОВАНИЯ (код выхода: {exitstatus})")
    logging.info("=" * 80)
    
    # Собираем статистику
    try:
        reporter = session.config.pluginmanager.get_plugin('terminalreporter')
        if reporter and hasattr(reporter, 'stats'):
            stats = reporter.stats
            passed = len(stats.get('passed', []))
            failed = len(stats.get('failed', []))
            skipped = len(stats.get('skipped', []))
        else:
            # Fallback если статистика недоступна
            passed = failed = skipped = 0
    except Exception as e:
        logging.warning(f"Не удалось получить статистику тестов: {str(e)}")
        passed = failed = skipped = 0
    
    total = passed + failed + skipped
    
    # Вычисляем длительность (приблизительно)
    duration = 0
    if hasattr(session, 'startdir'):
        # Можно использовать более точный расчет если нужно
        duration = 0
    
    # Отправляем в Graylog
    graylog = get_graylog()
    if graylog:
        graylog.send_session_finish(
            total_tests=total,
            passed=passed,
            failed=failed,
            skipped=skipped,
            duration=duration
        )
    
    logging.info(f"📊 Статистика: {passed} успешно, {failed} провалено, {skipped} пропущено")