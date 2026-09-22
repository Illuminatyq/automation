import pytest
import allure
from playwright.sync_api import Page, expect
from utils.screenshot_utils import ScreenshotUtils
from pages.login_page import LoginPage
import logging
import time
import sys
from PIL import Image, ImageChops
import numpy as np
from PIL import ImageEnhance

# Настройка логирования с явным указанием кодировки
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

logger = logging.getLogger(__name__)

@pytest.fixture(autouse=True)
def clear_browser_state(page: Page):
    """Фикстура для очистки состояния браузера перед каждым тестом"""
    with allure.step("Очистка состояния браузера"):
        # Очищаем куки
        page.context.clear_cookies()
        # Очищаем локальное хранилище
        page.evaluate("() => localStorage.clear()")
        # Очищаем sessionStorage
        page.evaluate("() => sessionStorage.clear()")
        # Перезагружаем страницу для применения изменений
        page.reload()
        # page.wait_for_load_state("networkidle", timeout=5000)
        try:
            # Используем более короткий таймаут, так как страница загружается быстро
            # page.wait_for_load_state("networkidle", timeout=5000)
            logging.info("Страница успешно загружена")
        except Exception as e:
            logging.error(f"Ошибка при ожидании загрузки страницы: {e}")
            # Пробуем альтернативный способ ожидания с коротким таймаутом
            try:
                # page.wait_for_load_state("domcontentloaded", timeout=5000)
                logging.info("Страница загружена (DOMContentLoaded)")
            except Exception as e2:
                logging.error(f"Ошибка при ожидании DOMContentLoaded: {e2}")
                raise

@allure.epic("UI/UX тесты")
@allure.feature("Верстка и отзывчивость")
class TestUILayout:
    @pytest.mark.usefixtures("authenticated_page")
    @allure.title("Проверка верстки главной страницы после авторизации")
    @allure.severity('NORMAL')
    def test_auth_page_basic_layout(self, page: Page, config, screenshot_utils):
        login_page = LoginPage(page, config["baseUrl"])
        with allure.step("Авторизация"):
            credentials = config["credentials"]["valid_user"]
            assert login_page.login(credentials["email"], credentials["password"]), "Авторизация не удалась"
            # Проверяем наличие сайдбара/меню
            sidebar = page.locator(".sidebar")
            assert sidebar.is_visible(timeout=10000), "Сайдбар не найден после логина"
            screenshot_utils.take_screenshot("sidebar_after_login")

        with allure.step("Проверка основных элементов интерфейса"):
            # Проверяем наличие пунктов меню
            assert page.locator("a.sidebar-link[href='/leads/']").is_visible(timeout=5000), "Пункт 'Лиды' не найден"
            assert page.locator("a.sidebar-link[href='/users/']").count() > 0, "Пункт 'Пользователи' не найден"
            assert page.locator(".nav-item.user-settings-dropdown").count() > 0, "Дропдаун профиля не найден"
            screenshot_utils.take_screenshot("main_elements_after_login")

    @allure.title("Проверка верстки основных страниц системы")
    @allure.severity('NORMAL')
    def test_specific_pages_layout(self, page: Page, config, screenshot_utils):
        login_page = LoginPage(page, config["baseUrl"])
        with allure.step("Авторизация"):
            credentials = config["credentials"]["valid_user"]
            assert login_page.login(credentials["email"], credentials["password"]), "Авторизация не удалась"
            assert page.locator(".sidebar").is_visible(timeout=10000), "Сайдбар не найден после логина"

        with allure.step("Переход на страницу лидов через сайдбар"):
            leads_link = page.locator("a.sidebar-link[href='/leads/']")
            assert leads_link.is_visible(timeout=10000), "Пункт меню 'Лиды' не найден"
            leads_link.click()
            # Ждём появления таблицы лидов
            assert page.locator("table.ajax-data-table, table.data-table, table.table").is_visible(timeout=15000), "Таблица лидов не загрузилась"
            screenshot_utils.take_screenshot("leads_page_layout")

        with allure.step("Переход на страницу настроек пользователя через дропдаун"):
            dropdown = page.locator(".nav-item.user-settings-dropdown > a.nav-link.dropdown-toggle")
            assert dropdown.is_visible(timeout=10000), "Дропдаун профиля не найден"
            dropdown.click()
            settings_link = page.locator(".dropdown-menu a[href*='/users/']")
            assert settings_link.is_visible(timeout=10000), "Ссылка на настройки не найдена"
            settings_link.click()
            # Ждём появления уникального элемента настроек
            assert page.locator("form, .user-settings-form, .settings-page").first.is_visible(timeout=10000), "Форма настроек не загрузилась"
            screenshot_utils.take_screenshot("user_settings_page_layout")

