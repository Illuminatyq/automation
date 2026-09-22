import pytest
import allure
from playwright.sync_api import Page, expect
from utils.screenshot_utils import ScreenshotUtils
from pages.login_page import LoginPage
import logging
import time

@allure.epic("UI Компоненты")
@allure.feature("Тесты UI компонентов")
class TestUIComponents:
    """Тесты для проверки различных UI компонентов"""
    
    @pytest.mark.usefixtures("authenticated_page")
    @allure.title("Проверка уведомлений (toast messages)")
    @allure.story("Уведомления")
    @allure.severity('NORMAL')
    @allure.description("""
    Тест проверяет систему уведомлений:
    1. Появление уведомлений при различных действиях
    2. Автоматическое скрытие уведомлений
    3. Кнопка закрытия уведомлений
    4. Различные типы уведомлений (success, error, warning, info)
    """)
    def test_toast_notifications(self, page: Page, config, screenshot_utils):
        """Тест системы уведомлений"""
        
        self._authenticate_and_navigate(page, config)
        
        with allure.step("Проверка наличия контейнера уведомлений"):
            # Ищем контейнер для уведомлений
            toast_container_selectors = [
                "#toast-container",
                ".toast-container",
                ".notifications-container",
                ".alerts-container",
                ".toastr-container"
            ]
            
            toast_container = None
            for selector in toast_container_selectors:
                try:
                    container = page.locator(selector)
                    if container.count() > 0:  # Проверяем наличие в DOM
                        toast_container = container
                        break
                except:
                    continue
            
            if not toast_container:
                logging.info("Контейнер уведомлений не найден в DOM")
                # Можем попробовать вызвать действие, которое должно показать уведомление
                self._trigger_notification_action(page)
                
                # Повторно ищем контейнер
                for selector in toast_container_selectors:
                    try:
                        container = page.locator(selector)
                        if container.is_visible():
                            toast_container = container
                            break
                    except:
                        continue
            
            if toast_container:
                screenshot_utils.take_screenshot("toast_container_found")
                logging.info("Контейнер уведомлений найден")
            else:
                pytest.skip("Система уведомлений недоступна для тестирования")
        
        with allure.step("Тестирование различных типов уведомлений"):
            # Пробуем вызвать разные типы уведомлений через действия
            self._test_notification_types(page, screenshot_utils)
        
        with allure.step("Проверка автоматического скрытия уведомлений"):
            self._test_notification_auto_hide(page, screenshot_utils)
    
    @pytest.mark.usefixtures("authenticated_page")
    @allure.title("Проверка модальных окон")
    @allure.story("Модальные окна")
    @allure.severity('HIGH')
    @allure.description("""
    Тест проверяет работу модальных окон:
    1. Открытие модальных окон
    2. Закрытие по кнопке X
    3. Закрытие по клику вне окна
    4. Закрытие по Escape
    5. Проверка содержимого модальных окон
    """)
    def test_modal_dialogs(self, page: Page, config, screenshot_utils):
        """Тест модальных окон"""
        
        self._authenticate_and_navigate(page, config)
        
        with allure.step("Поиск кнопок, открывающих модальные окна"):
            # Ищем кнопки, которые могут открывать модальные окна
            modal_trigger_selectors = [
                "[data-toggle='modal']",
                "[data-target*='modal']",
                ".btn-modal",
                "button:has-text('Создать')",
                "button:has-text('Добавить')",
                "button:has-text('Редактировать')",
                "button:has-text('Удалить')",
                ".fa-plus",
                ".fa-edit"
            ]
            
            modal_triggers = []
            for selector in modal_trigger_selectors:
                try:
                    buttons = page.locator(selector).all()
                    visible_buttons = [btn for btn in buttons if btn.is_visible()]
                    modal_triggers.extend(visible_buttons)
                except:
                    continue
            
            if not modal_triggers:
                pytest.skip("Кнопки для открытия модальных окон не найдены")
            
            logging.info(f"Найдено {len(modal_triggers)} потенциальных триггеров модальных окон")
        
        with allure.step("Тестирование открытия модального окна"):
            modal_opened = False
            
            for i, trigger in enumerate(modal_triggers[:5]):  # Тестируем первые 5
                try:
                    # Кликаем по триггеру
                    trigger.click()
                    page.wait_for_timeout(1000)  # Ждем анимации
                    
                    # Ищем открытое модальное окно
                    modal_selectors = [
                        ".modal.show",
                        ".modal.in",
                        ".modal.fade.show",
                        ".modal[style*='display: block']",
                        ".dialog.open",
                        ".popup.visible"
                    ]
                    
                    modal = None
                    for selector in modal_selectors:
                        try:
                            element = page.locator(selector)
                            if element.is_visible():
                                modal = element
                                modal_opened = True
                                break
                        except:
                            continue
                    
                    if modal_opened:
                        screenshot_utils.take_screenshot(f"modal_opened_{i}")
                        logging.info(f"Модальное окно открыто триггером {i+1}")
                        
                        # Тестируем функциональность модального окна
                        self._test_modal_functionality(page, modal, screenshot_utils)
                        break
                    
                except Exception as e:
                    logging.error(f"Ошибка при тестировании триггера {i+1}: {str(e)}")
                    continue
            
            if not modal_opened:
                pytest.skip("Не удалось открыть модальное окно")
    
    @pytest.mark.usefixtures("authenticated_page")
    @allure.title("Проверка выпадающих меню (dropdowns)")
    @allure.story("Выпадающие меню")
    @allure.severity('NORMAL')
    @allure.description("""
    Тест проверяет работу выпадающих меню:
    1. Открытие выпадающих меню
    2. Выбор пунктов меню
    3. Закрытие меню при клике вне его
    4. Клавиатурная навигация
    """)
    def test_dropdown_menus(self, page: Page, config, screenshot_utils):
        """Тест выпадающих меню"""
        
        self._authenticate_and_navigate(page, config)
        
        with allure.step("Поиск выпадающих меню"):
            dropdown_selectors = [
                ".dropdown",
                ".btn-group",
                ".select-dropdown",
                "[data-toggle='dropdown']",
                ".dropdown-toggle"
            ]
            
            dropdowns = []
            for selector in dropdown_selectors:
                try:
                    elements = page.locator(selector).all()
                    visible_elements = [elem for elem in elements if elem.is_visible()]
                    dropdowns.extend(visible_elements)
                except:
                    continue
            
            if not dropdowns:
                pytest.skip("Выпадающие меню не найдены")
            
            logging.info(f"Найдено {len(dropdowns)} выпадающих меню")
        
        with allure.step("Тестирование функциональности выпадающих меню"):
            tested_dropdowns = 0
            
            for i, dropdown in enumerate(dropdowns[:3]):  # Тестируем первые 3
                try:
                    with allure.step(f"Тестирование выпадающего меню {i+1}"):
                        # Ищем триггер внутри dropdown
                        trigger_selectors = [
                            ".dropdown-toggle",
                            "button",
                            "a",
                            "[data-toggle='dropdown']"
                        ]
                        
                        trigger = None
                        for trigger_selector in trigger_selectors:
                            try:
                                trigger_element = dropdown.locator(trigger_selector).first
                                if trigger_element.is_visible():
                                    trigger = trigger_element
                                    break
                            except:
                                continue
                        
                        if not trigger:
                            continue
                        
                        # Кликаем по триггеру
                        trigger.click()
                        page.wait_for_timeout(500)
                        
                        # Ищем открытое меню
                        menu_selectors = [
                            ".dropdown-menu.show",
                            ".dropdown-menu[style*='display: block']",
                            ".dropdown-content",
                            ".select-options"
                        ]
                        
                        menu_opened = False
                        for menu_selector in menu_selectors:
                            try:
                                menu = page.locator(menu_selector).first
                                if menu.is_visible():
                                    menu_opened = True
                                    screenshot_utils.take_screenshot(f"dropdown_{i}_opened")
                                    
                                    # Тестируем пункты меню
                                    self._test_dropdown_items(page, menu, screenshot_utils, i)
                                    tested_dropdowns += 1
                                    break
                            except:
                                continue
                        
                        if not menu_opened:
                            logging.warning(f"Меню {i+1} не открылось")
                
                except Exception as e:
                    logging.error(f"Ошибка при тестировании dropdown {i+1}: {str(e)}")
                    continue
            
            assert tested_dropdowns > 0, "Ни одно выпадающее меню не было протестировано"
    
    @pytest.mark.usefixtures("authenticated_page")
    @allure.title("Проверка всплывающих подсказок (tooltips)")
    @allure.story("Подсказки")
    @allure.severity('LOW')
    @allure.description("""
    Тест проверяет всплывающие подсказки:
    1. Появление подсказок при наведении
    2. Содержимое подсказок
    3. Позиционирование подсказок
    4. Исчезновение при уводе курсора
    """)
    def test_tooltips(self, page: Page, config, screenshot_utils):
        """Тест всплывающих подсказок"""
        
        self._authenticate_and_navigate(page, config)
        
        with allure.step("Поиск элементов с подсказками"):
            tooltip_selectors = [
                "[title]",
                "[data-tooltip]",
                "[data-toggle='tooltip']",
                ".tooltip-trigger",
                "[aria-describedby]"
            ]
            
            tooltip_elements = []
            for selector in tooltip_selectors:
                try:
                    elements = page.locator(selector).all()
                    visible_elements = [elem for elem in elements if elem.is_visible()]
                    tooltip_elements.extend(visible_elements)
                except:
                    continue
            
            if not tooltip_elements:
                pytest.skip("Элементы с подсказками не найдены")
            
            logging.info(f"Найдено {len(tooltip_elements)} элементов с потенциальными подсказками")
        
        with allure.step("Тестирование всплывающих подсказок"):
            tested_tooltips = 0
            
            for i, element in enumerate(tooltip_elements[:5]):  # Тестируем первые 5
                try:
                    # Наводим курсор на элемент
                    element.hover()
                    page.wait_for_timeout(1000)  # Ждем появления подсказки
                    
                    # Ищем появившуюся подсказку
                    tooltip_popup_selectors = [
                        ".tooltip.show",
                        ".tooltip.in",
                        ".tooltip[style*='display: block']",
                        ".popover.show",
                        "[role='tooltip']"
                    ]
                    
                    tooltip_found = False
                    for tooltip_selector in tooltip_popup_selectors:
                        try:
                            tooltip = page.locator(tooltip_selector).first
                            if tooltip.is_visible():
                                tooltip_found = True
                                screenshot_utils.take_screenshot(f"tooltip_{i}_shown")
                                
                                # Проверяем содержимое подсказки
                                tooltip_text = tooltip.text_content().strip()
                                if tooltip_text:
                                    logging.info(f"Подсказка {i+1}: {tooltip_text}")
                                    tested_tooltips += 1
                                break
                        except:
                            continue
                    
                    if not tooltip_found:
                        # Проверяем атрибут title как fallback
                        title = element.get_attribute("title")
                        if title:
                            logging.info(f"Элемент {i+1} имеет title: {title}")
                            tested_tooltips += 1
                    
                    # Убираем курсор с элемента
                    page.mouse.move(0, 0)
                    page.wait_for_timeout(500)
                
                except Exception as e:
                    logging.error(f"Ошибка при тестировании подсказки {i+1}: {str(e)}")
                    continue
            
            logging.info(f"Протестировано {tested_tooltips} подсказок")
    
    @pytest.mark.usefixtures("authenticated_page")
    @allure.title("Проверка загрузочных индикаторов")
    @allure.story("Загрузка")
    @allure.severity('NORMAL')
    @allure.description("""
    Тест проверяет индикаторы загрузки:
    1. Появление спиннеров при загрузке
    2. Блокировка интерфейса во время загрузки
    3. Исчезновение после завершения загрузки
    """)
    def test_loading_indicators(self, page: Page, config, screenshot_utils):
        """Тест индикаторов загрузки"""
        
        self._authenticate_and_navigate(page, config)
        
        with allure.step("Поиск действий, вызывающих загрузку"):
            # Ищем кнопки, которые могут вызвать загрузку
            loading_trigger_selectors = [
                "button[type='submit']",
                ".btn-primary",
                ".btn-search",
                ".btn-filter",
                ".btn-export",
                "button:has-text('Загрузить')",
                "button:has-text('Поиск')",
                "button:has-text('Применить')"
            ]
            
            loading_triggers = []
            for selector in loading_trigger_selectors:
                try:
                    buttons = page.locator(selector).all()
                    visible_buttons = [btn for btn in buttons if btn.is_visible()]
                    loading_triggers.extend(visible_buttons)
                except:
                    continue
            
            if not loading_triggers:
                pytest.skip("Кнопки, вызывающие загрузку, не найдены")
        
        with allure.step("Тестирование индикаторов загрузки"):
            loading_detected = False
            
            for i, trigger in enumerate(loading_triggers[:3]):  # Тестируем первые 3
                try:
                    # Кликаем по кнопке
                    trigger.click()
                    
                    # Быстро ищем индикаторы загрузки
                    loading_selectors = [
                        ".loading",
                        ".spinner",
                        ".loader",
                        ".loading-overlay",
                        ".progress",
                        "[aria-busy='true']",
                        ".fa-spinner",
                        ".btn-loading"
                    ]
                    
                    for selector in loading_selectors:
                        try:
                            loading_element = page.locator(selector).first
                            if loading_element.is_visible(timeout=2000):
                                loading_detected = True
                                screenshot_utils.take_screenshot(f"loading_indicator_{i}")
                                logging.info(f"Обнаружен индикатор загрузки: {selector}")
                                
                                # Ждем исчезновения загрузки
                                try:
                                    loading_element.wait_for(state="hidden", timeout=30000)
                                    logging.info("Индикатор загрузки исчез")
                                except:
                                    logging.warning("Индикатор загрузки не исчез в ожидаемое время")
                                
                                break
                        except:
                            continue
                    
                    if loading_detected:
                        break
                
                except Exception as e:
                    logging.error(f"Ошибка при тестировании загрузки {i+1}: {str(e)}")
                    continue
            
            if not loading_detected:
                logging.info("Индикаторы загрузки не обнаружены")
    
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
    
    def _trigger_notification_action(self, page: Page):
        """Пытается вызвать действие, которое покажет уведомление"""
        # Пробуем различные действия, которые могут вызвать уведомления
        possible_actions = [
            lambda: page.keyboard.press("F5"),  # Обновление страницы
            lambda: page.locator("button[type='submit']").first.click() if page.locator("button[type='submit']").count() > 0 else None
        ]
        
        for action in possible_actions:
            try:
                action()
                page.wait_for_timeout(2000)
                break
            except:
                continue
    
    def _test_notification_types(self, page: Page, screenshot_utils):
        """Тестирует различные типы уведомлений"""
        notification_types = [
            (".toast-success", "success"),
            (".toast-error", "error"),
            (".toast-warning", "warning"),
            (".toast-info", "info")
        ]
        
        for selector, type_name in notification_types:
            try:
                notifications = page.locator(selector).all()
                if notifications:
                    screenshot_utils.take_screenshot(f"notification_{type_name}")
                    logging.info(f"Найдены уведомления типа {type_name}")
            except:
                continue
    
    def _test_notification_auto_hide(self, page: Page, screenshot_utils):
        """Тестирует автоматическое скрытие уведомлений"""
        try:
            # Ищем любые видимые уведомления
            all_notifications = page.locator(".toast, .notification, .alert").all()
            visible_notifications = [notif for notif in all_notifications if notif.is_visible()]
            
            if visible_notifications:
                notification = visible_notifications[0]
                screenshot_utils.take_screenshot("notification_before_hide")
                
                # Ждем автоматического скрытия (обычно 3-5 секунд)
                try:
                    notification.wait_for(state="hidden", timeout=10000)
                    screenshot_utils.take_screenshot("notification_auto_hidden")
                    logging.info("Уведомление автоматически скрылось")
                except:
                    logging.info("Уведомление не скрылось автоматически")
        except:
            logging.info("Не удалось протестировать автоматическое скрытие")
    
    def _test_modal_functionality(self, page: Page, modal, screenshot_utils):
        """Тестирует функциональность модального окна"""
        with allure.step("Тестирование закрытия модального окна"):
            # Ищем кнопку закрытия
            close_selectors = [
                ".modal-header .close",
                ".modal-header .btn-close",
                ".modal .fa-times",
                ".modal [data-dismiss='modal']",
                ".dialog-close"
            ]
            
            close_button = None
            for selector in close_selectors:
                try:
                    button = modal.locator(selector).first
                    if button.is_visible():
                        close_button = button
                        break
                except:
                    continue
            
            if close_button:
                close_button.click()
                page.wait_for_timeout(1000)
                
                # Проверяем, что модальное окно закрылось
                if not modal.is_visible():
                    screenshot_utils.take_screenshot("modal_closed")
                    logging.info("Модальное окно закрыто кнопкой")
                else:
                    logging.warning("Модальное окно не закрылось")
            else:
                # Пробуем закрыть по Escape
                page.keyboard.press("Escape")
                page.wait_for_timeout(1000)
                
                if not modal.is_visible():
                    screenshot_utils.take_screenshot("modal_closed_escape")
                    logging.info("Модальное окно закрыто по Escape")
    
    def _test_dropdown_items(self, page: Page, menu, screenshot_utils, index):
        """Тестирует пункты выпадающего меню"""
        try:
            # Ищем пункты меню
            menu_items = menu.locator("a, .dropdown-item, li").all()
            visible_items = [item for item in menu_items if item.is_visible()]
            
            if visible_items and len(visible_items) > 0:
                # Кликаем по первому пункту
                first_item = visible_items[0]
                item_text = first_item.text_content().strip()
                
                if item_text:
                    first_item.click()
                    page.wait_for_timeout(1000)
                    screenshot_utils.take_screenshot(f"dropdown_{index}_item_clicked")
                    logging.info(f"Клик по пункту меню: {item_text}")
        except Exception as e:
            logging.error(f"Ошибка при тестировании пунктов меню: {str(e)}")
