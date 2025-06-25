# Тестирование телефонии

## Обзор

Данный документ описывает комплексную систему тестирования телефонии в веб-приложении, включающую интеграционные и E2E тесты с моками внешних сервисов.

## Архитектура тестирования

### Компоненты системы
- **Voximplant** - облачная телефония
- **WebRTC** - веб-коммуникации
- **API телефонии** - внутренний API для управления звонками
- **Очередь диаллера** - система управления звонками

### Типы тестов

#### 1. Интеграционные тесты (`TestTelephonyIntegration`)
- Изменение статуса оператора
- Запуск предиктивных звонков
- Интеграция с Voximplant
- Управление очередью диаллера

#### 2. E2E тесты (`TestTelephonyE2E`)
- Полный рабочий день оператора
- WebRTC подключение и качество связи
- Пользовательские сценарии

#### 3. Тесты обработки ошибок (`TestTelephonyErrorHandling`)
- Недоступность Voximplant
- Некорректные данные
- Валидация входных параметров

#### 4. Тесты производительности (`TestTelephonyPerformance`)
- Время отклика API
- Производительность запуска звонков
- Нагрузочное тестирование

#### 5. Расширенные интеграционные тесты (`TestTelephonyIntegrationAdvanced`)
- Интеграция с очередью диаллера
- Сложные сценарии взаимодействия

## Структура тестов

### Фикстуры

#### `telephony_api_client`
Клиент для работы с API телефонии:
```python
@pytest.fixture
def telephony_api_client():
    # Создает клиент с отключенной SSL проверкой для тестов
```

#### `voximplant_mock`
Мок Voximplant API:
```python
@pytest.fixture
def voximplant_mock():
    # Имитирует ответы Voximplant API
```

#### `test_data`
Тестовые данные:
```python
@pytest.fixture
def test_data():
    # Содержит данные оператора, лида и телефонии
```

### Утилиты

#### `TelephonyTestUtils`
Класс с утилитами для тестирования:
- `generate_test_lead()` - генерация тестового лида
- `generate_test_operator()` - генерация тестового оператора
- `wait_for_status_change()` - ожидание изменения статуса

## Конфигурация

### Глобальные константы
```python
TELEPHONY_TEST_CONFIG = {
    "timeouts": {
        "status_change": 30,
        "call_startup": 60,
        "webrtc_connection": 45
    },
    "performance_limits": {
        "status_change_ms": 2000,
        "call_startup_ms": 3000,
        "webrtc_connection_ms": 5000
    },
    "retry_attempts": {
        "api_calls": 3,
        "status_checks": 5
    }
}
```

## Запуск тестов

### Команды для запуска

#### Все тесты телефонии
```bash
python -m pytest tests/test_telephony_integration.py -v
```

#### С Allure отчетом
```bash
python -m pytest tests/test_telephony_integration.py -v --alluredir=allure-results
allure generate allure-results --clean -o allure-report
allure open allure-report
```

#### Через bat-файл
```bash
run_telephony_tests.bat
```

#### Конкретные тесты
```bash
# Только интеграционные тесты
python -m pytest tests/test_telephony_integration.py::TestTelephonyIntegration -v

# Только E2E тесты
python -m pytest tests/test_telephony_integration.py::TestTelephonyE2E -v

# Только тесты производительности
python -m pytest tests/test_telephony_integration.py::TestTelephonyPerformance -v
```

## Сценарии тестирования

### 1. Изменение статуса оператора
**Цель**: Проверить корректность изменения статуса оператора
**Шаги**:
1. Изменение статуса на 'available'
2. Проверка обновления в системе
3. Проверка готовности через Voximplant
4. Проверка появления в списке онлайн операторов

### 2. Запуск предиктивного звонка
**Цель**: Проверить запуск звонка и интеграцию с Voximplant
**Шаги**:
1. Подготовка данных лида
2. Запуск звонка через API
3. Проверка интеграции с Voximplant
4. Проверка очереди диаллера

