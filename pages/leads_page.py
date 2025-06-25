class LeadsPage(BasePage):
    """Страница лидов"""
    
    # Локаторы
    FILTER_BOX = ".filter-box"
    FILTER_HEADER = ".filter-header"
    FILTER_FORM = "#filter-m-form"
    FILTER_APPLY_BUTTON = "#filter-m-apply-btn"
    LEADS_TABLE = "table.leads-table"
    
    def __init__(self, page: Page, base_url: str = None):
        super().__init__(page, base_url)
        self.logger = logging.getLogger(__name__)
        
    def open_filters(self):
        """Открытие панели фильтров"""
        try:
            # Ждем появления кнопки фильтра
            self.page.wait_for_selector(self.FILTER_HEADER, state="visible", timeout=10000)
            
            # Проверяем, не открыты ли уже фильтры
            filter_box = self.page.locator(self.FILTER_BOX)
            if "show" not in filter_box.get_attribute("class"):
                # Кликаем по заголовку фильтра
                self.page.click(self.FILTER_HEADER)
                # Ждем открытия панели
                self.page.wait_for_selector(f"{self.FILTER_BOX}.show", timeout=5000)
            
            self.logger.info("Панель фильтров открыта")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка при открытии фильтров: {str(e)}")
            return False
            
    def apply_filters(self):
        """Применение фильтров"""
        try:
            # Ждем появления кнопки применения
            self.page.wait_for_selector(self.FILTER_APPLY_BUTTON, state="visible", timeout=5000)
            
            # Кликаем по кнопке
            self.page.click(self.FILTER_APPLY_BUTTON)
            
            # Ждем применения фильтров
            self.page.wait_for_load_state("networkidle")
            
            self.logger.info("Фильтры применены")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка при применении фильтров: {str(e)}")
            return False
            
    def is_leads_table_visible(self) -> bool:
        """Проверка видимости таблицы лидов"""
        try:
            return self.page.is_visible(self.LEADS_TABLE, timeout=5000)
        except Exception as e:
            self.logger.error(f"Ошибка при проверке таблицы лидов: {str(e)}")
            return False 