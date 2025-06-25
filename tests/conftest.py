from dotenv import load_dotenv
load_dotenv()

import pytest
import os
import json
import logging
import allure
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from allure_commons.types import AttachmentType
from urllib.parse import urljoin

from config.constants import TEST_RESULTS_DIR, LOGS_DIR, SCREENSHOTS_DIR
from config.viewport_config import VIEWPORT_CONFIGS
from utils.screenshot_utils import ScreenshotUtils

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
        help="Запуск браузера в headless режиме"
    )
    parser.addoption(
        "--browser-type", 
        action="store", 
        default="chromium", 
        choices=["chromium", "firefox", "webkit"],
        help="Тип браузера для тестов"
    )
    parser.addoption(
        "--slow-mo", 
        action="store", 
        type=int, 
        default=0, 
        help="Задержка между действиями в миллисекундах"
    )

def pytest_configure(config):
    """Конфигурация pytest"""
    # Добавляем маркеры
    config.addinivalue_line("markers", "smoke: Smoke тесты")
    config.addinivalue_line("markers", "regression: Регрессионные тесты")
    config.addinivalue_line("markers", "critical: Критически важные тесты")
    config.addinivalue_line("markers", "visual: Тесты визуального регрессивного тестирования")
    config.addinivalue_line("markers", "api: Тесты API интеграции")
    config.addinivalue_line("markers", "auth: Тесты авторизации")
    config.addinivalue_line("markers", "ui: Тесты пользовательского интерфейса")
    
    # Создаем директории для результатов
    for directory in [TEST_RESULTS_DIR, LOGS_DIR, SCREENSHOTS_DIR]:
        directory.mkdir(parents=True, exist_ok=True)

@pytest.fixture(scope="session")
def config(request):
    """Загрузка конфигурации приложения"""
    config_path = Path(__file__).parent.parent / "config" / "config.json"
    
    if not config_path.exists():
        pytest.fail(f"Файл конфигурации не найден: {config_path}")
    
    with open(config_path, "r", encoding="utf-8") as f:
        config_data = json.load(f)

    # Определяем окружение
    env_name = (
        request.config.getoption("--env") or 
        os.environ.get("TEST_ENV") or 
        config_data.get("defaultEnvironment", "dev")
    )
    
    if env_name not in config_data.get("environments", {}):
        available_envs = ", ".join(config_data["environments"].keys())
        pytest.fail(f"Окружение '{env_name}' не найдено. Доступные: {available_envs}")

    # Объединяем общую конфигурацию с конфигурацией окружения
    env_config = config_data["environments"][env_name].copy()
    env_config.update({
        "current_environment": env_name,
        "browser": config_data.get("browser", "chromium"),
        "timeout": config_data.get("timeout", 30),  # Увеличиваем таймаут по умолчанию
        "credentials": config_data.get("credentials", {})
    })
    
    # Получаем API ключ
    api_key = (
        request.config.getoption("--api-key") or 
        os.environ.get("LINER_API_KEY") or 
        os.environ.get(f"{env_name.upper()}_LINER_API_KEY") or
        env_config.get("api_key", "")
    )
    
    if not api_key:
        logging.warning("API ключ не найден. Проверьте следующие источники:")
        logging.warning("1. Параметр командной строки --api-key")
        logging.warning("2. Переменная окружения LINER_API_KEY")
        logging.warning(f"3. Переменная окружения {env_name.upper()}_LINER_API_KEY")
        logging.warning("4. Конфигурация окружения в config.json")
        pytest.skip("API ключ не найден. Тесты API будут пропущены.")
    
    env_config["api_key"] = api_key
    logging.info(f"Используется API ключ: {api_key[:4]}...{api_key[-4:]}")
    
    # Добавляем информацию в Allure
    allure.dynamic.feature(f"Окружение: {env_config['description']}")
    
    return env_config