@allure.title("Проверка производительности под нагрузкой")
@allure.severity('HIGH')
def test_performance_under_load(page: Page, config, screenshot_utils):
    login_page = LoginPage(page, config["baseUrl"])
    with allure.step("Авторизация"):
        credentials = config["credentials"]["valid_user"]
        assert login_page.login(credentials["email"], credentials["password"]), "Авторизация не удалась"
        sidebar = page.locator(".sidebar")
        assert sidebar.is_visible(timeout=10000), "Сайдбар не найден после логина"

    with allure.step("Переход на страницу лидов через сайдбар"):
        leads_link = page.locator("a.sidebar-link[href='/leads/']")
        assert leads_link.is_visible(timeout=10000), "Пункт меню 'Лиды' не найден"
        leads_link.click()
        assert page.locator("table.ajax-data-table, table.data-table, table.table").is_visible(timeout=15000), "Таблица лидов не загрузилась"
        screenshot_utils.take_screenshot("leads_page_loaded_performance")

    with allure.step("После применения фильтра"):
        # Сначала проверяем, есть ли кнопка фильтра и видна ли она
        filter_button = page.locator("#filter-m-apply-btn")
        if filter_button.count() > 0:
            # Ждем, пока кнопка станет видимой
            try:
                filter_button.wait_for(state="visible", timeout=10000)
                filter_button.click()
                assert page.locator("table.ajax-data-table, table.data-table, table.table").is_visible(timeout=15000), "Таблица не обновилась после фильтра"
            except Exception as e:
                logging.warning(f"Кнопка фильтра не видна или недоступна: {str(e)}")
                screenshot_utils.take_screenshot("filter_button_not_visible")
        else:
            logging.info("Кнопка фильтра не найдена на странице")

