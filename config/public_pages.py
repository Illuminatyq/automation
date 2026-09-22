"""
Реестр защищённых и публичных URL Лайнера для проверки обязательной авторизации.

Список составлен на основе анализа роутинга (App\\Liner::run + BaseController::action)
в data/Monolith/www/app: каждый HTML-контроллер использует единый паттерн
    /{module}/                -> actionIndex   (READ_ACCESS)
    /{module}/{id}/           -> actionDetail  (READ_ACCESS)
    /{module}/{action}/       -> actionCreate и т.п. (WRITE_ACCESS)
    /{module}/{action}/{id}/  -> actionEdit/actionCopy/... (WRITE_ACCESS)

Проверка доступа (BaseController::checkActionAccess) выполняется ДО загрузки
данных, поэтому конкретное значение {id} не влияет на срабатывание гейта —
можно использовать несуществующий id.

Если появится новый раздел в приложении — его нужно добавить сюда же.
"""

from typing import Dict, List

DUMMY_ID = "1"

# Модули с типовым паттерном index + detail, для которых READ_ACCESS
# переопределён на непустой список групп (т.е. должны требовать авторизацию).
PROTECTED_MODULES = [
    "agent-group", "agent-schedule", "analytics", "billing", "blocklist",
    "call-attempt", "call-prepare", "call-quality-criteria", "call-simulator",
    "call-statuses", "calls", "calls-quality", "conversations", "custom-fields",
    "insights", "integrations", "lead-status", "leads-cleaner", "leads-importer",
    "monitoring", "office", "orders", "plan-fact", "processing-rule",
    "quick-replies-category", "report-master", "sip-endpoint",
    "sip-endpoint-importer", "sip-line", "trunk", "users",
    "work-regulations-category",
]

# Модули, у которых есть отдельные формы создания/редактирования/копирования —
# самое чувствительное: доступ к форме правки чужих данных без авторизации.
MODULES_WITH_WRITE_FORMS: Dict[str, List[str]] = {
    "orders": ["create", "copy"],  # отдельного /orders/edit/ нет — правка инлайн на detail
    "call-scripts": ["create", "edit", "copy"],
    "projects": ["create", "edit"],
    "selection-candidate": ["create", "edit", "copy"],
    "work-regulations": ["create", "edit"],
}

# Публичные по замыслу страницы (READ_ACCESS = [] намеренно).
# Не должны требовать редиректа на /auth/, но не должны отдавать 500
# или содержимое, похожее на необработанную ошибку, при заведомо неверном токене.
PUBLIC_BY_DESIGN = [
    {"path": "/auth/", "note": "Страница логина"},
    {
        "path": "/open-history/?q=invalid-token-security-check",
        "note": "Публичная ссылка на историю звонка по зашифрованному id лида (OpenHistoryController)",
    },
    {
        "path": "/shortcut/?code=invalid-code-security-check",
        "note": "Публичная ссылка-шорткат по коду (ShortcutController)",
    },
]

# Точечные, подтверждённые анализом кода проблемные места:
# сюда не подходит общий паттерн index/detail/action, поэтому описаны явно.
KNOWN_RISK_ENTRIES = [
    {
        "path": f"/leads/active-call/?leadId={DUMMY_ID}",
        "module": "leads",
        "kind": "active-call",
        "note": (
            "LeadsController::actionActiveCall не входит в READ_ACTIONS/WRITE_ACTIONS "
            "и нигде не вызывает authorized() — потенциальный обход авторизации. "
            "Если тест не редиректит на /auth/, это подтверждает пробел из ревью кода; "
            "для окончательного вывода об утечке данных лида нужен реальный leadId."
        ),
    },
]


def build_registry() -> List[Dict]:
    entries: List[Dict] = []

    for module in PROTECTED_MODULES:
        entries.append({"path": f"/{module}/", "module": module, "kind": "index", "category": "protected"})
        entries.append({"path": f"/{module}/{DUMMY_ID}/", "module": module, "kind": "detail", "category": "protected"})

    for module, actions in MODULES_WITH_WRITE_FORMS.items():
        for action in actions:
            path = f"/{module}/create/" if action == "create" else f"/{module}/{action}/{DUMMY_ID}/"
            entries.append({"path": path, "module": module, "kind": action, "category": "protected"})

    # Лиды — отдельно: нет create/edit/copy как таковых (правка инлайн),
    # но их всё равно стоит проверить, что попытка попасть на несуществующее
    # действие не отдаёт 500 и не показывает данные лида.
    entries.append({"path": "/leads/", "module": "leads", "kind": "index", "category": "protected"})
    entries.append({"path": f"/leads/{DUMMY_ID}/", "module": "leads", "kind": "detail", "category": "protected"})
    entries.append({"path": f"/leads/edit/{DUMMY_ID}/", "module": "leads", "kind": "edit", "category": "protected"})
    entries.append({"path": f"/leads/copy/{DUMMY_ID}/", "module": "leads", "kind": "copy", "category": "protected"})

    for item in KNOWN_RISK_ENTRIES:
        entries.append({**item, "category": "known_risk"})

    for item in PUBLIC_BY_DESIGN:
        entries.append({"path": item["path"], "module": "public", "kind": "public", "category": "public", "note": item.get("note", "")})

    return entries


PUBLIC_PAGES_REGISTRY = build_registry()
