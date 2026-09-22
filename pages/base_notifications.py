from playwright.sync_api import Page, expect
from typing import Optional, Literal
import logging
import time
import allure

class BaseNotifications:
    """Базовый класс для работы с toast-уведомлениями"""
    
    TOAST_SELECTORS = {
        'container': '#toast-container',
        'error': '.toast-error, .notification.error, .alert-error',
        'success': '.toast-success, .notification.success, .alert-success',
        'warning': '.toast-warning, .notification.warning, .alert-warning',
        'info': '.toast-info, .notification.info, .alert-info'
    }
    
    def __init__(self, page: Page):
        self.page = page
        self.logger = logging.getLogger(__name__)
    
    @allure.step("Ожидание появления уведомления типа: {notification_type}")
    def wait_for_notification(
        self, 
        notification_type: Literal['error', 'success', 'warning', 'info'] = 'error',
        timeout: int = 10000,
        expect_text: Optional[str] = None
    ) -> bool:
        """
        Усиленное ожидание появления уведомления с проверкой DOM и видимости
        
        Args:
            notification_type: Тип уведомления
            timeout: Таймаут ожидания в миллисекундах
            expect_text: Ожидаемый текст в уведомлении
        """
        try:
            # 1. Ждем появления контейнера toast'ов
            container_selector = self.TOAST_SELECTORS['container']
            self.page.wait_for_selector(container_selector, state='attached', timeout=timeout)
            
            # 2. Ждем появления конкретного типа уведомления
            notification_selector = self.TOAST_SELECTORS[notification_type]
            
            # Используем комбинированный селектор для более точного поиска
            full_selector = f"{container_selector} {notification_selector}"
            
            # Ждем появления элемента в DOM
            self.page.wait_for_selector(full_selector, state='attached', timeout=5000)
            
            # Ждем, пока элемент станет видимым
            notification = self.page.locator(full_selector).first
            expect(notification).to_be_visible(timeout=5000)
            
            # 3. Проверяем текст, если он указан
            if expect_text:
                expect(notification).to_contain_text(expect_text, timeout=3000)
            
            self.logger.info(f"Уведомление типа '{notification_type}' успешно найдено")
            return True
            
        except Exception as e:
            self.logger.warning(f"Уведомление типа '{notification_type}' не найдено: {str(e)}")
            self._debug_notifications_state()
            return False
    
    def get_notification_text(self, notification_type: Literal['error', 'success', 'warning', 'info'] = 'error') -> str:
        """Получение текста уведомления"""
        try:
            full_selector = f"{self.TOAST_SELECTORS['container']} {self.TOAST_SELECTORS[notification_type]}"
            notification = self.page.locator(full_selector).first
            return notification.text_content().strip() if notification.is_visible() else ""
        except Exception as e:
            self.logger.error(f"Ошибка при получении текста уведомления: {str(e)}")
            return ""
    
    def close_notification(self, notification_type: Literal['error', 'success', 'warning', 'info'] = 'error') -> bool:
        """Закрытие уведомления"""
        try:
            full_selector = f"{self.TOAST_SELECTORS['container']} {self.TOAST_SELECTORS[notification_type]}"
            close_button = self.page.locator(f"{full_selector} .close, {full_selector} .btn-close")
            
            if close_button.is_visible():
                close_button.click()
                # Ждем исчезновения уведомления
                expect(self.page.locator(full_selector)).to_be_hidden(timeout=3000)
                return True
            return False
        except Exception:
            return False
    
    def _debug_notifications_state(self):
        """Отладочная информация о состоянии уведомлений"""
        try:
            # Проверяем наличие контейнера
            container_exists = self.page.locator(self.TOAST_SELECTORS['container']).count() > 0
            self.logger.debug(f"Toast container exists: {container_exists}")
            
            # Проверяем все типы уведомлений
            for notif_type, selector in self.TOAST_SELECTORS.items():
                if notif_type == 'container':
                    continue
                count = self.page.locator(selector).count()
                self.logger.debug(f"Notifications of type '{notif_type}': {count}")
            
            # Сохраняем HTML для отладки
            html_content = self.page.content()
            allure.attach(html_content, name="Page HTML Debug", attachment_type=allure.attachment_type.HTML)
            
        except Exception as e:
            self.logger.error(f"Ошибка при отладке состояния уведомлений: {str(e)}")