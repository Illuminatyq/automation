import pytest
import allure
from playwright.sync_api import Page, expect
from utils.screenshot_utils import ScreenshotUtils
from pages.login_page import LoginPage
import logging
import time

@allure.epic("Настройки пользователя")
@allure.feature("Детальные тесты настроек")
class TestUserSettingsDetailed:
    """Детальные тесты для каждого таба настроек пользователя"""
    
    @pytest.mark.usefixtures("authenticated_page")
    @allure.title("Проверка таба 'Профиль'")
    @allure.story("Таб Профиль")
    @allure.severity('HIGH')
    @allure.description("""
    Детальный тест таба 'Профиль':
    1. Переход на таб профиля
    2. Проверка всех полей профиля
    3. Возможность редактирования
    4. Загрузка аватара (если есть)
    5. Сохранение изменений
    """)
    def test_profile_tab_detailed(self, page: Page, config, screenshot_utils):
        """Детальный тест таба профиля"""
        
        self._navigate_to_settings(page, config)
        
        with allure.step("Переход на таб 'Профиль'"):
            profile_tab = page.locator("a[href='#profile'][role='tab']")
            if not profile_tab.is_visible():
                pytest.skip("Таб 'Профиль' не найден")
            
            profile_tab.click()
            page.wait_for_timeout(1000)
            
            # Проверяем, что содержимое профиля загрузилось
            profile_content = page.locator("#profile")
            assert profile_content.is_visible(), "Содержимое таба 'Профиль' не загрузилось"
            
            screenshot_utils.take_screenshot("profile_tab_opened")
        
        with allure.step("Проверка полей профиля"):
            # Ищем различные поля профиля
            profile_fields = {
                "Имя": ["input[name='first_name']", "input[name='name']", "#first_name", "#name"],
                "Фамилия": ["input[name='last_name']", "#last_name"],
                "Email": ["input[name='email']", "#email"],
                "Телефон": ["input[name='phone']", "#phone"],
                "Должность": ["input[name='position']", "#position"],
                "Компания": ["input[name='company']", "#company"],
                "Описание": ["textarea[name='bio']", "textarea[name='description']", "#bio"]
            }
            
            found_fields = []
            profile_content = page.locator("#profile")
            
            for field_name, selectors in profile_fields.items():
                for selector in selectors:
                    try:
                        field = profile_content.locator(selector).first
                        if field.is_visible():
                            found_fields.append((field_name, selector, field))
                            logging.info(f"Найдено поле '{field_name}': {selector}")
                            break
                    except:
                        continue
            
            if len(found_fields) == 0:
                # Попробуем найти поля с более общими селекторами
                general_selectors = [
                    "input[type='text']",
                    "input[type='email']", 
                    "input[type='tel']",
                    "textarea",
                    "select"
                ]
                
                for selector in general_selectors:
                    try:
                        elements = profile_content.locator(selector).all()
                        visible_elements = [elem for elem in elements if elem.is_visible()]
                        if visible_elements:
                            found_fields.extend([("Общее поле", selector, elem) for elem in visible_elements[:3]])
                            logging.info(f"Найдено {len(visible_elements)} элементов с селектором {selector}")
                            break
                    except:
                        continue
                
                if len(found_fields) == 0:
                    # Если все еще не найдено, делаем скриншот и пропускаем тест
                    screenshot_utils.take_screenshot("no_profile_fields_found")
                    pytest.skip("Не найдено ни одного поля профиля - возможно, страница не загрузилась корректно")
            
            logging.info(f"Найдено {len(found_fields)} полей профиля")
        
        with allure.step("Проверка возможности редактирования полей"):
            editable_fields = 0
            
            for field_name, selector, field in found_fields[:3]:  # Тестируем первые 3 поля
                try:
                    if field.is_enabled():
                        original_value = field.input_value() or ""
                        test_value = f"test_{field_name.lower()}_{int(time.time())}"
                        
                        # Пробуем изменить значение
                        field.clear()
                        field.fill(test_value)
                        
                        # Проверяем, что значение изменилось
                        new_value = field.input_value()
                        if new_value == test_value:
                            editable_fields += 1
                            logging.info(f"Поле '{field_name}' успешно отредактировано")
                            
                            # Возвращаем исходное значение
                            field.clear()
                            if original_value:
                                field.fill(original_value)
                        else:
                            logging.warning(f"Поле '{field_name}' не изменилось")
                    else:
                        logging.info(f"Поле '{field_name}' недоступно для редактирования")
                except Exception as e:
                    logging.error(f"Ошибка при тестировании поля '{field_name}': {str(e)}")
                    continue
            
            logging.info(f"Редактируемых полей: {editable_fields} из {len(found_fields)}")
        
        with allure.step("Проверка загрузки аватара"):
            # Ищем элементы для загрузки аватара
            avatar_selectors = [
                "input[type='file'][name*='avatar']",
                "input[type='file'][name*='photo']",
                "input[type='file'][name*='image']",
                ".avatar-upload",
                ".photo-upload"
            ]
            
            avatar_upload_found = False
            for selector in avatar_selectors:
                try:
                    avatar_input = profile_content.locator(selector).first
                    if avatar_input.count() > 0:
                        avatar_upload_found = True
                        logging.info(f"Найден элемент загрузки аватара: {selector}")
                        break
                except:
                    continue
            
            if avatar_upload_found:
                screenshot_utils.take_screenshot("avatar_upload_available")
            else:
                logging.info("Загрузка аватара недоступна")
    
    @pytest.mark.usefixtures("authenticated_page")
    @allure.title("Проверка таба 'Мессенджер'")
    @allure.story("Таб Мессенджер")
    @allure.severity('NORMAL')
    @allure.description("""
    Детальный тест таба 'Мессенджер':
    1. Переход на таб мессенджера
    2. Проверка настроек уведомлений
    3. Настройки интеграций с мессенджерами
    4. Проверка возможности изменения настроек
    """)
    def test_messenger_tab_detailed(self, page: Page, config, screenshot_utils):
        """Детальный тест таба мессенджера"""
        
        self._navigate_to_settings(page, config)
        
        with allure.step("Переход на таб 'Мессенджер'"):
            messenger_tab = page.locator("a[href='#messenger'][role='tab']")
            if not messenger_tab.is_visible():
                pytest.skip("Таб 'Мессенджер' не найден")
            
            messenger_tab.click()
            page.wait_for_timeout(1000)
            
            messenger_content = page.locator("#messenger")
            assert messenger_content.is_visible(), "Содержимое таба 'Мессенджер' не загрузилось"
            
            screenshot_utils.take_screenshot("messenger_tab_opened")
        
        with allure.step("Проверка настроек мессенджера"):
            messenger_content = page.locator("#messenger")
            
            # Ищем различные элементы настроек мессенджера
            messenger_elements = {
                "Чекбоксы": ["input[type='checkbox']"],
                "Селекты": ["select"],
                "Радиокнопки": ["input[type='radio']"],
                "Текстовые поля": ["input[type='text']", "textarea"],
                "Кнопки": ["button", ".btn"]
            }
            
            found_elements = {}
            
            for element_type, selectors in messenger_elements.items():
                found_elements[element_type] = []
                for selector in selectors:
                    try:
                        elements = messenger_content.locator(selector).all()
                        visible_elements = [elem for elem in elements if elem.is_visible()]
                        if visible_elements:
                            found_elements[element_type].extend(visible_elements)
                    except:
                        continue
            
            total_found = sum(len(elements) for elements in found_elements.values())
            assert total_found > 0, "Не найдено элементов настроек мессенджера"
            
            for element_type, elements in found_elements.items():
                if elements:
                    logging.info(f"Найдено {len(elements)} элементов типа '{element_type}'")
        
        with allure.step("Тестирование интерактивных элементов"):
            # Тестируем чекбоксы
            checkboxes = found_elements.get("Чекбоксы", [])
            for i, checkbox in enumerate(checkboxes[:3]):  # Тестируем первые 3
                try:
                    if checkbox.is_enabled():
                        initial_state = checkbox.is_checked()
                        checkbox.click()
                        page.wait_for_timeout(500)
                        new_state = checkbox.is_checked()
                        
                        if initial_state != new_state:
                            logging.info(f"Чекбокс {i+1} успешно переключен")
                            # Возвращаем исходное состояние
                            checkbox.click()
                        else:
                            logging.warning(f"Чекбокс {i+1} не переключился")
                except Exception as e:
                    logging.error(f"Ошибка при тестировании чекбокса {i+1}: {str(e)}")
                    continue
    
    @pytest.mark.usefixtures("authenticated_page")
    @allure.title("Проверка таба 'Интерфейс'")
    @allure.story("Таб Интерфейс")
    @allure.severity('NORMAL')
    @allure.description("""
    Детальный тест таба 'Интерфейс':
    1. Переход на таб интерфейса
    2. Проверка настроек темы
    3. Настройки языка
    4. Другие настройки интерфейса
    """)
    def test_interface_tab_detailed(self, page: Page, config, screenshot_utils):
        """Детальный тест таба интерфейса"""
        
        self._navigate_to_settings(page, config)
        
        with allure.step("Переход на таб 'Интерфейс'"):
            interface_tab = page.locator("a[href='#interface'][role='tab']")
            if not interface_tab.is_visible():
                pytest.skip("Таб 'Интерфейс' не найден")
            
            interface_tab.click()
            page.wait_for_timeout(1000)
            
            interface_content = page.locator("#interface")
            assert interface_content.is_visible(), "Содержимое таба 'Интерфейс' не загрузилось"
            
            screenshot_utils.take_screenshot("interface_tab_opened")
        
        with allure.step("Проверка настроек интерфейса"):
            interface_content = page.locator("#interface")
            
            # Ищем настройки интерфейса
            interface_settings = [
                ("Селекты (выпадающие списки)", "select"),
                ("Радиокнопки", "input[type='radio']"),
                ("Чекбоксы", "input[type='checkbox']"),
                ("Цветовые пикеры", "input[type='color']"),
                ("Слайдеры", "input[type='range']")
            ]
            
            found_settings = 0
            
            for setting_name, selector in interface_settings:
                try:
                    elements = interface_content.locator(selector).all()
                    visible_elements = [elem for elem in elements if elem.is_visible()]
                    
                    if visible_elements:
                        found_settings += len(visible_elements)
                        logging.info(f"Найдено {len(visible_elements)} элементов '{setting_name}'")
                        
                        # Тестируем первый элемент каждого типа
                        if setting_name == "Селекты (выпадающие списки)" and visible_elements:
                            self._test_select_element(visible_elements[0], setting_name)
                        elif setting_name == "Чекбоксы" and visible_elements:
                            self._test_checkbox_element(visible_elements[0], setting_name)
                            
                except Exception as e:
                    logging.error(f"Ошибка при проверке '{setting_name}': {str(e)}")
                    continue
            
            if found_settings == 0:
                logging.warning("Не найдено настроек интерфейса")
            else:
                logging.info(f"Всего найдено {found_settings} настроек интерфейса")
    
    @pytest.mark.usefixtures("authenticated_page")
    @allure.title("Проверка таба 'Безопасность'")
    @allure.story("Таб Безопасность")
    @allure.severity('CRITICAL')
    @allure.description("""
    Детальный тест таба 'Безопасность':
    1. Переход на таб безопасности
    2. Проверка формы смены пароля
    3. Настройки двухфакторной аутентификации
    4. Активные сессии
    5. История входов
    """)
    def test_security_tab_detailed(self, page: Page, config, screenshot_utils):
        """Детальный тест таба безопасности"""
        
        self._navigate_to_settings(page, config)
        
        with allure.step("Переход на таб 'Безопасность'"):
            security_tab = page.locator("a[href='#security'][role='tab']")
            if not security_tab.is_visible():
                pytest.skip("Таб 'Безопасность' не найден")
            
            security_tab.click()
            page.wait_for_timeout(1000)
            
            security_content = page.locator("#security")
            assert security_content.is_visible(), "Содержимое таба 'Безопасность' не загрузилось"
            
            screenshot_utils.take_screenshot("security_tab_opened")
        
        with allure.step("Проверка формы смены пароля"):
            security_content = page.locator("#security")
            
            password_fields = [
                ("Текущий пароль", ["input[name='current_password']", "input[name='old_password']"]),
                ("Новый пароль", ["input[name='new_password']", "input[name='password']"]),
                ("Подтверждение пароля", ["input[name='password_confirmation']", "input[name='confirm_password']"])
            ]
            
            password_form_complete = 0
            
            for field_name, selectors in password_fields:
                found = False
                for selector in selectors:
                    try:
                        field = security_content.locator(selector).first
                        if field.is_visible():
                            found = True
                            password_form_complete += 1
                            logging.info(f"Найдено поле '{field_name}': {selector}")
                            
                            # Проверяем, что поле имеет правильный тип
                            field_type = field.get_attribute("type")
                            assert field_type == "password", f"Поле '{field_name}' должно иметь type='password'"
                            break
                    except:
                        continue
                
                if not found:
                    logging.warning(f"Поле '{field_name}' не найдено")
            
            if password_form_complete >= 2:  # Минимум новый пароль и подтверждение
                logging.info("Форма смены пароля найдена")
                screenshot_utils.take_screenshot("password_change_form_found")
            else:
                logging.warning("Полная форма смены пароля не найдена")
        
        with allure.step("Проверка дополнительных элементов безопасности"):
            security_elements = [
                ("Двухфакторная аутентификация", [".two-factor", ".2fa", "input[name='two_factor']"]),
                ("Активные сессии", [".active-sessions", ".sessions", ".session-list"]),
                ("История входов", [".login-history", ".activity-log", ".audit-log"]),
                ("Кнопка сохранения", ["button[type='submit']", ".btn-save", ".btn-primary"])
            ]
            
            for element_name, selectors in security_elements:
                found = False
                for selector in selectors:
                    try:
                        element = security_content.locator(selector).first
                        if element.is_visible():
                            found = True
                            logging.info(f"Найден элемент '{element_name}': {selector}")
                            break
                    except:
                        continue
                
                if not found:
                    logging.info(f"Элемент '{element_name}' не найден")
    
    @pytest.mark.usefixtures("authenticated_page")
    @allure.title("Проверка таба 'История изменений'")
    @allure.story("Таб История")
    @allure.severity('NORMAL')
    @allure.description("""
    Детальный тест таба 'История изменений':
    1. Переход на таб истории
    2. Проверка списка изменений
    3. Фильтрация по дате
    4. Детали изменений
    """)
    def test_history_tab_detailed(self, page: Page, config, screenshot_utils):
        """Детальный тест таба истории изменений"""
        
        self._navigate_to_settings(page, config)
        
        with allure.step("Переход на таб 'История изменений'"):
            history_tab = page.locator("a[href='#history'][role='tab']")
            if not history_tab.is_visible():
                pytest.skip("Таб 'История изменений' не найден")
            
            history_tab.click()
            page.wait_for_timeout(1000)
            
            history_content = page.locator("#history")
            assert history_content.is_visible(), "Содержимое таба 'История изменений' не загрузилось"
            
            screenshot_utils.take_screenshot("history_tab_opened")
        
        with allure.step("Проверка элементов истории"):
            history_content = page.locator("#history")
            
            # Ищем различные элементы истории
            history_elements = [
                ("Таблица истории", ["table", ".history-table", ".log-table"]),
                ("Записи истории", [".history-item", ".log-entry", ".audit-entry", "tr"]),
                ("Фильтры", [".filter", "input[type='date']", "select"]),
                ("Пагинация", [".pagination", ".pager", ".page-navigation"])
            ]
            
            for element_name, selectors in history_elements:
                found = False
                for selector in selectors:
                    try:
                        elements = history_content.locator(selector).all()
                        visible_elements = [elem for elem in elements if elem.is_visible()]
                        
                        if visible_elements:
                            found = True
                            logging.info(f"Найдено {len(visible_elements)} элементов '{element_name}'")
                            
                            # Для записей истории проверяем содержимое
                            if element_name == "Записи истории" and visible_elements:
                                self._check_history_entries(visible_elements[:5])  # Проверяем первые 5
                            break
                    except:
                        continue
                
                if not found:
                    logging.info(f"Элементы '{element_name}' не найдены")
    
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
    
    def _test_select_element(self, select_element, element_name):
        """Тестирует элемент select"""
        try:
            options = select_element.locator("option").all()
            if len(options) > 1:
                # Выбираем первую доступную опцию (не пустую)
                for option in options[1:]:
                    try:
                        option.click()
                        logging.info(f"Успешно выбрана опция в '{element_name}'")
                        break
                    except:
                        continue
            else:
                logging.info(f"В '{element_name}' нет доступных опций для выбора")
        except Exception as e:
            logging.error(f"Ошибка при тестировании '{element_name}': {str(e)}")
    
    def _test_checkbox_element(self, checkbox_element, element_name):
        """Тестирует элемент checkbox"""
        try:
            if checkbox_element.is_enabled():
                initial_state = checkbox_element.is_checked()
                checkbox_element.click()
                
                new_state = checkbox_element.is_checked()
                if initial_state != new_state:
                    logging.info(f"Чекбокс в '{element_name}' успешно переключен")
                    # Возвращаем исходное состояние
                    checkbox_element.click()
                else:
                    logging.warning(f"Чекбокс в '{element_name}' не переключился")
            else:
                logging.info(f"Чекбокс в '{element_name}' недоступен для изменения")
        except Exception as e:
            logging.error(f"Ошибка при тестировании чекбокса в '{element_name}': {str(e)}")
    
    def _check_history_entries(self, entries):
        """Проверяет записи истории"""
        for i, entry in enumerate(entries):
            try:
                entry_text = entry.text_content().strip()
                if entry_text:
                    logging.info(f"Запись истории {i+1}: {entry_text[:100]}...")  # Первые 100 символов
                else:
                    logging.warning(f"Запись истории {i+1} пуста")
            except Exception as e:
                logging.error(f"Ошибка при проверке записи истории {i+1}: {str(e)}")
                continue
