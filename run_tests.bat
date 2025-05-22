@echo off
setlocal enabledelayedexpansion

REM Проверка наличия Python
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Python не найден! Пожалуйста, установите Python и добавьте его в PATH
    pause
    exit /b 1
)

REM Проверка наличия Allure
where allure >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Allure не найден! Устанавливаем...
    call pip install allure-commandline
    if %ERRORLEVEL% neq 0 (
        echo Не удалось установить Allure
        pause
        exit /b 1
    )
)

REM Проверка наличия зависимостей
echo Проверка и установка зависимостей...
call pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo Ошибка при установке зависимостей
    pause
    exit /b 1
)

REM Установка Playwright
echo Установка браузеров Playwright...
call playwright install
if %ERRORLEVEL% neq 0 (
    echo Ошибка при установке браузеров
    pause
    exit /b 1
)

REM Очистка старых результатов
if exist allure-results (
    echo Удаление старых результатов...
    rmdir /s /q allure-results
)
mkdir allure-results

REM Запуск API-тестов
echo.
echo Запуск API-тестов...
python -m pytest tests/test_api.py -v --env=dev --alluredir=./allure-results
set API_RESULT=%ERRORLEVEL%

REM Запуск UI-тестов
echo.
echo Запуск UI-тестов...
python -m pytest tests/test_auth.py tests/test_ui_layout.py -v --env=dev --browser=chromium --alluredir=./allure-results
set UI_RESULT=%ERRORLEVEL%

REM Проверка результатов тестов
if %API_RESULT% neq 0 (
    echo.
    echo ВНИМАНИЕ: API-тесты завершились с ошибками
)
if %UI_RESULT% neq 0 (
    echo.
    echo ВНИМАНИЕ: UI-тесты завершились с ошибками
)

REM Запуск сервера Allure с локализацией
echo.
echo Запуск сервера Allure...
allure serve ./allure-results --config-file ./config/allure_config.json

echo.
echo Тесты завершены.
echo Для просмотра результатов откройте браузер по адресу, указанному выше.
echo.
pause 