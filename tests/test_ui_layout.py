import pytest
import os
from playwright.sync_api import Page, expect
import allure
import json
from pages.login_page import LoginPage  # Предполагаем, что у тебя есть LoginPage из предыдущих документов

@pytest.mark.visual
@allure.feature("UI Layout Testing")
class TestUILayout:
    
    @allure.story("Visual layout of filters and table on calls preset page after login")
    @allure.severity(allure.severity_level.NORMAL)
    def test_visual_layout(self, page: Page, config):
        # Выполняем авторизацию
        login_page = LoginPage(page)
        login_page.navigate()
        
        valid_credentials = config['credentials']['valid_user']
        login_page.login(valid_credentials['email'], valid_credentials['password'])
        
        # Ждем успешной авторизации (например, переход на другую страницу или появление элемента дашборда)
        page.wait_for_url("**/*dashboard*")  # Замени на реальный URL после логина или добавь проверку элемента
        
        # Переходим на страницу с пресетом напрямую после авторизации
        preset_url = "https://liner.dstepanyuk.dev.smte.am/calls/?daterange=17.02.2025%20-%2003.03.2025&period=default&lead_id=&type=all&direction=all&predictive=all&isset_call=&total_call_time=all&client_call_time=all&call_record=all&call_recognition=all&call-hangups=all&rating=all&preset-name=Новый%20пресет%E2%80%8B"
        page.goto(preset_url)
        
        # Ждем, пока страница полностью загрузится
        page.wait_for_load_state("networkidle")
        
        # Делаем скриншот текущей страницы с фильтром и таблицей
        screenshot_path = os.path.join("screenshots", "actual", "filters_table.png")
        os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
        page.screenshot(path=screenshot_path)
        
        # Путь к эталонному скриншоту
        baseline_path = os.path.join("screenshots", "baseline", "filters_table.png")
        
        # Проверяем, существует ли эталонный скриншот
        if not os.path.exists(baseline_path):
            pytest.fail(f"Эталонный скриншот {baseline_path} не найден. Создай его вручную.")
        
        # Сравниваем скриншоты с помощью Playwright
        expect(page).to_have_screenshot(name="filters_table.png", threshold=0.1)  # Устанавливаем порог различий (0.1 = 10%)
        
        # Прикладываем скриншоты к отчету Allure
        with open(screenshot_path, "rb") as f:
            allure.attach(f.read(), name="Current Screenshot", attachment_type=allure.attachment_type.PNG)
        with open(baseline_path, "rb") as f:
            allure.attach(f.read(), name="Baseline Screenshot", attachment_type=allure.attachment_type.PNG)

    @pytest.fixture(scope="session")
    def config(self):
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.json')
        with open(config_path, 'r') as f:
            return json.load(f)

    @pytest.fixture
    def page(self, browser):
        page = browser.new_page()
        yield page
        page.close()

    @pytest.fixture(scope="session")
    def browser(self):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)  # headless=False для видимости
            yield browser
            browser.close()