#!/usr/bin/env python3
"""
Простой тест для проверки работы timer-based double-click detection
"""

import tkinter as tk
from tkinter import ttk
import time

class TimerDoubleClickTest:
    def __init__(self, root):
        self.root = root
        self.root.title("Тест Timer-Based Double Click")
        self.root.geometry("500x400")
        
        # Переменные для обнаружения двойного клика
        self.last_click_time = 0
        self.last_click_item = None
        self.double_click_delay = 500  # мсек
        
        # Создаем тестовое дерево
        self.tree = ttk.Treeview(root, columns=("col1", "col2"), show="tree headings")
        self.tree.heading("#0", text="Материал")
        self.tree.heading("col1", text="Вариант")
        self.tree.heading("col2", text="Релевантность")
        
        # Добавляем тестовые данные
        parent = self.tree.insert("", tk.END, text="Тестовый материал", tags=("material",))
        for i in range(3):
            child = self.tree.insert(parent, tk.END, 
                values=(f"Вариант {i+1}", f"{95-i*5}%"),
                tags=("high", f"variant_test_{i+1}"))
        
        # Раскрываем материал
        self.tree.item(parent, open=True)
        
        # Привязываем наш умный обработчик
        self.tree.bind("<Button-1>", self.on_smart_click)
        
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Текстовая область для логов
        self.log_text = tk.Text(root, height=8)
        self.log_text.pack(fill=tk.BOTH, padx=10, pady=5)
        
        # Инструкция
        instruction = tk.Label(root, text="Кликайте по вариантам!\nОдинарный клик = обычное сообщение\nБыстро два клика = ДВОЙНОЙ КЛИК!")
        instruction.pack(padx=10, pady=5)
        
        self.log("=== Timer-Based Double Click Test ===")
        self.log("Кликайте по вариантам для тестирования")
    
    def log(self, message):
        """Добавить сообщение в лог"""
        self.log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.log_text.see(tk.END)
        print(message)
    
    def on_smart_click(self, event):
        """Умный обработчик кликов - определяет одинарные и двойные клики по времени"""
        try:
            item = self.tree.identify('item', event.x, event.y)
            current_time = int(time.time() * 1000)  # время в миллисекундах
            
            if not item:
                return
                
            # Проверяем, является ли это двойным кликом
            if (item == self.last_click_item and 
                current_time - self.last_click_time < self.double_click_delay):
                
                # Это двойной клик!
                self.log("🔥 ДВОЙНОЙ КЛИК ОБНАРУЖЕН! (timer-based detection)")
                self.handle_double_click(event, item)
                
                # Сбрасываем данные клика
                self.last_click_item = None
                self.last_click_time = 0
                
            else:
                # Это одинарный клик
                self.last_click_item = item
                self.last_click_time = current_time
                
                # Информация об одинарном клике
                item_text = self.tree.item(item, 'text')
                item_values = self.tree.item(item, 'values')
                parent = self.tree.parent(item)
                
                if parent:
                    self.log(f"🖱️ Одинарный клик по варианту: {item_values}")
                else:
                    self.log(f"🖱️ Одинарный клик по материалу: {item_text}")
                    
        except Exception as e:
            self.log(f"❌ Ошибка: {e}")
    
    def handle_double_click(self, event, item):
        """Обработка двойного клика"""
        try:
            parent = self.tree.parent(item)
            if not parent:
                self.log("ℹ️ Двойной клик по материалу (не по варианту)")
                return
            
            item_values = self.tree.item(item, 'values')
            self.log(f"✅ ВЫБРАН ВАРИАНТ: {item_values[0]} с релевантностью {item_values[1]}")
            
            # Визуально выделяем выбранный вариант
            self.tree.item(item, tags=("selected",))
            self.tree.tag_configure("selected", background="lightgreen", font=('Arial', 10, 'bold'))
            
            # Скрываем остальные варианты для этого материала
            for child in self.tree.get_children(parent):
                if child != item:
                    # Помечаем как скрытый
                    current_tags = list(self.tree.item(child, 'tags'))
                    current_tags.append("hidden")
                    self.tree.item(child, tags=current_tags)
                    
            self.tree.tag_configure("hidden", foreground="gray")
            
        except Exception as e:
            self.log(f"❌ Ошибка при обработке двойного клика: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = TimerDoubleClickTest(root)
    root.mainloop()