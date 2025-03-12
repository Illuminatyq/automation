import pytest
import os
import json
from playwright.sync_api import sync_playwright

def pytest_addoption(parser):
    parser.addoption("--env", action="store", default=None, help="Environment to run tests against")

def pytest_configure(config):
    config.addinivalue_line("markers", "visual: mark test as visual regression test")

@pytest.fixture(scope="session")
def config(request):
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "config.json")
    with open(config_path, "r") as f:
        config = json.load(f)

    env_name = request.config.getoption("--env") or config.get("defaultEnvironment", "dev")
    if env_name not in config.get("environments", {}):
        available_envs = ", ".join(config["environments"].keys())
        pytest.fail(f"Environment '{env_name}' not found. Available: {available_envs}")

    config.update(config["environments"][env_name])
    config["current_environment"] = env_name
    return config

@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, devtools=True)
        yield browser
        browser.close()

@pytest.fixture
def page(browser):
    context = browser.new_context(viewport={"width": 1280, "height": 720})
    page = context.new_page()
    yield page
    page.close()
    context.close()

@pytest.fixture
def authenticated_page(page, config):
    from pages.login_page import LoginPage
    login_page = LoginPage(page, config["baseUrl"])
    login_page.navigate()
    creds = config["credentials"]["valid_user"]
    login_page.login(creds["email"], creds["password"])
    page.wait_for_url("**/*office*", timeout=10000)
    return page