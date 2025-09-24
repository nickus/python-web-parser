#!/usr/bin/env python3
"""
Предельно простая версия GUI для диагностики проблемы
"""
import sys
import os

def test_simple_gui():
    """Простейший тест GUI"""
    try:
        print("=== ТЕСТ ПРОСТЕЙШЕГО GUI ===")
        
        # Импорт
        try:
            import customtkinter as ctk
            print("[OK] CustomTkinter импортирован")
            use_ctk = True
        except ImportError:
            import tkinter as tk
            ctk = tk
            print("[WARNING] Используем обычный tkinter")
            use_ctk = False
        
        # Настройка темы для CustomTkinter
        if use_ctk:
            try:
                ctk.set_appearance_mode("light")
                ctk.set_default_color_theme("blue")
                print("[OK] Тема настроена")
            except:
                print("[WARNING] Ошибка настройки темы")
        
        # Создание окна
        if use_ctk:
            root = ctk.CTk()
        else:
            root = tk.Tk()
        
        print("[OK] Окно создано")
        
        # Настройка окна
        root.title("ТЕСТ GUI - ПРОСТОЕ ОКНО")
        root.geometry("800x600")
        
        print("[OK] Заголовок и размер установлены")
        
        # Windows специфичные настройки
        if os.name == 'nt':
            try:
                import ctypes
                user32 = ctypes.windll.user32
                user32.SetProcessDPIAware()
                print("[OK] Windows DPI awareness установлен")
            except:
                print("[WARNING] Не удалось установить DPI awareness")
        
        # Принудительное отображение
        root.deiconify()
        root.lift()
        root.attributes('-topmost', True)
        
        print("[OK] Принудительное отображение применено")
        
        # Центрирование
        root.update_idletasks()
        width = root.winfo_reqwidth()
        height = root.winfo_reqheight()
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        
        root.geometry(f"800x600+{x}+{y}")
        
        print(f"[OK] Окно центрировано: 800x600+{x}+{y}")
        print(f"[INFO] Размер экрана: {screen_width}x{screen_height}")
        
        # Добавляем простой контент
        if use_ctk:
            frame = ctk.CTkFrame(root)
            frame.pack(fill="both", expand=True, padx=50, pady=50)
            
            label = ctk.CTkLabel(frame, text="ТЕСТОВОЕ ОКНО GUI", font=ctk.CTkFont(size=32, weight="bold"))
            label.pack(pady=50)
            
            status_label = ctk.CTkLabel(frame, text="Если вы видите это окно, то GUI работает!", font=ctk.CTkFont(size=16))
            status_label.pack(pady=20)
            
            close_btn = ctk.CTkButton(frame, text="Закрыть", command=root.quit, width=200, height=50)
            close_btn.pack(pady=30)
            
        else:
            frame = tk.Frame(root, bg='white')
            frame.pack(fill="both", expand=True, padx=50, pady=50)
            
            label = tk.Label(frame, text="ТЕСТОВОЕ ОКНО GUI", font=("Arial", 32, "bold"), bg='white')
            label.pack(pady=50)
            
            status_label = tk.Label(frame, text="Если вы видите это окно, то GUI работает!", font=("Arial", 16), bg='white')
            status_label.pack(pady=20)
            
            close_btn = tk.Button(frame, text="Закрыть", command=root.quit, font=("Arial", 14), width=20, height=2)
            close_btn.pack(pady=30)
        
        print("[OK] Контент добавлен")
        
        # Убираем topmost через 2 секунды
        root.after(2000, lambda: root.attributes('-topmost', False))
        
        # Фокус
        root.focus_force()
        root.focus_set()
        
        print("[OK] Фокус установлен")
        
        # Windows API принудительное показ
        if os.name == 'nt':
            try:
                hwnd = root.winfo_id()
                user32.ShowWindow(hwnd, 1)  # SW_SHOWNORMAL
                user32.SetForegroundWindow(hwnd)
                user32.BringWindowToTop(hwnd)
                print("[OK] Windows API принудительный показ")
            except:
                print("[WARNING] Windows API не сработал")
        
        print("[INFO] Запуск mainloop...")
        print("=" * 50)
        
        # Запуск главного цикла
        root.mainloop()
        
        print("[OK] mainloop завершён")
        return True
        
    except Exception as e:
        print(f"[ERROR] Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_simple_gui()
    if success:
        print("ТЕСТ ЗАВЕРШЁН УСПЕШНО")
        sys.exit(0)
    else:
        print("ТЕСТ ПРОВАЛЕН")
        sys.exit(1)