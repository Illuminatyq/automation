import tkinter as tk
from tkinter import ttk, filedialog
import subprocess
import threading
import os
import json
import logging
import webbrowser

# Попытка загрузить переменные окружения из .env файла
try:
    from dotenv import load_dotenv
    load_dotenv()
    logging.info("Переменные окружения загружены из .env файла")
except ImportError:
    logging.warning("python-dotenv не установлен. Переменные окружения из .env файла не загружены.")

# Настройка логирования
logging.basicConfig(filename="test_execution.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def load_environments():
    """Загрузка сред из конфигурации"""
    config_path = os.path.join(os.path.dirname(__file__), "config", "config.json")
    try:
        with open(config_path, "r") as f:
            return {k: v.get("description", k) for k, v in json.load(f)["environments"].items()}
    except Exception as e:
        logging.error(f"Ошибка загрузки конфигурации: {e}")
        return {"dev": "Разработка (по умолчанию)"}

def run_command(command):
    """Выполнение команды с выводом в текстовое поле"""
    output_text.insert(tk.END, f"Выполнение: {command}\n")
    output_text.see(tk.END)
    
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True)
    for line in process.stdout:
        output_text.insert(tk.END, line)
        output_text.see(tk.END)
        root.update()
        logging.info(line.strip())
    
    process.wait()
    output_text.insert(tk.END, f"\n{'='*40}\nЗавершено. Код выхода: {process.returncode}\n{'='*40}\n")

def run_in_thread(command):
    """Запуск команды в отдельном потоке"""
    output_text.delete(1.0, tk.END)
    # Проверяем, является ли command функцией
    if callable(command):
        threading.Thread(target=command, daemon=True).start()
    else:
        threading.Thread(target=run_command, args=(command,), daemon=True).start()

def get_selected_env():
    """Получение выбранной среды"""
    return env_var.get().split(" - ")[0]

def get_api_key():
    """Получение API ключа из поля ввода"""
    api_key = api_key_var.get().strip()
    if api_key:
        return f"--api-key={api_key}"
    return ""

def get_browser_option():
    """Получение опции браузера для запуска тестов"""
    browser = browser_var.get()
    headless_option = "--headless" if headless_var.get() else ""
    
    # Формируем строку параметров
    options = []
    if browser:
        options.append(f"--browser={browser}")
    if headless_option:
        options.append(headless_option)
    
    return " ".join(options)

def generate_allure_report():
    """Генерация отчета Allure"""
    command = "allure generate ./allure-results -o ./allure-report --clean"
    run_in_thread(command)

def open_allure_report():
    """Открытие отчета Allure в браузере"""
    report_path = os.path.abspath("./allure-report/index.html")
    if os.path.exists(report_path):
        webbrowser.open(f"file://{report_path}")
    else:
        output_text.insert(tk.END, "Отчет не найден. Сначала сгенерируйте отчет.\n")

def serve_allure_report():
    """Запуск сервера Allure для просмотра отчета"""
    # Проверяем, существует ли директория с результатами
    if not os.path.exists("./allure-results") or not os.listdir("./allure-results"):
        output_text.insert(tk.END, "Нет результатов тестов для отображения. Сначала запустите тесты.\n")
        return
    
    # Запускаем сервер Allure
    command = "allure serve ./allure-results"
    output_text.insert(tk.END, f"Запуск сервера Allure: {command}\n")
    run_in_thread(command)

def open_screenshots_folder():
    """Открытие папки со скриншотами"""
    screenshots_path = os.path.abspath("./screenshots")
    os.makedirs(screenshots_path, exist_ok=True)
    if os.name == 'nt':  # Windows
        os.startfile(screenshots_path)
    else:  # Linux/Mac
        subprocess.run(['xdg-open', screenshots_path])