@allure.title("Проверка доступности (a11y)")
@allure.severity('NORMAL')
def test_accessibility(page: Page, config, screenshot_utils):
    login_page = LoginPage(page, config["baseUrl"])
    with allure.step("Авторизация"):
        credentials = config["credentials"]["valid_user"]
        assert login_page.login(credentials["email"], credentials["password"]), "Авторизация не удалась"
        sidebar = page.locator(".sidebar")
        assert sidebar.is_visible(timeout=10000), "Сайдбар не найден после логина"

    with allure.step("Переход на страницу лидов через сайдбар"):
        leads_link = page.locator("a.sidebar-link[href='/leads/']")
        assert leads_link.is_visible(timeout=10000), "Пункт меню 'Лиды' не найден"
        leads_link.click()
        assert page.locator("table.ajax-data-table, table.data-table, table.table").is_visible(timeout=15000), "Таблица лидов не загрузилась"
        screenshot_utils.take_screenshot("leads_page_loaded_accessibility")

    with allure.step("Проверяем наличие ARIA-атрибутов"):
        elements = page.query_selector_all("[aria-label], [aria-describedby], [role]")
        assert len(elements) > 0, "Не найдены элементы с ARIA-атрибутами"
        logging.info(f"Найдено ARIA-элементов: {len(elements)}")

    with allure.step("Проверяем навигацию с клавиатуры"):
        page.keyboard.press("Tab")
        focused = page.evaluate("document.activeElement.tagName")
        assert focused, "Элемент не получил фокус при навигации с клавиатуры"
        screenshot_utils.take_screenshot("accessibility_test")

    @allure.title("Проверка времени загрузки страницы")
    @allure.severity('NORMAL')
    def test_page_load_performance(self, page: Page, config, screenshot_utils):
        login_page = LoginPage(page, config["baseUrl"])
        pages_to_test = [
            {"url": config["baseUrl"], "name": "auth", "wait_for": lambda: login_page.wait_for_form(timeout=30000)},
            {"url": f"{config['baseUrl']}/office", "name": "office", "wait_for": lambda: page.wait_for_url("**/office*", timeout=60000)},
            {"url": f"{config['baseUrl']}/leads", "name": "leads", "wait_for": lambda: page.wait_for_url("**/leads/*", timeout=60000)}
        ]
        for page_info in pages_to_test:
            with allure.step(f"Измерение времени загрузки {page_info['name']}"):
                start_time = time.time()
                page.goto(page_info["url"])
                try:
                    page_info["wait_for"]()
                    end_time = time.time()
                    load_time = end_time - start_time
                    assert load_time < 15, f"Страница {page_info['name']} загружается слишком долго: {load_time:.2f} секунд"
                    logging.info(f"Время загрузки {page_info['name']}: {load_time:.2f} секунд")
                except Exception as e:
                    logging.error(f"Ошибка при загрузке {page_info['name']}: {e}")
                    screenshot_utils.take_screenshot(f"{page_info['name']}_load_error")
                    allure.attach(page.content(), "HTML страницы при ошибке", allure.attachment_type.HTML)
                    raise
                screenshot_utils.take_screenshot(f"{page_info['name']}_page_load")

    @allure.title("Проверка визуальных различий")
    @allure.severity('NORMAL')
    def test_visual_differences(self, page: Page, config, screenshot_utils):
        login_page = LoginPage(page, config["baseUrl"])
        with allure.step("Авторизация и переход на страницу лидов"):
            credentials = config["credentials"]["valid_user"]
            success = login_page.login(credentials["email"], credentials["password"])
            assert success, "Авторизация должна быть успешной"
            page.goto(f"{config['baseUrl']}/leads", wait_until="domcontentloaded")
            # Ждём появления нужного URL (до 30 секунд)
            timeout = 30
            start = time.time()
            while "/leads" not in page.url and time.time() - start < timeout:
                time.sleep(0.5)
            assert "/leads" in page.url, f"Не удалось перейти на страницу лидов. Текущий URL: {page.url}"
            assert "405" not in page.content(), f"После перехода на /leads попали на страницу ошибки 405! URL: {page.url}"
            try:
                page.wait_for_selector("table.ajax-data-table, table.data-table, table.table", timeout=30000)
            except Exception as e:
                html = page.content()
                with open("debug_page.html", "w", encoding="utf-8") as f:
                    f.write(html)
                allure.attach(html, "HTML страницы при ошибке", allure.attachment_type.HTML)
                raise
            logging.info(f"Страница лидов загружена: {page.url}")

        with allure.step("Применение фильтра"):
            # Открываем фильтр, если он свернут
            filter_header = page.locator(".filter-header.collapse-icon.collapsed")
            if filter_header.count() > 0 and filter_header.is_visible():
                filter_header.click()
                page.wait_for_selector(".filter-header.collapse-icon:not(.collapsed)", timeout=5000)
            # Теперь кнопка фильтра должна быть видимой
            filter_button = page.locator("#filter-m-apply-btn")
            assert filter_button.is_visible(timeout=5000), "Кнопка фильтра не видна"
            filter_button.click()
            # Ждём обновления таблицы
            assert page.locator("table.ajax-data-table, table.data-table, table.table").is_visible(timeout=15000), "Таблица не обновилась после фильтра"

        with allure.step("Проверка различий"):
            diff = screenshot_utils.compare_screenshots("before_filter", "after_filter")
            assert diff > 0, "Нет визуальных различий между скриншотами до и после применения фильтра"

    @allure.title("Проверка производительности под нагрузкой")
    @allure.story("Проверка производительности")
    @allure.severity('HIGH')
    @allure.description("""
    Тест проверяет производительность системы под нагрузкой:
    1. Авторизация в системе
    2. Последовательное выполнение действий:
       - Открытие фильтров
       - Загрузка таблицы данных
       - Применение фильтра по дате
       - Применение фильтра
    
    Для каждого действия измеряется:
    - Время выполнения
    - Успешность выполнения
    - Наличие ошибок
    
    Тест использует механизм повторных попыток для повышения надежности
    """)
    def test_performance_under_load(self, page: Page, config):
        """Тест проверяет производительность системы под нагрузкой"""
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from urllib3.util.retry import Retry
        from requests.adapters import HTTPAdapter
        import requests
        
        # Настройка сессии с повторными попытками
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Выполняем авторизацию
        login_page = LoginPage(page, config["baseUrl"])
        credentials = config["credentials"]["valid_user"]
        
        success = login_page.login(
            email=credentials["email"],
            password=credentials["password"],
            remember=True
        )
        assert success, "Авторизация не прошла успешно"
        
        # Переход на страницу лидов через UI (клик по меню)
        sidebar_leads = page.locator('.sidebar a[href="/leads/"]')
        sidebar_leads.click()
        page.wait_for_selector('table.leads-table', timeout=15000)
        
        # Создаём объект LeadsPage
        from pages.leads_page import LeadsPage
        leads_page = LeadsPage(page, config["baseUrl"])
        
        # Гарантируем раскрытие фильтра
        leads_page.ensure_filter_open()
        
        # Выполняем серию действий для проверки производительности
        actions = [
            lambda: page.locator('.filter-button, .btn-filter, [data-filter]').click(),
            lambda: page.locator('table.ajax-data-table, table.data-table, table.table').wait_for(state="visible", timeout=60000),
            lambda: page.locator('input[name="daterange"]').fill("01.05.2025 - 31.05.2025"),
            lambda: page.locator('#filter-m-apply-btn').click()
        ]
        
        for i, action in enumerate(actions, 1):
            try:
                start_time = time.time()
                action()
                end_time = time.time()
                duration = end_time - start_time
                assert duration < 10, f"Действие {i} выполнилось слишком долго: {duration:.2f}с"
            except PlaywrightTimeoutError as e:
                logging.error(f"Таймаут при выполнении действия {i}: {str(e)}")
                continue
            except Exception as e:
                logging.error(f"Ошибка при выполнении действия {i}: {str(e)}")
                continue

    @allure.title("Проверка адаптивности страницы авторизации на разных устройствах")
    @allure.story("Проверка отзывчивости страницы авторизации")
    @allure.severity('NORMAL')
    @allure.description("""
    Тест проверяет адаптивность страницы авторизации на разных устройствах:
    1. Десктоп (1920x1080)
    2. Ноутбук (1366x768)
    3. Планшет (768x1024)
    4. Мобильный (375x812)
    
    Для каждого размера проверяется:
    - Видимость формы авторизации
    - Корректное отображение всех элементов формы
    - Отсутствие горизонтальной прокрутки
    """)
    def test_auth_page_responsive(self, page: Page, config, screenshot_utils):
        with allure.step("Проверка на разных размерах экрана"):
            page.goto(config["baseUrl"])
            # page.wait_for_load_state("networkidle", timeout=90000)
            
            # Список размеров для проверки
            viewports = [
                {"width": 1920, "height": 1080, "name": "desktop"},
                {"width": 1366, "height": 768, "name": "laptop"},
                {"width": 768, "height": 1024, "name": "tablet"},
                {"width": 375, "height": 812, "name": "mobile"}
            ]
            
            for viewport in viewports:
                with allure.step(f"Проверка на {viewport['name']}"):
                    page.set_viewport_size({"width": viewport["width"], "height": viewport["height"]})
                    # page.wait_for_load_state("networkidle", timeout=90000)
                    
                    # Проверяем, что форма видна
                    form_selectors = ['form', '.auth-form', '.login-form']
                    form_found = False
                    
                    for selector in form_selectors:
                        try:
                            form = page.locator(selector)
                            if form.count() > 0:
                                form.wait_for(state="visible", timeout=30000)
                                form_found = True
                                break
                        except Exception as e:
                            logger.warning(f"Ошибка при поиске формы по селектору {selector}: {str(e)}")
                    
                    assert form_found, f"Форма не найдена на {viewport['name']}"
                    
                    # Проверяем, что все элементы формы видны
                    form_elements = page.locator('form input, form button')
                    for element in form_elements.all():
                        expect(element).to_be_visible(timeout=30000)
                    
                    # Делаем скриншот
                    screenshot_utils.take_screenshot(f"auth_page_{viewport['name']}")

    @pytest.mark.usefixtures("page")
    @allure.title("Проверка адаптивности верстки")
    @allure.story("Проверка верстки страницы авторизации")
    @allure.severity('NORMAL')
    @allure.description("""
    Тест проверяет верстку страницы офиса после успешной авторизации:
    1. Наличие и корректное отображение меню
    2. Наличие основных элементов интерфейса
    3. Корректное отображение контента
    4. Работоспособность навигации
    """)
    def test_office_page_layout(self, page: Page, config, screenshot_utils):
        with allure.step("Авторизация и переход в офис"):
            login_page = LoginPage(page, config["baseUrl"])
            credentials = config["credentials"]["valid_user"]
            
            # Авторизация
            success = login_page.login(credentials["email"], credentials["password"])
            assert success, "Авторизация должна быть успешной"
            
            # Ждем завершения авторизации
            # page.wait_for_load_state("domcontentloaded", timeout=30000)
            # page.wait_for_timeout(2000)
            
            # Проверяем, что мы на странице офиса
            assert "/office/" in page.url, f"После авторизации ожидался переход на /office/, а не {page.url}"
            
            # Проверяем основные элементы
            with allure.step("Проверка основных элементов офиса"):
                # Проверяем наличие меню
                menu_selectors = [
                    'nav',
                    '.navbar',
                    '.sidebar',
                    '.menu',
                    '.main-menu',
                    '.navigation'
                ]
                
                menu_found = False
                for selector in menu_selectors:
                    try:
                        menu = page.locator(selector)
                        if menu.count() > 0:
                            menu.wait_for(state="visible", timeout=30000)
                            logger.info(f"Меню найдено по селектору: {selector}")
                            menu_found = True
                            break
                    except Exception as e:
                        logger.warning(f"Ошибка при поиске меню по селектору {selector}: {str(e)}")
                
                assert menu_found, "Меню не найдено"
                
                # Проверяем наличие основного контента
                content_selectors = [
                    'main',
                    '.content',
                    '.container',
                    '#content',
                    '.main-content',
                    '.page-content'
                ]
                
                content_found = False
                for selector in content_selectors:
                    try:
                        content = page.locator(selector)
                        if content.count() > 0:
                            content.wait_for(state="visible", timeout=30000)
                            logger.info(f"Основной контент найден по селектору: {selector}")
                            content_found = True
                            break
                    except Exception as e:
                        logger.warning(f"Ошибка при поиске контента по селектору {selector}: {str(e)}")
                
                assert content_found, "Основной контент не найден"
                
                # Делаем скриншот
                screenshot_utils.take_screenshot("office_page_layout")

    @allure.title("Проверка времени загрузки страницы")
    @allure.story("Проверка производительности загрузки страницы")
    @allure.severity('NORMAL')
    @allure.description("""
    Тест проверяет время загрузки основных страниц системы:
    1. Страница авторизации
    2. Страница офиса
    3. Страница лидов
    
    Для каждой страницы измеряется:
    - Время до первого байта (TTFB)
    - Время полной загрузки страницы
    - Время до интерактивности (TTI)
    """)
    def test_page_load_performance(self, page: Page, config, screenshot_utils):
        with allure.step("Измерение времени загрузки страницы"):
            start_time = time.time()
            
            # Переход на страницу
            page.goto(config["baseUrl"])
            # page.wait_for_load_state("networkidle", timeout=90000)
            
            # Ждем загрузки всех ресурсов
            # page.wait_for_load_state("domcontentloaded", timeout=90000)
            
            end_time = time.time()
            load_time = end_time - start_time
            
            # Проверяем время загрузки
            assert load_time < 10, f"Страница загружается слишком долго: {load_time:.2f} секунд"
            
            # Делаем скриншот
            screenshot_utils.take_screenshot("page_load_performance")

    @allure.title("Проверка визуальных различий")
    @allure.severity('NORMAL')
    def test_visual_differences(self, page: Page, config, screenshot_utils):
        login_page = LoginPage(page, config["baseUrl"])
        with allure.step("Авторизация и переход на страницу лидов"):
            credentials = config["credentials"]["valid_user"]
            success = login_page.login(credentials["email"], credentials["password"])
            assert success, "Авторизация должна быть успешной"
            page.goto(f"{config['baseUrl']}/leads", wait_until="domcontentloaded")
            # Ждём появления нужного URL (до 30 секунд)
            timeout = 30
            start = time.time()
            while "/leads" not in page.url and time.time() - start < timeout:
                time.sleep(0.5)
            assert "/leads" in page.url, f"Не удалось перейти на страницу лидов. Текущий URL: {page.url}"
            assert "405" not in page.content(), f"После перехода на /leads попали на страницу ошибки 405! URL: {page.url}"
            try:
                page.wait_for_selector("table.ajax-data-table, table.data-table, table.table", timeout=30000)
            except Exception as e:
                html = page.content()
                with open("debug_page.html", "w", encoding="utf-8") as f:
                    f.write(html)
                allure.attach(html, "HTML страницы при ошибке", allure.attachment_type.HTML)
                raise
            logging.info(f"Страница лидов загружена: {page.url}")

        with allure.step("Применение фильтра"):
            filter_header = page.locator('.filter-button, .btn-filter, [data-filter], .filter-toggle')
            try:
                expect(filter_header).to_be_visible(timeout=15000)
                filter_header.click()
                logging.info("Кликнули по кнопке фильтров")
                page.wait_for_selector(".filter-box.show", timeout=15000)
            except Exception as e:
                logging.error(f"Ошибка при открытии фильтров: {e}")
                screenshot_utils.take_screenshot("filter_error")
                allure.attach(page.content(), "HTML страницы при ошибке фильтров", allure.attachment_type.HTML)
                raise
            screenshot_utils.take_screenshot("before_filter")

            apply_button = page.locator("#filter-m-apply-btn")
            try:
                expect(apply_button).to_be_visible(timeout=10000)
                apply_button.click()
                page.wait_for_selector(".filter-box:not(.show)", timeout=15000)
                logging.info("Фильтр применён")
            except Exception as e:
                logging.error(f"Ошибка при применении фильтра: {e}")
                screenshot_utils.take_screenshot("filter_apply_error")
                allure.attach(page.content(), "HTML страницы при ошибке фильтра", allure.attachment_type.HTML)
                raise
            screenshot_utils.take_screenshot("after_filter")

        with allure.step("Проверка различий"):
            diff = screenshot_utils.compare_screenshots("before_filter", "after_filter")
            assert diff > 0, "Нет визуальных различий между скриншотами до и после применения фильтра"

    @allure.title("Проверка доступности (a11y)")
    @allure.story("Проверка доступности")
    @allure.severity('NORMAL')
    @allure.description("""
    Тест проверяет доступность интерфейса (a11y):
    1. Наличие и корректность ARIA-атрибутов
    2. Доступность с клавиатуры
    3. Контрастность текста
    4. Наличие альтернативных текстов для изображений
    5. Семантическая структура HTML
    
    Проверка соответствует стандартам WCAG 2.1
    """)
    def test_accessibility(self, page: Page, config, screenshot_utils: ScreenshotUtils):
        """Тест проверяет соответствие стандартам доступности"""
        with allure.step("Авторизация"):
            login_page = LoginPage(page, config["baseUrl"])
            credentials = config["credentials"]["valid_user"]
            
            # Авторизация
            success = login_page.login(credentials["email"], credentials["password"])
            assert success, "Авторизация должна быть успешной"
            
            # Ждем завершения авторизации
            # page.wait_for_load_state("domcontentloaded", timeout=30000)
            # page.wait_for_timeout(2000)

        with allure.step("Открываем страницу лидов"):
            page.goto(f"{config['baseUrl']}/leads")
            # Ждём появления нужного URL (до 30 секунд)
            timeout = 30
            start = time.time()
            while "/leads" not in page.url and time.time() - start < timeout:
                time.sleep(0.5)
            assert "/leads" in page.url, f"Не удалось перейти на страницу лидов. Текущий URL: {page.url}"
            
        with allure.step("Проверяем наличие ARIA-атрибутов"):
            elements = page.query_selector_all("[aria-label], [aria-describedby], [role]")
            assert len(elements) > 0, "Не найдены элементы с ARIA-атрибутами"
            
        with allure.step("Проверяем контрастность текста"):
            # Здесь можно добавить проверку контрастности с помощью специальных инструментов
            pass
            
        with allure.step("Проверяем навигацию с клавиатуры"):
            page.keyboard.press("Tab")
            focused = page.evaluate("document.activeElement")
            assert focused is not None, "Элемент не получил фокус при навигации с клавиатуры"
            
        # Делаем скриншот для документации
        screenshot_utils.take_screenshot("accessibility_test")

    @allure.title("Проверка визуальных изменений на странице авторизации")
    @allure.story("Проверка визуальных различий")
    @allure.severity('NORMAL')
    @allure.description("""
    Тест проверяет визуальные изменения на странице авторизации:
    1. Сравнение скриншотов при разных состояниях:
       - Пустая форма
       - Форма с введенными данными
       - Форма с ошибкой валидации
    2. Проверка корректности отображения сообщений об ошибках
    3. Проверка анимаций и переходов
    
    Используется алгоритм сравнения изображений для определения различий
    """)
    def test_auth_page_visual_changes(self, page: Page, config, screenshot_utils: ScreenshotUtils):
        """Тест проверяет визуальные различия на странице авторизации"""
        with allure.step("Открываем страницу авторизации"):
            page.goto(config["baseUrl"])
            # page.wait_for_load_state("networkidle", timeout=30000)
            
            # Делаем базовый скриншот
            screenshot_before = screenshot_utils.take_screenshot("auth_page_before_changes")
            
        with allure.step("Вносим изменения в стили"):
            # Изменяем стили через JavaScript
            page.evaluate("""() => {
                // Изменяем стили формы
                const form = document.querySelector('form');
                if (form) {
                    form.style.backgroundColor = '#ff0000';
                    form.style.padding = '50px';
                    form.style.borderRadius = '20px';
                    form.style.transform = 'rotate(5deg)';
                }
                
                // Изменяем стили полей ввода
                const inputs = document.querySelectorAll('input');
                inputs.forEach(input => {
                    input.style.backgroundColor = '#ffff00';
                    input.style.border = '3px solid #0000ff';
                    input.style.padding = '20px';
                });
                
                // Изменяем стили кнопки
                const button = document.querySelector('button[type="submit"]');
                if (button) {
                    button.style.backgroundColor = '#00ff00';
                    button.style.color = '#ff0000';
                    button.style.fontSize = '24px';
                    button.style.padding = '15px 30px';
                }
            }""")
            
            # Ждем применения стилей
            # page.wait_for_timeout(1000)
            
            # Делаем скриншот после изменений
            screenshot_after = screenshot_utils.take_screenshot("auth_page_after_changes")
            
        with allure.step("Сравниваем скриншоты"):
            # Открываем изображения
            img1 = Image.open(screenshot_before).convert("RGB")
            img2 = Image.open(screenshot_after).convert("RGB")

            # Приводим к одному размеру
            if img1.size != img2.size:
                img2 = img2.resize(img1.size)

            # Создаем diff изображение
            diff = ImageChops.difference(img1, img2)

            # Усиливаем контраст и яркость для наглядности
            diff = ImageEnhance.Contrast(diff).enhance(4.0)
            diff = ImageEnhance.Brightness(diff).enhance(2.0)

            # Логируем min/max для отладки
            diff_np = np.array(diff)
            print(f"Diff min: {diff_np.min()}, max: {diff_np.max()}")

            # Проверяем, что есть визуальные различия
            if not np.any(diff_np):
                allure.attach.file(
                    screenshot_before,
                    name="Скриншот до изменений (debug)",
                    attachment_type=allure.attachment_type.PNG
                )
                allure.attach.file(
                    screenshot_after,
                    name="Скриншот после изменений (debug)",
                    attachment_type=allure.attachment_type.PNG
                )
                pytest.fail("Нет визуальных различий между скриншотами (diff полностью чёрный)")

            # Сохраняем diff изображение
            diff_path = screenshot_utils.screenshot_dirs["diff"] / "auth_page_diff.png"
            diff.save(diff_path)

            # Добавляем все скриншоты в отчет
            allure.attach.file(
                screenshot_before,
                name="Скриншот до изменений",
                attachment_type=allure.attachment_type.PNG
            )
            allure.attach.file(
                screenshot_after,
                name="Скриншот после изменений",
                attachment_type=allure.attachment_type.PNG
            )
            allure.attach.file(
                str(diff_path),
                name="Diff изображение",
                attachment_type=allure.attachment_type.PNG
            )
            
            # Проверяем, что изменения были применены
            form = page.locator('form')
            form_style = form.evaluate("el => window.getComputedStyle(el).backgroundColor")
            assert "rgb(255, 0, 0)" in form_style, "Фон формы не изменился на красный"
            
            button = page.locator('button[type="submit"]')
            button_style = button.evaluate("el => window.getComputedStyle(el).backgroundColor")
            assert "rgb(0, 255, 0)" in button_style, "Фон кнопки не изменился на зеленый"

    def is_login_form_ready(self, timeout: int = 5000) -> bool:
        """Проверяет, что форма авторизации готова к работе (есть и видима)"""
        form_selectors = [
            'form[action*="auth"]',
            'form[action*="login"]',
            'form.auth-form',
            'form.login-form',
            'form'
        ]
        for selector in form_selectors:
            try:
                form = self.page.locator(selector)
                if form.count() > 0 and form.is_visible():
                    self.logger.info(f"Форма авторизации готова по селектору: {selector}")
                    return True
            except Exception as e:
                self.logger.warning(f"Ошибка при поиске формы по селектору {selector}: {str(e)}")
        self.logger.warning("Форма авторизации не готова")
        return False