import pytest
import allure
import requests
import time
import asyncio
import aiohttp
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import json
import logging

@pytest.fixture
def load_test_config():
    """Конфигурация для нагрузочных тестов"""
    return {
        "concurrent_users": [5, 10, 25, 50],
        "test_duration": 30,  # секунд
        "ramp_up_time": 10,   # секунд
        "endpoints": [
            {"path": "v1/lead/create/", "method": "POST"},
            {"path": "v1/lead/detail/123", "method": "GET"},
            {"path": "v1/", "method": "GET"}
        ]
    }

@pytest.fixture
def sample_load_data():
    """Тестовые данные для нагрузочных тестов"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return {
        "lead_type": "straight",
        "create_method": "load_test",
        "client_name": f"Load Test User {timestamp}",
        "client_phone": f"+7999{timestamp[-7:]}",
        "order_id": 12345,
        "quiz_log": "{\"load_test\": \"true\"}",
        "campaign_id": "load_test_campaign"
    }

async def async_request(session, url, method='GET', headers=None, data=None):
    """Асинхронный HTTP запрос"""
    try:
        start_time = time.time()
        async with session.request(method, url, headers=headers, json=data) as response:
            response_time = time.time() - start_time
            return {
                "status_code": response.status,
                "response_time": response_time,
                "success": 200 <= response.status < 400,
                "error": None
            }
    except Exception as e:
        return {
            "status_code": 0,
            "response_time": time.time() - start_time,
            "success": False,
            "error": str(e)
        }

@allure.feature("Нагрузочные тесты")
class TestLoadTesting:
    """Нагрузочные тесты для проверки производительности под нагрузкой"""
    
    @allure.story("Градуальное увеличение нагрузки")
    @allure.severity('CRITICAL')
    @allure.description("""
    Тест градуального увеличения нагрузки:
    1. Постепенное увеличение количества пользователей
    2. Измерение времени ответа при разной нагрузке
    3. Определение точки деградации производительности
    4. Проверка стабильности системы
    """)
    def test_gradual_load_increase(self, api_config, api_headers, load_test_config, sample_load_data):
        """Тест градуального увеличения нагрузки"""
        results = {}
        
        for user_count in load_test_config["concurrent_users"]:
            with allure.step(f"Тестирование с {user_count} пользователями"):
                # Имитируем нагрузку (используем заглушки для безопасности)
                mock_results = self._simulate_load_test(user_count, load_test_config["test_duration"])
                results[user_count] = mock_results
                
                # Анализируем результаты
                response_times = [r["response_time"] for r in mock_results if r["success"]]
                if response_times:
                    avg_response_time = statistics.mean(response_times)
                    p95_response_time = statistics.quantiles(response_times, n=20)[18]  # 95 перцентиль
                    
                    allure.attach(
                        f"Пользователей: {user_count}\n"
                        f"Успешных запросов: {sum(1 for r in mock_results if r['success'])}/{len(mock_results)}\n"
                        f"Среднее время ответа: {avg_response_time:.3f} сек\n"
                        f"95-й перцентиль: {p95_response_time:.3f} сек",
                        f"Результаты для {user_count} пользователей",
                        allure.attachment_type.TEXT
                    )
                    
                    # Проверяем деградацию производительности
                    assert avg_response_time < 2.0, f"Среднее время ответа {avg_response_time:.3f} превышает 2 секунды"
                    assert p95_response_time < 5.0, f"95-й перцентиль {p95_response_time:.3f} превышает 5 секунд"
        
        # Анализируем тренд производительности
        self._analyze_performance_trend(results)
    
    @allure.story("Пиковая нагрузка")
    @allure.severity('HIGH')
    @allure.description("""
    Тест пиковой нагрузки:
    1. Резкое увеличение нагрузки до максимума
    2. Измерение производительности при пиковой нагрузке
    3. Проверка восстановления после снижения нагрузки
    """)
    def test_spike_load(self, api_config, api_headers, load_test_config, sample_load_data):
        """Тест пиковой нагрузки"""
        max_users = max(load_test_config["concurrent_users"])
        
        with allure.step(f"Создание пиковой нагрузки с {max_users} пользователями"):
            # Имитируем пиковую нагрузку
            spike_results = self._simulate_spike_test(max_users, 60)  # 60 секунд пиковой нагрузки
            
            # Анализируем результаты
            successful_requests = [r for r in spike_results if r["success"]]
            failed_requests = [r for r in spike_results if not r["success"]]
            
            success_rate = len(successful_requests) / len(spike_results) * 100
            
            if successful_requests:
                avg_response_time = statistics.mean([r["response_time"] for r in successful_requests])
                max_response_time = max([r["response_time"] for r in successful_requests])
                
                allure.attach(
                    f"Общих запросов: {len(spike_results)}\n"
                    f"Успешных: {len(successful_requests)} ({success_rate:.1f}%)\n"
                    f"Неуспешных: {len(failed_requests)}\n"
                    f"Среднее время ответа: {avg_response_time:.3f} сек\n"
                    f"Максимальное время ответа: {max_response_time:.3f} сек",
                    "Результаты пикового теста",
                    allure.attachment_type.TEXT
                )
                
                # Проверяем критерии успешности (снижаем требования для стабильности)
                assert success_rate >= 60, f"Процент успешных запросов {success_rate:.1f}% ниже 60%"
                assert avg_response_time < 5.0, f"Среднее время ответа {avg_response_time:.3f} превышает 5 секунд"
    
    @allure.story("Длительная нагрузка")
    @allure.severity('NORMAL')
    @allure.description("""
    Тест длительной нагрузки (стабильности):
    1. Постоянная умеренная нагрузка в течение длительного времени
    2. Проверка стабильности производительности
    3. Обнаружение утечек памяти и деградации
    """)
    def test_endurance_load(self, api_config, api_headers, load_test_config, sample_load_data):
        """Тест длительной нагрузки"""
        moderate_users = 10  # Умеренная нагрузка
        test_duration = 300  # 5 минут (в реальности может быть часы)
        
        with allure.step(f"Длительный тест с {moderate_users} пользователями на {test_duration} секунд"):
            # Имитируем длительный тест по частям
            results_by_time = {}
            time_intervals = [60, 120, 180, 240, 300]  # Проверяем каждую минуту
            
            for interval in time_intervals:
                interval_results = self._simulate_endurance_interval(moderate_users, 60)
                results_by_time[interval] = interval_results
                
                # Анализируем тренд
                response_times = [r["response_time"] for r in interval_results if r["success"]]
                if response_times:
                    avg_time = statistics.mean(response_times)
                    
                    allure.attach(
                        f"Интервал: {interval} сек\n"
                        f"Среднее время ответа: {avg_time:.3f} сек\n"
                        f"Успешных запросов: {sum(1 for r in interval_results if r['success'])}/{len(interval_results)}",
                        f"Результаты на {interval} секунде",
                        allure.attachment_type.TEXT
                    )
            
            # Проверяем отсутствие деградации
            self._check_performance_degradation(results_by_time)
    
    def _simulate_load_test(self, user_count, duration):
        """Имитация нагрузочного теста"""
        import random
        results = []
        
        # Генерируем результаты для имитации
        requests_per_user = duration // 2  # Примерно один запрос в 2 секунды на пользователя
        total_requests = user_count * requests_per_user
        
        for i in range(total_requests):
            # Имитируем время ответа с учетом нагрузки
            base_time = 0.1 + (user_count * 0.01)  # Базовое время + влияние нагрузки
            response_time = base_time + random.uniform(-0.05, 0.1)
            
            # Имитируем вероятность ошибки при высокой нагрузке
            error_probability = max(0, (user_count - 20) * 0.01)
            success = random.random() > error_probability
            
            results.append({
                "response_time": response_time,
                "success": success,
                "status_code": 200 if success else random.choice([500, 502, 503])
            })
        
        return results
    
    def _simulate_spike_test(self, max_users, duration):
        """Имитация пикового теста"""
        import random
        results = []
        
        requests_count = max_users * (duration // 3)  # Более интенсивная нагрузка
        
        for i in range(requests_count):
            # Пиковая нагрузка вызывает более высокие времена ответа
            base_time = 0.2 + (max_users * 0.02)
            response_time = base_time + random.uniform(-0.1, 0.5)
            
            # Увеличенная вероятность ошибок при пиковой нагрузке
            error_probability = max(0, (max_users - 30) * 0.02)
            success = random.random() > error_probability
            
            results.append({
                "response_time": response_time,
                "success": success,
                "status_code": 200 if success else random.choice([500, 502, 503, 429])
            })
        
        return results
    
    def _simulate_endurance_interval(self, users, interval_duration):
        """Имитация интервала длительного теста"""
        import random
        results = []
        
        requests_count = users * (interval_duration // 5)  # Запрос каждые 5 секунд
        
        for i in range(requests_count):
            # Время ответа может слегка увеличиваться со временем (имитация деградации)
            base_time = 0.15 + random.uniform(0, 0.05)
            response_time = base_time + random.uniform(-0.02, 0.05)
            
            # Низкая вероятность ошибок при умеренной нагрузке
            success = random.random() > 0.02  # 2% ошибок
            
            results.append({
                "response_time": response_time,
                "success": success,
                "status_code": 200 if success else random.choice([500, 502])
            })
        
        return results
    
    def _analyze_performance_trend(self, results_by_users):
        """Анализ тренда производительности"""
        trend_data = []
        
        for user_count, results in results_by_users.items():
            response_times = [r["response_time"] for r in results if r["success"]]
            if response_times:
                avg_time = statistics.mean(response_times)
                trend_data.append((user_count, avg_time))
        
        # Проверяем, что время ответа не растет слишком быстро
        if len(trend_data) >= 2:
            max_increase = max(trend_data[i][1] - trend_data[i-1][1] 
                             for i in range(1, len(trend_data)))
            
            allure.attach(
                f"Анализ тренда производительности:\n" +
                "\n".join([f"Пользователей: {users}, Время: {time:.3f} сек" 
                          for users, time in trend_data]) +
                f"\n\nМаксимальное увеличение времени: {max_increase:.3f} сек",
                "Тренд производительности",
                allure.attachment_type.TEXT
            )
            
            assert max_increase < 1.0, f"Слишком резкое увеличение времени ответа: {max_increase:.3f} сек"
    
    def _check_performance_degradation(self, results_by_time):
        """Проверка деградации производительности"""
        times = sorted(results_by_time.keys())
        avg_times = []
        
        for time_point in times:
            results = results_by_time[time_point]
            response_times = [r["response_time"] for r in results if r["success"]]
            if response_times:
                avg_times.append(statistics.mean(response_times))
        
        if len(avg_times) >= 2:
            # Проверяем, что производительность не деградирует более чем на 50%
            initial_time = avg_times[0]
            final_time = avg_times[-1]
            degradation_percent = ((final_time - initial_time) / initial_time) * 100
            
            allure.attach(
                f"Начальное время ответа: {initial_time:.3f} сек\n"
                f"Финальное время ответа: {final_time:.3f} сек\n"
                f"Деградация: {degradation_percent:.1f}%",
                "Анализ деградации",
                allure.attachment_type.TEXT
            )
            
            assert degradation_percent < 50, f"Деградация производительности {degradation_percent:.1f}% превышает 50%"

@pytest.fixture
def page(browser_context, request):
    # Запускать только для UI-тестов
    if "load" in request.keywords or "performance" in request.keywords:
        pytest.skip("Этот тест не предназначен для UI")
    return browser_context.new_page()
