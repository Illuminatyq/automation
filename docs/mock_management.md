# Управление моками в тестах телефонии

## Обзор

В файле `tests/test_telephony_integration.py` используются моки для изоляции тестов от внешних зависимостей. Тесты настроены на работу с **dev окружением**: `https://liner.dstepanyuk.dev.smte.am`

Это позволяет:

- ✅ Быстрое выполнение тестов
- ✅ Предсказуемые результаты
- ✅ Независимость от состояния внешних сервисов
- ✅ Тестирование без реальных API вызовов
- ✅ Работа с настроенной телефонией на dev

## Текущие моки

### 1. Voximplant Mock (строки 73-111)

```python
@pytest.fixture
def voximplant_mock():
    """Мок Voximplant API"""
    with patch('requests.post') as mock_post, \
         patch('requests.get') as mock_get:
        # Мокирует HTTP запросы к Voximplant
```

**Что мокирует:**
- `requests.post` - для запуска звонков
- `requests.get` - для проверки статуса операторов

**Возвращаемые данные:**
- Готовность оператора: `{"acd_status": "READY"}`
- Запуск звонка: `{"call_session_history_id": 789}`

## Способы отключения моков

### Способ 1: Переменные окружения

```bash
# Отключить все моки
export USE_MOCKS=false
export USE_VOXIMPLANT_MOCK=false
export FAIL_ON_API_ERROR=true

# Запустить тесты
pytest tests/test_telephony_integration.py
```

### Способ 2: Использование скрипта `run_telephony_tests.py`

```bash
# Запуск с моками (по умолчанию)
python run_telephony_tests.py

# Запуск без моков (реальные API вызовы на dev)
python run_telephony_tests.py --mode NO_MOCK

# Запуск во всех режимах
python run_telephony_tests.py --all-modes

# Показать доступные режимы
python run_telephony_tests.py --list-modes
```

### Способ 3: Прямое редактирование тестов

Удалить параметр `voximplant_mock` из тестов:

```python
# Было:
def test_operator_status_change_integration(self, telephony_api_client, voximplant_mock, test_data):

# Стало:
def test_operator_status_change_integration(self, telephony_api_client, test_data):
```

## Режимы тестирования

### 1. FULL_MOCK (по умолчанию)
- ✅ Все моки включены
- ✅ Fallback логика при ошибках API
- ⚡ Быстрое выполнение
- 🔒 Изолированное тестирование

### 2. PARTIAL_MOCK
- ✅ Только fallback логика
- ❌ Без моков Voximplant
- 🔄 Реальные HTTP запросы к dev API
- ⚠️ Медленнее, но более реалистично

### 3. NO_MOCK
- ❌ Все моки отключены
- ✅ Реальные API вызовы на dev
- ⚠️ Падает при ошибках API
- 🐌 Медленное выполнение

### 4. STRICT_NO_MOCK
- ❌ Все моки отключены
- ✅ Строгая проверка dev API
- ❌ Падает при любых ошибках
- 🔍 Максимальная реалистичность

## Что произойдет при отключении моков

### ✅ Положительные эффекты:
- Реальные интеграционные тесты на dev
- Проверка реального API телефонии
- Обнаружение реальных проблем
- Более точное тестирование

### ⚠️ Потенциальные проблемы:
- **Медленное выполнение** - реальные HTTP запросы
- **Нестабильность** - зависимость от состояния dev API
- **Ошибки сети** - таймауты, недоступность сервера
- **Побочные эффекты** - реальные изменения в dev системе

### 🔧 Fallback логика

В коде есть встроенная fallback логика:

```python
try:
    response = telephony_api_client.change_operator_status(operator_id, "available")
    if response.status_code != 200:
        logging.warning(f"API недоступен, имитируем ответ")
        response_data = {"success": True, "message": "Status changed successfully"}
except Exception as e:
    logging.warning(f"Ошибка при изменении статуса: {e}")
    response_data = {"success": True, "message": "Status changed successfully"}
```

## Рекомендации по использованию

### Для разработки:
```bash
# Быстрые тесты с моками
python run_telephony_tests.py --mode FULL_MOCK
```

### Для CI/CD:
```bash
# Проверка интеграции на dev
python run_telephony_tests.py --mode NO_MOCK
```

### Для отладки:
```bash
# Все режимы для сравнения
python run_telephony_tests.py --all-modes
```

### Для продакшн тестирования:
```bash
# Строгий режим на dev
python run_telephony_tests.py --mode STRICT_NO_MOCK
```

## Конфигурация

Настройки моков можно изменить в `config/mock_config.py`:

```python
# Переменные окружения
USE_MOCKS=true              # Включить/отключить моки
USE_VOXIMPLANT_MOCK=true    # Мок Voximplant
FAIL_ON_API_ERROR=false     # Падать при ошибках API
API_TIMEOUT=10              # Таймаут API запросов
```

## API эндпоинты dev окружения

### Базовый URL: `https://liner.dstepanyuk.dev.smte.am/api/`

### Доступные методы:

```python
# Изменение статуса оператора
POST /api/?controller=Vats&method=changeEmployeeStatusAction

# Получение статуса оператора  
GET /api/?controller=Vats&method=getEmployeeStatus

# Получение онлайн операторов
GET /api/?controller=Vats&method=getOnlineReadyEmployees

# Запуск предиктивного звонка
POST /api/?controller=Vats&method=startPredictiveCall

# Получение очереди диаллера
GET /api/?controller=Vats&method=getDialerQueue
```

## Мониторинг и логирование

При отключении моков включите подробное логирование:

```bash
# Подробные логи
pytest tests/test_telephony_integration.py -v --log-cli-level=INFO

# Логи в файл
pytest tests/test_telephony_integration.py --log-file=telephony_tests.log
```

## Troubleshooting

### Проблема: API недоступен
```bash
# Проверить доступность dev API
curl -k https://liner.dstepanyuk.dev.smte.am/api/?controller=Vats&method=getOnlineReadyEmployees

# Использовать моки
python run_telephony_tests.py --mode FULL_MOCK
```

### Проблема: Медленные тесты
```bash
# Увеличить таймауты
export API_TIMEOUT=30
python run_telephony_tests.py --mode NO_MOCK
```

### Проблема: Нестабильные тесты
```bash
# Добавить retry логику
pytest tests/test_telephony_integration.py --reruns=3 --reruns-delay=1
```

## Преимущества использования dev окружения

### ✅ По сравнению с test.linerapp.io:
- **Доступность** - dev окружение всегда доступно для разработки
- **Актуальность** - содержит последние изменения кода
- **Интеграция** - полная интеграция с остальными компонентами
- **Отладка** - легче отлаживать проблемы

### ✅ По сравнению с продакшн:
- **Безопасность** - не влияет на реальные данные
- **Эксперименты** - можно безопасно тестировать новые функции
- **Скорость** - быстрее для разработки и тестирования 