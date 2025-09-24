#!/usr/bin/env python3
"""
Минимальная версия GUI для тестирования проблемы с отображением
"""

import sys
import os

# Добавляем src в путь
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_customtkinter():
    """Тест CustomTkinter"""
    print("[TEST] Тестирование CustomTkinter...")
    
    try:
        import customtkinter as ctk
        print("[OK] CustomTkinter импортирован успешно")
        
        # Настройка темы
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        print("[OK] Тема настроена")
        
        # Создание окна
        root = ctk.CTk()
        root.title("Test CustomTkinter Window")
        root.geometry("600x400")
        
        # Принудительное отображение
        root.deiconify()
        root.lift()
        root.attributes('-topmost', True)
        root.after(1000, lambda: root.attributes('-topmost', False))
        root.focus_force()
        
        print("[OK] Окно CustomTkinter создано")
        
        # Добавляем контент
        label = ctk.CTkLabel(root, text="CustomTkinter работает!", font=ctk.CTkFont(size=20))
        label.pack(pady=50)
        
        button = ctk.CTkButton(root, text="Закрыть", command=root.quit)
        button.pack(pady=20)
        
        print("[OK] GUI элементы добавлены")
        print("[INFO] Запуск mainloop...")
        
        root.mainloop()
        print("[OK] CustomTkinter mainloop завершен")
        return True
        
    except Exception as e:
        print(f"[ERROR] Ошибка CustomTkinter: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_tkinter():
    """Тест обычного tkinter"""
    print("[TEST] Тестирование обычного tkinter...")
    
    try:
        import tkinter as tk
        from tkinter import ttk
        
        print("[OK] Tkinter импортирован успешно")
        
        # Создание окна
        root = tk.Tk()
        root.title("Test Tkinter Window")
        root.geometry("600x400")
        
        # Принудительное отображение
        root.deiconify()
        root.lift()
        root.attributes('-topmost', True)
        root.after(1000, lambda: root.attributes('-topmost', False))
        root.focus_force()
        
        print("[OK] Окно tkinter создано")
        
        # Добавляем контент
        label = tk.Label(root, text="Обычный tkinter работает!", font=("Arial", 20))
        label.pack(pady=50)
        
        button = tk.Button(root, text="Закрыть", command=root.quit)
        button.pack(pady=20)
        
        print("[OK] GUI элементы добавлены")
        print("[INFO] Запуск mainloop...")
        
        root.mainloop()
        print("[OK] Tkinter mainloop завершен")
        return True
        
    except Exception as e:
        print(f"[ERROR] Ошибка tkinter: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Главная функция тестирования"""
    print("=" * 60)
    print("ТЕСТ GUI БИБЛИОТЕК")
    print("=" * 60)
    
    # Тестируем CustomTkinter
    if test_customtkinter():
        print("[SUCCESS] CustomTkinter работает корректно")
    else:
        print("[FAILED] CustomTkinter не работает, пробуем обычный tkinter")
        
        # Тестируем обычный tkinter
        if test_tkinter():
            print("[SUCCESS] Обычный tkinter работает корректно")
        else:
            print("[FAILED] Ни одна GUI библиотека не работает")
            return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())