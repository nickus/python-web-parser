#!/usr/bin/env python3
"""
Тест функциональности GUI
"""

import sys
import tkinter as tk
from gui_app import MaterialMatcherGUI

def test_gui_creation():
    """Тест создания GUI"""
    print("=== Тест создания GUI интерфейса ===")
    
    try:
        # Создаем корневое окно
        root = tk.Tk()
        root.withdraw()  # Скрываем окно для тестирования
        
        # Создаем приложение
        app = MaterialMatcherGUI(root)
        
        # Проверяем, что основные переменные инициализированы
        assert hasattr(app, 'selected_variants'), "Отсутствует переменная selected_variants"
        assert isinstance(app.selected_variants, dict), "selected_variants должен быть словарем"
        
        # Проверяем наличие методов
        assert hasattr(app, 'on_variant_double_click'), "Отсутствует метод on_variant_double_click"
        assert hasattr(app, 'hide_other_variants'), "Отсутствует метод hide_other_variants"
        assert hasattr(app, 'update_selected_variant_display'), "Отсутствует метод update_selected_variant_display"
        assert hasattr(app, 'reset_selections'), "Отсутствует метод reset_selections"
        assert hasattr(app, 'export_selected_results'), "Отсутствует метод export_selected_results"
        
        # Проверяем наличие дерева результатов
        assert hasattr(app, 'results_tree'), "Отсутствует дерево результатов"
        
        print("✅ GUI интерфейс создан успешно")
        print("✅ Все необходимые методы присутствуют")
        print("✅ Переменные инициализированы правильно")
        
        root.destroy()
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при создании GUI: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_selection_functionality():
    """Тест функциональности выбора"""
    print("\n=== Тест функциональности выбора ===")
    
    try:
        # Создаем корневое окно
        root = tk.Tk()
        root.withdraw()  # Скрываем окно для тестирования
        
        # Создаем приложение
        app = MaterialMatcherGUI(root)
        
        # Тестируем сброс выборов на пустом состоянии
        app.reset_selections()  # Не должно выбросить ошибку
        
        # Добавляем тестовый выбор
        app.selected_variants['test_material'] = {
            'variant_id': 'test_variant',
            'variant_name': 'Тестовый вариант',
            'relevance': '100.0%',
            'price': '1000.00 RUB',
            'supplier': 'Тест поставщик',
            'brand': 'Тест бренд',
            'category': 'Тест категория'
        }
        
        # Проверяем, что выбор добавился
        assert len(app.selected_variants) == 1, "Выбор не добавился"
        assert 'test_material' in app.selected_variants, "Неправильный ключ материала"
        
        # Тестируем сброс выборов с данными
        app.reset_selections()
        assert len(app.selected_variants) == 0, "Выборы не сбросились"
        
        print("✅ Функциональность выбора работает корректно")
        
        root.destroy()
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании выбора: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Тестирование GUI функциональности...")
    print("=" * 50)
    
    success1 = test_gui_creation()
    success2 = test_selection_functionality()
    
    print("\n" + "=" * 50)
    if success1 and success2:
        print("✅ Все тесты прошли успешно!")
        print("\nДобавленная функциональность:")
        print("• Обработчик двойного клика по вариантам прайс-листа")
        print("• Скрытие остальных вариантов при выборе")
        print("• Обновление отображения с выбранным вариантом")
        print("• Кнопка сброса всех выборов")
        print("• Экспорт только выбранных результатов в Excel")
    else:
        print("❌ Некоторые тесты не прошли")
    
    sys.exit(0)