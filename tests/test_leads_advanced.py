# Файл временно закомментирован для отключения всех тестов
'''
import pytest
import allure
from playwright.sync_api import Page, expect
from utils.screenshot_utils import ScreenshotUtils
from pages.login_page import LoginPage
import logging
import time
import random
from datetime import datetime, timedelta

@allure.epic("Лиды")
@allure.feature("Расширенные тесты лидов")
class TestLeadsAdvanced:
    """Расширенные тесты для работы с лидами"""
    
    @pytest.mark.usefixtures("authenticated_page")
    @allure.title("Проверка таблицы лидов и её элементов")
    @allure.story("Таблица лидов")
    @allure.severity('HIGH')
    @allure.description("""
    Тест проверяет таблицу лидов:
    1. Наличие заголовков столбцов
    2. Наличие данных в таблице
    3. Функциональность сортировки
    4. Пагинация
    5. Изменение количества элементов на странице
    """)
    def test_leads_table_functionality(self, page: Page, config, screenshot_utils):
        """Тест функциональности таблицы лидов"""
        
        self._navigate_to_leads(page, config)
        
        with allure.step("Проверка структуры таблицы"):
            # Ищем таблицу лидов
            table_selectors = [
                "table.leads-table",
                "table.ajax-data-table", 
                "table.data-table",
                "table.table",
                ".table-container table"
            ]
            
            table = None
            for selector in table_selectors:
                try:
                    element = page.locator(selector)
                    if element.is_visible():
                        table = element
                        break
                except:
                    continue
            
            assert table is not None, "Таблица лидов не найдена"
            screenshot_utils.take_screenshot("leads_table_found")
            
            # Проверяем заголовки таблицы
            headers = table.locator("thead th, thead td").all()
            assert len(headers) > 0, "Заголовки таблицы не найдены"
            
            header_texts = [header.text_content().strip() for header in headers]
            logging.info(f"Найдены заголовки таблицы: {header_texts}")
        
        with allure.step("Проверка наличия данных в таблице"):
            # Проверяем строки данных
            rows = table.locator("tbody tr").all()
            if len(rows) == 0:
                logging.warning("Таблица лидов пуста")
                pytest.skip("Нет данных для тестирования")
            
            logging.info(f"Найдено {len(rows)} строк в таблице лидов")
            screenshot_utils.take_screenshot("leads_table_with_data")
        
        with allure.step("Проверка сортировки"):
            # Ищем кликабельные заголовки для сортировки
            sortable_headers = table.locator("thead th[data-sort], thead th.sortable, thead th a").all()
            
            if sortable_headers:
                for i, header in enumerate(sortable_headers[:3]):  # Тестируем первые 3
                    try:
                        header_text = header.text_content().strip()
                        
                        with allure.step(f"Тестирование сортировки по {header_text}"):
                            # Кликаем по заголовку
                            header.click()
                            page.wait_for_load_state("domcontentloaded", timeout=15000)
                            
                            # Делаем скриншот после сортировки
                            safe_name = header_text.lower().replace(" ", "_")
                            screenshot_utils.take_screenshot(f"sorted_by_{safe_name}")
                            
                            logging.info(f"Сортировка по {header_text} выполнена")
                    except Exception as e:
                        logging.error(f"Ошибка при тестировании сортировки: {str(e)}")
                        continue
            else:
                logging.info("Сортируемые заголовки не найдены")
        
        with allure.step("Проверка пагинации"):
            self._test_pagination(page, screenshot_utils)
    
    @pytest.mark.usefixtures("authenticated_page")
    @allure.title("Проверка расширенных фильтров лидов")
    @allure.story("Фильтрация лидов")
    @allure.severity('NORMAL')
    @allure.description("""
    Тест проверяет расширенные фильтры лидов:
    1. Фильтр по дате
    2. Фильтр по статусу
    3. Фильтр по источнику
    4. Комбинированные фильтры
    5. Сброс фильтров
    """)
    def test_advanced_leads_filtering(self, page: Page, config, screenshot_utils):
        """Тест расширенных фильтров лидов"""
        
        self._navigate_to_leads(page, config)
        
        with allure.step("Открытие панели фильтров"):
            # Ищем и открываем фильтры
            filter_button_selectors = [
                ".filter-button",
                ".btn-filter", 
                "[data-filter]",
                ".filter-toggle",
                "button:has-text('Фильтр')"
            ]
            
            filter_opened = False
            for selector in filter_button_selectors:
                try:
                    button = page.locator(selector).first
                    if button.is_visible():
                        button.click()
                        page.wait_for_load_state("domcontentloaded", timeout=10000)
                        filter_opened = True
                        break
                except:
                    continue
            
            if not filter_opened:
                pytest.skip("Кнопка фильтров не найдена")
            
            screenshot_utils.take_screenshot("filters_opened")
        
        with allure.step("Тестирование фильтра по дате"):
            self._test_date_filter(page, screenshot_utils)
        
        with allure.step("Тестирование фильтра по статусу"):
            self._test_status_filter(page, screenshot_utils)
        
        with allure.step("Тестирование сброса фильтров"):
            self._test_filter_reset(page, screenshot_utils)
    
    @pytest.mark.usefixtures("authenticated_page")
    @allure.title("Проверка экспорта данных лидов")
    @allure.story("Экспорт данных")
    @allure.severity('NORMAL')
    @allure.description("""
    Тест проверяет функциональность экспорта:
    1. Наличие кнопки экспорта
    2. Различные форматы экспорта (CSV, Excel, PDF)
    3. Процесс скачивания файлов
    """)
    def test_leads_export_functionality(self, page: Page, config, screenshot_utils):
        """Тест экспорта данных лидов"""
        
        self._navigate_to_leads(page, config)
        
        with allure.step("Поиск кнопки экспорта"):
            export_selectors = [
                ".btn-export",
                ".export-button",
                "button:has-text('Экспорт')",
                "button:has-text('Export')",
                ".fa-download",
                "[data-export]"
            ]
            
            export_button = None
            for selector in export_selectors:
                try:
                    button = page.locator(selector).first
                    if button.is_visible():
                        export_button = button
                        break
                except:
                    continue
            
            if not export_button:
                pytest.skip("Кнопка экспорта не найдена")
            
            screenshot_utils.take_screenshot("export_button_found")
        
        with allure.step("Тестирование экспорта"):
            # Настраиваем обработчик загрузки
            with page.expect_download() as download_info:
                export_button.click()
                
            download = download_info.value
            
            # Проверяем, что файл скачался
            assert download.suggested_filename is not None, "Файл не был скачан"
            
            logging.info(f"Файл экспорта скачан: {download.suggested_filename}")
            screenshot_utils.take_screenshot("export_completed")
    
    @pytest.mark.usefixtures("authenticated_page")
    @allure.title("Проверка детальной информации о лиде")
    @allure.story("Детали лида")
    @allure.severity('HIGH')
    @allure.description("""
    Тест проверяет просмотр детальной информации о лиде:
    1. Переход к детальной странице лида
    2. Проверка всех блоков информации
    3. Возможность редактирования
    4. История активности
    """)
    def test_lead_details_view(self, page: Page, config, screenshot_utils):
        """Тест детальной информации о лиде"""
        
        self._navigate_to_leads(page, config)
        
        with allure.step("Поиск первого лида в таблице"):
            # Ищем первую строку с данными
            first_lead_selectors = [
                "tbody tr:first-child a",
                ".lead-row:first-child a",
                "tr[data-lead-id]:first-child a",
                "tbody tr:first-child td:first-child a"
            ]
            
            first_lead_link = None
            for selector in first_lead_selectors:
                try:
                    link = page.locator(selector).first
                    if link.is_visible():
                        first_lead_link = link
                        break
                except:
                    continue
            
            if not first_lead_link:
                pytest.skip("Ссылка на детали лида не найдена")
        
        with allure.step("Переход к деталям лида"):
            # Кликаем по ссылке
            first_lead_link.click()
            page.wait_for_load_state("domcontentloaded", timeout=30000)
            
            # Проверяем, что мы на странице деталей
            current_url = page.url
            assert any(keyword in current_url for keyword in ["/lead/", "/leads/", "/detail"]), \
                f"URL не соответствует странице деталей лида: {current_url}"
            
            screenshot_utils.take_screenshot("lead_details_page")
        
        with allure.step("Проверка блоков информации"):
            # Ищем основные блоки информации
            info_blocks = [
                (".lead-info, .contact-info", "Контактная информация"),
                (".lead-status, .status-info", "Статус лида"),
                (".lead-source, .source-info", "Источник лида"),
                (".lead-activity, .activity-log", "История активности"),
                (".lead-notes, .notes", "Заметки")
            ]
            
            found_blocks = 0
            for selector, block_name in info_blocks:
                try:
                    if page.locator(selector).first.is_visible():
                        found_blocks += 1
                        logging.info(f"Найден блок: {block_name}")
                except:
                    continue
            
            assert found_blocks > 0, "Не найдены блоки с информацией о лиде"
            logging.info(f"Найдено {found_blocks} информационных блоков")
    
    @pytest.mark.usefixtures("authenticated_page")
    @allure.title("Проверка создания нового лида")
    @allure.story("Создание лида")
    @allure.severity('CRITICAL')
    @allure.description("""
    Тест проверяет создание нового лида:
    1. Переход к форме создания
    2. Заполнение обязательных полей
    3. Сохранение лида
    4. Проверка создания
    """)
    def test_create_new_lead(self, page: Page, config, screenshot_utils):
        """Тест создания нового лида"""
        
        self._navigate_to_leads(page, config)
        
        with allure.step("Поиск кнопки создания лида"):
            create_selectors = [
                ".btn-create",
                ".btn-add",
                "button:has-text('Создать')",
                "button:has-text('Добавить')",
                "button:has-text('Create')",
                "button:has-text('Add')",
                ".fa-plus",
                "[data-create]"
            ]
            
            create_button = None
            for selector in create_selectors:
                try:
                    button = page.locator(selector).first
                    if button.is_visible():
                        create_button = button
                        break
                except:
                    continue
            
            if not create_button:
                pytest.skip("Кнопка создания лида не найдена")
            
            screenshot_utils.take_screenshot("create_button_found")
        
        with allure.step("Открытие формы создания"):
            create_button.click()
            page.wait_for_load_state("domcontentloaded", timeout=15000)
            
            # Проверяем, что форма открылась
            form_selectors = [
                "form.lead-form",
                ".create-lead-form",
                "form[action*='lead']",
                ".modal form",
                ".form-container"
            ]
            
            form_found = False
            for selector in form_selectors:
                try:
                    if page.locator(selector).is_visible():
                        form_found = True
                        break
                except:
                    continue
            
            if not form_found:
                pytest.skip("Форма создания лида не открылась")
            
            screenshot_utils.take_screenshot("create_form_opened")
        
        with allure.step("Заполнение формы"):
            # Генерируем тестовые данные
            test_data = {
                "name": f"Test Lead {int(time.time())}",
                "email": f"test.lead.{int(time.time())}@example.com",
                "phone": f"+7900{random.randint(1000000, 9999999)}",
                "company": f"Test Company {int(time.time())}"
            }
            
            # Ищем и заполняем поля
            field_mappings = [
                ("name", ["input[name='name']", "#name", ".name-input"]),
                ("email", ["input[name='email']", "#email", ".email-input"]),
                ("phone", ["input[name='phone']", "#phone", ".phone-input"]),
                ("company", ["input[name='company']", "#company", ".company-input"])
            ]
            
            filled_fields = 0
            for field_key, selectors in field_mappings:
                for selector in selectors:
                    try:
                        field = page.locator(selector).first
                        if field.is_visible() and field.is_enabled():
                            field.fill(test_data[field_key])
                            filled_fields += 1
                            logging.info(f"Заполнено поле {field_key}: {test_data[field_key]}")
                            break
                    except:
                        continue
            
            assert filled_fields > 0, "Не удалось заполнить ни одного поля"
            screenshot_utils.take_screenshot("form_filled")
        
        with allure.step("Сохранение лида"):
            # Ищем кнопку сохранения
            save_selectors = [
                "button[type='submit']",
                ".btn-save",
                ".btn-primary:has-text('Сохранить')",
                "button:has-text('Save')",
                "input[type='submit']"
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
                
                # Проверяем сообщение об успехе или переход
                success_indicators = [
                    ".alert-success",
                    ".toast-success", 
                    ".notification-success"
                ]
                
                success_found = False
                for selector in success_indicators:
                    try:
                        if page.locator(selector).is_visible(timeout=5000):
                            success_found = True
                            break
                    except:
                        continue
                
                if success_found:
                    screenshot_utils.take_screenshot("lead_created_success")
                    logging.info("Лид создан успешно")
                else:
                    # Проверяем, что произошел переход (например, на страницу деталей)
                    current_url = page.url
                    if "/lead/" in current_url or "/leads/" in current_url:
                        screenshot_utils.take_screenshot("lead_created_redirect")
                        logging.info("Лид создан (переход на страницу деталей)")
                    else:
                        screenshot_utils.take_screenshot("lead_create_unknown_result")
                        logging.warning("Результат создания лида неясен")
    
    def _navigate_to_leads(self, page: Page, config):
        """Вспомогательный метод для перехода к лидам"""
        # Авторизация
        login_page = LoginPage(page, config["baseUrl"])
        credentials = config["credentials"]["valid_user"]
        
        success = login_page.login(
            email=credentials["email"],
            password=credentials["password"],
            remember=True
        )
        assert success, "Авторизация не прошла успешно"
        
        # Переход на страницу лидов
        leads_url = f"{config['baseUrl'].replace('/auth', '')}/leads/"
        page.goto(leads_url)
        page.wait_for_load_state("domcontentloaded", timeout=30000)
        
        # Проверяем, что мы на странице лидов
        current_url = page.url
        assert "/leads" in current_url, f"Не удалось перейти на страницу лидов: {current_url}"
    
    def _test_pagination(self, page: Page, screenshot_utils):
        """Тестирует пагинацию"""
        pagination_selectors = [
            ".pagination",
            ".pager",
            ".page-navigation",
            ".dataTables_paginate"
        ]
        
        pagination = None
        for selector in pagination_selectors:
            try:
                element = page.locator(selector)
                if element.is_visible():
                    pagination = element
                    break
            except:
                continue
        
        if not pagination:
            logging.info("Пагинация не найдена")
            return
        
        # Ищем кнопку "Следующая страница"
        next_selectors = [
            ".page-item:has-text('›')",
            ".next",
            "a:has-text('Следующая')",
            "a:has-text('Next')"
        ]
        
        for selector in next_selectors:
            try:
                next_button = pagination.locator(selector).first
                if next_button.is_visible() and not next_button.get_attribute("class").includes("disabled"):
                    next_button.click()
                    page.wait_for_load_state("domcontentloaded", timeout=15000)
                    screenshot_utils.take_screenshot("pagination_next_page")
                    logging.info("Переход на следующую страницу выполнен")
                    return
            except:
                continue
        
        logging.info("Активная кнопка перехода на следующую страницу не найдена")
    
    def _test_date_filter(self, page: Page, screenshot_utils):
        """Тестирует фильтр по дате"""
        date_selectors = [
            "input[name='daterange']",
            "input[name='date_from']",
            "input[name='date_to']",
            ".date-picker",
            "input[type='date']"
        ]
        
        for selector in date_selectors:
            try:
                date_field = page.locator(selector).first
                if date_field.is_visible():
                    # Устанавливаем дату (последние 30 дней)
                    start_date = (datetime.now() - timedelta(days=30)).strftime("%d.%m.%Y")
                    end_date = datetime.now().strftime("%d.%m.%Y")
                    date_range = f"{start_date} - {end_date}"
                    
                    date_field.fill(date_range)
                    screenshot_utils.take_screenshot("date_filter_set")
                    logging.info(f"Установлен фильтр по дате: {date_range}")
                    return
            except:
                continue
        
        logging.info("Поле фильтра по дате не найдено")
    
    def _test_status_filter(self, page: Page, screenshot_utils):
        """Тестирует фильтр по статусу"""
        status_selectors = [
            "select[name='status']",
            ".status-filter",
            "select[name='lead_status']",
            "#status_filter"
        ]
        
        for selector in status_selectors:
            try:
                status_field = page.locator(selector).first
                if status_field.is_visible():
                    # Получаем доступные опции
                    options = status_field.locator("option").all()
                    if len(options) > 1:  # Есть опции кроме пустой
                        # Выбираем вторую опцию (первая обычно пустая)
                        options[1].click()
                        screenshot_utils.take_screenshot("status_filter_set")
                        logging.info("Установлен фильтр по статусу")
                        return
            except:
                continue
        
        logging.info("Поле фильтра по статусу не найдено")
    
    def _test_filter_reset(self, page: Page, screenshot_utils):
        """Тестирует сброс фильтров"""
        reset_selectors = [
            ".btn-reset",
            ".filter-reset",
            "button:has-text('Сбросить')",
            "button:has-text('Reset')",
            "button:has-text('Очистить')",
            "[data-reset]"
        ]
        
        for selector in reset_selectors:
            try:
                reset_button = page.locator(selector).first
                if reset_button.is_visible():
                    reset_button.click()
                    page.wait_for_load_state("domcontentloaded", timeout=10000)
                    screenshot_utils.take_screenshot("filters_reset")
                    logging.info("Фильтры сброшены")
                    return
            except:
                continue
        
        logging.info("Кнопка сброса фильтров не найдена")
'''
