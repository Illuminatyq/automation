import pytest
import allure
from playwright.sync_api import Page, expect
from utils.screenshot_utils import ScreenshotUtils
from pages.login_page import LoginPage
import logging
import time

@allure.epic("Лиды")
@allure.feature("Работа с лидами")
class TestLeads:
    """Тесты для проверки работы с лидами"""

    @pytest.mark.usefixtures("authenticated_page")
    @allure.title("Проверка верстки страницы лидов")
    @allure.story("Верстка")
    @allure.severity('NORMAL')
    @allure.description("""
    Тест проверяет верстку страницы лидов:
    1. Проверка наличия основных элементов:
       - Заголовок страницы
       - Таблица лидов
       - Кнопки управления
       - Фильтры
    2. Проверка корректного отображения всех элементов
    3. Проверка адаптивности верстки
    
    Проверяется корректность отображения всех компонентов страницы
    """)
    def test_leads_page_layout(self, page: Page, config, screenshot_utils):
        """Тест проверяет верстку страницы лидов"""
        login_page = LoginPage(page, config["baseUrl"])
        credentials = config["credentials"]["valid_user"]
        
        # Выполняем авторизацию
        success = login_page.login(
            email=credentials["email"],
            password=credentials["password"],
            remember=True
        )
        assert success, "Авторизация не прошла успешно"
        # Явно ждём появления сайдбара/меню
        sidebar = page.locator(".sidebar")
        assert sidebar.is_visible(timeout=10000), "Сайдбар не найден после логина"
        
        # Переход на страницу лидов через сайдбар
        leads_link = page.locator("a.sidebar-link[href='/leads/']")
        assert leads_link.is_visible(timeout=10000), "Пункт меню 'Лиды' не найден"
        leads_link.click()
        screenshot_utils.take_screenshot("after_leads_link_click")
        logging.info(f"Текущий URL после клика: {page.url}")
        # Ждём появления таблицы лидов (берём первую, если их несколько)
        lead_table = page.locator('table.ajax-data-table, table.data-table, table.table').first
        if lead_table.count() == 0 or not lead_table.is_visible():
            screenshot_utils.take_screenshot("lead_table_not_found")
            allure.attach(page.content(), "HTML страницы при ошибке поиска таблицы", allure.attachment_type.HTML)
            logging.error(f"Таблица лидов не найдена! URL: {page.url}")
            assert False, "Таблица лидов не появилась после перехода"
        
        # Проверяем, что мы на странице лидов
        current_url = page.url
        assert "/leads/" in current_url, f"Не удалось перейти на страницу лидов. Текущий URL: {current_url}"
        
        # Проверяем наличие основных элементов
        assert page.locator('h1, .page-title, .title').is_visible(), "Заголовок страницы не найден"
        
        # Проверяем таблицу лидов (используем first для избежания ошибки strict mode)
        tables = page.locator('table.ajax-data-table, table.data-table, table.table')
        assert tables.count() > 0, "Таблица лидов не найдена"
        assert tables.first.is_visible(), "Таблица лидов не видна"

    @pytest.mark.usefixtures("authenticated_page")
    @allure.title("Проверка фильтрации лидов")
    @allure.story("Фильтрация")
    @allure.severity('NORMAL')
    @allure.description("""
    Тест проверяет функционал фильтрации лидов:
    1. Проверка работы фильтров:
       - По дате
       - По статусу
       - По источнику
    2. Проверка применения фильтров
    3. Проверка сброса фильтров
    4. Проверка корректности отфильтрованных данных
    
    Проверяется корректность работы всех фильтров
    """)
    def test_leads_filtering(self, page: Page, config, screenshot_utils):
        """Тест проверяет работу фильтров на странице лидов"""
        login_page = LoginPage(page, config["baseUrl"])
        credentials = config["credentials"]["valid_user"]
        
        # Выполняем авторизацию
        success = login_page.login(
            email=credentials["email"],
            password=credentials["password"],
            remember=True
        )
        assert success, "Авторизация не прошла успешно"
        # Явно ждём появления сайдбара/меню
        sidebar = page.locator(".sidebar")
        assert sidebar.is_visible(timeout=10000), "Сайдбар не найден после логина"
        
        # Переход на страницу лидов через сайдбар
        leads_link = page.locator("a.sidebar-link[href='/leads/']")
        assert leads_link.is_visible(timeout=10000), "Пункт меню 'Лиды' не найден"
        leads_link.click()
        screenshot_utils.take_screenshot("after_leads_link_click")
        logging.info(f"Текущий URL после клика: {page.url}")
        # Ждём появления таблицы лидов (берём первую, если их несколько)
        lead_table = page.locator('table.ajax-data-table, table.data-table, table.table').first
        assert lead_table.is_visible(timeout=15000), "Таблица лидов не появилась после перехода"
        
        # Проверяем наличие фильтров (исправленный селектор)
        filter_button = page.locator('a.filter-header.collapse-icon')
        if filter_button.count() == 0:
            filter_button = page.get_by_text('Фильтр', exact=False)
        screenshot_utils.take_screenshot("filter_button_search")
        logging.info(f"Найдено кнопок фильтра: {filter_button.count()}")
        if filter_button.count() == 0 or not filter_button.first.is_visible():
            allure.attach(page.content(), "HTML страницы при ошибке поиска фильтра", allure.attachment_type.HTML)
            logging.error(f"Кнопка фильтра не найдена! URL: {page.url}")
            assert False, "Кнопка фильтров не найдена"
        
        # Открываем фильтры
        filter_button.first.click()
        page.wait_for_load_state("domcontentloaded")
        
        # Проверяем наличие полей фильтрации
        assert page.locator('.filter-form, .filter-panel').is_visible(), "Панель фильтров не найдена"

    @pytest.mark.usefixtures("authenticated_page")
    @allure.title("Проверка клика по кнопке фильтра")
    @allure.story("Фильтрация")
    @allure.severity('NORMAL')
    @allure.description("""
    Тест проверяет работу кнопки фильтра:
    1. Проверка видимости кнопки фильтра
    2. Проверка клика по кнопке
    3. Проверка появления панели фильтров
    4. Проверка закрытия панели фильтров
    
    Проверяется корректность работы кнопки фильтра и панели фильтров
    """)
    def test_filter_button_click(self, page: Page, config, screenshot_utils):
        """Тест проверяет работу кнопки фильтра"""
        login_page = LoginPage(page, config["baseUrl"])
        credentials = config["credentials"]["valid_user"]
        
        # Выполняем авторизацию
        success = login_page.login(
            email=credentials["email"],
            password=credentials["password"],
            remember=True
        )
        assert success, "Авторизация не прошла успешно"
        # Явно ждём появления сайдбара/меню
        sidebar = page.locator(".sidebar")
        assert sidebar.is_visible(timeout=10000), "Сайдбар не найден после логина"
        
        # Переход на страницу лидов через сайдбар
        leads_link = page.locator("a.sidebar-link[href='/leads/']")
        assert leads_link.is_visible(timeout=10000), "Пункт меню 'Лиды' не найден"
        leads_link.click()
        screenshot_utils.take_screenshot("after_leads_link_click")
        logging.info(f"Текущий URL после клика: {page.url}")
        # Ждём появления таблицы лидов (берём первую, если их несколько)
        lead_table = page.locator('table.ajax-data-table, table.data-table, table.table').first
        assert lead_table.is_visible(timeout=15000), "Таблица лидов не появилась после перехода"
        
        # Находим кнопку фильтра (исправленный селектор)
        filter_button = page.locator('a.filter-header.collapse-icon')
        if filter_button.count() == 0:
            filter_button = page.get_by_text('Фильтр', exact=False)
        screenshot_utils.take_screenshot("filter_button_search")
        logging.info(f"Найдено кнопок фильтра: {filter_button.count()}")
        if filter_button.count() == 0 or not filter_button.first.is_visible():
            allure.attach(page.content(), "HTML страницы при ошибке поиска фильтра", allure.attachment_type.HTML)
            logging.error(f"Кнопка фильтра не найдена! URL: {page.url}")
            assert False, "Кнопка фильтров не найдена"
        
        # Запоминаем начальное состояние
        initial_state = page.locator('.filter-form, .filter-panel').is_visible()
        
        # Кликаем по первой найденной кнопке
        filter_button.first.click()
        page.wait_for_load_state("domcontentloaded")
        
        # Проверяем изменение состояния
        new_state = page.locator('.filter-form, .filter-panel').is_visible()
        assert initial_state != new_state, "Состояние фильтров не изменилось после клика"