import pytest
import os
from playwright.sync_api import expect
import allure

@allure.feature("UI Layout")
@pytest.mark.visual
class TestUILayout:
    @allure.story("Calls preset page layout")
    @allure.severity(allure.severity_level.NORMAL)
    def test_calls_preset_layout(self, authenticated_page):
        page = authenticated_page
        preset_url = "https://liner.dstepanyuk.dev.smte.am/calls/?daterange=17.02.2025%20-%2003.03.2025&period=default&lead_id=&type=all&direction=all&predictive=all&isset_call=&total_call_time=all&client_call_time=all&call_record=all&call_recognition=all&call-hangups=all&rating=all&preset-name=Новый%20пресет"
        page.goto(preset_url)
        page.wait_for_load_state("networkidle")

        screenshot_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "screenshots")
        baseline_path = os.path.join(screenshot_dir, "baseline", "calls_preset.png")
        actual_path = os.path.join(screenshot_dir, "actual", "calls_preset.png")
        diff_path = os.path.join(screenshot_dir, "diff", "calls_preset.png")

        os.makedirs(os.path.dirname(baseline_path), exist_ok=True)

        if not os.path.exists(baseline_path):
            page.screenshot(path=baseline_path, full_page=True)
            allure.attach.file(baseline_path, "Baseline Created", allure.attachment_type.PNG)
            pytest.skip("Baseline screenshot created. Rerun the test.")

        page.screenshot(path=actual_path, full_page=True)
        allure.attach.file(actual_path, "Current Screenshot", allure.attachment_type.PNG)
        allure.attach.file(baseline_path, "Baseline Screenshot", allure.attachment_type.PNG)

        expect(page).to_have_screenshot(baseline_path, threshold=0.1, full_page=True)