@pytest.fixture(scope="session")
def browser_context_session(request, config):
    """Создание сессионного контекста браузера"""
    browser_type = request.config.getoption("--browser-type")
    headless = request.config.getoption("--headless") or os.environ.get("HEADLESS", "false").lower() == "true"
    slow_mo = request.config.getoption("--slow-mo")
    
    with sync_playwright() as playwright:
        # Выбираем браузер
        if browser_type == "firefox":
            browser = playwright.firefox.launch(headless=headless, slow_mo=slow_mo)
        elif browser_type == "webkit":
            browser = playwright.webkit.launch(headless=headless, slow_mo=slow_mo)
        else:
            browser = playwright.chromium.launch(headless=headless, slow_mo=slow_mo)
        
        yield browser
        
        browser.close()

@pytest.fixture
def browser_context(browser_context_session):
    """Создание нового контекста для каждого теста (ИЗОЛЯЦИЯ!)"""
    context = browser_context_session.new_context(
        viewport={"width": 1920, "height": 1080},
        locale="ru-RU",
        timezone_id="Europe/Moscow",
        ignore_https_errors=True,
        record_video_dir=str(TEST_RESULTS_DIR / "videos") if os.environ.get("RECORD_VIDEO") == "true" else None
    )
    
    yield context
    
    # Очищаем все данные контекста после каждого теста
    try:
        context.clear_cookies()
        context.clear_permissions()
    except Exception as e:
        logging.warning(f"Ошибка при очистке контекста: {e}")
    finally:
        context.close()

@pytest.fixture
def page(browser_context):
    """Создание новой страницы для каждого теста"""
    page = browser_context.new_page()
    
    # Добавляем логирование консольных сообщений
    def log_console_message(msg):
        logging.info(f"Console [{msg.type}]: {msg.text}")
    
    page.on("console", log_console_message)
    
    # Добавляем обработку ошибок страницы
    def log_page_error(error):
        logging.error(f"Page error: {error}")
    
    page.on("pageerror", log_page_error)
    
    yield page
    
    # Очищаем состояние страницы
    try:
        # Попытка очистить localStorage безопасным способом
        page.evaluate("""
            try {
                if (typeof Storage !== 'undefined' && window.localStorage) {
                    localStorage.clear();
                }
                if (typeof Storage !== 'undefined' && window.sessionStorage) {
                    sessionStorage.clear();
                }
            } catch (e) {
                console.log('Storage clear error:', e);
            }
        """)
    except Exception as e:
        logging.warning(f"Ошибка при очистке storage: {e}")
    finally:
        page.close()

@pytest.fixture
def authenticated_page(page, config):
    """Страница с уже выполненной авторизацией"""
    from pages.login_page import LoginPage
    
    login_page = LoginPage(page, config["baseUrl"])
    creds = config["credentials"]["valid_user"]
    
    # Проверяем, не авторизованы ли мы уже
    if login_page._check_login_result():
        logging.info("Пользователь уже авторизован, пропускаем повторную авторизацию")
    else:
        # Выполняем авторизацию
        success = login_page.login(creds["email"], creds["password"])
        
        if not success:
            login_page.take_error_screenshot("authentication_failed")
            pytest.fail("Не удалось выполнить авторизацию для теста")
    
    # Ждем редиректа
    page.wait_for_load_state("networkidle")
    
    yield page

@pytest.fixture
def screenshot_utils(page):
    """Утилиты для работы со скриншотами"""
    return ScreenshotUtils(page)

@pytest.fixture(scope="function", autouse=True)
def test_info(request):
    """Автоматическое добавление информации о тесте в Allure"""
    test_name = request.node.name
    test_file = request.node.fspath.basename
    
    allure.dynamic.title(test_name.replace("_", " ").title())
    allure.dynamic.label("test_file", test_file)
    allure.dynamic.label("test_method", test_name)

@pytest.fixture(autouse=True)
def log_test_start_end(request):
    """Логирование начала и окончания каждого теста"""
    test_name = request.node.name
    logging.info(f"[НАЧАЛО] Тест: {test_name}")
    
    yield
    
    logging.info(f"[КОНЕЦ] Тест: {test_name}")

