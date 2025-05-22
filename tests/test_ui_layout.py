import pytest
import os
from playwright.sync_api import expect, Page
import allure
import time
import logging
from utils.screenshot_utils import ScreenshotUtils
from config.viewport_config import VIEWPORT_CONFIGS, ALL_VIEWPORTS

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

@allure.feature("UI макет")
@pytest.mark.visual
class TestUILayout:
    @allure.story("Макет страницы пресетов звонков")
    @allure.severity(allure.severity_level.NORMAL)
    def test_calls_preset_layout(self, page: Page, config, screenshot_utils):
        preset_url = (
            f"{config['baseUrl'].replace('/auth/', '')}/calls/"
            "?daterange=17.02.2025%20-%2003.03.2025&period=default&lead_id=&type=all"
            "&direction=all&predictive=all&isset_call=&total_call_time=all"
            "&client_call_time=all&call_record=all&call_recognition=all"
            "&call-hangups=all&rating=all&preset-name=Новый%20пресет"
        )
        
        # Переходим на страницу
        with allure.step("Открытие страницы пресетов звонков"):
            page.goto(preset_url)
            page.wait_for_load_state("domcontentloaded", timeout=60000)
            try:
                page.wait_for_load_state("networkidle", timeout=60000)
            except Exception:
                logging.warning("Превышен таймаут ожидания networkidle, продолжаем выполнение")
        
        with allure.step("Ожидание загрузки UI"):
            try:
                containers = [
                    ".container",
                    ".main-content",
                    ".content-wrapper",
                    "#app",
                    "main"
                ]
                for selector in containers:
                    try:
                        page.locator(selector).wait_for(state="visible", timeout=10000)
                        logging.info(f"Найден контейнер: {selector}")
                        break
                    except Exception:
                        continue
                else:
                    if page.locator("body").is_visible():
                        logging.warning("Контейнеры не найдены, но страница загружена")
                    else:
                        pytest.fail("Страница не загрузилась")
            except Exception as e:
                logging.error(f"Ошибка при ожидании загрузки UI: {str(e)}")
                pytest.fail(f"Не удалось дождаться загрузки UI: {str(e)}")
        
        with allure.step("Проверка визуального соответствия"):
            screenshot_name = f"calls_preset_{config['current_environment']}"
            if not screenshot_utils.compare_with_baseline(screenshot_name):
                screenshot_utils.save_error_screenshot(f"error_{screenshot_name}")
                pytest.fail(f"Визуальные различия на странице пресетов звонков")
        
        logging.info("Сравнение скриншотов успешно выполнено")

    @allure.story("Макет страницы аутентификации")
    @allure.severity(allure.severity_level.NORMAL)
    def test_auth_page_basic(self, page: Page, config):
        page.set_viewport_size({"width": 1280, "height": 720})
        with allure.step("Открытие страницы аутентификации"):
            page.goto(config["baseUrl"])
            page.wait_for_load_state("domcontentloaded", timeout=60000)
        with allure.step("Проверка наличия ключевых элементов"):
            login_form = page.locator("form")
            expect(login_form).to_be_visible()
            email_field = page.locator("input[type='email'], input[name='login'], input[name='username'], input[name='email']")
            expect(email_field).to_be_visible()
            password_field = page.locator("input[type='password']")
            expect(password_field).to_be_visible()
            login_button = page.locator("button[type='submit'], input[type='submit']")
            expect(login_button).to_be_visible()
        with allure.step("Проверка функциональности полей"):
            email_field.fill("test@example.com")
            expect(email_field).to_have_value("test@example.com")
            password_field.fill("password123")
            expect(password_field).to_have_value("password123")
        logging.info("Базовый тест страницы аутентификации успешно выполнен")

    @allure.story("Адаптивность страницы аутентификации")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.parametrize("device_type,viewport_type", [
        ("desktop", "small"),
        ("desktop", "medium"),
        ("desktop", "large"),
        ("tablet", "portrait"),
        ("tablet", "landscape")
    ])
    def test_auth_page_responsive(self, page: Page, config, device_type, viewport_type, screenshot_utils):
        viewport_config = VIEWPORT_CONFIGS[device_type][viewport_type]
        page.set_viewport_size(viewport_config)
        
        with allure.step(f"Открытие страницы аутентификации на {device_type} {viewport_type}"):
            page.goto(config["baseUrl"])
            page.wait_for_load_state("domcontentloaded", timeout=60000)
        
        dynamic_selectors = [
            ".timestamp",
            ".user-info",
            ".notification",
            ".loading",
            ".error-message",
            ".success-message"
        ]
        screenshot_utils.mask_dynamic_content(dynamic_selectors)
        
        with allure.step("Проверка наличия ключевых элементов"):
            login_form = page.locator("form")
            expect(login_form).to_be_visible()
            email_field = page.locator("input[type='email'], input[name='login'], input[name='username'], input[name='email']")
            expect(email_field).to_be_visible()
            password_field = page.locator("input[type='password']")
            expect(password_field).to_be_visible()
            login_button = page.locator("button[type='submit'], input[type='submit']")
            expect(login_button).to_be_visible()
        
        with allure.step(f"Проверка адаптивности для {device_type} {viewport_type}"):
            form_box = login_form.bounding_box()
            page_width = viewport_config["width"]
            if device_type == "desktop":
                assert form_box["width"] < page_width * 0.8, "Форма слишком широкая для десктопа"
            elif device_type == "tablet":
                if viewport_type == "portrait":
                    assert form_box["width"] < page_width * 0.9, "Форма слишком широкая для планшета в портретной ориентации"
                else:
                    assert form_box["width"] < page_width * 0.8, "Форма слишком широкая для планшета в ландшафтной ориентации"
        
        with allure.step("Проверка визуального соответствия"):
            screenshot_name = f"auth_page_{device_type}_{viewport_type}"
            if not screenshot_utils.compare_with_baseline(screenshot_name):
                screenshot_utils.save_error_screenshot(f"error_{screenshot_name}")
                pytest.fail(f"Визуальные различия на странице аутентификации для {device_type} {viewport_type}")
        
        logging.info(f"Тест адаптивности успешно выполнен для {device_type} {viewport_type}")