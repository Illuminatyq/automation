#!/usr/bin/env python3
"""
Утилита для получения реальных данных телефонии из dev системы
"""

import requests
import json
import os
import sys
from typing import Dict, List, Optional
import urllib3

# Отключаем предупреждения о небезопасных запросах
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class TelephonyDataExtractor:
    """Класс для извлечения реальных данных телефонии"""
    
    def __init__(self, base_url: str = "https://liner.dstepanyuk.dev.smte.am"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.verify = False
        
    def get_operators(self) -> List[Dict]:
        """Получение списка операторов"""
        try:
            url = f"{self.base_url}/api/?controller=Vats&method=getOnlineReadyEmployees"
            response = self.session.get(url)
            
            if response.status_code == 200:
                data = response.json()
                operators = []
                
                for operator in data.get('result', []):
                    operators.append({
                        "id": str(operator.get('ID', '')),
                        "vox_user_name": operator.get('UF_VOX_USER_NAME', ''),
                        "display_name": operator.get('UF_NAME', ''),
                        "status": operator.get('UF_UIS_STATUS', ''),
                        "is_available": operator.get('IS_AVAILABLE', False)
                    })
                
                return operators
            else:
                print(f"❌ Ошибка получения операторов: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"❌ Ошибка при получении операторов: {e}")
            return []
    
    def get_leads(self) -> List[Dict]:
        """Получение списка лидов"""
        try:
            url = f"{self.base_url}/api/?controller=Vats&method=getDialerQueue"
            response = self.session.get(url)
            
            if response.status_code == 200:
                data = response.json()
                leads = []
                
                for lead in data.get('queue', []):
                    leads.append({
                        "id": str(lead.get('lead_id', '')),
                        "phone": lead.get('phone', ''),
                        "name": lead.get('name', ''),
                        "order_id": str(lead.get('order_id', '')),
                        "status": lead.get('status', '')
                    })
                
                return leads
            else:
                print(f"❌ Ошибка получения лидов: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"❌ Ошибка при получении лидов: {e}")
            return []
    
    def get_operator_status(self, operator_id: str) -> Optional[Dict]:
        """Получение статуса конкретного оператора"""
        try:
            url = f"{self.base_url}/api/?controller=Vats&method=getEmployeeStatus"
            params = {'operator_id': operator_id}
            response = self.session.get(url, params=params)
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ Ошибка получения статуса оператора: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Ошибка при получении статуса оператора: {e}")
            return None
    
    def generate_config(self, operators: List[Dict], leads: List[Dict]) -> Dict:
        """Генерация конфигурации на основе реальных данных"""
        
        # Фильтруем только доступных операторов
        available_operators = [
            op for op in operators 
            if op.get('vox_user_name') and op.get('is_available')
        ]
        
        # Берем первые 2 оператора для тестов
        test_operators = available_operators[:2]
        
        # Берем первые 2 лида для тестов
        test_leads = leads[:2]
        
        config = {
            "telephony": {
                "api": {
                    "base_url": self.base_url,
                    "timeout": 30,
                    "retry_attempts": 3
                },
                "test_data": {
                    "operators": test_operators,
                    "leads": test_leads,
                    "phones": [
                        {
                            "connection_type": "webrtc",
                            "params": {
                                "user_name": test_operators[0].get('vox_user_name', 'test_operator') if test_operators else 'test_operator',
                                "display_name": test_operators[0].get('display_name', 'Test Operator') if test_operators else 'Test Operator'
                            }
                        }
                    ]
                }
            }
        }
        
        return config
    
    def save_config(self, config: Dict, filename: str = "config/telephony_real_data.json"):
        """Сохранение конфигурации в файл"""
        try:
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Конфигурация сохранена в {filename}")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка сохранения конфигурации: {e}")
            return False
    
    def print_summary(self, operators: List[Dict], leads: List[Dict]):
        """Вывод сводки данных"""
        print("\n" + "="*60)
        print("📊 СВОДКА ДАННЫХ ТЕЛЕФОНИИ")
        print("="*60)
        
        print(f"\n👥 ОПЕРАТОРЫ (всего: {len(operators)})")
        for i, op in enumerate(operators[:5], 1):  # Показываем первые 5
            status_icon = "🟢" if op.get('is_available') else "🔴"
            print(f"  {i}. {status_icon} {op.get('display_name', 'N/A')} "
                  f"({op.get('vox_user_name', 'N/A')}) - {op.get('status', 'N/A')}")
        
        if len(operators) > 5:
            print(f"  ... и еще {len(operators) - 5} операторов")
        
        print(f"\n📞 ЛИДЫ (всего: {len(leads)})")
        for i, lead in enumerate(leads[:5], 1):  # Показываем первые 5
            print(f"  {i}. {lead.get('name', 'N/A')} "
                  f"({lead.get('phone', 'N/A')}) - {lead.get('status', 'N/A')}")
        
        if len(leads) > 5:
            print(f"  ... и еще {len(leads) - 5} лидов")
        
        print("\n" + "="*60)

def main():
    """Основная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Извлечение реальных данных телефонии из dev системы"
    )
    
    parser.add_argument(
        '--base-url',
        default='https://liner.dstepanyuk.dev.smte.am',
        help='Базовый URL системы (по умолчанию: dev окружение)'
    )
    
    parser.add_argument(
        '--output',
        default='config/telephony_real_data.json',
        help='Файл для сохранения конфигурации'
    )
    
    parser.add_argument(
        '--operators-only',
        action='store_true',
        help='Получить только операторов'
    )
    
    parser.add_argument(
        '--leads-only',
        action='store_true',
        help='Получить только лидов'
    )
    
    args = parser.parse_args()
    
    print("🔍 Извлечение реальных данных телефонии...")
    print(f"🌐 API: {args.base_url}")
    
    extractor = TelephonyDataExtractor(args.base_url)
    
    # Получаем данные
    operators = []
    leads = []
    
    if not args.leads_only:
        print("\n👥 Получение операторов...")
        operators = extractor.get_operators()
        print(f"✅ Найдено операторов: {len(operators)}")
    
    if not args.operators_only:
        print("\n📞 Получение лидов...")
        leads = extractor.get_leads()
        print(f"✅ Найдено лидов: {len(leads)}")
    
    # Выводим сводку
    extractor.print_summary(operators, leads)
    
    # Генерируем и сохраняем конфигурацию
    if operators or leads:
        print("\n⚙️  Генерация конфигурации...")
        config = extractor.generate_config(operators, leads)
        
        if extractor.save_config(config, args.output):
            print(f"\n📝 Пример использования в тестах:")
            print(f"```python")
            print(f"# Загрузить реальные данные")
            print(f"with open('{args.output}', 'r') as f:")
            print(f"    real_data = json.load(f)")
            print(f"")
            print(f"# Использовать в тестах")
            print(f"operator = real_data['telephony']['test_data']['operators'][0]")
            print(f"lead = real_data['telephony']['test_data']['leads'][0]")
            print(f"```")
        else:
            print("❌ Не удалось сохранить конфигурацию")
    else:
        print("❌ Не удалось получить данные для конфигурации")

if __name__ == "__main__":
    main() 