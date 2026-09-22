"""
Проверка того, что ни одна защищённая страница Лайнера не открывается без
авторизации: анонимный переход должен либо редиректить на /auth/, либо (для
несуществующих action/id комбинаций) отдавать управляемую ошибку 4xx — но
никогда не показывать реальный контент и не падать в 500.

Список проверяемых URL собран в config/public_pages.py на основе анализа
роутинга приложения (см. историю задачи). Если появляется новый раздел —
он добавляется туда, а не сюда.
"""

import logging
from urllib.parse import urljoin

import allure
import pytest

from config.public_pages import PUBLIC_PAGES_REGISTRY
from utils.allure_helpers import AllureHelper

logger = logging.getLogger(__name__)

# Статусы, которые сами по себе не являются утечкой данных: доступ отклонён,
# просто не через редирект на страницу логина (например, JSON realm или
# несуществующее действие/id).
SAFE_NO_CONTENT_STATUSES = {401, 403, 404, 405}

ERROR_MARKERS = [
    "fatal error", "stack trace", "uncaught exception", "whoops",
    "internal server error", "<title>error</title>", "undefined index",
    "undefined variable", "warning: ", "notice: ",
]


def _looks_broken(content: str) -> bool:
    lowered = content.lower()
    return any(marker in lowered for marker in ERROR_MARKERS)


def _entry_id(entry: dict) -> str:
    return f"{entry.get('category')}:{entry.get('module')}:{entry.get('kind')}"


def _full_url(base_url: str, path: str) -> str:
    return urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


@allure.epic("Безопасность")
@allure.feature("Авторизация публичных страниц")
@pytest.mark.security
@pytest.mark.auth
class TestPublicPagesRequireAuth:
    """Обходит реестр страниц приложения в анонимном режиме (без cookies/сессии)."""

    @pytest.mark.parametrize("entry", PUBLIC_PAGES_REGISTRY, ids=_entry_id)
    @allure.title("Анонимный доступ: {entry[path]}")
    def test_page_requires_auth(self, page, config, screenshot_utils, entry):
        url = _full_url(config["baseUrl"], entry["path"])
        category = entry["category"]

        allure.dynamic.description(entry.get("note", ""))

        with allure.step(f"Открытие {url} без авторизации (чистый контекст браузера)"):
            try:
                response = page.goto(url, timeout=30000)
                page.wait_for_load_state("domcontentloaded", timeout=15000)
            except Exception as e:
                screenshot_utils.save_error_screenshot(f"nav_error_{entry['module']}_{entry['kind']}")
                allure.attach(str(e), name="Ошибка навигации", attachment_type=allure.attachment_type.TEXT)
                pytest.fail(f"Не удалось открыть {url}: {e}")

            status = response.status if response else None
            final_url = page.url
            content = page.content()

            AllureHelper.attach_test_data({
                "url": url,
                "final_url": final_url,
                "status": status,
                "category": category,
                "note": entry.get("note", ""),
            }, "Результат перехода")
            screenshot_utils.take_screenshot(f"{entry['module']}_{entry['kind']}")

        with allure.step("Оценка результата"):
            if status is not None and status >= 500:
                allure.attach(content[:5000], name="HTML при серверной ошибке", attachment_type=allure.attachment_type.HTML)
                pytest.fail(f"{url} вернул серверную ошибку {status} для анонимного запроса")

            redirected_to_auth = "/auth/" in final_url

            if category == "public":
                if _looks_broken(content):
                    allure.attach(content[:5000], name="HTML публичной страницы", attachment_type=allure.attachment_type.HTML)
                    pytest.fail(f"{url} — публичная по замыслу страница отдала содержимое, похожее на необработанную ошибку")
                return

            if redirected_to_auth:
                return

            if category == "known_risk":
                allure.attach(content[:8000], name="HTML при обходе авторизации", attachment_type=allure.attachment_type.HTML)
                pytest.fail(
                    f"{url} не редиректит на /auth/ (status={status}, final_url={final_url}). "
                    f"{entry.get('note', '')}"
                )

            # category == "protected"
            if status in SAFE_NO_CONTENT_STATUSES:
                allure.attach(
                    f"Редиректа на /auth/ не было, но доступ отклонён статусом {status} "
                    f"(вероятно, действие/id не существует как маршрут) — данные не раскрыты.",
                    name="Без редиректа, но безопасно",
                    attachment_type=allure.attachment_type.TEXT,
                )
                return

            allure.attach(content[:8000], name="HTML незащищённой страницы", attachment_type=allure.attachment_type.HTML)
            pytest.fail(
                f"{url} открылся без авторизации: редиректа на /auth/ не произошло, "
                f"итоговый URL: {final_url} (status={status})"
            )

    @allure.title("docs.php не должен быть доступен без авторизации")
    @allure.severity("CRITICAL")
    def test_docs_php_blocked_for_anon(self, page, config):
        """
        docs.php — самостоятельный скрипт вне роутера Liner (нет Liner::init(),
        нет проверки сессии). Гейт в коде — `if (empty($_GET['is_dev']))`,
        обходится параметром ?is_dev=1. Проверяем только безопасный GET без
        ?type=create (который на сервере запускает phpdoc/tar).
        """
        url = config["baseUrl"].rstrip("/") + "/docs.php?is_dev=1"
        response = page.request.get(url)
        status = response.status
        body = response.text()[:3000]

        allure.attach(body, name=f"Ответ docs.php (status={status})", attachment_type=allure.attachment_type.TEXT)

        assert status >= 400, (
            f"/docs.php?is_dev=1 вернул {status} без авторизации — скрипт вне роутера Liner "
            f"и потенциально раскрывает служебную информацию/сборку документации анонимному пользователю"
        )
