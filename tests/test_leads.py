import pytest
import allure
from playwright.sync_api import Page, expect
from utils.screenshot_utils import ScreenshotUtils
import logging

@allure.epic("Управление лидами")
@allure.feature("Страница лидов")
class TestLeads:
    @allure.story("Проверка верстки страницы лидов")
    @allure.severity(allure.severity_level.NORMAL)
    @allure.description("""
    Проверка корректности отображения элементов на странице лидов.
    Тест демонстрирует разницу между ожидаемым и фактическим состоянием верстки.
    """)
    def test_leads_page_layout(self, page: Page, config, screenshot_utils):
        with allure.step("Подготовка: Авторизация и переход на страницу лидов"):
            # Авторизация
            page.goto(config['baseUrl'].rstrip('/'))  # Убираем trailing slash
            page.wait_for_load_state("domcontentloaded", timeout=60000)
            page.locator('input[name="email"]').fill(config['credentials']['valid_user']['email'])
            page.locator('input[name="password"]').fill(config['credentials']['valid_user']['password'])
            page.locator('button[type="submit"]').click()
            page.wait_for_load_state("networkidle")
            
            # Переход на страницу лидов через меню
            page.locator('a.sidebar-link:has-text("Лиды")').click()
            page.wait_for_load_state("networkidle")
            
            # Намеренно изменяем стили для демонстрации разницы
            page.evaluate("""
                () => {
                    // Смещаем таблицу лидов
                    const table = document.querySelector('.leads-table');
                    if (table) {
                        table.style.marginLeft = '50px';
                        table.style.transform = 'rotate(2deg)';
                    }
                    
                    // Изменяем цвет заголовков
                    const headers = document.querySelectorAll('.leads-table th');
                    headers.forEach(header => {
                        header.style.backgroundColor = '#ffcccc';
                        header.style.color = '#ff0000';
                    });
                    
                    // Смещаем кнопки действий
                    const actionButtons = document.querySelectorAll('.action-button');
                    actionButtons.forEach(button => {
                        button.style.marginTop = '20px';
                        button.style.transform = 'scale(1.2)';
                    });
                }
            """)
            
            # Делаем скриншот для сравнения
            screenshot_utils.save_error_screenshot("leads_page_layout")
            
            # Проверяем основные элементы
            with allure.step("Проверка: Наличие основных элементов"):
                try:
                    # Проверяем заголовок страницы
                    expect(page.locator('h1:has-text("Лиды")')).to_be_visible()
                    
                    # Проверяем таблицу лидов
                    table = page.locator('.leads-table')
                    expect(table).to_be_visible()
                    
                    # Проверяем кнопки действий
                    expect(page.locator('.action-button:has-text("Добавить лид")')).to_be_visible()
                    expect(page.locator('.action-button:has-text("Импорт")')).to_be_visible()
                    
                    # Проверяем фильтры
                    expect(page.locator('.filters-section')).to_be_visible()
                    
                except Exception as e:
                    screenshot_utils.save_error_screenshot("leads_page_elements_error")
                    pytest.fail(f"Ошибка при проверке элементов: {str(e)}")
            
            # Проверяем стили (намеренно создаем ошибки)
            with allure.step("Проверка: Стили элементов"):
                try:
                    # Проверяем отступы таблицы
                    table_style = page.evaluate("""
                        () => {
                            const table = document.querySelector('.leads-table');
                            return {
                                marginLeft: window.getComputedStyle(table).marginLeft,
                                transform: window.getComputedStyle(table).transform
                            };
                        }
                    """)
                    
                    # Намеренно создаем ошибку в проверке стилей
                    assert table_style['marginLeft'] == '0px', "Таблица смещена вправо"
                    assert table_style['transform'] == 'none', "Таблица повернута"
                    
                except AssertionError as e:
                    # Добавляем информацию о разнице в отчет
                    allure.attach(
                        f"""
                        Ожидаемые стили:
                        - marginLeft: 0px
                        - transform: none
                        
                        Фактические стили:
                        - marginLeft: {table_style['marginLeft']}
                        - transform: {table_style['transform']}
                        
                        Ошибка: {str(e)}
                        """,
                        name="Разница в стилях",
                        attachment_type=allure.attachment_type.TEXT
                    )
                    raise

    @allure.story("Проверка фильтрации лидов")
    @allure.severity(allure.severity_level.NORMAL)
    def test_leads_filtering(self, page: Page, config, screenshot_utils):
        with allure.step("Подготовка: Авторизация и переход на страницу лидов"):
            # Авторизация
            page.goto(config['baseUrl'].rstrip('/'))  # Убираем trailing slash
            page.wait_for_load_state("domcontentloaded", timeout=60000)
            page.locator('input[name="email"]').fill(config['credentials']['valid_user']['email'])
            page.locator('input[name="password"]').fill(config['credentials']['valid_user']['password'])
            page.locator('button[type="submit"]').click()
            page.wait_for_load_state("networkidle")
            
            # Переход на страницу лидов через меню
            page.locator('a.sidebar-link:has-text("Лиды")').click()
            page.wait_for_load_state("networkidle")
        
        with allure.step("Действие: Применение фильтров"):
            # Намеренно создаем проблему с фильтрами
            page.evaluate("""
                () => {
                    const filterInput = document.querySelector('.filter-input');
                    if (filterInput) {
                        filterInput.style.opacity = '0.5';
                        filterInput.style.pointerEvents = 'none';
                    }
                }
            """)
            
            try:
                # Пытаемся использовать фильтр
                page.locator('.filter-input').fill('Тестовый лид')
                page.locator('.apply-filter-button').click()
                
                # Проверяем результаты
                expect(page.locator('.leads-table')).to_contain_text('Тестовый лид')
            except Exception as e:
                screenshot_utils.save_error_screenshot("leads_filtering_error")
                pytest.fail(f"Ошибка при фильтрации: {str(e)}") 