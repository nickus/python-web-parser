#!/usr/bin/env python3
"""
Тест функциональности двойного клика
"""

import tkinter as tk
from gui_app import MaterialMatcherGUI
import threading
import time

def test_double_click_functionality():
    """Тест двойного клика"""
    print("=== Тест функциональности двойного клика ===")
    
    # Создаем GUI
    root = tk.Tk()
    app = MaterialMatcherGUI(root)
    
    # Функция для автоматического создания тестовых данных в дереве
    def create_test_data():
        # Очищаем дерево
        for item in app.results_tree.get_children():
            app.results_tree.delete(item)
        
        # Добавляем тестовый материал
        parent = app.results_tree.insert("", tk.END, 
            text="Тестовый материал",
            tags=("material",)
        )
        
        # Добавляем тестовые варианты
        for i in range(3):
            child = app.results_tree.insert(parent, tk.END,
                values=(f"Тестовый вариант {i+1}", "95.0%", "1000.00 RUB", "Поставщик", "Бренд", "Категория"),
                tags=("high", f"variant_test_material_{i+1}")
            )
        
        # Раскрываем материал
        app.results_tree.item(parent, open=True)
        
        print("Тестовые данные добавлены в дерево результатов")
        print("Попробуйте сделать двойной клик по любому варианту")
        print("Логи двойного клика будут отображаться в нижней части окна")
    
    # Создаем кнопку для создания тестовых данных
    test_button = tk.Button(root, text="Создать тестовые данные", command=create_test_data)
    test_button.pack(side=tk.BOTTOM, padx=10, pady=10)
    
    # Добавляем инструкцию
    instruction = tk.Label(root, text="1. Нажмите 'Создать тестовые данные'\n2. Сделайте двойной клик по варианту\n3. Проверьте логи внизу", 
                          font=('Arial', 10), bg='lightyellow')
    instruction.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
    
    print("GUI создан с тестовой функциональностью")
    print("Инструкции:")
    print("1. Нажмите кнопку 'Создать тестовые данные'")
    print("2. Сделайте двойной клик по любому варианту в дереве")
    print("3. Проверьте сообщения в логах внизу окна")
    
    # Запускаем GUI
    root.mainloop()

if __name__ == "__main__":
    test_double_click_functionality()