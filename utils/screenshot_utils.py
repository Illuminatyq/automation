import os
import shutil
import logging
from datetime import datetime, timedelta
from pathlib import Path
from playwright.sync_api import Page
import allure
from PIL import Image, ImageChops
import numpy as np
from config.constants import TEST_RESULTS_DIR, SCREENSHOT_CONFIG

logger = logging.getLogger(__name__)

class ScreenshotUtils:
    """Утилиты для создания и сравнения скриншотов"""
    
    def __init__(self, page: Page):
        self.page = page
        self.base_dir = TEST_RESULTS_DIR
        self.screenshot_dirs = {
            "baseline": self.base_dir / "screenshots" / "baseline",
            "actual": self.base_dir / "screenshots" / "actual", 
            "diff": self.base_dir / "screenshots" / "diff",
            "errors": self.base_dir / "screenshots" / "errors"
        }
        self.logger = logging.getLogger(self.__class__.__name__)
        self._create_directories()
        
        # Очищаем старые скриншоты при инициализации
        self.cleanup_old_screenshots()

    def _create_directories(self):
        """Создает необходимые директории для хранения скриншотов"""
        for directory in self.screenshot_dirs.values():
            directory.mkdir(parents=True, exist_ok=True)

    def _get_screenshot_path(self, name: str, screenshot_type: str) -> Path:
        """Возвращает путь для сохранения скриншота"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_{timestamp}.png"
        return self.screenshot_dirs[screenshot_type] / filename

    def _cleanup_temp_files(self, name: str):
        """Очищает временные файлы скриншотов"""
        temp_dir = self.base_dir / "temp"
        if temp_dir.exists():
            for file in temp_dir.glob(f"temp_{name}_*.png"):
                try:
                    file.unlink()
                except Exception as e:
                    self.logger.warning(f"Не удалось удалить временный файл {file}: {str(e)}")

    def _handle_screenshot_error(self, name: str, error: Exception) -> str:
        """Обрабатывает ошибки при создании скриншотов"""
        error_message = f"Ошибка при создании скриншота {name}: {str(error)}"
        self.logger.error(error_message)
        
        # Пытаемся создать скриншот ошибки
        try:
            error_path = self.save_error_screenshot(f"error_{name}")
            allure.attach(
                error_message,
                name="❌ Ошибка создания скриншота",
                attachment_type=allure.attachment_type.TEXT
            )
            return error_path
        except Exception as e:
            self.logger.error(f"Не удалось создать скриншот ошибки: {str(e)}")
            return ""

    def take_screenshot(self, name: str, screenshot_type: str = "actual") -> str:
        """Делает скриншот и сохраняет его"""
        try:
            path = self._get_screenshot_path(name, screenshot_type)
            
            # Делаем скриншот с настройками из конфигурации
            self.page.screenshot(path=str(path), **SCREENSHOT_CONFIG)
            
            # Добавляем в Allure отчет
            allure.attach.file(
                str(path), 
                name=f"📸 {name}", 
                attachment_type=allure.attachment_type.PNG
            )
            
            self.logger.info(f"Скриншот сохранен: {path}")
            return str(path)
            
        except Exception as e:
            return self._handle_screenshot_error(name, e)

    def compare_with_baseline(self, name: str, threshold: float = 0.1) -> bool:
        """Сравнивает текущий скриншот с базовым"""
        try:
            baseline_path = self.screenshot_dirs["baseline"] / f"{name}.png"
            actual_path = self.take_screenshot(name, "actual")
            
            if not actual_path:
                return False
                
            if not baseline_path.exists():
                # Если базового скриншота нет, создаем его
                shutil.copy2(actual_path, baseline_path)
                allure.attach.file(
                    str(baseline_path), 
                    name="📋 Создан базовый скриншот", 
                    attachment_type=allure.attachment_type.PNG
                )
                self.logger.info(f"Создан базовый скриншот: {baseline_path}")
                return True
            
            # Сравниваем скриншоты
            return self._compare_images(baseline_path, actual_path, name, threshold)
            
        except Exception as e:
            self.logger.error(f"Ошибка при сравнении скриншотов для {name}: {str(e)}")
            return False

    def _compare_images(self, baseline_path: Path, actual_path: str, name: str, threshold: float) -> bool:
        """Внутренний метод для сравнения изображений"""
        try:
            baseline = Image.open(baseline_path).convert('RGB')
            actual = Image.open(actual_path).convert('RGB')
            
            # Приводим к одинаковому размеру если нужно
            if baseline.size != actual.size:
                self.logger.warning(f"Размеры скриншотов различаются: {baseline.size} vs {actual.size}")
                
                # Изменяем размер actual изображения под baseline
                actual = actual.resize(baseline.size, Image.Resampling.LANCZOS)
            
            # Вычисляем различия
            diff = ImageChops.difference(baseline, actual)
            diff_array = np.array(diff)
            
            # Вычисляем процент различий
            total_pixels = diff_array.size
            different_pixels = np.count_nonzero(diff_array)
            diff_percentage = different_pixels / total_pixels
            
            self.logger.info(f"Различий в скриншоте {name}: {diff_percentage:.2%}")
            
            if diff_percentage > threshold:
                # Сохраняем diff изображение
                diff_path = self._get_screenshot_path(f"{name}_diff", "diff")
                diff.save(diff_path)
                
                # Добавляем в отчет
                allure.attach.file(
                    str(baseline_path), 
                    name="📋 Базовый скриншот", 
                    attachment_type=allure.attachment_type.PNG
                )
                allure.attach.file(
                    actual_path, 
                    name="📸 Текущий скриншот", 
                    attachment_type=allure.attachment_type.PNG
                )
                allure.attach.file(
                    str(diff_path), 
                    name="🔍 Различия", 
                    attachment_type=allure.attachment_type.PNG
                )
                allure.attach(
                    f"Процент различий: {diff_percentage:.2%}\nПорог: {threshold:.2%}",
                    name="📊 Статистика сравнения",
                    attachment_type=allure.attachment_type.TEXT
                )
                
                self.logger.warning(f"Превышен порог различий для {name}: {diff_percentage:.2%} > {threshold:.2%}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка при сравнении изображений: {str(e)}")
            return False

    def mask_dynamic_content(self, selectors: list):
        """Маскирует динамический контент на странице для стабильности скриншотов"""
        masked_count = 0
        
        for selector in selectors:
            try:
                elements = self.page.locator(selector)
                count = elements.count()
                
                if count > 0:
                    # Скрываем все найденные элементы
                    elements.evaluate_all("elements => elements.forEach(el => el.style.visibility = 'hidden')")
                    masked_count += count
                    self.logger.debug(f"Замаскировано {count} элементов по селектору: {selector}")
                    
            except Exception as e:
                self.logger.warning(f"Не удалось замаскировать элементы {selector}: {str(e)}")
        
        if masked_count > 0:
            self.logger.info(f"Замаскировано динамических элементов: {masked_count}")

    def save_error_screenshot(self, name: str) -> str:
        """Сохраняет скриншот при ошибке с улучшенным именованием"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            error_name = f"ERROR_{name}_{timestamp}"
            path = self.screenshot_dirs["errors"] / f"{error_name}.png"
            
            # Создаем скриншот
            self.page.screenshot(path=str(path), **SCREENSHOT_CONFIG)
            
            # Добавляем в отчет с эмодзи для лучшей визуализации
            allure.attach.file(
                str(path), 
                name=f"🚨 Ошибка: {name}", 
                attachment_type=allure.attachment_type.PNG
            )
            
            # Добавляем дополнительную информацию
            page_info = {
                "URL": self.page.url,
                "Заголовок": self.page.title(),
                "Время": datetime.now().isoformat(),
                "Размер окна": str(self.page.viewport_size)
            }
            
            allure.attach(
                "\n".join([f"{key}: {value}" for key, value in page_info.items()]),
                name="📋 Информация о странице",
                attachment_type=allure.attachment_type.TEXT
            )
            
            self.logger.error(f"Скриншот ошибки сохранен: {path}")
            return str(path)
            
        except Exception as e:
            self.logger.error(f"Не удалось сохранить скриншот ошибки: {str(e)}")
            return ""

    def cleanup_old_screenshots(self, days: int = 7):
        """Удаляет старые скриншоты для экономии места"""
        cutoff_date = datetime.now() - timedelta(days=days)
        deleted_count = 0
        
        # Очищаем только временные папки, не трогаем baseline
        cleanup_dirs = ["actual", "diff", "errors"]
        
        for dir_name in cleanup_dirs:
            directory = self.screenshot_dirs[dir_name]
            
            if not directory.exists():
                continue
                
            for file_path in directory.glob("*.png"):
                try:
                    file_date = datetime.fromtimestamp(file_path.stat().st_ctime)
                    
                    if file_date < cutoff_date:
                        file_path.unlink()
                        deleted_count += 1
                        self.logger.debug(f"Удален старый файл: {file_path}")
                        
                except Exception as e:
                    self.logger.warning(f"Ошибка при удалении файла {file_path}: {str(e)}")
        
        if deleted_count > 0:
            self.logger.info(f"Очистка завершена: удалено {deleted_count} старых файлов")

    def create_comparison_report(self, comparisons: list):
        """Создает отчет о сравнениях скриншотов"""
        try:
            report_path = self.base_dir / "screenshot_comparison_report.html"
            
            html_content = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Отчет сравнения скриншотов</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 20px; }
                    .comparison { border: 1px solid #ccc; margin: 10px 0; padding: 10px; }
                    .success { background-color: #d4edda; }
                    .failure { background-color: #f8d7da; }
                </style>
            </head>
            <body>
                <h1>📊 Отчет сравнения скриншотов</h1>
                <p>Создан: {}</p>
            """.format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            
            for comparison in comparisons:
                status_class = "success" if comparison["success"] else "failure"
                status_text = "✅ Успешно" if comparison["success"] else "❌ Различия найдены"
                
                html_content += f"""
                <div class="comparison {status_class}">
                    <h3>{comparison["name"]}</h3>
                    <p>Статус: {status_text}</p>
                    <p>Различий: {comparison.get("diff_percentage", "N/A")}</p>
                </div>
                """
            
            html_content += "</body></html>"
            
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            allure.attach.file(
                str(report_path),
                name="📊 Отчет сравнения скриншотов",
                attachment_type=allure.attachment_type.HTML
            )
            
            self.logger.info(f"Создан отчет сравнения: {report_path}")
            
        except Exception as e:
            self.logger.error(f"Ошибка при создании отчета: {str(e)}")

    def wait_for_stable_screenshot(self, name: str, max_attempts: int = 3, delay: float = 1.0) -> str:
        """Ждет стабилизации страницы перед созданием скриншота"""
        import time
        
        previous_screenshot = None
        
        for attempt in range(max_attempts):
            # Ждем между попытками
            if attempt > 0:
                time.sleep(delay)
            
            # Делаем временный скриншот
            temp_path = self.base_dir / "temp" / f"temp_{name}_{attempt}.png"
            temp_path.parent.mkdir(exist_ok=True)
            
            self.page.screenshot(path=str(temp_path), **SCREENSHOT_CONFIG)
            
            if previous_screenshot and self._images_are_identical(previous_screenshot, temp_path):
                # Страница стабилизировалась
                final_path = self.take_screenshot(name)
                self._cleanup_temp_files(name)
                self.logger.info(f"Страница стабилизировалась после {attempt + 1} попыток")
                return final_path
            
            previous_screenshot = temp_path
        
        # Если не удалось стабилизировать, возвращаем последний скриншот
        final_path = self.take_screenshot(name)
        self._cleanup_temp_files(name)
        self.logger.warning(f"Не удалось стабилизировать страницу за {max_attempts} попыток")
        return final_path

    def _images_are_identical(self, path1: Path, path2: Path, threshold: float = 0.01) -> bool:
        """Проверяет идентичность двух изображений"""
        try:
            img1 = Image.open(path1).convert('RGB')
            img2 = Image.open(path2).convert('RGB')
            
            if img1.size != img2.size:
                return False
            
            diff = ImageChops.difference(img1, img2)
            diff_array = np.array(diff)
            diff_percentage = np.count_nonzero(diff_array) / diff_array.size
            
            return diff_percentage < threshold
            
        except Exception as e:
            self.logger.error(f"Ошибка при сравнении изображений: {str(e)}")
            return False