def run_api_tests():
    """Запуск API-тестов с API ключом"""
    api_key_param = get_api_key()
    # Устанавливаем переменные окружения
    if api_key_var.get().strip():
        os.environ["LINER_API_KEY"] = api_key_var.get().strip()
    
    # Устанавливаем режим заглушки
    os.environ["USE_MOCK"] = str(use_mock_var.get()).lower()
    
    # Для API-тестов не используем параметр --browser
    command = f"python -m pytest tests/test_api.py -v --env={get_selected_env()} {api_key_param} --alluredir=./allure-results"
    run_in_thread(command)

def run_all_tests():
    """Запуск всех тестов (API и UI) без генерации отчета Allure"""
    # Запуск API-тестов
    api_key_param = get_api_key()
    if api_key_var.get().strip():
        os.environ["LINER_API_KEY"] = api_key_var.get().strip()
    os.environ["USE_MOCK"] = str(use_mock_var.get()).lower()
    
    api_command = f"python -m pytest tests/test_api.py -v --env={get_selected_env()} {api_key_param}"
    output_text.insert(tk.END, f"Выполнение API-тестов: {api_command}\n")
    output_text.see(tk.END)
    
    process = subprocess.Popen(api_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True)
    for line in process.stdout:
        output_text.insert(tk.END, line)
        output_text.see(tk.END)
        root.update()
        logging.info(line.strip())
    
    process.wait()
    output_text.insert(tk.END, f"\n{'='*40}\nAPI-тесты завершены. Код выхода: {process.returncode}\n{'='*40}\n")
    
    # Запуск UI-тестов
    browser_option = get_browser_option()
    ui_command = f"python -m pytest tests/test_auth.py tests/test_ui_layout.py -v --env={get_selected_env()} {browser_option}"
    output_text.insert(tk.END, f"Выполнение UI-тестов: {ui_command}\n")
    output_text.see(tk.END)
    
    process = subprocess.Popen(ui_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True)
    for line in process.stdout:
        output_text.insert(tk.END, line)
        output_text.see(tk.END)
        root.update()
        logging.info(line.strip())
    
    process.wait()
    output_text.insert(tk.END, f"\n{'='*40}\nUI-тесты завершены. Код выхода: {process.returncode}\n{'='*40}\n")

def run_all_tests_with_allure():
    """Запуск всех тестов (API и UI) с генерацией отчета Allure"""
    # Очистка старых результатов
    if os.path.exists("./allure-results"):
        import shutil
        shutil.rmtree("./allure-results")
        output_text.insert(tk.END, "Старые результаты тестов удалены\n")
    
    # Запуск API-тестов
    api_key_param = get_api_key()
    if api_key_var.get().strip():
        os.environ["LINER_API_KEY"] = api_key_var.get().strip()
    os.environ["USE_MOCK"] = str(use_mock_var.get()).lower()
    
    api_command = f"python -m pytest tests/test_api.py -v --env={get_selected_env()} {api_key_param} --alluredir=./allure-results"
    output_text.insert(tk.END, f"Выполнение API-тестов: {api_command}\n")
    output_text.see(tk.END)
    
    process = subprocess.Popen(api_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True)
    for line in process.stdout:
        output_text.insert(tk.END, line)
        output_text.see(tk.END)
        root.update()
        logging.info(line.strip())
    
    process.wait()
    output_text.insert(tk.END, f"\n{'='*40}\nAPI-тесты завершены. Код выхода: {process.returncode}\n{'='*40}\n")
    
    # Запуск UI-тестов
    browser_option = get_browser_option()
    ui_command = f"python -m pytest tests/test_auth.py tests/test_ui_layout.py -v --env={get_selected_env()} {browser_option} --alluredir=./allure-results"
    output_text.insert(tk.END, f"Выполнение UI-тестов: {ui_command}\n")
    output_text.see(tk.END)
    
    process = subprocess.Popen(ui_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True)
    for line in process.stdout:
        output_text.insert(tk.END, line)
        output_text.see(tk.END)
        root.update()
        logging.info(line.strip())
    
    process.wait()
    output_text.insert(tk.END, f"\n{'='*40}\nUI-тесты завершены. Код выхода: {process.returncode}\n{'='*40}\n")
    
    # Запуск Allure-сервера вместо генерации статического отчета
    output_text.insert(tk.END, "Запуск сервера Allure...\n")
    serve_allure_report()

