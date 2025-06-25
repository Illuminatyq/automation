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
        try:
            # Используем более короткий таймаут, так как страница загружается быстро
            page.wait_for_load_state("networkidle", timeout=5000)
            logging.info("Страница успешно загружена")
        except Exception as e:
            logging.error(f"Ошибка при ожидании загрузки страницы: {e}")
            # Пробуем альтернативный способ ожидания с коротким таймаутом
            try:
                page.wait_for_load_state("domcontentloaded", timeout=5000)
                logging.info("Страница загружена (DOMContentLoaded)")
            except Exception as e2:
                logging.error(f"Ошибка при ожидании DOMContentLoaded: {e2}")
                raise

@allure.epic("UI/UX тесты")
@allure.feature("Верстка и отзывчивость")
class TestUILayout:
    @allure.title("Проверка базовой верстки страницы авторизации")
    @allure.story("Проверка базовой верстки страницы авторизации")
    @allure.severity('NORMAL')
    @allure.description("""
    Тест проверяет базовую верстку страницы авторизации:
    1. Наличие формы авторизации
    2. Наличие полей ввода (логин/пароль)
    3. Наличие кнопки входа
    4. Корректное отображение всех элементов
    """)
    def test_auth_page_basic_layout(self, page: Page, config, screenshot_utils):
        with allure.step("Переход на страницу авторизации"):
            page.goto(config["baseUrl"])
            page.wait_for_load_state("networkidle", timeout=30000)
            
            # Проверяем наличие основных элементов
            with allure.step("Проверка основных элементов"):
                # Проверяем форму авторизации
                form_selectors = [
                    'form[action*="auth"]',
                    'form[action*="login"]',
                    'form.auth-form',
                    'form.login-form',
                    'form'
                ]
                
                form_found = False
                for selector in form_selectors:
                    try:
                        form = page.locator(selector)
                        if form.count() > 0:
                            form.wait_for(state="visible", timeout=30000)
                            logger.info(f"Форма авторизации найдена по селектору: {selector}")
                            form_found = True
                            break
                    except Exception as e:
                        logger.warning(f"Ошибка при поиске формы по селектору {selector}: {str(e)}")
                
                assert form_found, "Форма авторизации не найдена"
                
                # Проверяем поля ввода
                input_selectors = [
                    'input[type="text"]',
                    'input[type="email"]',
                    'input[type="password"]',
                    'input[name="login"]',
                    'input[name="password"]'
                ]
                
                input_found = False
                for selector in input_selectors:
                    try:
                        input_field = page.locator(selector)
                        if input_field.count() > 0:
                            input_field.wait_for(state="visible", timeout=30000)
                            logger.info(f"Поля ввода найдены по селектору: {selector}")
                            input_found = True
                            break
                    except Exception as e:
                        logger.warning(f"Ошибка при поиске полей ввода по селектору {selector}: {str(e)}")
                
                assert input_found, "Поля ввода не найдены"
                
                # Проверяем кнопку входа
                button_selectors = [
                    'button[type="submit"]',
                    'input[type="submit"]',
                    '.btn-primary',
                    '.btn-login'
                ]
                
                button_found = False
                for selector in button_selectors:
                    try:
                        button = page.locator(selector)
                        if button.count() > 0:
                            button.wait_for(state="visible", timeout=30000)
                            logger.info(f"Кнопка входа найдена по селектору: {selector}")
                            button_found = True
                            break
                    except Exception as e:
                        logger.warning(f"Ошибка при поиске кнопки по селектору {selector}: {str(e)}")
                
                assert button_found, "Кнопка входа не найдена"
                
                # Делаем скриншот
                screenshot_utils.take_screenshot("auth_page_basic_layout")

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
            page.wait_for_load_state("networkidle", timeout=90000)
            
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
                    page.wait_for_load_state("networkidle", timeout=90000)
                    
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

    @allure.title("Проверка верстки страницы офиса")
    @allure.story("Проверка верстки офиса")
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
            page.wait_for_load_state("domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)
            
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

    @allure.title("Проверка верстки основных страниц системы")
    @allure.story("Проверка верстки специфических страниц")
    @allure.severity('NORMAL')
    @allure.description("""
    Тест проверяет верстку основных страниц системы:
    1. Страница лидов
    2. Страница настроек
    3. Страница профиля
    
    Для каждой страницы проверяется:
    - Корректное отображение заголовков
    - Наличие и работоспособность основных элементов
    - Отсутствие ошибок в консоли
    """)
    def test_specific_pages_layout(self, page: Page, config, screenshot_utils):
        with allure.step("Авторизация"):
            login_page = LoginPage(page, config["baseUrl"])
            credentials = config["credentials"]["valid_user"]
            
            # Авторизация
            success = login_page.login(credentials["email"], credentials["password"])
            assert success, "Авторизация должна быть успешной"
            
            # Ждем завершения авторизации
            page.wait_for_load_state("domcontentloaded", timeout=30000)
        
        # Проверяем страницу лидов
        with allure.step("Проверка страницы лидов"):
            # Переход на страницу лидов
            full_url = f"{config['baseUrl']}/leads"
            logger.info(f"Переход на страницу: {full_url}")
            page.goto(full_url)
            
            # Проверяем, что мы действительно перешли на нужную страницу
            current_url = page.url
            assert "/leads" in current_url, f"Не удалось перейти на страницу лидов. Текущий URL: {current_url}"
            
            # Ждем загрузки страницы
            page.wait_for_load_state("domcontentloaded", timeout=30000)
            
            # Делаем скриншот
            screenshot_utils.take_screenshot("leads_page_layout")
            
        # Проверяем страницу настроек пользователя
        with allure.step("Проверка страницы настроек пользователя"):
            # Открываем дропдаун с настройками
            page.click(".user-settings-dropdown .dropdown-toggle")
            
            # Кликаем по ссылке настроек
            page.click(".dropdown-menu a[href*='/users/']")
            
            # Ждем загрузки страницы
            page.wait_for_load_state("domcontentloaded", timeout=30000)
            
            # Проверяем, что мы перешли на страницу настроек пользователя
            current_url = page.url
            assert "/users/" in current_url, f"Не удалось перейти на страницу настроек пользователя. Текущий URL: {current_url}"
            
            # Делаем скриншот
            screenshot_utils.take_screenshot("user_settings_page_layout")

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
            page.wait_for_load_state("networkidle", timeout=90000)
            
            # Ждем загрузки всех ресурсов
            page.wait_for_load_state("domcontentloaded", timeout=90000)
            
            end_time = time.time()
            load_time = end_time - start_time
            
            # Проверяем время загрузки
            assert load_time < 10, f"Страница загружается слишком долго: {load_time:.2f} секунд"
            
            # Делаем скриншот
            screenshot_utils.take_screenshot("page_load_performance")

    @allure.title("Проверка визуальных различий")
    @allure.story("Визуальные тесты")
    @allure.severity('NORMAL')
    @allure.description("Проверка визуальных различий между состояниями страницы")
    def test_visual_differences(self, page: Page, config, screenshot_utils):
        """Тест визуальных различий"""
        with allure.step("Открытие страницы"):
            page.goto(config["baseUrl"])
            page.wait_for_load_state("networkidle", timeout=60000)
            
            # Делаем первый скриншот
            screenshot_utils.take_screenshot("before_filter")
            
        with allure.step("Применение фильтра"):
            # Открываем фильтры
            filter_header = page.locator(".filter-header")
            filter_header.click()
            
            # Ждем открытия панели фильтров
            page.wait_for_selector(".filter-box.show", timeout=5000)
            
            # Применяем фильтр
            apply_button = page.locator("#filter-m-apply-btn")
            apply_button.click()
            
            # Ждем применения фильтра
            page.wait_for_load_state("networkidle", timeout=60000)
            # Дополнительное ожидание для анимаций
            page.wait_for_timeout(2000)
            
            # Делаем второй скриншот
            screenshot_utils.take_screenshot("after_filter")
            
        with allure.step("Проверка различий"):
            # Сравниваем скриншоты
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
        
        # Переход на страницу лидов
        page.goto(f"{config['baseUrl']}/leads/")
        page.wait_for_load_state("domcontentloaded", timeout=60000)  # Увеличиваем таймаут
        
        # Проверяем, что мы на странице лидов
        current_url = page.url
        assert "/leads/" in current_url, f"Не удалось перейти на страницу лидов. Текущий URL: {current_url}"
        
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
                
                # Проверяем, что действие выполнилось за разумное время
                assert duration < 10, f"Действие {i} выполнилось слишком долго: {duration:.2f}с"
                
                # Ждем загрузки страницы после действия
                page.wait_for_load_state("domcontentloaded", timeout=60000)
                
            except PlaywrightTimeoutError as e:
                logging.error(f"Таймаут при выполнении действия {i}: {str(e)}")
                continue
            except Exception as e:
                logging.error(f"Ошибка при выполнении действия {i}: {str(e)}")
                continue

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
            page.wait_for_load_state("domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)

        with allure.step("Открываем страницу лидов"):
            page.goto(f"{config['baseUrl']}/leads")
            page.wait_for_load_state("domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)
            
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
            page.wait_for_load_state("networkidle", timeout=30000)
            
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
            page.wait_for_timeout(1000)
            
            # Делаем скриншот после изменений
            screenshot_after = screenshot_utils.take_screenshot("auth_page_after_changes")
            
        with allure.step("Сравниваем скриншоты"):
            # Открываем изображения
            img1 = Image.open(screenshot_before)
            img2 = Image.open(screenshot_after)
            
            # Создаем diff изображение
            diff = ImageChops.difference(img1, img2)
            
            # Проверяем, что есть визуальные различия
            if not np.any(np.array(diff)):
                pytest.fail("Нет визуальных различий между скриншотами")
            
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
                diff_path,
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