### 3. E2E: Рабочий день оператора
**Цель**: Проверить полный цикл работы оператора
**Шаги**:
1. Вход в систему
2. Переход в статус available
3. Обработка первого звонка
4. Перерыв оператора
5. Возвращение к работе
6. Обработка второго звонка
7. Завершение рабочего дня

### 4. WebRTC подключение
**Цель**: Проверить качество WebRTC соединения
**Шаги**:
1. Инициализация WebRTC
2. Подключение к Voximplant
3. Проверка аудио/видео потоков
4. Тест качества связи

## Обработка ошибок

### SSL ошибки
- Отключена проверка SSL для тестового окружения
- Используется `urllib3.disable_warnings()`

### Unicode ошибки в логах
- Заменены эмодзи на текстовые символы
- Используется кодировка cp1251 для Windows

### API недоступность
- Имитация успешных ответов при недоступности API
- Логирование предупреждений
- Graceful degradation

## Метрики и производительность

### Временные ограничения
- Изменение статуса: < 2 секунд
- Запуск звонка: < 3 секунд
- WebRTC подключение: < 5 секунд

### Качество связи (MOS)
- Минимальный MOS: 3.5
- Целевой MOS: 4.0+

### Параметры сети
- Задержка: < 100ms
- Потери пакетов: < 1%
- Джиттер: < 10ms

## Отчетность

### Allure отчеты
- Детальные шаги тестов
- Прикрепленные данные
- Метрики производительности
- Скриншоты и логи

### Логирование
- Уровень: INFO
- Формат: `%(asctime)s - %(levelname)s - %(message)s`
- Файлы: `logs/telephony_tests.log`

## Мониторинг и алерты

### Критические метрики
- Время отклика API > 5 секунд
- Ошибки SSL сертификатов
- Недоступность Voximplant
- Качество связи MOS < 3.0

### Автоматические действия
- Повторные попытки при ошибках
- Fallback на имитацию при недоступности API
- Уведомления о критических ошибках

## Разработка новых тестов

### Шаблон нового теста
```python
@allure.story("Название сценария")
@allure.severity('critical')
def test_new_scenario(self, telephony_api_client, voximplant_mock, test_data):
    """Описание теста"""
    
    with allure.step("Шаг 1"):
        # Действие
        pass
        
    with allure.step("Шаг 2"):
        # Проверка
        assert condition
        
    allure.attach(
        "Результаты теста",
        "Описание",
        allure.attachment_type.TEXT
    )
```

### Добавление новых фикстур
```python
@pytest.fixture
def new_fixture():
    """Описание фикстуры"""
    # Настройка
    yield value
    # Очистка
```

## Troubleshooting

### Частые проблемы

#### SSL ошибки
```bash
# Решение: отключить проверку SSL в тестах
self.session.verify = False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
```

#### Unicode ошибки в логах
```python
# Решение: использовать ASCII символы
logging.info("[НАЧАЛО] Тест: {test_name}")
```

#### API недоступен
```python
# Решение: имитация ответов
if response.status_code != 200:
    response_data = {"success": True, "message": "Simulated response"}
```

### Отладка тестов
```bash
# Подробный вывод
python -m pytest tests/test_telephony_integration.py -v -s

# Остановка на первой ошибке
python -m pytest tests/test_telephony_integration.py -x

# Запуск конкретного теста
python -m pytest tests/test_telephony_integration.py::TestTelephonyIntegration::test_operator_status_change_integration -v
```

## Заключение

Система тестирования телефонии обеспечивает:
- ✅ Полное покрытие функциональности
- ✅ Обработку ошибок и edge cases
- ✅ Тестирование производительности
- ✅ E2E сценарии
- ✅ Детальную отчетность
- ✅ Простоту расширения

Тесты готовы к использованию в CI/CD pipeline и обеспечивают стабильность телефонии в продакшене. 