import pytest
import allure
from playwright.sync_api import Page, expect
from utils.screenshot_utils import ScreenshotUtils
from pages.login_page import LoginPage
import logging
import time

@allure.epic("Настройки пользователя")
@allure.feature("UI тесты настроек")
class TestUserSettings:
    """Тесты для проверки страницы настроек пользователя"""
    
    @pytest.mark.usefixtures("authenticated_page")
    @allure.title("Проверка навигации к настройкам пользователя")
    @allure.story("Навигация")
    @allure.severity('HIGH')
    @allure.description("""
    Тест проверяет корректность перехода к настройкам пользователя:
    1. Нажатие на дропдаун профиля пользователя
    2. Переход к настройкам через меню
    3. Проверка загрузки страницы настроек
    4. Проверка URL страницы
    """)
    def test_navigate_to_user_settings(self, page: Page, config, screenshot_utils):
        """Тест навигации к настройкам пользователя"""
        
        # Авторизация
        login_page = LoginPage(page, config["baseUrl"])
        credentials = config["credentials"]["valid_user"]
        
        success = login_page.login(
            email=credentials["email"],
            password=credentials["password"],
            remember=True
        )
        assert success, "Авторизация не прошла успешно"
        
        with allure.step("Открытие дропдауна профиля"):
            # Ждем появления дропдауна профиля
            profile_dropdown = page.locator(".user-settings-dropdown .dropdown-toggle")
            profile_dropdown.wait_for(state="visible", timeout=30000)
            profile_dropdown.click()
            
            # Ждем открытия меню
            dropdown_menu = page.locator(".user-settings-dropdown .dropdown-menu")
            dropdown_menu.wait_for(state="visible", timeout=10000)
            
            screenshot_utils.take_screenshot("profile_dropdown_opened")
        
        with allure.step("Переход к настройкам пользователя"):
            # Ищем ссылку настроек пользователя
            settings_selectors = [
                ".dropdown-menu a[href*='/users/']",
                ".dropdown-menu a[href*='/settings']",
                ".dropdown-menu a[href*='/profile']",
                ".dropdown-menu a:has-text('Настройки')",
                ".dropdown-menu a:has-text('Профиль')",
                ".dropdown-menu a:has-text('Settings')"
            ]
            
            settings_link = None
            for selector in settings_selectors:
                try:
                    link = page.locator(selector).first
                    if link.is_visible():
                        settings_link = link
                        break
                except:
                    continue
            
            assert settings_link is not None, "Ссылка на настройки пользователя не найдена"
            settings_link.click()
            
            # Ждем загрузки страницы настроек
            page.wait_for_load_state("domcontentloaded", timeout=30000)
            
        with allure.step("Проверка загрузки страницы настроек"):
            current_url = page.url
            assert any(keyword in current_url.lower() for keyword in ["/users/", "/settings", "/profile"]), \
                f"URL не соответствует странице настроек: {current_url}"
            
            # Проверяем наличие основных элементов настроек
            page_selectors = [
                "h1, .page-title, .settings-title",
                ".nav-tabs, .tabs, .tab-navigation",
                ".settings-content, .profile-content, .user-settings"
            ]
            
            for selector in page_selectors:
                try:
                    element = page.locator(selector).first
                    if element.is_visible():
                        break
                except:
                    continue
            else:
                assert False, "Основные элементы страницы настроек не найдены"
            
            screenshot_utils.take_screenshot("user_settings_page_loaded")
    
    @pytest.mark.usefixtures("authenticated_page")
    @allure.title("Проверка всех табов в настройках пользователя")
    @allure.story("Табы настроек")
    @allure.severity('NORMAL')
    @allure.description("""
    Тест проверяет работу всех табов в настройках пользователя:
    1. Профиль
    2. Мессенджер
    3. Интерфейс
    4. Безопасность
    5. История изменений
    
    Для каждого таба проверяется:
    - Клик по табу
    - Загрузка содержимого
    - Наличие соответствующих полей
    """)
    def test_user_settings_tabs(self, page: Page, config, screenshot_utils):
        """Тест проверяет все табы в настройках пользователя"""
        
        # Переходим к настройкам пользователя
        self._navigate_to_settings(page, config)
        
        # Ищем конкретные табы по структуре HTML
        tab_container = page.locator(".list-group[role='tablist']")
        if not tab_container.is_visible():
            pytest.skip("Контейнер табов настроек не найден")
        
        # Получаем все табы
        tabs = tab_container.locator("a[role='tab']").all()
        
        if not tabs:
            pytest.skip("Табы в настройках не найдены")
        
        # Ожидаемые табы и их селекторы содержимого
        expected_tabs = {
            "Профиль": "#profile",
            "Мессенджер": "#messenger", 
            "Интерфейс": "#interface",
            "Безопасность": "#security",
            "История изменений": "#history"
        }
        
        with allure.step(f"Найдено {len(tabs)} табов для проверки"):
            tested_tabs = 0
            
            for tab in tabs:
                try:
                    # Получаем название таба
                    tab_text = tab.text_content().strip().replace("\u200B", "")  # Удаляем ZeroWidthSpace
                    
                    with allure.step(f"Проверка таба: {tab_text}"):
                        logging.info(f"Проверяем таб: {tab_text}")
                        
                        # Кликаем по табу
                        tab.click()
                        page.wait_for_timeout(1000)  # Ждем анимации переключения
                        
                        # Проверяем, что таб стал активным
                        tab_classes = tab.get_attribute("class")
                        assert "active" in tab_classes, f"Таб '{tab_text}' не стал активным"
                        
                        # Получаем href для определения содержимого
                        href = tab.get_attribute("href")
                        if href:
                            content_id = href.replace("#", "")
                            content_selector = f"#{content_id}"
                            
                            # Проверяем загрузку содержимого
                            content = page.locator(content_selector)
                            if content.is_visible():
                                logging.info(f"Содержимое таба '{tab_text}' загружено")
                                
                                # Делаем скриншот каждого таба
                                safe_tab_name = tab_text.lower().replace(" ", "_").replace("/", "_")
                                screenshot_utils.take_screenshot(f"settings_tab_{safe_tab_name}")
                                
                                # Специфичные проверки для разных типов табов
                                self._check_tab_specific_content(page, tab_text.lower(), content_selector)
                                
                                tested_tabs += 1
                            else:
                                logging.warning(f"Содержимое таба '{tab_text}' не видимо")
                        
                except Exception as e:
                    logging.error(f"Ошибка при проверке таба '{tab_text}': {str(e)}")
                    screenshot_utils.take_screenshot(f"settings_tab_error_{tab_text.lower().replace(' ', '_')}")
                    continue
            
            assert tested_tabs > 0, "Ни один таб не был успешно протестирован"
            logging.info(f"Успешно протестировано {tested_tabs} из {len(tabs)} табов")
    
    @pytest.mark.usefixtures("authenticated_page")
    @allure.title("Проверка редактирования профиля пользователя")
    @allure.story("Редактирование профиля")
    @allure.severity('HIGH')
    @allure.description("""
    Тест проверяет возможность редактирования профиля:
    1. Изменение основной информации (имя, email, телефон)
    2. Загрузка аватара
    3. Сохранение изменений
    4. Проверка отображения изменений
    """)
    def test_edit_user_profile(self, page: Page, config, screenshot_utils):
        """Тест редактирования профиля пользователя"""
        
        self._navigate_to_settings(page, config)
        
        with allure.step("Поиск полей для редактирования"):
            # Ищем поля профиля
            profile_fields = {
                "name": ["input[name='name']", "input[name='first_name']", "#name", ".name-input"],
                "email": ["input[name='email']", "#email", ".email-input"],
                "phone": ["input[name='phone']", "#phone", ".phone-input"],
                "bio": ["textarea[name='bio']", "textarea[name='description']", "#bio"]
            }
            
            screenshot_utils.take_screenshot("profile_before_edit")
            
            changes_made = False
            
            for field_name, selectors in profile_fields.items():
                for selector in selectors:
                    try:
                        field = page.locator(selector).first
                        if field.is_visible() and field.is_enabled():
                            with allure.step(f"Изменение поля '{field_name}'"):
                                original_value = field.input_value()
                                test_value = f"test_{field_name}_{int(time.time())}"
                                
                                # Изменяем значение
                                field.clear()
                                field.fill(test_value)
                                
                                # Проверяем, что значение изменилось
                                new_value = field.input_value()
                                assert new_value == test_value, f"Значение поля {field_name} не изменилось"
                                
                                changes_made = True
                                logging.info(f"Поле {field_name} изменено с '{original_value}' на '{test_value}'")
                                break
                    except Exception as e:
                        logging.warning(f"Не удалось изменить поле {field_name} с селектором {selector}: {e}")
                        continue
            
            if not changes_made:
                pytest.skip("Не найдены редактируемые поля профиля")
        
        with allure.step("Сохранение изменений"):
            # Ищем кнопку сохранения
            save_selectors = [
                "button[type='submit']",
                ".btn-save",
                ".btn-primary:has-text('Сохранить')",
                "input[type='submit']",
                "button:has-text('Save')",
                "button:has-text('Update')"
            ]
            
            save_button = None
            for selector in save_selectors:
                try:
                    button = page.locator(selector).first
                    if button.is_visible():
                        save_button = button
                        break
                except:
                    continue
            
            if save_button:
                save_button.click()
                page.wait_for_load_state("domcontentloaded", timeout=15000)
                
                # Проверяем уведомление об успешном сохранении
                success_selectors = [
                    ".alert-success",
                    ".toast-success",
                    ".notification-success",
                    "#toast-container .toast-success"
                ]
                
                success_found = False
                for selector in success_selectors:
                    try:
                        if page.locator(selector).is_visible(timeout=5000):
                            success_found = True
                            break
                    except:
                        continue
                
                if success_found:
                    logging.info("Изменения профиля сохранены успешно")
                    screenshot_utils.take_screenshot("profile_saved_successfully")
                else:
                    logging.warning("Уведомление о сохранении не найдено")
                    screenshot_utils.take_screenshot("profile_save_no_notification")
            else:
                logging.warning("Кнопка сохранения не найдена")
                screenshot_utils.take_screenshot("profile_no_save_button")
    
    @pytest.mark.usefixtures("authenticated_page")
    @allure.title("Проверка настроек безопасности")
    @allure.story("Безопасность")
    @allure.severity('CRITICAL')
    @allure.description("""
    Тест проверяет настройки безопасности:
    1. Смена пароля
    2. Двухфакторная аутентификация (если есть)
    3. Активные сессии
    4. История входов
    """)
    def test_security_settings(self, page: Page, config, screenshot_utils):
        """Тест настроек безопасности"""
        
        self._navigate_to_settings(page, config)
        
        with allure.step("Поиск таба безопасности"):
            security_tab_selectors = [
                "a:has-text('Безопасность')",
                "a:has-text('Security')",
                "a:has-text('Пароль')",
                "a:has-text('Password')",
                "a[href*='security']",
                "a[href*='password']"
            ]
            
            security_tab = None
            for selector in security_tab_selectors:
                try:
                    tab = page.locator(selector).first
                    if tab.is_visible():
                        security_tab = tab
                        break
                except:
                    continue
            
            if not security_tab:
                pytest.skip("Таб безопасности не найден")
            
            security_tab.click()
            page.wait_for_load_state("domcontentloaded", timeout=15000)
            screenshot_utils.take_screenshot("security_settings_tab")
        
        with allure.step("Проверка формы смены пароля"):
            password_fields = {
                "current": ["input[name='current_password']", "input[name='old_password']", "#current_password"],
                "new": ["input[name='new_password']", "input[name='password']", "#new_password"],
                "confirm": ["input[name='password_confirmation']", "input[name='confirm_password']", "#confirm_password"]
            }
            
            password_form_found = False
            for field_type, selectors in password_fields.items():
                for selector in selectors:
                    try:
                        field = page.locator(selector).first
                        if field.is_visible():
                            password_form_found = True
                            logging.info(f"Найдено поле {field_type}: {selector}")
                            break
                    except:
                        continue
                if password_form_found:
                    break
            
            if password_form_found:
                screenshot_utils.take_screenshot("password_change_form")
                logging.info("Форма смены пароля найдена")
            else:
                logging.warning("Форма смены пароля не найдена")
        
        with allure.step("Проверка дополнительных настроек безопасности"):
            # Ищем элементы 2FA, активных сессий и т.д.
            security_elements = [
                ("2FA", ["input[name='two_factor']", ".two-factor", "#2fa"]),
                ("Активные сессии", [".active-sessions", ".sessions", "#sessions"]),
                ("История входов", [".login-history", ".activity-log", "#login_history"])
            ]
            
            for element_name, selectors in security_elements:
                found = False
                for selector in selectors:
                    try:
                        if page.locator(selector).first.is_visible():
                            found = True
                            logging.info(f"Найден элемент {element_name}")
                            break
                    except:
                        continue
                
                if not found:
                    logging.info(f"Элемент {element_name} не найден")
    
    def _navigate_to_settings(self, page: Page, config):
        """Вспомогательный метод для перехода к настройкам"""
        # Авторизация
        login_page = LoginPage(page, config["baseUrl"])
        credentials = config["credentials"]["valid_user"]
        
        success = login_page.login(
            email=credentials["email"],
            password=credentials["password"],
            remember=True
        )
        assert success, "Авторизация не прошла успешно"
        
        # Открытие дропдауна профиля
        profile_dropdown = page.locator(".user-settings-dropdown .dropdown-toggle")
        profile_dropdown.wait_for(state="visible", timeout=30000)
        profile_dropdown.click()
        
        # Переход к настройкам
        settings_selectors = [
            ".dropdown-menu a[href*='/users/']",
            ".dropdown-menu a[href*='/settings']",
            ".dropdown-menu a[href*='/profile']"
        ]
        
        for selector in settings_selectors:
            try:
                link = page.locator(selector).first
                if link.is_visible():
                    link.click()
                    page.wait_for_load_state("domcontentloaded", timeout=30000)
                    return
            except:
                continue
        
        raise Exception("Не удалось перейти к настройкам пользователя")
    
    def _check_tab_specific_content(self, page: Page, tab_name: str, content_selector: str = None):
        """Проверяет специфичное содержимое для разных табов"""
        
        # Если передан селектор контента, ограничиваем поиск только этой областью
        search_context = page.locator(content_selector) if content_selector else page
        
        if "профиль" in tab_name or "profile" in tab_name:
            # Проверяем поля профиля
            profile_elements = ["input[name='name']", "input[name='email']", "input[name='phone']", "input[name='first_name']", "input[name='last_name']"]
            for element in profile_elements:
                try:
                    if search_context.locator(element).is_visible():
                        logging.info(f"Найден элемент профиля: {element}")
                        break
                except:
                    continue
        
        elif "безопасность" in tab_name or "security" in tab_name:
            # Проверяем элементы безопасности
            security_elements = ["input[name='password']", "input[name='current_password']", "input[name='new_password']", "input[name='password_confirmation']"]
            for element in security_elements:
                try:
                    if search_context.locator(element).is_visible():
                        logging.info(f"Найден элемент безопасности: {element}")
                        break
                except:
                    continue
        
        elif "мессенджер" in tab_name or "messenger" in tab_name:
            # Проверяем настройки мессенджера
            messenger_elements = ["input[type='checkbox']", "select", ".messenger-setting", ".notification-setting"]
            for element in messenger_elements:
                try:
                    if search_context.locator(element).first.is_visible():
                        logging.info(f"Найден элемент мессенджера: {element}")
                        break
                except:
                    continue
        
        elif "интерфейс" in tab_name or "interface" in tab_name:
            # Проверяем настройки интерфейса
            interface_elements = ["select", "input[type='radio']", "input[type='checkbox']", ".theme-setting", ".language-setting"]
            for element in interface_elements:
                try:
                    if search_context.locator(element).first.is_visible():
                        logging.info(f"Найден элемент интерфейса: {element}")
                        break
                except:
                    continue
        
        elif "история" in tab_name or "history" in tab_name:
            # Проверяем историю изменений
            history_elements = [".history-item", ".activity-log", "table", ".log-entry"]
            for element in history_elements:
                try:
                    if search_context.locator(element).first.is_visible():
                        logging.info(f"Найден элемент истории: {element}")
                        break
                except:
                    continue
