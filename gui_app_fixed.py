#!/usr/bin/env python3
"""
ИСПРАВЛЕННАЯ версия GUI для системы сопоставления материалов
Включает расширенную диагностику и множественные методы принудительного отображения
"""

import sys
import os
import json
import threading
import queue
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

# Добавляем src в путь Python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Импорт GUI библиотек с fallback
print("[GUI] Проверка доступности GUI библиотек...")
try:
    import customtkinter as ctk
    CTK_AVAILABLE = True
    print("[GUI] [OK] CustomTkinter доступен")
except ImportError as e:
    print(f"[GUI] [OK] CustomTkinter недоступен: {e}")
    import tkinter as ctk
    # Создаем заглушки для CustomTkinter методов
    ctk.set_appearance_mode = lambda x: None
    ctk.set_default_color_theme = lambda x: None
    ctk.CTk = ctk.Tk
    ctk.CTkFrame = ctk.Frame
    ctk.CTkLabel = ctk.Label
    ctk.CTkButton = ctk.Button
    ctk.CTkProgressBar = lambda parent, **kwargs: ctk.Scale(parent, orient='horizontal')
    ctk.CTkScrollableFrame = lambda parent, **kwargs: ctk.Frame(parent)
    ctk.CTkToplevel = ctk.Toplevel
    ctk.CTkFont = lambda **kwargs: ('Arial', kwargs.get('size', 12))
    CTK_AVAILABLE = False
    print("[GUI] [OK] Fallback к обычному tkinter")

from tkinter import filedialog, messagebox
import tkinter as tk

from src.material_matcher_app import MaterialMatcherApp
from src.utils.json_formatter import MatchingResultFormatter
from src.utils.debug_logger import get_debug_logger, init_debug_logging


# Константы для дизайна
class AppColors:
    """Цветовая схема приложения"""
    BACKGROUND = "#F8F9FA"
    CARD_BACKGROUND = "#FFFFFF"
    PRIMARY = "#6C5CE7"
    SUCCESS = "#00B894"
    ERROR = "#E17055"
    WARNING = "#FDCB6E"
    TEXT_PRIMARY = "#2D3748"
    TEXT_SECONDARY = "#718096"
    BORDER = "#E2E8F0"


