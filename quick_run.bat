@echo off
setlocal enabledelayedexpansion

echo Запуск тестов в фоновом режиме...

REM Проверка наличия Python
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Python не найден! Пожалуйста, установите Python и добавьте его в PATH
    pause
    exit /b 1
)

REM Активация виртуального окружения
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)

REM Очистка старых результатов
if exist allure-results (
    echo Удаление старых результатов...
    rmdir /s /q allure-results
)
mkdir allure-results

REM Запуск тестов в фоновом режиме
echo Запуск тестов...
start /B cmd /c "python -m pytest tests/test_auth.py tests/test_ui_layout.py tests/test_leads.py -v --alluredir=./allure-results --browser=chromium --headless > test_output.log 2>&1"

REM Ждем завершения тестов
echo Ожидание завершения тестов...
:WAIT_LOOP
timeout /t 5 /nobreak >nul
findstr /C:"FAILED" test_output.log >nul
if %ERRORLEVEL% equ 0 goto TESTS_DONE
findstr /C:"passed" test_output.log >nul
if %ERRORLEVEL% equ 0 goto TESTS_DONE
goto WAIT_LOOP

:TESTS_DONE
echo Тесты завершены, запуск Allure...

REM Запуск Allure в фоновом режиме
start /B cmd /c "allure serve ./allure-results --config-file ./config/allure_config.json > allure_output.log 2>&1"

REM Ждем запуска Allure
timeout /t 5 /nobreak >nul

echo.
echo Тесты выполнены. Результаты:
type test_output.log
echo.
echo Отчет Allure запущен в фоновом режиме.
echo Для просмотра результатов откройте браузер по адресу, указанному выше.
echo.
echo Нажмите любую клавишу для выхода...
pause >nul 