#!/usr/bin/env python3
"""
Минимальный тест кликов
"""

import tkinter as tk
from tkinter import ttk

def on_click(event):
    print("ОБЫЧНЫЙ КЛИК!")

def on_double_click(event):
    print("ДВОЙНОЙ КЛИК СРАБОТАЛ!")

# Создаем окно
root = tk.Tk()
root.title("Тест кликов")
root.geometry("400x300")

# Создаем Treeview
tree = ttk.Treeview(root, columns=("col1",), show="tree headings")
tree.heading("#0", text="Материал")
tree.heading("col1", text="Вариант")

# Добавляем тестовые данные
parent = tree.insert("", tk.END, text="Тестовый материал")
child1 = tree.insert(parent, tk.END, values=("Вариант 1",))
child2 = tree.insert(parent, tk.END, values=("Вариант 2",))
child3 = tree.insert(parent, tk.END, values=("Вариант 3",))

# Раскрываем материал
tree.item(parent, open=True)

# Привязываем события
tree.bind("<Button-1>", on_click)
tree.bind("<Double-1>", on_double_click)
tree.bind("<Double-Button-1>", on_double_click)

tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

# Инструкция
label = tk.Label(root, text="Кликайте по вариантам!\nОбычный клик -> консоль\nДвойной клик -> консоль", 
                bg='lightyellow')
label.pack(fill=tk.X, padx=10, pady=5)

print("=== МИНИМАЛЬНЫЙ ТЕСТ КЛИКОВ ===")
print("1. Кликните по любому варианту - должно появиться 'ОБЫЧНЫЙ КЛИК!'")
print("2. Сделайте двойной клик - должно появиться 'ДВОЙНОЙ КЛИК СРАБОТАЛ!'")
print("3. Закройте окно для завершения теста")
print("-" * 40)

root.mainloop()

print("Тест завершен.")