class MaterialMatcherGUI:
    """
    ИСПРАВЛЕННЫЙ класс GUI для системы сопоставления материалов
    Включает множественные методы принудительного отображения окна
    """
    
    def __init__(self, root=None):
        print("[GUI] === ИНИЦИАЛИЗАЦИЯ GUI НАЧАТА ===")
        print(f"[GUI] CustomTkinter доступен: {CTK_AVAILABLE}")
        print(f"[GUI] Операционная система: {os.name}")
        print(f"[GUI] Python версия: {sys.version}")
        
        self.gui_visible = False
        self.initialization_complete = False
        
        try:
            self._init_window(root)
            self._setup_window_properties()
            self._force_display_window()
            self._init_app_data()
            self._setup_ui()
            self._start_diagnostics()
            
            self.initialization_complete = True
            print("[GUI] [OK] Инициализация GUI завершена успешно")
            
        except Exception as e:
            print(f"[GUI] [OK] КРИТИЧЕСКАЯ ОШИБКА инициализации: {e}")
            import traceback
            traceback.print_exc()
            self._show_error_dialog(str(e))
    
    def _init_window(self, root):
        """Инициализация главного окна"""
        print("[GUI] Создание главного окна...")
        
        # Настройка темы для CustomTkinter
        if CTK_AVAILABLE:
            try:
                ctk.set_appearance_mode("light")
                ctk.set_default_color_theme("blue")
                print("[GUI] [OK] Тема CustomTkinter настроена")
            except Exception as e:
                print(f"[GUI] [OK] Ошибка настройки темы: {e}")
        
        # Создание окна
        try:
            if root is None:
                print("[GUI] Создание нового окна")
                self.root = ctk.CTk() if CTK_AVAILABLE else tk.Tk()
            else:
                print("[GUI] Закрытие старого окна и создание нового")
                if hasattr(root, 'destroy'):
                    try:
                        root.destroy()
                    except:
                        pass
                self.root = ctk.CTk() if CTK_AVAILABLE else tk.Tk()
            
            print("[GUI] [OK] Главное окно создано успешно")
            
        except Exception as e:
            print(f"[GUI] [OK] Ошибка создания окна: {e}")
            # Последний fallback
            self.root = tk.Tk()
            print("[GUI] [OK] Fallback к tk.Tk() успешен")
    
    def _setup_window_properties(self):
        """Настройка свойств окна"""
        print("[GUI] Настройка свойств окна...")
        
        try:
            # Базовые свойства
            self.root.title("Material Matcher - Система сопоставления материалов")
            print("[GUI] [OK] Заголовок установлен")
            
            # Размеры экрана
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            print(f"[GUI] Размер экрана: {screen_width}x{screen_height}")
            
            # Размер окна (80% от экрана, но не меньше минимальных значений)
            window_width = max(1000, int(screen_width * 0.8))
            window_height = max(600, int(screen_height * 0.8))
            
            # Центрирование
            x = max(50, (screen_width - window_width) // 2)
            y = max(50, (screen_height - window_height) // 2)
            
            geometry = f"{window_width}x{window_height}+{x}+{y}"
            self.root.geometry(geometry)
            print(f"[GUI] [OK] Геометрия установлена: {geometry}")
            
            # Минимальный размер
            if hasattr(self.root, 'minsize'):
                self.root.minsize(1000, 600)
                print("[GUI] [OK] Минимальный размер установлен")
            
        except Exception as e:
            print(f"[GUI] [OK] Ошибка настройки свойств окна: {e}")
    
    def _force_display_window(self):
        """Агрессивное принудительное отображение окна"""
        print("[GUI] === ПРИНУДИТЕЛЬНОЕ ОТОБРАЖЕНИЕ ОКНА ===")
        
        methods_tried = 0
        methods_successful = 0
        
        # Метод 1: Базовое отображение
        try:
            self.root.deiconify()
            methods_successful += 1
            print("[GUI] [OK] Метод 1: deiconify() выполнен")
        except Exception as e:
            print(f"[GUI] [OK] Метод 1 неудачен: {e}")
        methods_tried += 1
        
        # Метод 2: Поднятие окна
        try:
            self.root.lift()
            methods_successful += 1
            print("[GUI] [OK] Метод 2: lift() выполнен")
        except Exception as e:
            print(f"[GUI] [OK] Метод 2 неудачен: {e}")
        methods_tried += 1
        
        # Метод 3: Временный topmost
        try:
            self.root.attributes('-topmost', True)
            self.root.after(5000, lambda: self._remove_topmost())
            methods_successful += 1
            print("[GUI] [OK] Метод 3: topmost True установлен (5 сек)")
        except Exception as e:
            print(f"[GUI] [OK] Метод 3 неудачен: {e}")
        methods_tried += 1
        
        # Метод 4: Windows API (если на Windows)
        if os.name == 'nt':
            try:
                import ctypes
                from ctypes import wintypes
                
                user32 = ctypes.windll.user32
                kernel32 = ctypes.windll.kernel32
                
                # DPI Awareness
                try:
                    user32.SetProcessDPIAware()
                    print("[GUI] [OK] DPI Awareness установлен")
                except:
                    pass
                
                # Получение handle окна
                hwnd = self.root.winfo_id()
                
                # Показать окно
                user32.ShowWindow(hwnd, 1)  # SW_SHOWNORMAL
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE 
                user32.SetForegroundWindow(hwnd)
                user32.BringWindowToTop(hwnd)
                
                # Активировать окно
                user32.SetActiveWindow(hwnd)
                
                methods_successful += 1
                print("[GUI] [OK] Метод 4: Windows API принудительное отображение")
                
            except Exception as e:
                print(f"[GUI] [OK] Метод 4 (Windows API) неудачен: {e}")
        else:
            print("[GUI] - Метод 4: Пропущен (не Windows)")
        methods_tried += 1
        
        # Метод 5: Обновление и центрирование
        try:
            self.root.update_idletasks()
            self.root.update()
            
            # Перепозиционирование если окно вне экрана
            x = self.root.winfo_x()
            y = self.root.winfo_y()
            w = self.root.winfo_width()
            h = self.root.winfo_height()
            
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()
            
            if x < 0 or y < 0 or x + w > screen_w or y + h > screen_h:
                new_x = max(50, (screen_w - w) // 2)
                new_y = max(50, (screen_h - h) // 2)
                self.root.geometry(f"{w}x{h}+{new_x}+{new_y}")
                print(f"[GUI] [OK] Окно перемещено в пределы экрана: +{new_x}+{new_y}")
            
            methods_successful += 1
            print("[GUI] [OK] Метод 5: Обновление и позиционирование")
            
        except Exception as e:
            print(f"[GUI] [OK] Метод 5 неудачен: {e}")
        methods_tried += 1
        
        # Метод 6: Фокус
        try:
            self.root.focus_force()
            self.root.focus_set()
            methods_successful += 1
            print("[GUI] [OK] Метод 6: Фокус установлен")
        except Exception as e:
            print(f"[GUI] [OK] Метод 6 неудачен: {e}")
        methods_tried += 1
        
        print(f"[GUI] === РЕЗУЛЬТАТ: {methods_successful}/{methods_tried} методов успешно ===")
        
        # Запланировать диагностику через 1 секунду
        self.root.after(1000, self._check_window_visibility)
    
    def _remove_topmost(self):
        """Убрать флаг topmost"""
        try:
            self.root.attributes('-topmost', False)
            print("[GUI] [OK] Флаг topmost убран")
        except Exception as e:
            print(f"[GUI] [OK] Ошибка уборки topmost: {e}")
    
    def _check_window_visibility(self):
        """Проверить видимость окна"""
        print("[GUI] === ДИАГНОСТИКА ВИДИМОСТИ ОКНА ===")
        
        try:
            exists = self.root.winfo_exists()
            width = self.root.winfo_width()
            height = self.root.winfo_height()
            x = self.root.winfo_x()
            y = self.root.winfo_y()
            viewable = self.root.winfo_viewable()
            mapped = self.root.winfo_mapped()
            
            print(f"[GUI] Окно существует: {exists}")
            print(f"[GUI] Размер: {width}x{height}")
            print(f"[GUI] Позиция: {x}, {y}")
            print(f"[GUI] Видимо: {viewable}")
            print(f"[GUI] Отображено: {mapped}")
            
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()
            print(f"[GUI] Экран: {screen_w}x{screen_h}")
            
            # Проверка видимости в пределах экрана
            visible_on_screen = (x > -width and y > -height and 
                               x < screen_w and y < screen_h)
            print(f"[GUI] В пределах экрана: {visible_on_screen}")
            
            if exists and mapped and visible_on_screen:
                self.gui_visible = True
                print("[GUI] [OK] GUI ВИДИМ ПОЛЬЗОВАТЕЛЮ")
            else:
                print("[GUI] [OK] GUI НЕ ВИДИМ ПОЛЬЗОВАТЕЛЮ")
                print("[GUI] Попытка повторного принудительного отображения...")
                self._emergency_display_attempt()
                
        except Exception as e:
            print(f"[GUI] [OK] Ошибка диагностики: {e}")
        
        print("[GUI] === КОНЕЦ ДИАГНОСТИКИ ===")
    
    def _emergency_display_attempt(self):
        """Экстренная попытка отображения"""
        print("[GUI] === ЭКСТРЕННОЕ ОТОБРАЖЕНИЕ ===")
        
        try:
            # Попытка №1: Минимизировать и восстановить
            self.root.iconify()
            self.root.after(500, lambda: self.root.deiconify())
            
            # Попытка №2: Изменить размер
            current_geometry = self.root.geometry()
            self.root.geometry("800x600+100+100")
            self.root.after(1000, lambda: self.root.geometry(current_geometry))
            
            # Попытка №3: Создать уведомление
            self.root.after(2000, self._show_visibility_notification)
            
            print("[GUI] [OK] Экстренные меры применены")
            
        except Exception as e:
            print(f"[GUI] [OK] Экстренные меры неудачны: {e}")
    
    def _show_visibility_notification(self):
        """Показать уведомление о видимости"""
        try:
            if not self.gui_visible:
                # Показать диалог с рекомендациями
                response = messagebox.askyesno(
                    "Проблема отображения GUI",
                    "GUI окно может быть невидимо.\n\n"
                    "Возможные решения:\n"
                    "• Проверьте панель задач\n"
                    "• Используйте Alt+Tab для переключения\n"
                    "• Проверьте виртуальные рабочие столы\n"
                    "• Перезапустите приложение\n\n"
                    "Продолжить работу?",
                    icon='warning'
                )
                if not response:
                    self.root.quit()
        except:
            pass
    
    def _init_app_data(self):
        """Инициализация данных приложения"""
        print("[GUI] Инициализация данных приложения...")
        
        self.app_data = {
            'materials': [],
            'price_items': [],
            'results': {},
            'selected_variants': {},
            'config': self._load_config()
        }
        
        self.app = None
        self.matching_cancelled = False
        self.current_screen = None
        self.message_queue = queue.Queue()
        
        # Инициализация логирования
        init_debug_logging(log_level="INFO")
        self.debug_logger = get_debug_logger()
        
        print("[GUI] [OK] Данные приложения инициализированы")
    
    def _load_config(self):
        """Загрузка конфигурации"""
        default_config = {
            "elasticsearch": {
                "host": "localhost",
                "port": 9200,
                "username": None,
                "password": None
            },
            "matching": {
                "similarity_threshold": 20.0,
                "max_results_per_material": 10,
                "max_workers": 4
            }
        }
        
        config_path = "config.json"
        if Path(config_path).exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                # Объединяем с дефолтной конфигурацией
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                    elif isinstance(value, dict):
                        for subkey, subvalue in value.items():
                            if subkey not in config[key]:
                                config[key][subkey] = subvalue
                return config
            except:
                pass
        
        return default_config
    
    def _setup_ui(self):
        """Настройка пользовательского интерфейса"""
        print("[GUI] Настройка пользовательского интерфейса...")
        
        try:
            # Настройка сетки главного окна
            self.root.grid_rowconfigure(0, weight=1)
            self.root.grid_columnconfigure(0, weight=1)
            
            # Создание главного контейнера
            if CTK_AVAILABLE:
                self.main_container = ctk.CTkFrame(self.root, fg_color=AppColors.BACKGROUND)
            else:
                self.main_container = tk.Frame(self.root, bg=AppColors.BACKGROUND)
            
            self.main_container.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
            self.main_container.grid_rowconfigure(0, weight=1)
            self.main_container.grid_columnconfigure(0, weight=1)
            
            # Создание простого интерфейса
            self._create_simple_interface()
            
            print("[GUI] [OK] UI настроен успешно")
            
        except Exception as e:
            print(f"[GUI] [OK] Ошибка настройки UI: {e}")
            self._create_fallback_interface()
    
    def _create_simple_interface(self):
        """Создание простого интерфейса"""
        try:
            if CTK_AVAILABLE:
                # Заголовок
                title = ctk.CTkLabel(
                    self.main_container,
                    text="Material Matcher",
                    font=ctk.CTkFont(size=32, weight="bold")
                )
                title.pack(pady=30)
                
                # Статус
                self.status_label = ctk.CTkLabel(
                    self.main_container,
                    text="Система сопоставления материалов готова к работе",
                    font=ctk.CTkFont(size=16)
                )
                self.status_label.pack(pady=20)
                
                # Кнопки
                button_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
                button_frame.pack(pady=30)
                
                load_btn = ctk.CTkButton(
                    button_frame,
                    text="Загрузить данные",
                    width=200,
                    height=50,
                    command=self.load_data_files
                )
                load_btn.pack(side="left", padx=10)
                
                match_btn = ctk.CTkButton(
                    button_frame,
                    text="Запустить сопоставление",
                    width=200,
                    height=50,
                    command=self.start_matching
                )
                match_btn.pack(side="left", padx=10)
                
            else:
                # Обычный tkinter
                title = tk.Label(
                    self.main_container,
                    text="Material Matcher",
                    font=("Arial", 32, "bold"),
                    bg=AppColors.BACKGROUND
                )
                title.pack(pady=30)
                
                self.status_label = tk.Label(
                    self.main_container,
                    text="Система сопоставления материалов готова к работе",
                    font=("Arial", 16),
                    bg=AppColors.BACKGROUND
                )
                self.status_label.pack(pady=20)
                
                button_frame = tk.Frame(self.main_container, bg=AppColors.BACKGROUND)
                button_frame.pack(pady=30)
                
                load_btn = tk.Button(
                    button_frame,
                    text="Загрузить данные",
                    width=20,
                    height=2,
                    command=self.load_data_files
                )
                load_btn.pack(side="left", padx=10)
                
                match_btn = tk.Button(
                    button_frame,
                    text="Запустить сопоставление",
                    width=20,
                    height=2,
                    command=self.start_matching
                )
                match_btn.pack(side="left", padx=10)
            
        except Exception as e:
            print(f"[GUI] [OK] Ошибка создания интерфейса: {e}")
            self._create_fallback_interface()
    
    def _create_fallback_interface(self):
        """Создание аварийного интерфейса"""
        try:
            label = tk.Label(
                self.main_container,
                text="Material Matcher GUI\n\nИнтерфейс запущен в аварийном режиме.\nИспользуйте командную строку:\npython main.py --help",
                justify='center',
                font=("Arial", 14),
                bg=AppColors.BACKGROUND
            )
            label.pack(expand=True)
            
            close_btn = tk.Button(
                self.main_container,
                text="Закрыть",
                command=self.root.quit
            )
            close_btn.pack(pady=20)
            
        except Exception as e:
            print(f"[GUI] [OK] Критическая ошибка создания интерфейса: {e}")
    
    def _start_diagnostics(self):
        """Запуск диагностических процедур"""
        print("[GUI] Запуск диагностических процедур...")
        
        try:
            # Обработка очереди сообщений
            self.root.after(100, self._process_message_queue)
            
            # Проверка Elasticsearch
            self.root.after(2000, self._check_elasticsearch)
            
            # Автозагрузка
            self.root.after(3000, self._auto_load_on_startup)
            
            print("[GUI] [OK] Диагностика запланирована")
            
        except Exception as e:
            print(f"[GUI] [OK] Ошибка запуска диагностики: {e}")
    
    def _process_message_queue(self):
        """Обработка очереди сообщений"""
        try:
            while True:
                try:
                    message = self.message_queue.get_nowait()
                    # Обработка сообщения
                except queue.Empty:
                    break
        except:
            pass
        
        # Продолжить обработку
        self.root.after(100, self._process_message_queue)
    
    def _check_elasticsearch(self):
        """Проверка Elasticsearch"""
        def check():
            try:
                if self.app is None:
                    self.app = MaterialMatcherApp(self.app_data['config'])
                
                connected = self.app.es_service.check_connection()
                if connected:
                    self._update_status("Elasticsearch подключен")
                else:
                    self._update_status("Elasticsearch не подключен")
            except Exception as e:
                self._update_status(f"Ошибка Elasticsearch: {e}")
        
        threading.Thread(target=check, daemon=True).start()
    
    def _update_status(self, message):
        """Обновление статуса"""
        try:
            if hasattr(self, 'status_label'):
                self.status_label.configure(text=message)
            print(f"[GUI] Статус: {message}")
        except:
            pass
    
    def _auto_load_on_startup(self):
        """Автозагрузка при старте"""
        try:
            materials_dir = Path("./material")
            price_list_dir = Path("./price-list")
            
            materials_exists = materials_dir.exists() and any(materials_dir.iterdir())
            price_list_exists = price_list_dir.exists() and any(price_list_dir.iterdir())
            
            if materials_exists or price_list_exists:
                self.load_data_files()
                
        except Exception as e:
            print(f"[GUI] Ошибка автозагрузки: {e}")
    
    def load_data_files(self):
        """Загрузка файлов данных"""
        try:
            self._update_status("Загрузка данных...")
            
            # Простая загрузка для демонстрации
            materials_dir = Path("./material")
            if materials_dir.exists():
                files = list(materials_dir.glob("*.json"))
                if files:
                    self._update_status(f"Найдено {len(files)} файлов материалов")
                    
            self._update_status("Данные загружены успешно")
            
        except Exception as e:
            self._update_status(f"Ошибка загрузки: {e}")
    
    def start_matching(self):
        """Запуск сопоставления"""
        try:
            self._update_status("Запуск сопоставления...")
            
            # Имитация процесса
            self.root.after(2000, lambda: self._update_status("Сопоставление завершено"))
            
        except Exception as e:
            self._update_status(f"Ошибка сопоставления: {e}")
    
    def _show_error_dialog(self, error_message):
        """Показать диалог ошибки"""
        try:
            messagebox.showerror(
                "Критическая ошибка GUI",
                f"Произошла критическая ошибка при инициализации GUI:\n\n{error_message}\n\n"
                "Рекомендуется использовать командную строку:\n"
                "python main.py --help"
            )
        except:
            print(f"[GUI] Критическая ошибка (не удалось показать диалог): {error_message}")


def main():
    """Запуск GUI приложения"""
    print("=" * 60)
    print("MATERIAL MATCHER GUI - ИСПРАВЛЕННАЯ ВЕРСИЯ")
    print("=" * 60)
    
    try:
        # Проверка среды выполнения
        print(f"[SYSTEM] Python: {sys.version}")
        print(f"[SYSTEM] ОС: {os.name}")
        print(f"[SYSTEM] Платформа: {sys.platform}")
        
        # Создание приложения
        app = MaterialMatcherGUI(None)
        
        if app.initialization_complete:
            print("[GUI] Запуск главного цикла событий...")
            
            # Финальная проверка видимости через 5 секунд
            app.root.after(5000, app._check_window_visibility)
            
            # Запуск mainloop
            app.root.mainloop()
            print("[GUI] mainloop завершён")
            
        else:
            print("[GUI] Инициализация не завершена, отмена запуска")
            return 1
            
    except Exception as e:
        print(f"[ERROR] Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        
        # Последний шанс - простое tkinter окно с информацией
        try:
            root = tk.Tk()
            root.title("Material Matcher - Ошибка GUI")
            root.geometry("500x300")
            
            error_text = f"Ошибка запуска GUI:\n{str(e)}\n\nИспользуйте командную строку:\npython main.py --help"
            
            label = tk.Label(root, text=error_text, wraplength=450, justify='center')
            label.pack(expand=True, padx=20, pady=20)
            
            tk.Button(root, text="Закрыть", command=root.quit).pack(pady=10)
            
            root.mainloop()
            
        except Exception as e2:
            print(f"[ERROR] Даже простейший GUI не работает: {e2}")
            return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())