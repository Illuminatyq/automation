"""
Утилиты для работы со скриншотами в тестах
"""
import os
import time
import shutil
import logging
from datetime import datetime, timedelta
from playwright.sync_api import Page
import allure
from PIL import Image, ImageChops
import numpy as np
from config.constants import SCREENSHOTS_DIR

class ScreenshotUtils:
    def __init__(self, page: Page):
        self.page = page
        self.base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test_results")
        self.screenshot_dirs = {
            "baseline": os.path.join(self.base_dir, "screenshots", "baseline"),
            "actual": os.path.join(self.base_dir, "screenshots", "actual"),
            "diff": os.path.join(self.base_dir, "screenshots", "diff"),
            "errors": os.path.join(self.base_dir, "screenshots", "errors")
        }
        self._create_directories()

    def _create_directories(self):
        """Создает необходимые директории для хранения скриншотов"""
        for directory in self.screenshot_dirs.values():
            os.makedirs(directory, exist_ok=True)

    def _get_screenshot_path(self, name: str, type: str) -> str:
        """Возвращает путь для сохранения скриншота"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return os.path.join(self.screenshot_dirs[type], f"{name}_{timestamp}.png")

    def take_screenshot(self, name: str, type: str = "actual") -> str:
        """Делает скриншот и сохраняет его"""
        path = self._get_screenshot_path(name, type)
        self.page.screenshot(path=path, full_page=True)
        allure.attach.file(path, f"Скриншот {name}", allure.attachment_type.PNG)
        return path

    def compare_with_baseline(self, name: str, threshold: float = 0.1) -> bool:
        """Сравнивает текущий скриншот с базовым"""
        baseline_path = os.path.join(self.screenshot_dirs["baseline"], f"{name}.png")
        actual_path = self.take_screenshot(name, "actual")
        
        if not os.path.exists(baseline_path):
            # Если базового скриншота нет, создаем его
            shutil.copy2(actual_path, baseline_path)
            allure.attach.file(baseline_path, "Создан базовый скриншот", allure.attachment_type.PNG)
            return True
            
        # Сравниваем скриншоты
        baseline = Image.open(baseline_path)
        actual = Image.open(actual_path)
        
        if baseline.size != actual.size:
            return False
            
        diff = ImageChops.difference(baseline, actual)
        diff_array = np.array(diff)
        diff_percentage = np.mean(diff_array > 0)
        
        if diff_percentage > threshold:
            # Сохраняем diff изображение
            diff_path = self._get_screenshot_path(name, "diff")
            diff.save(diff_path)
            allure.attach.file(diff_path, "Различия в скриншотах", allure.attachment_type.PNG)
            return False
            
        return True

    def mask_dynamic_content(self, selectors: list):
        """Маскирует динамический контент на странице"""
        for selector in selectors:
            elements = self.page.locator(selector).all()
            for element in elements:
                try:
                    element.evaluate("el => el.style.visibility = 'hidden'")
                except Exception as e:
                    logging.warning(f"Не удалось замаскировать элемент {selector}: {str(e)}")

    def cleanup_old_screenshots(self, days: int = 7):
        """Удаляет старые скриншоты"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        for directory in [self.screenshot_dirs["actual"], self.screenshot_dirs["diff"], self.screenshot_dirs["errors"]]:
            for filename in os.listdir(directory):
                filepath = os.path.join(directory, filename)
                file_date = datetime.fromtimestamp(os.path.getctime(filepath))
                
                if file_date < cutoff_date:
                    try:
                        os.remove(filepath)
                        logging.info(f"Удален старый файл: {filepath}")
                    except Exception as e:
                        logging.error(f"Ошибка при удалении файла {filepath}: {str(e)}")

    def save_error_screenshot(self, name: str):
        """Сохраняет скриншот при ошибке"""
        path = self._get_screenshot_path(name, "errors")
        self.page.screenshot(path=path, full_page=True)
        allure.attach.file(path, f"Скриншот ошибки: {name}", allure.attachment_type.PNG)
        return path 