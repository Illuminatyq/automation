#!/usr/bin/env python3
"""
Скрипт для запуска тестов телефонии с разными режимами моков
Теперь использует dev окружение: https://liner.dstepanyuk.dev.smte.am
"""

import os
import sys
import subprocess
import argparse
from typing import List, Optional

def run_tests_with_mode(mode: str, test_file: str = "tests/test_telephony_integration.py", 
                       additional_args: Optional[List[str]] = None) -> int:
    """
    Запуск тестов с указанным режимом моков
    
    Args:
        mode: Режим моков (FULL_MOCK, PARTIAL_MOCK, NO_MOCK, STRICT_NO_MOCK)
        test_file: Путь к файлу с тестами
        additional_args: Дополнительные аргументы для pytest
    
    Returns:
        Код возврата pytest
    """
    
    # Настройки для разных режимов
    mock_settings = {
        'FULL_MOCK': {
            'USE_MOCKS': 'true',
            'USE_VOXIMPLANT_MOCK': 'true',
            'FAIL_ON_API_ERROR': 'false'
        },
        'PARTIAL_MOCK': {
            'USE_MOCKS': 'true',
            'USE_VOXIMPLANT_MOCK': 'false',
            'FAIL_ON_API_ERROR': 'false'
        },
        'NO_MOCK': {
            'USE_MOCKS': 'false',
            'USE_VOXIMPLANT_MOCK': 'false',
            'FAIL_ON_API_ERROR': 'true'
        },
        'STRICT_NO_MOCK': {
            'USE_MOCKS': 'false',
            'USE_VOXIMPLANT_MOCK': 'false',
            'FAIL_ON_API_ERROR': 'true'
        }
    }
    
    if mode not in mock_settings:
        print(f"❌ Неизвестный режим: {mode}")
        print(f"Доступные режимы: {list(mock_settings.keys())}")
        return 1
    
    # Устанавливаем переменные окружения
    env = os.environ.copy()
    env.update(mock_settings[mode])
    
    # Формируем команду pytest
    cmd = [
        sys.executable, '-m', 'pytest',
        test_file,
        '-v',
        '--tb=short'
    ]
    
    if additional_args:
        cmd.extend(additional_args)
    
    print(f"🚀 Запуск тестов в режиме: {mode}")
    print(f"📁 Файл: {test_file}")
    print(f"🌐 API: https://liner.dstepanyuk.dev.smte.am (dev окружение)")
    print(f"⚙️  Настройки: {mock_settings[mode]}")
    print(f"🔧 Команда: {' '.join(cmd)}")
    print("-" * 60)
    
    try:
        result = subprocess.run(cmd, env=env, check=False)
        return result.returncode
    except KeyboardInterrupt:
        print("\n⏹️  Тесты прерваны пользователем")
        return 1
    except Exception as e:
        print(f"❌ Ошибка запуска тестов: {e}")
        return 1

def run_all_modes(test_file: str = "tests/test_telephony_integration.py", 
                 additional_args: Optional[List[str]] = None) -> None:
    """
    Запуск тестов во всех режимах моков
    """
    modes = ['FULL_MOCK', 'PARTIAL_MOCK', 'NO_MOCK']
    results = {}
    
    print("🧪 Запуск тестов во всех режимах моков")
    print("🌐 API: https://liner.dstepanyuk.dev.smte.am (dev окружение)")
    print("=" * 60)
    
    for mode in modes:
        print(f"\n📋 Режим: {mode}")
        result = run_tests_with_mode(mode, test_file, additional_args)
        results[mode] = result
        
        if result == 0:
            print(f"✅ {mode}: УСПЕХ")
        else:
            print(f"❌ {mode}: ОШИБКА (код: {result})")
    
    print("\n" + "=" * 60)
    print("📊 ИТОГОВЫЕ РЕЗУЛЬТАТЫ:")
    for mode, result in results.items():
        status = "✅ УСПЕХ" if result == 0 else f"❌ ОШИБКА ({result})"
        print(f"  {mode}: {status}")

def main():
    parser = argparse.ArgumentParser(
        description="Запуск тестов телефонии с разными режимами моков (dev окружение)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  # Запуск с моками (по умолчанию)
  python run_telephony_tests.py
  
  # Запуск без моков (реальные API вызовы на dev)
  python run_telephony_tests.py --mode NO_MOCK
  
  # Запуск во всех режимах
  python run_telephony_tests.py --all-modes
  
  # Запуск с дополнительными параметрами
  python run_telephony_tests.py --mode NO_MOCK -- -k "test_operator_status"
  
  # Запуск другого файла тестов
  python run_telephony_tests.py --mode NO_MOCK --test-file tests/test_telephony_integration_no_mocks.py

API: https://liner.dstepanyuk.dev.smte.am
        """
    )
    
    parser.add_argument(
        '--mode',
        choices=['FULL_MOCK', 'PARTIAL_MOCK', 'NO_MOCK', 'STRICT_NO_MOCK'],
        default='FULL_MOCK',
        help='Режим моков (по умолчанию: FULL_MOCK)'
    )
    
    parser.add_argument(
        '--test-file',
        default='tests/test_telephony_integration.py',
        help='Путь к файлу с тестами (по умолчанию: tests/test_telephony_integration.py)'
    )
    
    parser.add_argument(
        '--all-modes',
        action='store_true',
        help='Запустить тесты во всех режимах моков'
    )
    
    parser.add_argument(
        '--list-modes',
        action='store_true',
        help='Показать доступные режимы и их описание'
    )
    
    # Все остальные аргументы передаются в pytest
    args, pytest_args = parser.parse_known_args()
    
    if args.list_modes:
        print("📋 Доступные режимы моков:")
        print("  FULL_MOCK      - Полные моки (Voximplant + fallback логика)")
        print("  PARTIAL_MOCK   - Частичные моки (только fallback логика)")
        print("  NO_MOCK        - Без моков (реальные API вызовы на dev)")
        print("  STRICT_NO_MOCK - Строгий режим без моков (падает при ошибках API)")
        print(f"\n🌐 API: https://liner.dstepanyuk.dev.smte.am")
        return 0
    
    if args.all_modes:
        run_all_modes(args.test_file, pytest_args)
        return 0
    
    return run_tests_with_mode(args.mode, args.test_file, pytest_args)

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 