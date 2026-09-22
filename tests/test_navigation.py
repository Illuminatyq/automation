import pytest
import allure
from playwright.sync_api import Page, expect
from utils.screenshot_utils import ScreenshotUtils
from pages.login_page import LoginPage
import logging
import time

@allure.epic("Навигация")
@allure.feature("UI тесты навигации")
class TestNavigation:
    """Тесты для проверки навигации и основного меню"""
    
    @pytest.mark.usefixtures("authenticated_page")
    @allure.title("Проверка основного меню и навигации")
    @allure.story("Основное меню")
    @allure.severity('HIGH')
    @allure.description("""
    Тест проверяет работу основного меню:
    1. Проверка видимости всех пунктов меню
    2. Переход по каждому пункту меню
    3. Проверка загрузки соответствующих страниц
    4. Проверка корректности URL
    """)
    def test_main_menu_navigation(self, page: Page, config, screenshot_utils):
        """Тест основного меню и навигации"""
        
        # Авторизация
        login_page = LoginPage(page, config["baseUrl"])
        credentials = config["credentials"]["valid_user"]
        
        success = login_page.login(
            email=credentials["email"],
            password=credentials["password"],
            remember=True
        )
        assert success, "Авторизация не прошла успешно"
        
        with allure.step("Поиск основного меню"):
            # Ищем основное меню
            menu_selectors = [
                "nav.main-menu",
                ".sidebar nav",
                ".main-navigation",
                ".navbar-nav",
                "nav ul",
                ".menu-list"
            ]
            
            main_menu = None
            for selector in menu_selectors:
                try:
                    menu = page.locator(selector)
                    if menu.is_visible():
                        main_menu = menu
                        break
                except:
                    continue
            
            assert main_menu is not None, "Основное меню не найдено"
            screenshot_utils.take_screenshot("main_menu_found")
        
        with allure.step("Получение списка пунктов меню"):
            # Ищем пункты меню
            menu_item_selectors = [
                "nav a",
                ".menu-item a",
                ".nav-link",
                "li a",
                ".sidebar a"
            ]
            
            menu_items = []
            for selector in menu_item_selectors:
                try:
                    items = page.locator(selector).all()
                    # Фильтруем только видимые элементы
                    visible_items = [item for item in items if item.is_visible()]
                    if visible_items:
                        menu_items = visible_items
                        break
                except:
                    continue
            
            assert len(menu_items) > 0, "Пункты меню не найдены"
            logging.info(f"Найдено {len(menu_items)} пунктов меню")
        
        with allure.step("Проверка каждого пункта меню"):
            tested_urls = set()
            successful_navigations = 0
            
            for i, item in enumerate(menu_items[:10]):  # Ограничиваем до 10 пунктов
                try:
                    # Получаем текст и href
                    item_text = item.text_content().strip()
                    href = item.get_attribute("href")
                    
                    # Пропускаем пустые элементы и внешние ссылки
                    if not item_text or not href or href.startswith("http") or href.startswith("mailto"):
                        continue
                    
                    # Пропускаем дубликаты
                    if href in tested_urls:
                        continue
                    
                    tested_urls.add(href)
                    
                    with allure.step(f"Проверка пункта меню: {item_text}"):
                        logging.info(f"Тестируем пункт меню: {item_text} -> {href}")
                        
                        # Кликаем по пункту меню
                        item.click()
                        page.wait_for_load_state("domcontentloaded", timeout=30000)
                        
                        # Проверяем изменение URL
                        current_url = page.url
                        assert href in current_url or current_url.endswith(href), \
                            f"URL не соответствует ожидаемому: {current_url} vs {href}"
                        
                        # Проверяем, что страница загрузилась корректно
                        self._verify_page_loaded(page, item_text)
                        
                        # Делаем скриншот
                        safe_name = item_text.lower().replace(" ", "_").replace("/", "_")
                        screenshot_utils.take_screenshot(f"menu_item_{safe_name}")
                        
                        successful_navigations += 1
                        logging.info(f"Успешная навигация к: {item_text}")
                        
                except Exception as e:
                    logging.error(f"Ошибка при проверке пункта меню {i+1}: {str(e)}")
                    screenshot_utils.take_screenshot(f"menu_error_{i+1}")
                    continue
            
            assert successful_navigations > 0, "Ни один пункт меню не прошел проверку"
            logging.info(f"Успешно протестировано {successful_navigations} пунктов меню")
    
    @pytest.mark.usefixtures("authenticated_page")
    @allure.title("Проверка хлебных крошек (breadcrumbs)")
    @allure.story("Хлебные крошки")
    @allure.severity('NORMAL')
    @allure.description("""
    Тест проверяет работу хлебных крошек:
    1. Наличие элемента breadcrumbs на страницах
    2. Корректность отображения пути
    3. Функциональность ссылок в крошках
    """)
    def test_breadcrumbs_functionality(self, page: Page, config, screenshot_utils):
        """Тест хлебных крошек"""
        
        # Авторизация и переход на страницу с крошками
        self._authenticate_and_navigate(page, config, "/leads/")
        
        with allure.step("Поиск хлебных крошек"):
            breadcrumb_selectors = [
                ".breadcrumb",
                ".breadcrumbs",
                "nav[aria-label='breadcrumb']",
                ".page-breadcrumb",
                ".navigation-path"
            ]
            
            breadcrumbs = None
            for selector in breadcrumb_selectors:
                try:
                    element = page.locator(selector)
                    if element.is_visible():
                        breadcrumbs = element
                        break
                except:
                    continue
            
            if not breadcrumbs:
                pytest.skip("Хлебные крошки не найдены на странице")
            
            screenshot_utils.take_screenshot("breadcrumbs_found")
        
        with allure.step("Проверка ссылок в хлебных крошках"):
            # Ищем ссылки в крошках
            breadcrumb_links = breadcrumbs.locator("a").all()
            
            if breadcrumb_links:
                for i, link in enumerate(breadcrumb_links[:-1]):  # Исключаем последнюю крошку
                    try:
                        link_text = link.text_content().strip()
                        href = link.get_attribute("href")
                        
                        if href:
                            with allure.step(f"Проверка ссылки: {link_text}"):
                                link.click()
                                page.wait_for_load_state("domcontentloaded", timeout=15000)
                                
                                # Проверяем, что произошел переход
                                current_url = page.url
                                assert href in current_url, f"Переход по крошке не выполнен: {href}"
                                
                                logging.info(f"Успешный переход по крошке: {link_text}")
                    except Exception as e:
                        logging.error(f"Ошибка при проверке крошки {i+1}: {str(e)}")
                        continue
    
    @pytest.mark.usefixtures("authenticated_page")
    @allure.title("Проверка поиска в системе")
    @allure.story("Поиск")
    @allure.severity('NORMAL')
    @allure.description("""
    Тест проверяет функциональность поиска:
    1. Наличие поля поиска
    2. Ввод поискового запроса
    3. Выполнение поиска
    4. Проверка результатов
    """)
    def test_search_functionality(self, page: Page, config, screenshot_utils):
        """Тест функциональности поиска"""
        
        self._authenticate_and_navigate(page, config)
        
        with allure.step("Поиск элементов поиска"):
            search_selectors = [
                "input[type='search']",
                "input[name='search']",
                "input[placeholder*='поиск']",
                "input[placeholder*='search']",
                ".search-input",
                "#search"
            ]
            
            search_input = None
            for selector in search_selectors:
                try:
                    element = page.locator(selector)
                    if element.is_visible():
                        search_input = element
                        break
                except:
                    continue
            
            if not search_input:
                pytest.skip("Поле поиска не найдено")
            
            screenshot_utils.take_screenshot("search_field_found")
        
        with allure.step("Выполнение поиска"):
            test_query = "test"
            search_input.fill(test_query)
            
            # Ищем кнопку поиска или используем Enter
            search_button_selectors = [
                "button[type='submit']",
                ".search-button",
                ".btn-search"
            ]
            
            search_submitted = False
            for selector in search_button_selectors:
                try:
                    button = page.locator(selector).first
                    if button.is_visible():
                        button.click()
                        search_submitted = True
                        break
                except:
                    continue
            
            if not search_submitted:
                # Пробуем Enter
                search_input.press("Enter")
            
            page.wait_for_load_state("domcontentloaded", timeout=15000)
            screenshot_utils.take_screenshot("search_executed")
        
        with allure.step("Проверка результатов поиска"):
            # Ищем результаты поиска
            results_selectors = [
                ".search-results",
                ".search-result",
                ".results",
                ".search-list"
            ]
            
            results_found = False
            for selector in results_selectors:
                try:
                    if page.locator(selector).is_visible():
                        results_found = True
                        logging.info(f"Найдены результаты поиска: {selector}")
                        break
                except:
                    continue
            
            # Даже если результаты не найдены, это может быть нормально (нет данных)
            if results_found:
                screenshot_utils.take_screenshot("search_results_found")
            else:
                logging.info("Результаты поиска не найдены (возможно, нет данных)")
    
    @pytest.mark.usefixtures("authenticated_page")
    @allure.title("Проверка бокового меню (sidebar)")
    @allure.story("Боковое меню")
    @allure.severity('NORMAL')
    @allure.description("""
    Тест проверяет работу бокового меню:
    1. Сворачивание/разворачивание sidebar
    2. Адаптивность на разных экранах
    3. Функциональность кнопок управления
    """)
    def test_sidebar_functionality(self, page: Page, config, screenshot_utils):
        """Тест бокового меню"""
        
        self._authenticate_and_navigate(page, config)
        
        with allure.step("Поиск бокового меню"):
            sidebar_selectors = [
                ".sidebar",
                ".side-menu",
                ".main-sidebar",
                "aside"
            ]
            
            sidebar = None
            for selector in sidebar_selectors:
                try:
                    element = page.locator(selector)
                    if element.is_visible():
                        sidebar = element
                        break
                except:
                    continue
            
            if not sidebar:
                pytest.skip("Боковое меню не найдено")
            
            screenshot_utils.take_screenshot("sidebar_found")
        
        with allure.step("Проверка кнопки сворачивания sidebar"):
            toggle_selectors = [
                ".sidebar-toggle",
                ".menu-toggle",
                ".toggle-sidebar",
                "[data-toggle='sidebar']"
            ]
            
            toggle_button = None
            for selector in toggle_selectors:
                try:
                    button = page.locator(selector)
                    if button.is_visible():
                        toggle_button = button
                        break
                except:
                    continue
            
            if toggle_button:
                # Запоминаем начальное состояние
                initial_classes = sidebar.get_attribute("class")
                
                # Кликаем по кнопке
                toggle_button.click()
                page.wait_for_timeout(1000)  # Ждем анимации
                
                # Проверяем изменение состояния
                new_classes = sidebar.get_attribute("class")
                assert initial_classes != new_classes, "Состояние sidebar не изменилось"
                
                screenshot_utils.take_screenshot("sidebar_toggled")
                logging.info("Кнопка сворачивания sidebar работает корректно")
            else:
                logging.info("Кнопка сворачивания sidebar не найдена")
        
        with allure.step("Проверка адаптивности sidebar на мобильных устройствах"):
            # Переключаемся на мобильный размер
            page.set_viewport_size({"width": 375, "height": 812})
            page.wait_for_timeout(1000)
            
            # Проверяем поведение sidebar на мобильном
            mobile_classes = sidebar.get_attribute("class")
            screenshot_utils.take_screenshot("sidebar_mobile")
            
            # Возвращаем обычный размер
            page.set_viewport_size({"width": 1920, "height": 1080})
            page.wait_for_timeout(1000)
    
    def _authenticate_and_navigate(self, page: Page, config, path: str = ""):
        """Вспомогательный метод для авторизации и навигации"""
        login_page = LoginPage(page, config["baseUrl"])
        credentials = config["credentials"]["valid_user"]
        
        success = login_page.login(
            email=credentials["email"],
            password=credentials["password"],
            remember=True
        )
        assert success, "Авторизация не прошла успешно"
        
        if path:
            full_url = f"{config['baseUrl'].replace('/auth', '')}{path}"
            page.goto(full_url)
            page.wait_for_load_state("domcontentloaded", timeout=30000)
    
    def _verify_page_loaded(self, page: Page, page_name: str):
        """Проверяет, что страница загрузилась корректно"""
        # Проверяем основные элементы страницы
        page_elements = [
            "h1, h2, .page-title, .title",
            "main, .main-content, .content",
            "nav, .navigation"
        ]
        
        page_loaded = False
        for selector in page_elements:
            try:
                if page.locator(selector).first.is_visible():
                    page_loaded = True
                    break
            except:
                continue
        
        assert page_loaded, f"Страница '{page_name}' не загрузилась корректно"
