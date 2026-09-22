# Техническая часть и логика данных в телефонии

## Обзор

В системе телефонии используются различные типы данных для работы с операторами, лидами и звонками. Давайте разберем логику каждого компонента.

## 1. Операторы (Operators)

### Структура данных оператора

```json
{
  "id": "test_operator_123",           // ID оператора в системе
  "vox_user_name": "test_operator",    // Имя пользователя в Voximplant
  "display_name": "Test Operator 1"    // Отображаемое имя
}
```

### Логика работы с операторами

#### **UF_VOX_USER_NAME** - ключевое поле
Это поле связывает оператора в системе с его аккаунтом в Voximplant:

```php
// Из Vats.php - строка 526
$phoneFieldCode = match (InstanceHelper::getVatsProviderCode()) {
    VatProvider::VOX => 'UF_VOX_USER_NAME',
    default => 'UF_UIS_ID',
};
```

#### **Как это работает:**

1. **Регистрация в Voximplant:**
   - Оператор регистрируется в Voximplant с именем `test_operator`
   - В системе создается запись с `UF_VOX_USER_NAME = "test_operator"`

2. **Проверка готовности:**
   ```php
   // Строка 561-563
   $isReadyForCall = match (InstanceHelper::getVatsProviderCode()) {
       VatProvider::VOX => (!empty($employeeItem['UF_VOX_USER_NAME']) && 
                           $voxProvider->userIsReadyForCall($employeeItem['UF_VOX_USER_NAME'])),
   };
   ```

3. **Запуск звонка:**
   ```php
   // Строка 1982
   $voxUserName = $callEmployeeData['UF_VOX_USER_NAME'];
   ```

### Где брать реальные данные операторов

#### **1. Из базы данных системы:**
```sql
SELECT ID, UF_VOX_USER_NAME, UF_UIS_STATUS 
FROM b_user 
WHERE UF_IS_CALL_CENTER_USER = 1 
AND UF_VOX_USER_NAME IS NOT NULL;
```

#### **2. Из админки системы:**
- Перейти в раздел "Операторы" или "Пользователи"
- Найти пользователей с ролью "Оператор колл-центра"
- Скопировать `UF_VOX_USER_NAME`

#### **3. Из Voximplant панели:**
- Войти в Voximplant Console
- Перейти в раздел "Users"
- Найти пользователей операторов

### Пример реальных данных:
```json
{
  "operators": [
    {
      "id": "12345",
      "vox_user_name": "operator_ivan",
      "display_name": "Иван Петров"
    },
    {
      "id": "12346", 
      "vox_user_name": "operator_maria",
      "display_name": "Мария Сидорова"
    }
  ]
}
```

## 2. Лиды (Leads)

### Структура данных лида

```json
{
  "id": "lead_456",           // ID лида в системе
  "phone": "+79991234567",    // Телефон клиента
  "name": "Test Client 1",    // Имя клиента
  "order_id": 789             // ID заказа
}
```

### Логика работы с лидами

#### **Как используются данные лида в startPredictiveCall:**

```php
// Строка 1000-1005
$callSessionData = $voxProvider->predictiveOutgoingCall(
    leadPhone: (string) $leadArr['Leads_UF_PHONE'],        // Телефон клиента
    sipEndpoint: $outgoingPhone,                           // Исходящий номер
    leadId: (int) $leadArr['Leads_ID'],                   // ID лида
    callerIdForTransferPhone: (string) $callerEvent['callerIdForTransferPhone'],
    clientCallScript: $CallScripts->getPlainScriptText(...), // Скрипт звонка
    aiIsAllowed: $leadArr['Orders_aiPredictiveIsAllowed'],   // Разрешено ли ИИ
    aiPrompt: $leadArr['Orders_aiPrompt']                    // Промпт для ИИ
);
```

#### **Ключевые поля лида:**

1. **Leads_UF_PHONE** - телефон клиента для звонка
2. **Leads_ID** - уникальный идентификатор лида
3. **Leads_UF_ORDER** - связанный заказ
4. **Orders_aiPredictiveIsAllowed** - разрешение на ИИ
5. **Orders_aiPrompt** - промпт для ИИ

### Где брать реальные данные лидов

#### **1. Из базы данных:**
```sql
SELECT 
    l.ID as lead_id,
    l.UF_PHONE as phone,
    l.UF_NAME as name,
    l.UF_ORDER as order_id,
    o.UF_CALL_CENTER_SCRIPT as script,
    o.aiPredictiveIsAllowed,
    o.aiPrompt
FROM b_hlblock_entity_leads l
LEFT JOIN b_hlblock_entity_orders o ON l.UF_ORDER = o.ID
WHERE l.UF_STATUS = 'primary'  -- Только новые лиды
AND l.UF_PHONE IS NOT NULL;
```

#### **2. Из админки системы:**
- Перейти в раздел "Лиды" или "Заявки"
- Найти лиды со статусом "Новый"
- Экспортировать данные

