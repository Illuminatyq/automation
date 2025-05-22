from playwright.sync_api import PlaywrightContextManager
import os

def run(playwright: PlaywrightContextManager):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        record_video_dir='./videos' if os.getenv('RECORD_VIDEO') else None,
        record_video_size={'width': 1920, 'height': 1080}
    )
    
    # Включаем трассировку
    context.tracing.start(screenshots=True, snapshots=True, sources=True)
    
    page = context.new_page()
    
    try:
        # Ваш код тестов
        pass
    finally:
        # Сохраняем трассировку
        context.tracing.stop(path='./trace.zip')
        context.close()
        browser.close()

if __name__ == '__main__':
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        run(playwright) 