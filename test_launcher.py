import tkinter as tk
from tkinter import ttk
import subprocess
import threading
import os
import json
import logging

logging.basicConfig(filename="test_execution.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def load_environments():
    config_path = os.path.join(os.path.dirname(__file__), "config", "config.json")
    try:
        with open(config_path, "r") as f:
            return {k: v.get("description", k) for k, v in json.load(f)["environments"].items()}
    except Exception as e:
        logging.error(f"Config load error: {e}")
        return {"dev": "Development (default)"}

def run_command(command):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True)
    for line in process.stdout:
        output_text.insert(tk.END, line)
        output_text.see(tk.END)
        root.update()
        logging.info(line.strip())
    process.wait()
    output_text.insert(tk.END, f"\n{'='*40}\nDone. Exit code: {process.returncode}\n{'='*40}\n")

def run_in_thread(command):
    output_text.delete(1.0, tk.END)
    threading.Thread(target=run_command, args=(command,), daemon=True).start()

def get_selected_env():
    return env_var.get().split(" - ")[0]

root = tk.Tk()
root.title("UI Test Runner")
root.geometry("700x550")

env_frame = tk.Frame(root)
env_frame.pack(pady=10, padx=10, fill=tk.X)
tk.Label(env_frame, text="Environment:").pack(side=tk.LEFT, padx=5)
env_options = [f"{k} - {v}" for k, v in load_environments().items()]
env_var = tk.StringVar(value=env_options[0])
ttk.Combobox(env_frame, textvariable=env_var, values=env_options, state="readonly").pack(side=tk.LEFT, fill=tk.X, expand=True)

button_frame = tk.Frame(root)
button_frame.pack(pady=10, fill=tk.X)
buttons = [
    ("Install Dependencies", lambda: run_in_thread("pip install -r requirements.txt && playwright install"), "#e6f7ff"),
    ("Run All Tests", lambda: run_in_thread(f"python -m pytest tests -v --env={get_selected_env()}"), "#e6ffe6"),
    ("Auth Tests", lambda: run_in_thread(f"python -m pytest tests/test_auth.py -v --env={get_selected_env()}"), "#fff2e6"),
    ("UI Tests", lambda: run_in_thread(f"python -m pytest tests/test_ui_layout.py -v --env={get_selected_env()}"), "#e6e6ff"),
    ("Run with Allure", lambda: run_in_thread(f"python -m pytest tests -v --env={get_selected_env()} --alluredir=./allure-results"), "#ffe6e6"),
    ("Copy Output", lambda: root.clipboard_append(output_text.get(1.0, tk.END)), "#f0f0f0"),
]
for text, cmd, bg in buttons:
    tk.Button(button_frame, text=text, command=cmd, bg=bg).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

output_text = tk.Text(root, bg="black", fg="white")
output_text.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
scrollbar = tk.Scrollbar(output_text, command=output_text.yview)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
output_text.config(yscrollcommand=scrollbar.set)

output_text.insert(tk.END, f"UI Test Runner ready.\nSelected env: {get_selected_env()}\nChoose an action above.\n")
root.mainloop()