#### **3. Создать тестовые лиды:**
```sql
INSERT INTO b_hlblock_entity_leads (
    UF_PHONE, UF_NAME, UF_ORDER, UF_STATUS, UF_CALL_DATE_TIME
) VALUES (
    '+79991234567', 'Тестовый клиент', 789, 'primary', NOW()
);
```

## 3. Телефоны (Phones)

### Структура данных телефона

```json
{
  "connection_type": "webrtc",
  "params": {
    "user_name": "test_operator",
    "display_name": "Test Operator"
  }
}
```

### Логика работы с телефонами

#### **SipEndpoint - класс для работы с телефонами:**

```php
// Из Vats.php - строка 970
public function startPredictiveCall($leadArr, SipEndpoint $outgoingPhone)
{
    $outgoingPhoneNumber = $outgoingPhone->extractPhoneNumber();
    // ...
}
```

#### **Типы подключений:**
- **webrtc** - веб-телефония через браузер
- **sip** - SIP-телефония
- **pstn** - обычная телефония

### Где брать данные телефонов

#### **1. Из настроек заказа:**
```sql
SELECT 
    o.ID as order_id,
    o.UF_OUTGOING_PHONE as phone_number,
    o.UF_PHONE_TYPE as connection_type
FROM b_hlblock_entity_orders o
WHERE o.UF_OUTGOING_PHONE IS NOT NULL;
```

#### **2. Из конфигурации Voximplant:**
- В Voximplant Console
- Раздел "Scenarios" или "Phone Numbers"
- Найти настроенные номера

## 4. Статусы операторов

### Маппинг статусов

```json
{
  "operator": {
    "statuses": {
      "available": 1,    // Доступен для звонков
      "busy": 2,         // Занят звонком
      "break": 3,        // На перерыве
      "offline": 4,      // Не на работе
      "post_call": 5     // После звонка
    }
  }
}
```

### Логика статусов

```php
// Из Vats.php - строка 586
public function getEmployeeStatusesMap($flip = false)
{
    // Получаем статусы из базы данных
    $callCenterStatusesRes = DB::getList(Callcenterstatushistory::DB_TABLE_NAME_STATUSES_LIST, $params);
    
    while ($callCenterStatusItem = $callCenterStatusesRes->fetch()) {
        if ($callCenterStatusItem['UF_IS_AVAILABLE']) {
            $result['available'] = intval($callCenterStatusItem['UF_UIS_ID']);
        }
        // ... другие статусы
    }
}
```

## 5. Практические рекомендации

### Для тестирования с моками:
```json
{
  "test_data": {
    "operators": [
      {
        "id": "test_operator_123",
        "vox_user_name": "test_operator",
        "display_name": "Test Operator 1"
      }
    ],
    "leads": [
      {
        "id": "lead_456",
        "phone": "+79991234567",
        "name": "Test Client 1",
        "order_id": 789
      }
    ]
  }
}
```

### Для реального тестирования:

#### **1. Получить реальных операторов:**
```bash
# API запрос для получения операторов
curl -X GET "https://liner.dstepanyuk.dev.smte.am/api/?controller=Vats&method=getOnlineReadyEmployees" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### **2. Получить реальные лиды:**
```bash
# API запрос для получения лидов
curl -X GET "https://liner.dstepanyuk.dev.smte.am/api/?controller=Leads&method=getLeadsList" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d "filter[UF_STATUS]=primary"
```

#### **3. Обновить конфигурацию:**
```json
{
  "telephony": {
    "test_data": {
      "operators": [
        {
          "id": "12345",
          "vox_user_name": "operator_ivan",
          "display_name": "Иван Петров"
        }
      ],
      "leads": [
        {
          "id": "1001",
          "phone": "+79991234567",
          "name": "Реальный клиент",
          "order_id": "500"
        }
      ]
    }
  }
}
```

## 6. Отладка и проверка

### Проверка операторов:
```bash
# Проверить статус оператора
curl -X GET "https://liner.dstepanyuk.dev.smte.am/api/?controller=Vats&method=getEmployeeStatus" \
  -d "operator_id=12345"
```

### Проверка лидов:
```bash
# Проверить очередь диаллера
curl -X GET "https://liner.dstepanyuk.dev.smte.am/api/?controller=Vats&method=getDialerQueue"
```

### Проверка Voximplant:
```bash
# Проверить готовность оператора в Voximplant
curl -X POST "https://api.voximplant.com/platform_api/GetUsers" \
  -H "Authorization: Bearer YOUR_VOX_TOKEN" \
  -d '{"user_name": "operator_ivan"}'
```

## Заключение

Логика данных в телефонии построена на связях между:
- **Операторами** (с `UF_VOX_USER_NAME` для Voximplant)
- **Лидами** (с телефонами и заказами)
- **Телефонами** (исходящие номера)
- **Статусами** (состояния операторов)

Для реального тестирования нужно использовать данные из вашей dev системы, а не тестовые значения. 