def run_auth_tests_command():
    """Формирует команду для запуска тестов авторизации"""
    browser_option = get_browser_option()
    return f"python -m pytest tests/test_auth.py -v --env={get_selected_env()} {browser_option}"

def run_ui_tests_command():
    """Формирует команду для запуска UI-тестов"""
    browser_option = get_browser_option()
    return f"python -m pytest tests/test_ui_layout.py -v --env={get_selected_env()} {browser_option}"

def run_layout_test_command():
    """Формирует команду для запуска теста верстки авторизации"""
    browser_option = get_browser_option()
    return f"python -m pytest tests/test_ui_layout.py::TestUILayout::test_auth_page_layout -v --env={get_selected_env()} {browser_option}"

# Создание главного окна
root = tk.Tk()
root.title("Запуск UI-тестов")
root.geometry("800x600")

# Создание фрейма для выбора среды
env_frame = tk.Frame(root)
env_frame.pack(pady=10, padx=10, fill=tk.X)
tk.Label(env_frame, text="Среда:").pack(side=tk.LEFT, padx=5)
env_options = [f"{k} - {v}" for k, v in load_environments().items()]
env_var = tk.StringVar(value=env_options[0])
ttk.Combobox(env_frame, textvariable=env_var, values=env_options, state="readonly").pack(side=tk.LEFT, fill=tk.X, expand=True)

# Создание фрейма для выбора браузера
browser_frame = tk.Frame(root)
browser_frame.pack(pady=5, padx=10, fill=tk.X)
tk.Label(browser_frame, text="Браузер:").pack(side=tk.LEFT, padx=5)
browser_options = ["chromium", "firefox", "webkit"]
browser_var = tk.StringVar(value=browser_options[0])
ttk.Combobox(browser_frame, textvariable=browser_var, values=browser_options, state="readonly").pack(side=tk.LEFT, fill=tk.X, expand=True)

# Создание фрейма для дополнительных опций
options_frame = tk.Frame(root)
options_frame.pack(pady=5, padx=10, fill=tk.X)
headless_var = tk.BooleanVar(value=False)
tk.Checkbutton(options_frame, text="Headless режим (без отображения браузера)", variable=headless_var).pack(side=tk.LEFT, padx=5)

# Создание фрейма для API ключа
api_key_frame = tk.Frame(root)
api_key_frame.pack(pady=5, padx=10, fill=tk.X)
tk.Label(api_key_frame, text="API ключ:").pack(side=tk.LEFT, padx=5)
api_key_var = tk.StringVar()
tk.Entry(api_key_frame, textvariable=api_key_var, width=40, show="*").pack(side=tk.LEFT, fill=tk.X, expand=True)

# Создание фрейма для настроек API тестов
api_settings_frame = tk.Frame(root)
api_settings_frame.pack(pady=5, padx=10, fill=tk.X)
use_mock_var = tk.BooleanVar(value=True)
tk.Checkbutton(api_settings_frame, text="Использовать заглушки", variable=use_mock_var).pack(side=tk.LEFT, padx=5)
tk.Button(api_settings_frame, text="Запустить API-тесты", command=lambda: run_api_tests(), bg="#ffe6ff").pack(side=tk.RIGHT, padx=5)

# Создание фреймов для кнопок
button_frame1 = tk.Frame(root)
button_frame1.pack(pady=5, fill=tk.X)

button_frame2 = tk.Frame(root)
button_frame2.pack(pady=5, fill=tk.X)

