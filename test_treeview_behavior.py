#!/usr/bin/env python3
"""
Тестирование поведения tkinter TreeView для понимания причины схлопывания
"""

import tkinter as tk
from tkinter import ttk

class TreeViewTestApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("TreeView Behavior Test")
        self.root.geometry("800x600")
        
        # Создаем TreeView
        self.tree = ttk.Treeview(self.root, columns=('col1', 'col2'), show='tree headings')
        self.tree.heading('#0', text='Material')
        self.tree.heading('col1', text='Price Item')
        self.tree.heading('col2', text='Similarity')
        
        self.tree.pack(fill=tk.BOTH, expand=True)
        
        # Создаем тестовые данные
        self.create_test_data()
        
        # Кнопки для тестирования
        button_frame = tk.Frame(self.root)
        button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Button(button_frame, text="Test 1: Delete children", command=self.test_delete_children).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Test 2: Modify parent text", command=self.test_modify_parent).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Test 3: Modify parent values", command=self.test_modify_parent_values).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Reset", command=self.create_test_data).pack(side=tk.LEFT, padx=5)
        
        # Лог для результатов
        self.log_text = tk.Text(self.root, height=8)
        self.log_text.pack(fill=tk.BOTH, padx=5, pady=5)
        
        self.log("Приложение запущено. Все материалы изначально раскрыты.")
        self.log("Тестируйте различные операции и наблюдайте за поведением TreeView.")
    
    def log(self, message):
        """Добавление сообщения в лог"""
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.root.update()
    
    def create_test_data(self):
        """Создание тестовых данных"""
        # Очищаем дерево
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Создаем 3 материала с вариантами
        for i in range(1, 4):
            # Создаем родительский элемент (материал)
            parent = self.tree.insert('', 'end', text=f'Material {i}', open=True)
            
            # Создаем 3 дочерних элемента (варианта) для каждого материала
            for j in range(1, 4):
                self.tree.insert(parent, 'end', text='', values=(f'Price Item {i}-{j}', f'{90+j}%'))
        
        self.log("Тестовые данные созданы. Все материалы раскрыты.")
    
    def get_expanded_state(self):
        """Получение состояния раскрытости всех элементов"""
        states = {}
        for item in self.tree.get_children():
            states[item] = self.tree.item(item, 'open')
            name = self.tree.item(item, 'text')
            self.log(f"  {name}: {'РАСКРЫТ' if states[item] else 'СХЛОПНУТ'}")
        return states
    
    def test_delete_children(self):
        """Тест 1: Удаление дочерних элементов из первого материала"""
        self.log("\n=== ТЕСТ 1: Удаление дочерних элементов ===")
        self.log("Состояние ДО удаления:")
        before_state = self.get_expanded_state()
        
        # Находим первый материал и его дочерние элементы
        first_material = self.tree.get_children()[0]
        children = self.tree.get_children(first_material)
        
        self.log(f"Удаляем {len(children)} дочерних элементов из первого материала...")
        
        # Удаляем все дочерние элементы кроме первого
        for child in children[1:]:
            self.tree.delete(child)
        
        self.log("Состояние ПОСЛЕ удаления:")
        after_state = self.get_expanded_state()
        
        # Сравниваем состояния
        self.log("Изменения:")
        for item in before_state:
            if before_state[item] != after_state.get(item, False):
                name = self.tree.item(item, 'text')
                self.log(f"  {name}: {before_state[item]} -> {after_state.get(item, False)}")
    
    def test_modify_parent(self):
        """Тест 2: Изменение текста родительского элемента"""
        self.log("\n=== ТЕСТ 2: Изменение текста родителя ===")
        self.log("Состояние ДО изменения:")
        before_state = self.get_expanded_state()
        
        # Изменяем текст второго материала
        second_material = self.tree.get_children()[1]
        old_text = self.tree.item(second_material, 'text')
        new_text = f"{old_text} -> MODIFIED"
        
        self.log(f"Изменяем текст: '{old_text}' -> '{new_text}'")
        self.tree.item(second_material, text=new_text)
        
        self.log("Состояние ПОСЛЕ изменения:")
        after_state = self.get_expanded_state()
        
        # Сравниваем состояния
        self.log("Изменения:")
        changes_found = False
        for item in before_state:
            if before_state[item] != after_state.get(item, False):
                name = self.tree.item(item, 'text')
                self.log(f"  {name}: {before_state[item]} -> {after_state.get(item, False)}")
                changes_found = True
        if not changes_found:
            self.log("  Никаких изменений в состоянии раскрытости не обнаружено!")
    
    def test_modify_parent_values(self):
        """Тест 3: Изменение значений родительского элемента"""
        self.log("\n=== ТЕСТ 3: Изменение значений родителя ===")
        self.log("Состояние ДО изменения:")
        before_state = self.get_expanded_state()
        
        # Изменяем значения третьего материала
        third_material = self.tree.get_children()[2]
        
        self.log("Устанавливаем новые значения для третьего материала...")
        self.tree.item(third_material, values=("NEW PRICE ITEM", "100%"))
        
        self.log("Состояние ПОСЛЕ изменения:")
        after_state = self.get_expanded_state()
        
        # Сравниваем состояния
        self.log("Изменения:")
        changes_found = False
        for item in before_state:
            if before_state[item] != after_state.get(item, False):
                name = self.tree.item(item, 'text')
                self.log(f"  {name}: {before_state[item]} -> {after_state.get(item, False)}")
                changes_found = True
        if not changes_found:
            self.log("  Никаких изменений в состоянии раскрытости не обнаружено!")
    
    def run(self):
        self.root.mainloop()

if __name__ == '__main__':
    app = TreeViewTestApp()
    app.run()