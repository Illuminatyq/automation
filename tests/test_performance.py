import pytest
import requests
import json
import allure
import logging
import os
import time
import statistics
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
import threading
from unittest.mock import Mock, patch
import random

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

@pytest.fixture
def use_mock():
    """Фикстура для определения, использовать ли заглушки вместо реальных запросов"""
    return os.environ.get("USE_MOCK", "true").lower() in ("true", "1", "yes")

@pytest.fixture
def api_config(config):
    """Фикстура для получения конфигурации API"""
    api_base_url = config["apiUrl"]
    api_url = api_base_url
    
    api_key = os.environ.get("LINER_API_KEY") or config.get("api_key", "")
    
    if not api_key:
        logging.warning("API ключ не найден. Тесты API могут не работать.")
    
    return {
        "base_url": api_url,
        "api_key": api_key,
        "environment": config["current_environment"]
    }

@pytest.fixture
def api_headers(api_config):
    """Фикстура для создания заголовков запросов"""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Python/Requests"
    }
    
    if api_config["api_key"]:
        headers["x-api-key"] = api_config["api_key"]
    
    return headers

@pytest.fixture
def mock_performance_responses():
    """Фикстура с заглушками для перфоманс тестов"""
    def generate_lead_data(lead_id):
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return {
            "id": f"perf_{lead_id}_{timestamp}",
            "order_id": 2640,
            "client_phone": f"+7999{timestamp[-7:]}",
            "lead_type": "straight",
            "UF_NAME": f"Performance Test Lead {lead_id}",
            "UF_COMMENT_MANAGER": "Перфоманс тест",
            "UF_EXTERNAL_ID": f"perf_ext_id_{lead_id}_{timestamp}",
            "UF_CITY": "Москва",
            "UF_DISTRICT": "Центральный",
            "UF_STAGE": "Новый",
            "status": "new",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
    
    def generate_search_results(page=1, limit=10):
        results = []
        for i in range(limit):
            results.append(generate_lead_data(f"search_{page}_{i}"))
        
        return {
            "status": "success",
            "data": results,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": 1000,
                "pages": 100
            }
        }
    
    return {
        "create": lambda lead_id: {
            "status": "success",
            "id": f"perf_{lead_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "message": "Лид успешно создан"
        },
        "detail": generate_lead_data,
        "search": generate_search_results,
        "update": {
            "status": "success",
            "message": "Лид успешно обновлен"
        },
        "list": lambda page=1: generate_search_results(page, 20),
        "error": {
            "status": "error",
            "message": "Временная ошибка сервера"
        }
    }