@pytest.fixture(autouse=True)
def test_isolation(page, config):
    """Обеспечение изоляции тестов"""
    # Перед тестом - убеждаемся что мы на чистой странице
    try:
        page.goto(config["baseUrl"])
        page.wait_for_load_state("networkidle")
    except Exception as e:
        logging.warning(f"Ошибка при предварительной навигации: {e}")
    
    yield
    
    # После теста - принудительно очищаем все
    try:
        # Очищаем cookies через контекст
        page.context.clear_cookies()
        
        # Очищаем storage безопасным способом
        page.evaluate("""
            try {
                if (typeof Storage !== 'undefined') {
                    if (window.localStorage) localStorage.clear();
                    if (window.sessionStorage) sessionStorage.clear();
                }
            } catch (e) {
                console.log('Post-test storage clear error:', e);
            }
        """)
        
        # Переходим на базовую страницу для сброса состояния
        page.goto(config["baseUrl"])
        
    except Exception as e:
        logging.warning(f"Ошибка при очистке после теста: {e}")

@pytest.fixture(scope="session")
def api_client(config):
    """Фикстура для работы с API"""
    class ApiClient:
        def __init__(self, base_url, api_key):
            self.base_url = base_url
            self.api_key = api_key
            self.session = requests.Session()
            self.session.headers.update({
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'User-Agent': 'python-requests/2.31.0'
            })

        def _make_request(self, method, endpoint, **kwargs):
            url = urljoin(self.base_url, endpoint)
            try:
                response = self.session.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except requests.exceptions.RequestException as e:
                logging.error(f"Ошибка при выполнении {method} запроса к {endpoint}: {e}")
                if hasattr(e.response, 'text'):
                    logging.error(f"Ответ сервера: {e.response.text}")
                raise

        def get(self, endpoint, **kwargs):
            return self._make_request('GET', endpoint, **kwargs)

        def post(self, endpoint, **kwargs):
            """Выполнение POST запроса"""
            return self._make_request('POST', endpoint, **kwargs)

        def put(self, endpoint, **kwargs):
            return self._make_request('PUT', endpoint, **kwargs)

        def delete(self, endpoint, **kwargs):
            return self._make_request('DELETE', endpoint, **kwargs)

    return ApiClient(config['apiUrl'], config['apiKey'])

@pytest.fixture(scope="function")
def browser(config):
    """Фикстура для работы с браузером (только для UI тестов)"""
    if not hasattr(browser, 'driver'):
        chrome_options = Options()
        if config.get('headless', False):
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        
        service = Service(ChromeDriverManager().install())
        browser.driver = webdriver.Chrome(service=service, options=chrome_options)
        browser.driver.implicitly_wait(10)
        browser.wait = WebDriverWait(browser.driver, 10)
        
        logging.info("Браузер успешно запущен")
    
    yield browser.driver
    
    if hasattr(browser, 'driver'):
        browser.driver.quit()
        delattr(browser, 'driver')
        logging.info("Браузер успешно закрыт")

@pytest.fixture(scope="function")
def take_screenshot_on_failure(browser, request):
    """Фикстура для создания скриншота при падении теста"""
    yield
    
    if request.node.rep_call.failed:
        try:
            screenshot = browser.get_screenshot_as_png()
            allure.attach(
                screenshot,
                name="failure_screenshot",
                attachment_type=AttachmentType.PNG
            )
            logging.info("Скриншот ошибки сохранен")
        except Exception as e:
            logging.error(f"Не удалось сохранить скриншот: {e}")

# Хуки pytest
def pytest_runtest_makereport(item, call):
    """Создание отчета о выполнении теста"""
    if call.when == "call":
        if call.excinfo is not None:
            # Тест упал, добавляем дополнительную информацию
            logging.error(f"❌ Тест {item.nodeid} завершился с ошибкой: {call.excinfo.value}")

def pytest_sessionstart(session):
    """Действия в начале сессии тестирования"""
    logging.info("=" * 80)
    logging.info("🧪 НАЧАЛО СЕССИИ ТЕСТИРОВАНИЯ")
    logging.info("=" * 80)

def pytest_sessionfinish(session, exitstatus):
    """Действия после завершения сессии тестирования"""
    logging.info("=" * 80)
    logging.info(f"[ЗАВЕРШЕНИЕ] СЕССИИ ТЕСТИРОВАНИЯ (код выхода: {exitstatus})")
    logging.info("=" * 80)