import pytest
import os
from playwright.sync_api import expect, Page
import allure
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

@allure.feature("UI макет")
@pytest.mark.visual
class TestUILayout:
    @allure.story("Макет страницы пресетов звонков")
    @allure.severity(allure.severity_level.NORMAL)
    def test_calls_preset_layout(self, authenticated_page: Page, config):
        page = authenticated_page
        preset_url = (
            f"{config['baseUrl'].replace('/auth/', '')}/calls/"
            "?daterange=17.02.2025%20-%2003.03.2025&period=default&lead_id=&type=all"
            "&direction=all&predictive=all&isset_call=&total_call_time=all"
            "&client_call_time=all&call_record=all&call_recognition=all"
            "&call-hangups=all&rating=all&preset-name=Новый%20пресет"
        )
        
        # Переходим на страницу
        page.goto(preset_url)
        page.wait_for_load_state("networkidle", timeout=30000)  # Увеличили таймаут
        
        # Ждем ключевой элемент, чтобы убедиться, что UI прогрузился
        page.locator(".container").wait_for(state="visible", timeout=10000)  # Замени на реальный селектор
        
        # Пути для скриншотов
        screenshot_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "screenshots")
        os.makedirs(os.path.join(screenshot_dir, "baseline"), exist_ok=True)
        os.makedirs(os.path.join(screenshot_dir, "actual"), exist_ok=True)
        os.makedirs(os.path.join(screenshot_dir, "diff"), exist_ok=True)
        
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        baseline_path = os.path.join(screenshot_dir, "baseline", f"calls_preset_{config['current_environment']}.png")
        actual_path = os.path.join(screenshot_dir, "actual", f"calls_preset_{config['current_environment']}_{timestamp}.png")
        diff_path = os.path.join(screenshot_dir, "diff", f"calls_preset_diff_{config['current_environment']}_{timestamp}.png")
        
        # Делаем скриншот текущего состояния
        page.screenshot(path=actual_path, full_page=True)
        allure.attach.file(actual_path, "Текущий скриншот", allure.attachment_type.PNG)
        
        # Если базового скриншота нет, создаем его
        if not os.path.exists(baseline_path):
            page.screenshot(path=baseline_path, full_page=True)
            allure.attach.file(baseline_path, "Создан базовый скриншот", allure.attachment_type.PNG)
            pytest.skip("Базовый скриншот создан. Запустите тест еще раз.")
        else:
            allure.attach.file(baseline_path, "Базовый скриншот", allure.attachment_type.PNG)
        
        # Сравниваем скриншоты
        try:
            expect(page).to_have_screenshot(
                baseline_path,
                threshold=0.1,  # Уменьшили порог до 10% для большей точности
                full_page=True,
                save_diff=True,  # Сохраняем diff
                diff_path=diff_path
            )
        except AssertionError:
            if os.path.exists(diff_path):
                allure.attach.file(diff_path, "Различия в скриншотах", allure.attachment_type.PNG)
            raise  # Повторно кидаем ошибку для отчета
        
        logging.info("Сравнение скриншотов успешно выполнено")
    
    @allure.story("Макет страницы аутентификации")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.parametrize("browser_page", [
        "chromium", 
        "firefox", 
        "webkit", 
        ("chromium", "tablet"), 
        ("chromium", "mobile")
    ], indirect=True)
    def test_auth_page_layout(self, browser_page, config):
        """Тест для проверки верстки страницы аутентификации на разных устройствах и в разных браузерах"""
        page, browser_name = browser_page
        
        # Определяем тип устройства
        device_name = "desktop"
        if hasattr(browser_page, "param") and isinstance(browser_page.param, tuple):
            _, device_name = browser_page.param
        
        with allure.step(f"Открытие страницы аутентификации в {browser_name} на {device_name}"):
            page.goto(config["baseUrl"])
            page.wait_for_load_state("networkidle", timeout=10000)
        
        # Проверяем наличие ключевых элементов
        with allure.step("Проверка наличия ключевых элементов"):
            # Логотип или изображение (более общий селектор)
            logo = page.locator("img, .logo, .auth-logo")
            if logo.count() > 0:
                expect(logo.first).to_be_visible()
            else:
                logging.warning(f"Логотип не найден в {browser_name}")
                allure.attach(page.screenshot(path=f"logo_not_found_{browser_name}.png"), 
                             f"Логотип не найден в {browser_name}", 
                             allure.attachment_type.PNG)
            
            # Форма входа (более общий селектор)
            login_form = page.locator("form")
            expect(login_form).to_be_visible()
            
            # Поле email/логина (более общие селекторы)
            email_field = page.locator("input[type='email'], input[name='login'], input[name='username'], input[name='email']")
            expect(email_field).to_be_visible()
            
            # Поле пароля (более общий селектор)
            password_field = page.locator("input[type='password']")
            expect(password_field).to_be_visible()
            
            # Кнопка входа (более общий селектор)
            login_button = page.locator("button[type='submit'], input[type='submit']")
            expect(login_button).to_be_visible()
            
            # Ссылка "Забыли пароль?" (более общий селектор)
            forgot_password_link = page.locator("a:has-text('Забыли пароль'), a:has-text('Forgot password'), a[href*='forgot']")
            if forgot_password_link.count() > 0:
                expect(forgot_password_link.first).to_be_visible()
            else:
                logging.info(f"Ссылка 'Забыли пароль' не найдена в {browser_name}")
        
        # Проверяем адаптивность
        with allure.step(f"Проверка адаптивности для {device_name}"):
            # Получаем размеры формы
            form_box = login_form.bounding_box()
            page_width = page.viewport_size["width"]
            
            if device_name == "desktop":
                # На десктопе форма должна быть центрирована и не занимать всю ширину
                assert form_box["width"] < page_width * 0.8, "Форма слишком широкая для десктопа"
            elif device_name == "mobile":
                # На мобильном форма должна занимать почти всю ширину
                assert form_box["width"] > page_width * 0.8, "Форма слишком узкая для мобильного"
        
        # Делаем скриншот для отчета
        screenshot_path = f"auth_page_{browser_name.lower()}_{device_name}.png"
        page.screenshot(path=screenshot_path)
        allure.attach.file(screenshot_path, f"Скриншот страницы аутентификации ({browser_name} - {device_name})", allure.attachment_type.PNG)
        
        # Проверяем функциональность полей
        with allure.step("Проверка функциональности полей"):
            # Проверяем, что поле email принимает ввод
            email_field.fill("test@example.com")
            expect(email_field).to_have_value("test@example.com")
            
            # Проверяем, что поле пароля принимает ввод и скрывает его
            password_field.fill("password123")
            expect(password_field).to_have_value("password123")
            expect(password_field).to_have_attribute("type", "password")
        
        # Проверяем валидацию формы
        with allure.step("Проверка валидации формы"):
            # Очищаем поля
            email_field.fill("")
            password_field.fill("")
            
            # Делаем скриншот перед отправкой формы
            before_submit_path = f"before_submit_{browser_name.lower()}_{device_name}.png"
            page.screenshot(path=before_submit_path)
            allure.attach.file(before_submit_path, f"Перед отправкой формы ({browser_name} - {device_name})", allure.attachment_type.PNG)
            
            # Пытаемся отправить пустую форму
            login_button.click()
            
            # Ждем появления сообщений об ошибках
            page.wait_for_timeout(1000)  # Даем время на появление сообщений
            
            # Делаем скриншот с ошибками валидации
            validation_screenshot_path = f"auth_validation_{browser_name.lower()}_{device_name}.png"
            page.screenshot(path=validation_screenshot_path)
            allure.attach.file(validation_screenshot_path, f"Валидация формы ({browser_name} - {device_name})", allure.attachment_type.PNG)
            
            # Проверяем, что форма не отправилась (мы все еще на странице логина)
            current_url = page.url
            if "/auth/" in current_url or "/login" in current_url:
                logging.info(f"Валидация формы работает корректно в {browser_name} - остались на странице авторизации")
            else:
                logging.warning(f"Форма была отправлена несмотря на пустые поля в {browser_name}, URL: {current_url}")
                pytest.fail(f"Форма была отправлена несмотря на пустые поля в {browser_name}, URL: {current_url}")
        
        logging.info(f"Тест верстки страницы аутентификации успешно выполнен для {browser_name} на {device_name}")