class MockAPIClient:
    """Мок клиент API для перфоманс тестов"""
    
    def __init__(self, base_url: str, api_key: str, mock_responses):
        self.base_url = base_url
        self.api_key = api_key
        self.mock_responses = mock_responses
        self.logger = logging.getLogger(__name__)
        
    def _simulate_network_delay(self, min_delay=0.01, max_delay=0.1):
        """Симуляция сетевой задержки"""
        delay = random.uniform(min_delay, max_delay)
        time.sleep(delay)
        return delay
    
    def create_lead(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """Создание лида с симуляцией задержки"""
        delay = self._simulate_network_delay(0.05, 0.2)
        lead_id = random.randint(1000, 9999)
        response = self.mock_responses["create"](lead_id)
        response["delay"] = delay
        return response
    
    def get_lead(self, lead_id: str) -> Dict[str, Any]:
        """Получение лида с симуляцией задержки"""
        delay = self._simulate_network_delay(0.02, 0.1)
        response = self.mock_responses["detail"](lead_id)
        response["delay"] = delay
        return response
    
    def search_leads(self, query_params: Dict[str, Any]) -> Dict[str, Any]:
        """Поиск лидов с симуляцией задержки"""
        delay = self._simulate_network_delay(0.1, 0.5)
        page = query_params.get("page", 1)
        limit = query_params.get("limit", 10)
        response = self.mock_responses["search"](page, limit)
        response["delay"] = delay
        return response
    
    def update_lead(self, lead_id: str, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """Обновление лида с симуляцией задержки"""
        delay = self._simulate_network_delay(0.03, 0.15)
        response = self.mock_responses["update"].copy()
        response["delay"] = delay
        return response
    
    def list_leads(self, page: int = 1) -> Dict[str, Any]:
        """Получение списка лидов с симуляцией задержки"""
        delay = self._simulate_network_delay(0.05, 0.3)
        response = self.mock_responses["list"](page)
        response["delay"] = delay
        return response

def measure_response_time(func, *args, **kwargs):
    """Измерение времени выполнения функции"""
    start_time = time.time()
    try:
        result = func(*args, **kwargs)
        end_time = time.time()
        return {
            "success": True,
            "response_time": end_time - start_time,
            "result": result
        }
    except Exception as e:
        end_time = time.time()
        return {
            "success": False,
            "response_time": end_time - start_time,
            "error": str(e)
        }

def run_concurrent_requests(client, method, iterations, *args, **kwargs):
    """Выполнение конкурентных запросов"""
    results = []
    
    with ThreadPoolExecutor(max_workers=min(iterations, 10)) as executor:
        futures = []
        for i in range(iterations):
            future = executor.submit(measure_response_time, method, *args, **kwargs)
            futures.append(future)
        
        for future in as_completed(futures):
            results.append(future.result())
    
    return results

@allure.feature("Перфоманс тесты API")
class TestAPIPerformance:
    """Тесты производительности API"""
    
    def setup_method(self):
        """Настройка перед каждым тестом"""
        logging.info(f"USE_MOCK value: {os.environ.get('USE_MOCK', 'not set')}")
    
    @allure.story("Базовые перфоманс тесты")
    @allure.severity('NORMAL')
    @allure.description("""
    Тест производительности создания лидов:
    1. Создание одного лида
    2. Измерение времени ответа
    3. Проверка стабильности
    """)
    def test_single_lead_creation_performance(self, api_config, api_headers, use_mock, mock_performance_responses):
        """Тест производительности создания одного лида"""
        if not use_mock:
            pytest.skip("Тест требует моков для стабильности")
        
        client = MockAPIClient(api_config["base_url"], api_config["api_key"], mock_performance_responses)
        
        lead_data = {
            "lead_type": "straight",
            "create_method": "performance_test",
            "client_name": "Performance Test Lead",
            "client_phone": "+79991234567",
            "order_id": 2640
        }
        
        # Выполняем несколько запросов для получения статистики
        iterations = 10
        results = []
        
        for i in range(iterations):
            result = measure_response_time(client.create_lead, lead_data)
            results.append(result)
            time.sleep(0.1)  # Небольшая пауза между запросами
        
        # Анализируем результаты
        successful_results = [r for r in results if r["success"]]
        response_times = [r["response_time"] for r in successful_results]
        
        if response_times:
            avg_time = statistics.mean(response_times)
            min_time = min(response_times)
            max_time = max(response_times)
            std_dev = statistics.stdev(response_times) if len(response_times) > 1 else 0
            
            allure.attach(
                f"Результаты теста:\n"
                f"Успешных запросов: {len(successful_results)}/{iterations}\n"
                f"Среднее время ответа: {avg_time:.3f} сек\n"
                f"Минимальное время: {min_time:.3f} сек\n"
                f"Максимальное время: {max_time:.3f} сек\n"
                f"Стандартное отклонение: {std_dev:.3f} сек",
                "Статистика производительности",
                allure.attachment_type.TEXT
            )
            
            # Проверяем, что среднее время ответа не превышает 0.5 секунды
            assert avg_time < 0.5, f"Среднее время ответа {avg_time:.3f} сек превышает 0.5 сек"
            assert len(successful_results) == iterations, f"Не все запросы были успешными: {len(successful_results)}/{iterations}"
        else:
            pytest.fail("Все запросы завершились с ошибкой")
    
    @allure.story("Конкурентные перфоманс тесты")
    @allure.severity('NORMAL')
    @allure.description("""
    Тест конкурентной производительности:
    1. Одновременное создание нескольких лидов
    2. Измерение времени ответа при нагрузке
    3. Проверка стабильности под нагрузкой
    """)
    def test_concurrent_lead_creation_performance(self, api_config, api_headers, use_mock, mock_performance_responses):
        """Тест конкурентной производительности создания лидов"""
        if not use_mock:
            pytest.skip("Тест требует моков для стабильности")
        
        client = MockAPIClient(api_config["base_url"], api_config["api_key"], mock_performance_responses)
        
        lead_data = {
            "lead_type": "straight",
            "create_method": "concurrent_performance_test",
            "client_name": "Concurrent Test Lead",
            "client_phone": "+79991234567",
            "order_id": 2640
        }
        
        # Тестируем разные уровни конкурентности
        concurrency_levels = [5, 10, 20]
        
        for concurrency in concurrency_levels:
            with allure.step(f"Тестирование с {concurrency} одновременными запросами"):
                results = run_concurrent_requests(client, client.create_lead, concurrency, lead_data)
                
                successful_results = [r for r in results if r["success"]]
                response_times = [r["response_time"] for r in successful_results]
                
                if response_times:
                    avg_time = statistics.mean(response_times)
                    max_time = max(response_times)
                    
                    allure.attach(
                        f"Результаты для {concurrency} запросов:\n"
                        f"Успешных запросов: {len(successful_results)}/{concurrency}\n"
                        f"Среднее время ответа: {avg_time:.3f} сек\n"
                        f"Максимальное время: {max_time:.3f} сек",
                        f"Статистика для {concurrency} запросов",
                        allure.attachment_type.TEXT
                    )
                    
                    # Проверяем, что все запросы завершились успешно
                    assert len(successful_results) == concurrency, f"Не все запросы были успешными: {len(successful_results)}/{concurrency}"
                    assert avg_time < 1.0, f"Среднее время ответа {avg_time:.3f} сек превышает 1.0 сек при {concurrency} запросах"
    
    @allure.story("Тесты производительности поиска")
    @allure.severity('NORMAL')
    @allure.description("""
    Тест производительности поиска лидов:
    1. Поиск лидов с различными параметрами
    2. Измерение времени ответа
    3. Проверка производительности поиска
    """)
    def test_search_performance(self, api_config, api_headers, use_mock, mock_performance_responses):
        """Тест производительности поиска лидов"""
        if not use_mock:
            pytest.skip("Тест требует моков для стабильности")
        
        client = MockAPIClient(api_config["base_url"], api_config["api_key"], mock_performance_responses)
        
        # Тестируем разные сценарии поиска
        search_scenarios = [
            {"page": 1, "limit": 10},
            {"page": 1, "limit": 50},
            {"page": 5, "limit": 20},
            {"status": "new", "page": 1, "limit": 10},
            {"lead_type": "straight", "page": 1, "limit": 10}
        ]
        
        for i, scenario in enumerate(search_scenarios):
            with allure.step(f"Тестирование поиска сценарий {i+1}: {scenario}"):
                results = []
                
                # Выполняем несколько запросов для получения статистики
                for j in range(5):
                    result = measure_response_time(client.search_leads, scenario)
                    results.append(result)
                    time.sleep(0.1)
                
                successful_results = [r for r in results if r["success"]]
                response_times = [r["response_time"] for r in successful_results]
                
                if response_times:
                    avg_time = statistics.mean(response_times)
                    max_time = max(response_times)
                    
                    allure.attach(
                        f"Результаты поиска для сценария {scenario}:\n"
                        f"Успешных запросов: {len(successful_results)}/5\n"
                        f"Среднее время ответа: {avg_time:.3f} сек\n"
                        f"Максимальное время: {max_time:.3f} сек",
                        f"Статистика поиска - сценарий {i+1}",
                        allure.attachment_type.TEXT
                    )
                    
                    # Проверяем производительность поиска
                    assert avg_time < 0.8, f"Среднее время поиска {avg_time:.3f} сек превышает 0.8 сек"
                    assert len(successful_results) == 5, f"Не все поисковые запросы были успешными"
    
    @allure.story("Тесты производительности чтения")
    @allure.severity('NORMAL')
    @allure.description("""
    Тест производительности чтения данных:
    1. Получение деталей лидов
    2. Получение списков лидов
    3. Измерение времени ответа
    """)
    def test_read_performance(self, api_config, api_headers, use_mock, mock_performance_responses):
        """Тест производительности операций чтения"""
        if not use_mock:
            pytest.skip("Тест требует моков для стабильности")
        
        client = MockAPIClient(api_config["base_url"], api_config["api_key"], mock_performance_responses)
        
        # Тестируем получение деталей лидов
        with allure.step("Тестирование получения деталей лидов"):
            lead_ids = [f"test_lead_{i}" for i in range(1, 11)]
            get_results = []
            
            for lead_id in lead_ids:
                result = measure_response_time(client.get_lead, lead_id)
                get_results.append(result)
                time.sleep(0.05)
            
            successful_gets = [r for r in get_results if r["success"]]
            get_times = [r["response_time"] for r in successful_gets]
            
            if get_times:
                avg_get_time = statistics.mean(get_times)
                allure.attach(
                    f"Результаты получения деталей лидов:\n"
                    f"Успешных запросов: {len(successful_gets)}/{len(lead_ids)}\n"
                    f"Среднее время ответа: {avg_get_time:.3f} сек",
                    "Статистика получения деталей",
                    allure.attachment_type.TEXT
                )
                
                assert avg_get_time < 0.3, f"Среднее время получения деталей {avg_get_time:.3f} сек превышает 0.3 сек"
        
        # Тестируем получение списков лидов
        with allure.step("Тестирование получения списков лидов"):
            list_results = []
            
            for page in range(1, 6):
                result = measure_response_time(client.list_leads, page)
                list_results.append(result)
                time.sleep(0.1)
            
            successful_lists = [r for r in list_results if r["success"]]
            list_times = [r["response_time"] for r in successful_lists]
            
            if list_times:
                avg_list_time = statistics.mean(list_times)
                allure.attach(
                    f"Результаты получения списков лидов:\n"
                    f"Успешных запросов: {len(successful_lists)}/5\n"
                    f"Среднее время ответа: {avg_list_time:.3f} сек",
                    "Статистика получения списков",
                    allure.attachment_type.TEXT
                )
                
                assert avg_list_time < 0.5, f"Среднее время получения списков {avg_list_time:.3f} сек превышает 0.5 сек"
    
    @allure.story("Тесты производительности обновления")
    @allure.severity('NORMAL')
    @allure.description("""
    Тест производительности обновления данных:
    1. Обновление лидов
    2. Измерение времени ответа
    3. Проверка производительности обновления
    """)
    def test_update_performance(self, api_config, api_headers, use_mock, mock_performance_responses):
        """Тест производительности обновления лидов"""
        if not use_mock:
            pytest.skip("Тест требует моков для стабильности")
        
        client = MockAPIClient(api_config["base_url"], api_config["api_key"], mock_performance_responses)
        
        # Тестируем обновление лидов
        update_data = {
            "UF_COMMENT_MANAGER": "Обновлено в перфоманс тесте",
            "status": "in_progress"
        }
        
        lead_ids = [f"update_test_{i}" for i in range(1, 11)]
        update_results = []
        
        for lead_id in lead_ids:
            result = measure_response_time(client.update_lead, lead_id, update_data)
            update_results.append(result)
            time.sleep(0.1)
        
        successful_updates = [r for r in update_results if r["success"]]
        update_times = [r["response_time"] for r in successful_updates]
        
        if update_times:
            avg_update_time = statistics.mean(update_times)
            max_update_time = max(update_times)
            
            allure.attach(
                f"Результаты обновления лидов:\n"
                f"Успешных запросов: {len(successful_updates)}/{len(lead_ids)}\n"
                f"Среднее время ответа: {avg_update_time:.3f} сек\n"
                f"Максимальное время: {max_update_time:.3f} сек",
                "Статистика обновления",
                allure.attachment_type.TEXT
            )
            
            assert avg_update_time < 0.4, f"Среднее время обновления {avg_update_time:.3f} сек превышает 0.4 сек"
            assert len(successful_updates) == len(lead_ids), f"Не все обновления были успешными"
    
    @allure.story("Стресс-тесты")
    @allure.severity('NORMAL')
    @allure.description("""
    Стресс-тест API:
    1. Высокая нагрузка на API
    2. Измерение производительности под нагрузкой
    3. Проверка стабильности системы
    """)
    def test_stress_performance(self, api_config, api_headers, use_mock, mock_performance_responses):
        """Стресс-тест производительности API"""
        if not use_mock:
            pytest.skip("Тест требует моков для стабильности")
        
        client = MockAPIClient(api_config["base_url"], api_config["api_key"], mock_performance_responses)
        
        # Выполняем стресс-тест с большим количеством запросов
        total_requests = 50
        concurrent_requests = 10
        
        with allure.step(f"Стресс-тест: {total_requests} запросов с {concurrent_requests} потоками"):
            # Создаем данные для разных типов запросов
            lead_data = {
                "lead_type": "straight",
                "create_method": "stress_test",
                "client_name": "Stress Test Lead",
                "client_phone": "+79991234567",
                "order_id": 2640
            }
            
            search_params = {"page": 1, "limit": 10}
            
            # Выполняем смешанные запросы
            all_results = []
            
            # Создание лидов
            create_results = run_concurrent_requests(client, client.create_lead, total_requests // 3, lead_data)
            all_results.extend(create_results)
            
            # Поиск лидов
            search_results = run_concurrent_requests(client, client.search_leads, total_requests // 3, search_params)
            all_results.extend(search_results)
            
            # Получение списков
            list_results = run_concurrent_requests(client, client.list_leads, total_requests // 3, 1)
            all_results.extend(list_results)
            
            # Анализируем общие результаты
            successful_results = [r for r in all_results if r["success"]]
            response_times = [r["response_time"] for r in successful_results]
            
            if response_times:
                avg_time = statistics.mean(response_times)
                min_time = min(response_times)
                max_time = max(response_times)
                std_dev = statistics.stdev(response_times) if len(response_times) > 1 else 0
                
                success_rate = len(successful_results) / len(all_results) * 100
                
                allure.attach(
                    f"Результаты стресс-теста:\n"
                    f"Всего запросов: {len(all_results)}\n"
                    f"Успешных запросов: {len(successful_results)}\n"
                    f"Процент успеха: {success_rate:.1f}%\n"
                    f"Среднее время ответа: {avg_time:.3f} сек\n"
                    f"Минимальное время: {min_time:.3f} сек\n"
                    f"Максимальное время: {max_time:.3f} сек\n"
                    f"Стандартное отклонение: {std_dev:.3f} сек",
                    "Результаты стресс-теста",
                    allure.attachment_type.TEXT
                )
                
                # Проверяем результаты стресс-теста
                assert success_rate >= 95, f"Процент успешных запросов {success_rate:.1f}% ниже 95%"
                assert avg_time < 1.0, f"Среднее время ответа {avg_time:.3f} сек превышает 1.0 сек"
                assert max_time < 2.0, f"Максимальное время ответа {max_time:.3f} сек превышает 2.0 сек"
            else:
                pytest.fail("Все запросы в стресс-тесте завершились с ошибкой")

@pytest.fixture
def page(browser_context, request):
    # Запускать только для UI-тестов
    if "performance" in request.keywords:
        pytest.skip("Этот тест не предназначен для UI")
    return browser_context.new_page()