# Добавление кнопок в первый фрейм
buttons1 = [
    ("Установить зависимости", lambda: run_in_thread("pip install -r requirements.txt && playwright install && pip install allure-commandline"), "#e6f7ff"),
    ("Запустить все тесты", lambda: run_in_thread(run_all_tests), "#e6ffe6"),
    ("Тесты авторизации", lambda: run_in_thread(run_auth_tests_command()), "#fff2e6"),
    ("UI-тесты", lambda: run_in_thread(run_ui_tests_command()), "#e6e6ff"),
    ("Тест верстки авторизации", lambda: run_in_thread(run_layout_test_command()), "#ffe6ff"),
]

for text, cmd, bg in buttons1:
    tk.Button(button_frame1, text=text, command=cmd, bg=bg, padx=10, pady=5).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

# Добавление кнопок для Allure во второй фрейм
buttons2 = [
    ("Запустить с Allure", lambda: run_in_thread(run_all_tests_with_allure), "#ffe6e6"),
    ("Сгенерировать отчет", lambda: generate_allure_report(), "#ffd1dc"),
    ("Открыть отчет", lambda: open_allure_report(), "#d1ffdc"),
    ("Запустить сервер Allure", lambda: serve_allure_report(), "#d1dcff"),
    ("Открыть скриншоты", lambda: open_screenshots_folder(), "#f0f0f0"),
    ("Запустить всё и открыть отчет", lambda: run_in_thread(run_all_tests_with_allure), "#ffccaa"),
]

for text, cmd, bg in buttons2:
    tk.Button(button_frame2, text=text, command=cmd, bg=bg, padx=10, pady=5).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

# Создание текстового поля вывода
output_text = tk.Text(root, bg="black", fg="white")
output_text.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
scrollbar = tk.Scrollbar(output_text, command=output_text.yview)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
output_text.config(yscrollcommand=scrollbar.set)

# Вывод начального сообщения
output_text.insert(tk.END, f"Запуск UI-тестов готов.\nВыбранная среда: {get_selected_env()}\nВыберите действие выше.\n")

if __name__ == "__main__":
    # Проверяем аргументы командной строки
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--run-all":
        # Запускаем все тесты с очисткой результатов и открытием отчета
        print("Запуск всех тестов с очисткой результатов и открытием отчета...")
        
        # Очистка старых результатов
        if os.path.exists("./allure-results"):
            import shutil
            shutil.rmtree("./allure-results")
            print("Старые результаты тестов удалены")
        
        # Определяем браузер из аргументов или используем chromium по умолчанию
        browser = "chromium"
        headless = False
        api_key = ""
        use_mock = "true"
        
        for arg in sys.argv:
            if arg.startswith("--browser="):
                browser = arg.split("=")[1]
            elif arg == "--headless":
                headless = True
            elif arg.startswith("--api-key="):
                api_key = arg.split("=")[1]
            elif arg.startswith("--use-mock="):
                use_mock = arg.split("=")[1].lower()
        
        # Устанавливаем переменные окружения для API-тестов
        if api_key:
            os.environ["LINER_API_KEY"] = api_key
        os.environ["USE_MOCK"] = use_mock
        
        # Запускаем API-тесты (без параметра --browser)
        api_key_param = f"--api-key={api_key}" if api_key else ""
        api_command = f"python -m pytest tests/test_api.py -v --env=dev {api_key_param} --alluredir=./allure-results"
        print(f"Выполнение API-тестов: {api_command}")
        subprocess.run(api_command, shell=True)
        
        # Запускаем UI-тесты (с параметром --browser)
        browser_option = f"--browser={browser}"
        if headless:
            browser_option += " --headless"
        
        ui_command = f"python -m pytest tests/test_auth.py tests/test_ui_layout.py -v --env=dev {browser_option} --alluredir=./allure-results"
        print(f"Выполнение UI-тестов: {ui_command}")
        subprocess.run(ui_command, shell=True)
        
        # Запуск Allure-сервера
        print("Запуск сервера Allure...")
        subprocess.run("allure serve ./allure-results", shell=True)
        
        sys.exit(0)
    
    # Запуск GUI
    root.mainloop()