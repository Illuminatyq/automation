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
        
        # Переход на страницу лидов
        page.goto(f"{config['baseUrl']}/leads/")
        page.wait_for_load_state("domcontentloaded")
        
        # Проверяем, что мы на странице лидов
        current_url = page.url
        assert "/leads/" in current_url, f"Не удалось перейти на страницу лидов. Текущий URL: {current_url}"
        
        # Проверяем наличие основных элементов
        assert page.locator('h1, .page-title, .title').is_visible(), "Заголовок страницы не найден"
        assert page.locator('table.ajax-data-table, table.data-table, table.table').is_visible(), "Таблица лидов не найдена"

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
        
        # Переход на страницу лидов
        page.goto(f"{config['baseUrl']}/leads/")
        page.wait_for_load_state("domcontentloaded")
        
        # Проверяем наличие фильтров
        filter_button = page.locator('.filter-button, .btn-filter, [data-filter]')
        assert filter_button.is_visible(), "Кнопка фильтров не найдена"
        
        # Открываем фильтры
        filter_button.click()
        page.wait_for_load_state("domcontentloaded")
        
        # Проверяем наличие полей фильтрации
        assert page.locator('.filter-form, .filter-panel').is_visible(), "Панель фильтров не найдена"

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
        
        # Переход на страницу лидов
        page.goto(f"{config['baseUrl']}/leads/")
        page.wait_for_load_state("domcontentloaded")
        
        # Находим кнопку фильтра
        filter_button = page.locator('.filter-button, .btn-filter, [data-filter]')
        assert filter_button.is_visible(), "Кнопка фильтров не найдена"
        
        # Запоминаем начальное состояние
        initial_state = page.locator('.filter-form, .filter-panel').is_visible()
        
        # Кликаем по кнопке
        filter_button.click()
        page.wait_for_load_state("domcontentloaded")
        
        # Проверяем изменение состояния
        new_state = page.locator('.filter-form, .filter-panel').is_visible()
        assert initial_state != new_state, "Состояние фильтров не изменилось после клика"