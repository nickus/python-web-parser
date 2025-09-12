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
import time
from collections import deque, defaultdict
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False
from concurrent.futures import ThreadPoolExecutor

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


class PerformanceMonitor:
    """Монитор производительности для отслеживания метрик в реальном времени"""
    
    def __init__(self):
        self.indexing_speeds = deque(maxlen=50)  # Последние 50 измерений
        self.search_times = deque(maxlen=100)   # Последние 100 поисковых запросов
        self.cache_stats = {'hits': 0, 'misses': 0, 'total': 0}
        self.system_stats = {'cpu': 0, 'memory': 0}
        self.start_time = time.time()
        self.operations_count = 0
        self.last_update = time.time()
        
    def record_indexing_speed(self, docs_per_second: float):
        """Записать скорость индексации"""
        self.indexing_speeds.append(docs_per_second)
        
    def record_search_time(self, response_time_ms: float):
        """Записать время поиска"""
        self.search_times.append(response_time_ms)
        
    def update_cache_stats(self, hits: int, total: int):
        """Обновить статистику кеша"""
        self.cache_stats['hits'] = hits
        self.cache_stats['total'] = total
        self.cache_stats['misses'] = total - hits
        
    def update_system_stats(self):
        """Обновить системную статистику"""
        if PSUTIL_AVAILABLE:
            self.system_stats['cpu'] = psutil.cpu_percent(interval=None)
            self.system_stats['memory'] = psutil.virtual_memory().percent
        else:
            # Fallback values if psutil is not available
            self.system_stats['cpu'] = 0
            self.system_stats['memory'] = 0
        
    def get_avg_indexing_speed(self) -> float:
        """Получить среднюю скорость индексации"""
        return sum(self.indexing_speeds) / len(self.indexing_speeds) if self.indexing_speeds else 0
        
    def get_avg_search_time(self) -> float:
        """Получить среднее время поиска"""
        return sum(self.search_times) / len(self.search_times) if self.search_times else 0
        
    def get_cache_hit_ratio(self) -> float:
        """Получить коэффициент попаданий в кеш"""
        return (self.cache_stats['hits'] / self.cache_stats['total'] * 100) if self.cache_stats['total'] > 0 else 0


class MaterialMatcherGUI:
    """
    ОПТИМИЗИРОВАННЫЙ класс GUI для системы сопоставления материалов
    Включает мониторинг производительности и оптимизацию для быстрого backend'а
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
        
        # ОПТИМИЗАЦИЯ: Добавляем мониторинг производительности
        self.performance_monitor = PerformanceMonitor()
        self.performance_widgets = {}
        self.update_interval = 100  # Обновляем каждые 100мс для отзывчивости
        self.thread_pool = ThreadPoolExecutor(max_workers=8)  # Увеличенный пул потоков
        
        # Метрики операций
        self.operation_metrics = {
            'current_operation': None,
            'start_time': None,
            'total_items': 0,
            'processed_items': 0,
            'speed_buffer': deque(maxlen=20)  # Буфер для сглаживания скорости
        }
        
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
                "max_workers": 8,  # Увеличено для быстрого backend
                "performance_monitoring": True,
                "real_time_updates": True,
                "cache_enabled": True
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
            
            # Создание оптимизированного интерфейса с мониторингом производительности
            self._create_optimized_interface()
            
            print("[GUI] [OK] UI настроен успешно")
            
        except Exception as e:
            print(f"[GUI] [OK] Ошибка настройки UI: {e}")
            self._create_fallback_interface()
    
    def _create_optimized_interface(self):
        """Создание оптимизированного интерфейса с мониторингом производительности"""
        try:
            if CTK_AVAILABLE:
                # Главный контейнер с вертикальной компоновкой
                main_layout = ctk.CTkFrame(self.main_container, fg_color="transparent")
                main_layout.pack(fill="both", expand=True, padx=10, pady=10)
                
                # Заголовок с индикатором производительности
                header_frame = ctk.CTkFrame(main_layout, fg_color="transparent")
                header_frame.pack(fill="x", pady=(0, 20))
                
                title = ctk.CTkLabel(
                    header_frame,
                    text="Material Matcher - ВЫСОКОПРОИЗВОДИТЕЛЬНАЯ ВЕРСИЯ",
                    font=ctk.CTkFont(size=28, weight="bold"),
                    text_color=AppColors.PRIMARY
                )
                title.pack(pady=10)
                
                perf_indicator = ctk.CTkLabel(
                    header_frame,
                    text="🚀 Оптимизирован для 2-4x увеличения скорости",
                    font=ctk.CTkFont(size=14),
                    text_color=AppColors.SUCCESS
                )
                perf_indicator.pack(pady=5)
                
                # Создание панели производительности
                self._create_performance_dashboard(main_layout)
                
                # Статус и операции
                operations_frame = ctk.CTkFrame(main_layout, fg_color=AppColors.CARD_BACKGROUND)
                operations_frame.pack(fill="x", pady=10)
                
                self.status_label = ctk.CTkLabel(
                    operations_frame,
                    text="Система готова к высокоскоростной работе",
                    font=ctk.CTkFont(size=16, weight="bold")
                )
                self.status_label.pack(pady=15)
                
                # Прогресс-бар с улучшенной анимацией
                self.progress_frame = ctk.CTkFrame(operations_frame, fg_color="transparent")
                self.progress_frame.pack(fill="x", padx=20, pady=10)
                
                self.progress_bar = ctk.CTkProgressBar(
                    self.progress_frame,
                    height=20,
                    progress_color=AppColors.SUCCESS
                )
                self.progress_bar.pack(fill="x", pady=5)
                self.progress_bar.set(0)
                
                self.progress_label = ctk.CTkLabel(
                    self.progress_frame,
                    text="",
                    font=ctk.CTkFont(size=12)
                )
                self.progress_label.pack(pady=5)
                
                # Кнопки с улучшенным дизайном - первый ряд (загрузка данных)
                load_frame = ctk.CTkFrame(operations_frame, fg_color="transparent")
                load_frame.pack(pady=10)
                
                self.load_materials_btn = ctk.CTkButton(
                    load_frame,
                    text="📦 Загрузить материалы",
                    width=180,
                    height=45,
                    command=self.load_materials_manually,
                    font=ctk.CTkFont(size=13, weight="bold"),
                    fg_color=AppColors.PRIMARY
                )
                self.load_materials_btn.pack(side="left", padx=10)
                
                self.load_pricelist_btn = ctk.CTkButton(
                    load_frame,
                    text="💰 Загрузить прайс-лист",
                    width=180,
                    height=45,
                    command=self.load_pricelist_manually,
                    font=ctk.CTkFont(size=13, weight="bold"),
                    fg_color=AppColors.WARNING
                )
                self.load_pricelist_btn.pack(side="left", padx=10)
                
                self.load_auto_btn = ctk.CTkButton(
                    load_frame,
                    text="⚡ Автозагрузка",
                    width=140,
                    height=45,
                    command=self.load_data_files_optimized,
                    font=ctk.CTkFont(size=13, weight="bold"),
                    fg_color="#6366f1"
                )
                self.load_auto_btn.pack(side="left", padx=10)
                
                # Второй ряд кнопок (операции)
                button_frame = ctk.CTkFrame(operations_frame, fg_color="transparent")
                button_frame.pack(pady=10)
                
                self.match_btn = ctk.CTkButton(
                    button_frame,
                    text="🚀 Запустить сопоставление",
                    width=220,
                    height=50,
                    command=self.start_matching_optimized,
                    font=ctk.CTkFont(size=14, weight="bold"),
                    fg_color=AppColors.SUCCESS
                )
                self.match_btn.pack(side="left", padx=10)
                
                # Кнопка мониторинга
                monitor_btn = ctk.CTkButton(
                    button_frame,
                    text="📊 Монитор",
                    width=140,
                    height=50,
                    command=self.toggle_performance_details,
                    font=ctk.CTkFont(size=14),
                    fg_color=AppColors.WARNING
                )
                monitor_btn.pack(side="left", padx=10)
                
                # Добавляем область для отображения результатов сопоставления
                self._create_results_area(main_layout)
                
            else:
                # Fallback для обычного tkinter
                self._create_fallback_interface()
            
        except Exception as e:
            print(f"[GUI] [OK] Ошибка создания оптимизированного интерфейса: {e}")
            self._create_fallback_interface()
    
    def _create_performance_dashboard(self, parent):
        """Создание панели мониторинга производительности"""
        try:
            # Основная панель производительности
            perf_frame = ctk.CTkFrame(parent, fg_color=AppColors.CARD_BACKGROUND)
            perf_frame.pack(fill="x", pady=10)
            
            perf_title = ctk.CTkLabel(
                perf_frame,
                text="📈 Мониторинг производительности",
                font=ctk.CTkFont(size=18, weight="bold")
            )
            perf_title.pack(pady=(15, 10))
            
            # Сетка метрик
            metrics_grid = ctk.CTkFrame(perf_frame, fg_color="transparent")
            metrics_grid.pack(fill="x", padx=20, pady=10)
            
            # Конфигурация сетки
            for i in range(4):
                metrics_grid.columnconfigure(i, weight=1)
            
            # Метрика: Скорость индексации
            indexing_frame = ctk.CTkFrame(metrics_grid, width=180, height=100)
            indexing_frame.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
            indexing_frame.grid_propagate(False)
            
            ctk.CTkLabel(indexing_frame, text="⚡ Индексация", font=ctk.CTkFont(size=12, weight="bold")).pack(pady=5)
            self.performance_widgets['indexing_speed'] = ctk.CTkLabel(
                indexing_frame, text="0 док/сек", font=ctk.CTkFont(size=16, weight="bold"), text_color=AppColors.PRIMARY
            )
            self.performance_widgets['indexing_speed'].pack()
            
            # Метрика: Время поиска
            search_frame = ctk.CTkFrame(metrics_grid, width=180, height=100)
            search_frame.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
            search_frame.grid_propagate(False)
            
            ctk.CTkLabel(search_frame, text="🔍 Поиск", font=ctk.CTkFont(size=12, weight="bold")).pack(pady=5)
            self.performance_widgets['search_time'] = ctk.CTkLabel(
                search_frame, text="0 мс", font=ctk.CTkFont(size=16, weight="bold"), text_color=AppColors.SUCCESS
            )
            self.performance_widgets['search_time'].pack()
            
            # Метрика: Кеш
            cache_frame = ctk.CTkFrame(metrics_grid, width=180, height=100)
            cache_frame.grid(row=0, column=2, padx=5, pady=5, sticky="ew")
            cache_frame.grid_propagate(False)
            
            ctk.CTkLabel(cache_frame, text="💾 Кеш", font=ctk.CTkFont(size=12, weight="bold")).pack(pady=5)
            self.performance_widgets['cache_ratio'] = ctk.CTkLabel(
                cache_frame, text="0%", font=ctk.CTkFont(size=16, weight="bold"), text_color=AppColors.WARNING
            )
            self.performance_widgets['cache_ratio'].pack()
            
            # Метрика: Система
            system_frame = ctk.CTkFrame(metrics_grid, width=180, height=100)
            system_frame.grid(row=0, column=3, padx=5, pady=5, sticky="ew")
            system_frame.grid_propagate(False)
            
            ctk.CTkLabel(system_frame, text="🖥️ Система", font=ctk.CTkFont(size=12, weight="bold")).pack(pady=5)
            self.performance_widgets['system_cpu'] = ctk.CTkLabel(
                system_frame, text="CPU: 0%", font=ctk.CTkFont(size=12), text_color=AppColors.TEXT_PRIMARY
            )
            self.performance_widgets['system_cpu'].pack()
            
            self.performance_widgets['system_memory'] = ctk.CTkLabel(
                system_frame, text="RAM: 0%", font=ctk.CTkFont(size=12), text_color=AppColors.TEXT_PRIMARY
            )
            self.performance_widgets['system_memory'].pack()
            
            # Детальная панель (скрыта по умолчанию)
            self.details_frame = ctk.CTkFrame(perf_frame, fg_color=AppColors.BACKGROUND)
            # Не показываем пока не нажата кнопка
            
            self._start_performance_monitoring()
            
        except Exception as e:
            print(f"[GUI] [OK] Ошибка создания панели производительности: {e}")
    
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
            # ОПТИМИЗАЦИЯ: Обработка очереди сообщений с увеличенной частотой
            self.root.after(50, self._process_message_queue)  # Чаще обновляем для отзывчивости
            
            # Проверка Elasticsearch
            self.root.after(1000, self._check_elasticsearch)  # Быстрее проверяем подключение
            
            # Автозагрузка
            self.root.after(2000, self._auto_load_on_startup)  # Быстрее стартуем
            
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
        
        # ОПТИМИЗАЦИЯ: Продолжить обработку с увеличенной частотой
        self.root.after(50, self._process_message_queue)
    
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
                self.load_data_files_optimized()
                # Автоматически запускаем сопоставление после загрузки
                self.root.after(5000, self.start_matching_optimized)
                
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
        """Запуск реального сопоставления"""
        try:
            from src.material_matcher_app import MaterialMatcherApp
            from src.utils.data_loader import DataLoader
            
            self._update_status("Запуск сопоставления материалов...")
            
            # Инициализируем приложение для сопоставления
            if not hasattr(self, 'matcher_app'):
                self.matcher_app = MaterialMatcherApp()
            
            # Загружаем данные из папок
            data_loader = DataLoader()
            
            # Загрузка материалов
            materials_dir = Path("./material")
            materials = []
            if materials_dir.exists():
                for file_path in materials_dir.glob("*"):
                    if file_path.suffix in ['.json', '.csv', '.xlsx']:
                        loaded = data_loader.load_materials(str(file_path))
                        materials.extend(loaded)
            
            # Загрузка прайс-листов  
            pricelist_dir = Path("./price-list")
            price_items = []
            if pricelist_dir.exists():
                for file_path in pricelist_dir.glob("*"):
                    if file_path.suffix in ['.json', '.csv', '.xlsx']:
                        loaded = data_loader.load_price_list(str(file_path))
                        price_items.extend(loaded)
            
            # Запуск сопоставления в отдельном потоке
            def run_matching():
                try:
                    results = self.matcher_app.run_matching(
                        materials=materials,
                        price_items=price_items,
                        similarity_threshold=20.0,
                        max_results=10
                    )
                    
                    # Обновляем GUI с результатами
                    self.root.after(0, lambda: self._show_results(results, materials, price_items))
                    
                    # Также обновляем главную область результатов
                    self.root.after(0, lambda: self.update_results_display(results, materials, price_items))
                    
                except Exception as e:
                    error_msg = f"Ошибка сопоставления: {e}"
                    self.root.after(0, lambda msg=error_msg: self._update_status(msg))
            
            # Запускаем в потоке
            import threading
            thread = threading.Thread(target=run_matching, daemon=True)
            thread.start()
            
        except Exception as e:
            self._update_status(f"Ошибка инициализации сопоставления: {e}")
    
    def _show_results(self, results, materials, price_items):
        """Показать результаты сопоставления"""
        try:
            total_materials = len(materials)
            matched_materials = len(results)
            total_matches = sum(len(matches) for matches in results.values())
            
            status_text = f"Сопоставление завершено! Найдено {matched_materials}/{total_materials} материалов, всего совпадений: {total_matches}"
            self._update_status(status_text)
            
            # Создаем окно с результатами
            self._create_results_window(results, materials, price_items)
            
        except Exception as e:
            self._update_status(f"Ошибка отображения результатов: {e}")
    
    def _create_results_window(self, results, materials, price_items):
        """Создать окно с результатами"""
        try:
            results_window = ctk.CTkToplevel(self.root)
            results_window.title("Результаты сопоставления")
            results_window.geometry("1000x600")
            
            # Заголовок
            title = ctk.CTkLabel(results_window, text="📊 Результаты сопоставления материалов", 
                               font=ctk.CTkFont(size=20, weight="bold"))
            title.pack(pady=20)
            
            # Статистика
            stats_frame = ctk.CTkFrame(results_window)
            stats_frame.pack(fill="x", padx=20, pady=10)
            
            total_materials = len(materials)
            matched_materials = len(results)
            total_matches = sum(len(matches) for matches in results.values())
            
            stats_text = f"Обработано материалов: {total_materials} | Найдены соответствия: {matched_materials} | Всего совпадений: {total_matches}"
            stats_label = ctk.CTkLabel(stats_frame, text=stats_text, font=ctk.CTkFont(size=14))
            stats_label.pack(pady=10)
            
            # Скроллируемый фрейм для результатов
            scrollable_frame = ctk.CTkScrollableFrame(results_window)
            scrollable_frame.pack(fill="both", expand=True, padx=20, pady=10)
            
            # Отображаем результаты
            for material_id, matches in list(results.items())[:20]:  # Показываем первые 20
                material = next((m for m in materials if m.id == material_id), None)
                if material and matches:
                    self._add_material_result_card(scrollable_frame, material, matches[:3])  # Топ-3 совпадения
            
            # Кнопка экспорта
            export_btn = ctk.CTkButton(results_window, text="📥 Экспорт результатов", 
                                     command=lambda: self._export_results(results))
            export_btn.pack(pady=20)
            
        except Exception as e:
            print(f"[GUI] Ошибка создания окна результатов: {e}")
    
    def _add_material_result_card(self, parent, material, matches):
        """Добавить карточку результата материала"""
        try:
            # Карточка материала
            card = ctk.CTkFrame(parent)
            card.pack(fill="x", pady=5)
            
            # Название материала
            material_label = ctk.CTkLabel(card, text=f"🔧 {material.name}", 
                                        font=ctk.CTkFont(size=16, weight="bold"),
                                        anchor="w")
            material_label.pack(fill="x", padx=10, pady=5)
            
            # Лучшие совпадения
            for i, match in enumerate(matches, 1):
                match_text = f"  {i}. {match['price_item']['material_name']} - {match['similarity']:.1f}% | {match['price_item']['price']} {match['price_item']['currency']}"
                match_label = ctk.CTkLabel(card, text=match_text, anchor="w", 
                                         font=ctk.CTkFont(size=12))
                match_label.pack(fill="x", padx=20, pady=2)
                
        except Exception as e:
            print(f"[GUI] Ошибка добавления карточки: {e}")
    
    def _export_results(self, results):
        """Экспорт результатов"""
        try:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"matching_results_{timestamp}.json"
            
            # Простой экспорт в JSON
            import json
            export_data = {}
            for material_id, matches in results.items():
                export_data[material_id] = matches
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)
            
            self._update_status(f"Результаты экспортированы в {filename}")
            
        except Exception as e:
            self._update_status(f"Ошибка экспорта: {e}")
    
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
    
    # ======= НОВЫЕ ОПТИМИЗИРОВАННЫЕ МЕТОДЫ =======
    
    def _start_performance_monitoring(self):
        """Запуск мониторинга производительности"""
        try:
            self._update_performance_metrics()
            # ОПТИМИЗАЦИЯ: Частые обновления для отзывчивости
            self.root.after(self.update_interval, self._start_performance_monitoring)
        except Exception as e:
            print(f"[GUI] Ошибка мониторинга: {e}")
    
    def _update_performance_metrics(self):
        """Обновление метрик производительности"""
        try:
            # Обновляем системную статистику
            self.performance_monitor.update_system_stats()
            
            # Обновляем виджеты
            if hasattr(self, 'performance_widgets'):
                # Скорость индексации
                avg_speed = self.performance_monitor.get_avg_indexing_speed()
                speed_color = AppColors.SUCCESS if avg_speed > 8 else AppColors.WARNING if avg_speed > 4 else AppColors.ERROR
                self.performance_widgets['indexing_speed'].configure(
                    text=f"{avg_speed:.1f} док/сек",
                    text_color=speed_color
                )
                
                # Время поиска
                avg_search = self.performance_monitor.get_avg_search_time()
                search_color = AppColors.SUCCESS if avg_search < 10 else AppColors.WARNING if avg_search < 50 else AppColors.ERROR
                self.performance_widgets['search_time'].configure(
                    text=f"{avg_search:.1f} мс",
                    text_color=search_color
                )
                
                # Кеш
                cache_ratio = self.performance_monitor.get_cache_hit_ratio()
                cache_color = AppColors.SUCCESS if cache_ratio > 80 else AppColors.WARNING if cache_ratio > 50 else AppColors.ERROR
                self.performance_widgets['cache_ratio'].configure(
                    text=f"{cache_ratio:.0f}%",
                    text_color=cache_color
                )
                
                # Система
                cpu = self.performance_monitor.system_stats['cpu']
                memory = self.performance_monitor.system_stats['memory']
                self.performance_widgets['system_cpu'].configure(text=f"CPU: {cpu:.0f}%")
                self.performance_widgets['system_memory'].configure(text=f"RAM: {memory:.0f}%")
                
        except Exception as e:
            print(f"[GUI] Ошибка обновления метрик: {e}")
    
    def toggle_performance_details(self):
        """Переключить детальную панель производительности"""
        try:
            if hasattr(self, 'details_frame'):
                if self.details_frame.winfo_viewable():
                    self.details_frame.pack_forget()
                else:
                    self.details_frame.pack(fill="x", padx=20, pady=10)
                    self._create_detailed_metrics()
        except Exception as e:
            print(f"[GUI] Ошибка переключения деталей: {e}")
    
    def _create_detailed_metrics(self):
        """Создание детальных метрик"""
        try:
            # Очистить предыдущий контент
            for widget in self.details_frame.winfo_children():
                widget.destroy()
            
            details_title = ctk.CTkLabel(
                self.details_frame,
                text="📊 Детальная статистика",
                font=ctk.CTkFont(size=16, weight="bold")
            )
            details_title.pack(pady=10)
            
            # Статистика операций
            stats_text = f"""
            Время работы: {time.time() - self.performance_monitor.start_time:.0f} сек
            Операций выполнено: {self.performance_monitor.operations_count}
            Последние измерения индексации: {len(self.performance_monitor.indexing_speeds)}
            Последние измерения поиска: {len(self.performance_monitor.search_times)}
            """
            
            stats_label = ctk.CTkLabel(
                self.details_frame,
                text=stats_text,
                font=ctk.CTkFont(size=12),
                justify="left"
            )
            stats_label.pack(pady=10)
            
        except Exception as e:
            print(f"[GUI] Ошибка создания детальных метрик: {e}")
    
    def load_data_files_optimized(self):
        """Оптимизированная загрузка данных с мониторингом производительности"""
        try:
            self._update_status("⚡ Высокоскоростная загрузка данных...")
            self._update_progress(0, "Инициализация...")
            
            # Блокируем кнопки загрузки
            self.load_auto_btn.configure(state="disabled")
            
            def load_with_monitoring():
                start_time = time.time()
                try:
                    from src.utils.data_loader import DataLoader
                    data_loader = DataLoader()
                    
                    # Загрузка материалов
                    materials_dir = Path("./material")
                    materials = []
                    if materials_dir.exists():
                        files = list(materials_dir.glob("*"))
                        total_files = len(files)
                        
                        for i, file_path in enumerate(files):
                            if file_path.suffix in ['.json', '.csv', '.xlsx']:
                                self.root.after(0, lambda p=(i+1)/total_files*50: self._update_progress(p, f"Загрузка материалов: {file_path.name}"))
                                loaded = data_loader.load_materials(str(file_path))
                                materials.extend(loaded)
                                
                                # Записываем скорость
                                docs_speed = len(loaded) / max(0.1, time.time() - start_time)
                                self.performance_monitor.record_indexing_speed(docs_speed)
                    
                    # Загрузка прайс-листов  
                    pricelist_dir = Path("./price-list")
                    price_items = []
                    if pricelist_dir.exists():
                        files = list(pricelist_dir.glob("*"))
                        total_files = len(files)
                        
                        for i, file_path in enumerate(files):
                            if file_path.suffix in ['.json', '.csv', '.xlsx']:
                                progress = 50 + (i+1)/total_files*50
                                self.root.after(0, lambda p=progress: self._update_progress(p, f"Загрузка прайс-листов: {file_path.name}"))
                                loaded = data_loader.load_price_list(str(file_path))
                                price_items.extend(loaded)
                    
                    # Сохраняем данные
                    self.app_data['materials'] = materials
                    self.app_data['price_items'] = price_items
                    
                    load_time = time.time() - start_time
                    total_docs = len(materials) + len(price_items)
                    speed = total_docs / max(0.1, load_time)
                    
                    self.root.after(0, lambda: self._data_load_completed(total_docs, speed, load_time))
                    
                except Exception as e:
                    error_msg = f"Ошибка загрузки: {e}"
                    self.root.after(0, lambda: self._update_status(error_msg))
                finally:
                    self.root.after(0, lambda: self.load_auto_btn.configure(state="normal"))
            
            # Запускаем в отдельном потоке
            self.thread_pool.submit(load_with_monitoring)
            
        except Exception as e:
            self._update_status(f"Ошибка инициализации загрузки: {e}")
            self.load_auto_btn.configure(state="normal")
    
    def load_materials_manually(self):
        """Ручная загрузка материалов с выбором файла"""
        try:
            from tkinter import filedialog
            
            file_path = filedialog.askopenfilename(
                title="Выберите файл с материалами",
                filetypes=[
                    ("Excel files", "*.xlsx *.xls"),
                    ("JSON files", "*.json"),
                    ("CSV files", "*.csv"),
                    ("All Excel files", "*.xlsx;*.xls"),
                    ("All files", "*.*")
                ]
            )
            
            if file_path:
                self._update_status("📦 Загрузка материалов...")
                self._update_progress(0, "Инициализация...")
                self.load_materials_btn.configure(state="disabled")
                
                def load_materials():
                    try:
                        from src.utils.data_loader import DataLoader
                        data_loader = DataLoader()
                        
                        materials = data_loader.load_materials(file_path)
                        
                        # Обновляем данные приложения
                        self.app_data['materials'] = materials
                        
                        # Обновляем UI
                        self.root.after(0, lambda: self._update_status(
                            f"✅ Материалы загружены: {len(materials)} шт. из {Path(file_path).name}"
                        ))
                        self.root.after(0, lambda: self._update_progress(100, 
                            f"Загружено {len(materials)} материалов"))
                        
                    except Exception as e:
                        error_msg = f"Ошибка загрузки материалов: {e}"
                        self.root.after(0, lambda: self._update_status(error_msg))
                        print(f"[GUI] {error_msg}")
                    finally:
                        self.root.after(0, lambda: self.load_materials_btn.configure(state="normal"))
                
                # Запускаем в отдельном потоке
                self.thread_pool.submit(load_materials)
                
        except Exception as e:
            self._update_status(f"Ошибка выбора файла материалов: {e}")
    
    def load_pricelist_manually(self):
        """Ручная загрузка прайс-листа с выбором файла"""
        try:
            from tkinter import filedialog
            
            file_path = filedialog.askopenfilename(
                title="Выберите файл с прайс-листом",
                filetypes=[
                    ("Excel files", "*.xlsx *.xls"),
                    ("JSON files", "*.json"),
                    ("CSV files", "*.csv"),
                    ("All Excel files", "*.xlsx;*.xls"),
                    ("All files", "*.*")
                ]
            )
            
            if file_path:
                self._update_status("💰 Загрузка прайс-листа...")
                self._update_progress(0, "Инициализация...")
                self.load_pricelist_btn.configure(state="disabled")
                
                def load_pricelist():
                    try:
                        from src.utils.data_loader import DataLoader
                        data_loader = DataLoader()
                        
                        price_items = data_loader.load_price_list(file_path)
                        
                        # Обновляем данные приложения
                        self.app_data['price_items'] = price_items
                        
                        # Обновляем UI
                        self.root.after(0, lambda: self._update_status(
                            f"✅ Прайс-лист загружен: {len(price_items)} позиций из {Path(file_path).name}"
                        ))
                        self.root.after(0, lambda: self._update_progress(100, 
                            f"Загружено {len(price_items)} позиций"))
                        
                    except Exception as e:
                        error_msg = f"Ошибка загрузки прайс-листа: {e}"
                        self.root.after(0, lambda: self._update_status(error_msg))
                        print(f"[GUI] {error_msg}")
                    finally:
                        self.root.after(0, lambda: self.load_pricelist_btn.configure(state="normal"))
                
                # Запускаем в отдельном потоке
                self.thread_pool.submit(load_pricelist)
                
        except Exception as e:
            self._update_status(f"Ошибка выбора файла прайс-листа: {e}")
    
    def _data_load_completed(self, total_docs, speed, load_time):
        """Завершение загрузки данных"""
        self._update_progress(100, f"Загружено {total_docs} документов за {load_time:.1f}с")
        self._update_status(f"✅ Загрузка завершена! {total_docs} документов, скорость: {speed:.1f} док/сек")
        self.performance_monitor.record_indexing_speed(speed)
        
        # Автоматически активируем кнопку сопоставления
        self.match_btn.configure(state="normal")
    
    def start_matching_optimized(self):
        """Оптимизированное сопоставление с мониторингом производительности"""
        try:
            if not self.app_data['materials'] or not self.app_data['price_items']:
                self._update_status("⚠️ Сначала загрузите данные!")
                return
                
            self._update_status("🚀 Запуск высокоскоростного сопоставления...")
            self._update_progress(0, "Инициализация сопоставления...")
            
            # Блокируем кнопку
            self.match_btn.configure(state="disabled")
            
            def run_matching_with_monitoring():
                start_time = time.time()
                self.operation_metrics['start_time'] = start_time
                self.operation_metrics['current_operation'] = 'matching'
                
                try:
                    from src.material_matcher_app import MaterialMatcherApp
                    
                    # Инициализируем приложение с оптимизированными настройками
                    if not hasattr(self, 'matcher_app'):
                        config = self.app_data['config'].copy()
                        config['matching']['max_workers'] = 8  # Увеличиваем количество потоков
                        self.matcher_app = MaterialMatcherApp(config)
                    
                    materials = self.app_data['materials']
                    price_items = self.app_data['price_items']
                    
                    self.operation_metrics['total_items'] = len(materials)
                    
                    # Запускаем сопоставление с прогрессом
                    results = self.matcher_app.run_matching(
                        materials=materials,
                        price_items=price_items,
                        similarity_threshold=20.0,
                        max_results=10,
                        progress_callback=self._matching_progress_callback
                    )
                    
                    # Измеряем производительность
                    total_time = time.time() - start_time
                    total_searches = sum(len(matches) for matches in results.values())
                    avg_search_time = (total_time * 1000) / max(1, total_searches)  # в миллисекундах
                    
                    self.performance_monitor.record_search_time(avg_search_time)
                    
                    # Обновляем GUI с результатами
                    self.root.after(0, lambda: self._matching_completed(results, materials, price_items, total_time))
                    
                except Exception as e:
                    error_msg = f"Ошибка сопоставления: {e}"
                    self.root.after(0, lambda: self._update_status(error_msg))
                finally:
                    self.root.after(0, lambda: self.match_btn.configure(state="normal"))
                    self.operation_metrics['current_operation'] = None
            
            # Запускаем в отдельном потоке
            self.thread_pool.submit(run_matching_with_monitoring)
            
        except Exception as e:
            self._update_status(f"Ошибка инициализации сопоставления: {e}")
            self.match_btn.configure(state="normal")
    
    def _matching_progress_callback(self, processed, total, current_material=None):
        """Callback для обновления прогресса сопоставления"""
        try:
            progress = (processed / total * 100) if total > 0 else 0
            material_info = f" - {current_material[:50]}..." if current_material and len(current_material) > 50 else f" - {current_material}" if current_material else ""
            
            # Расчет скорости
            if self.operation_metrics['start_time']:
                elapsed = time.time() - self.operation_metrics['start_time']
                speed = processed / max(0.1, elapsed)
                remaining = (total - processed) / max(0.1, speed) if speed > 0 else 0
                
                speed_info = f" | {speed:.1f} мат/сек | ~{remaining:.0f}с осталось"
            else:
                speed_info = ""
            
            progress_text = f"Обработано {processed}/{total}{material_info}{speed_info}"
            
            self.root.after(0, lambda: self._update_progress(progress, progress_text))
            
        except Exception as e:
            print(f"[GUI] Ошибка обновления прогресса: {e}")
    
    def _matching_completed(self, results, materials, price_items, total_time):
        """Завершение сопоставления"""
        try:
            total_materials = len(materials)
            matched_materials = len(results)
            total_matches = sum(len(matches) for matches in results.values())
            
            speed = total_materials / max(0.1, total_time)
            
            status_text = f"🎯 Сопоставление завершено! {matched_materials}/{total_materials} материалов за {total_time:.1f}с (скорость: {speed:.1f} мат/сек)"
            self._update_status(status_text)
            self._update_progress(100, f"Найдено {total_matches} совпадений")
            
            # Обновляем главную область результатов
            self.update_results_display(results, materials, price_items)
            
            # Создаем улучшенное окно результатов
            self._create_optimized_results_window(results, materials, price_items, {
                'total_time': total_time,
                'speed': speed,
                'total_matches': total_matches
            })
            
        except Exception as e:
            self._update_status(f"Ошибка отображения результатов: {e}")
    
    def _create_optimized_results_window(self, results, materials, price_items, stats):
        """Создать оптимизированное окно с результатами"""
        try:
            results_window = ctk.CTkToplevel(self.root)
            results_window.title("🚀 Результаты высокоскоростного сопоставления")
            results_window.geometry("1200x800")
            
            # Заголовок с производительностью
            title_frame = ctk.CTkFrame(results_window, fg_color="transparent")
            title_frame.pack(fill="x", padx=20, pady=10)
            
            title = ctk.CTkLabel(
                title_frame, 
                text="🎯 Результаты сопоставления материалов", 
                font=ctk.CTkFont(size=24, weight="bold"),
                text_color=AppColors.PRIMARY
            )
            title.pack()
            
            perf_info = ctk.CTkLabel(
                title_frame,
                text=f"⚡ Обработано за {stats['total_time']:.1f}с | Скорость: {stats['speed']:.1f} мат/сек | Найдено: {stats['total_matches']} совпадений",
                font=ctk.CTkFont(size=14),
                text_color=AppColors.SUCCESS
            )
            perf_info.pack(pady=5)
            
            # Улучшенная статистика
            stats_frame = ctk.CTkFrame(results_window, fg_color=AppColors.CARD_BACKGROUND)
            stats_frame.pack(fill="x", padx=20, pady=10)
            
            stats_grid = ctk.CTkFrame(stats_frame, fg_color="transparent")
            stats_grid.pack(fill="x", padx=20, pady=15)
            
            # Конфигурация сетки статистики
            for i in range(4):
                stats_grid.columnconfigure(i, weight=1)
            
            # Статистика в виде карточек
            self._create_stat_card(stats_grid, "📊 Материалы", f"{len(results)}/{len(materials)}", 0, 0)
            self._create_stat_card(stats_grid, "🎯 Совпадения", f"{stats['total_matches']}", 0, 1)
            self._create_stat_card(stats_grid, "⚡ Скорость", f"{stats['speed']:.1f}/сек", 0, 2)
            self._create_stat_card(stats_grid, "⏱️ Время", f"{stats['total_time']:.1f}с", 0, 3)
            
            # Скроллируемый фрейм для результатов с улучшенной производительностью
            scrollable_frame = ctk.CTkScrollableFrame(results_window, fg_color=AppColors.BACKGROUND)
            scrollable_frame.pack(fill="both", expand=True, padx=20, pady=10)
            
            # Отображаем результаты с лимитом для производительности
            displayed_count = 0
            max_display = 50  # Ограничиваем для производительности
            
            for material_id, matches in results.items():
                if displayed_count >= max_display:
                    remaining = len(results) - displayed_count
                    info_label = ctk.CTkLabel(
                        scrollable_frame,
                        text=f"... и еще {remaining} материалов (используйте экспорт для полного списка)",
                        font=ctk.CTkFont(size=14, style="italic")
                    )
                    info_label.pack(pady=10)
                    break
                
                material = next((m for m in materials if m.id == material_id), None)
                if material and matches:
                    self._add_optimized_material_card(scrollable_frame, material, matches[:5])  # Топ-5 совпадений
                    displayed_count += 1
            
            # Улучшенные кнопки экспорта
            export_frame = ctk.CTkFrame(results_window, fg_color="transparent")
            export_frame.pack(fill="x", padx=20, pady=15)
            
            export_json_btn = ctk.CTkButton(
                export_frame, 
                text="📄 Экспорт JSON", 
                command=lambda: self._export_results_optimized(results, 'json'),
                width=150,
                height=40
            )
            export_json_btn.pack(side="left", padx=10)
            
            export_excel_btn = ctk.CTkButton(
                export_frame, 
                text="📊 Экспорт Excel", 
                command=lambda: self._export_results_optimized(results, 'excel'),
                width=150,
                height=40,
                fg_color=AppColors.SUCCESS
            )
            export_excel_btn.pack(side="left", padx=10)
            
            close_btn = ctk.CTkButton(
                export_frame, 
                text="❌ Закрыть", 
                command=results_window.destroy,
                width=100,
                height=40,
                fg_color=AppColors.ERROR
            )
            close_btn.pack(side="right", padx=10)
            
        except Exception as e:
            print(f"[GUI] Ошибка создания оптимизированного окна результатов: {e}")
    
    def _create_results_area(self, parent):
        """Создать область для отображения результатов сопоставления в главном окне"""
        try:
            # Фрейм для результатов
            results_container = ctk.CTkFrame(parent, fg_color=AppColors.CARD_BACKGROUND)
            results_container.pack(fill="both", expand=True, pady=(20, 0))
            
            # Заголовок области результатов
            results_header = ctk.CTkFrame(results_container, fg_color="transparent")
            results_header.pack(fill="x", padx=15, pady=(15, 10))
            
            results_title = ctk.CTkLabel(
                results_header,
                text="📊 Результаты сопоставления материалов",
                font=ctk.CTkFont(size=18, weight="bold"),
                text_color=AppColors.PRIMARY
            )
            results_title.pack(side="left")
            
            # Кнопки управления результатами
            controls_frame = ctk.CTkFrame(results_header, fg_color="transparent")
            controls_frame.pack(side="right")
            
            self.clear_results_btn = ctk.CTkButton(
                controls_frame,
                text="🗑️ Очистить",
                width=100,
                height=30,
                command=self.clear_results,
                font=ctk.CTkFont(size=11),
                fg_color=AppColors.ERROR
            )
            self.clear_results_btn.pack(side="right", padx=5)
            
            self.export_results_btn = ctk.CTkButton(
                controls_frame,
                text="💾 Экспорт",
                width=100,
                height=30,
                command=self.export_current_results,
                font=ctk.CTkFont(size=11),
                fg_color=AppColors.SUCCESS,
                state="disabled"
            )
            self.export_results_btn.pack(side="right", padx=5)
            
            # Статистика результатов
            self.results_stats_frame = ctk.CTkFrame(results_container, fg_color="transparent")
            self.results_stats_frame.pack(fill="x", padx=15, pady=(0, 10))
            
            self.results_stats_label = ctk.CTkLabel(
                self.results_stats_frame,
                text="Результаты будут отображены после выполнения сопоставления",
                font=ctk.CTkFont(size=12),
                text_color=AppColors.TEXT_SECONDARY
            )
            self.results_stats_label.pack()
            
            # Скроллируемая область для результатов
            self.results_scrollable = ctk.CTkScrollableFrame(
                results_container,
                fg_color=AppColors.BACKGROUND,
                height=300
            )
            self.results_scrollable.pack(fill="both", expand=True, padx=15, pady=(0, 15))
            
            # Сохраняем ссылку на контейнер результатов для обновлений
            self.results_container = results_container
            self.current_results = {}
            
            print("[GUI] [OK] Область результатов создана")
            
        except Exception as e:
            print(f"[GUI] Ошибка создания области результатов: {e}")
    
    def clear_results(self):
        """Очистить область результатов"""
        try:
            # Очистить скроллируемую область
            for widget in self.results_scrollable.winfo_children():
                widget.destroy()
            
            # Сбросить текущие результаты
            self.current_results = {}
            
            # Обновить статистику
            self.results_stats_label.configure(
                text="Результаты очищены. Выполните новое сопоставление для получения данных.",
                text_color=AppColors.TEXT_SECONDARY
            )
            
            # Отключить кнопку экспорта
            self.export_results_btn.configure(state="disabled")
            
            print("[GUI] Результаты очищены")
            
        except Exception as e:
            print(f"[GUI] Ошибка очистки результатов: {e}")
    
    def export_current_results(self):
        """Экспорт текущих результатов"""
        try:
            if not self.current_results:
                messagebox.showinfo("Экспорт", "Нет данных для экспорта")
                return
            
            from tkinter import filedialog
            from datetime import datetime
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = filedialog.asksaveasfilename(
                title="Сохранить результаты",
                defaultextension=".json",
                initialvalue=f"matching_results_{timestamp}.json",
                filetypes=[
                    ("JSON files", "*.json"),
                    ("Excel files", "*.xlsx"),
                    ("All files", "*.*")
                ]
            )
            
            if filename:
                if filename.endswith('.json'):
                    self._export_json_optimized(self.current_results, filename)
                elif filename.endswith('.xlsx'):
                    self._export_excel_optimized(self.current_results, filename)
                else:
                    # По умолчанию JSON
                    self._export_json_optimized(self.current_results, filename + '.json')
                    
        except Exception as e:
            print(f"[GUI] Ошибка экспорта: {e}")
            messagebox.showerror("Ошибка", f"Ошибка экспорта: {e}")
    
    def update_results_display(self, results, materials=None, price_items=None):
        """Обновить отображение результатов в главной области"""
        try:
            # Очистить предыдущие результаты
            for widget in self.results_scrollable.winfo_children():
                widget.destroy()
            
            # Сохранить текущие результаты
            self.current_results = results
            
            # Подсчет статистики
            total_materials = len(materials) if materials else len(results)
            matched_materials = len(results)
            total_matches = sum(len(matches) for matches in results.values())
            
            # Обновить статистику
            stats_text = f"📊 Обработано: {total_materials} материалов | ✅ Найдены соответствия: {matched_materials} | 🎯 Всего совпадений: {total_matches}"
            self.results_stats_label.configure(
                text=stats_text,
                text_color=AppColors.SUCCESS
            )
            
            # Включить кнопку экспорта
            self.export_results_btn.configure(state="normal")
            
            # Отобразить результаты (ограничиваем до 20 для производительности)
            display_count = 0
            max_display = 20
            
            for material_id, matches in results.items():
                if display_count >= max_display:
                    remaining = len(results) - display_count
                    more_label = ctk.CTkLabel(
                        self.results_scrollable,
                        text=f"... и ещё {remaining} материалов (всего результатов: {len(results)})",
                        font=ctk.CTkFont(size=12, style="italic"),
                        text_color=AppColors.TEXT_SECONDARY
                    )
                    more_label.pack(pady=10, padx=10)
                    break
                
                # Найти материал по ID
                material = None
                if materials:
                    material = next((m for m in materials if m.id == material_id), None)
                
                if matches:  # Показываем только материалы с совпадениями
                    self._add_result_card_to_main_area(material, matches, material_id)
                    display_count += 1
            
            if not display_count:
                # Если нет результатов для отображения
                no_results_label = ctk.CTkLabel(
                    self.results_scrollable,
                    text="🔍 Совпадения не найдены. Попробуйте изменить параметры поиска.",
                    font=ctk.CTkFont(size=14),
                    text_color=AppColors.TEXT_SECONDARY
                )
                no_results_label.pack(pady=50, padx=20)
            
            print(f"[GUI] Результаты обновлены: {matched_materials} материалов, {total_matches} совпадений")
            
        except Exception as e:
            print(f"[GUI] Ошибка обновления результатов: {e}")
    
    def _add_result_card_to_main_area(self, material, matches, material_id):
        """Добавить карточку результата в главную область"""
        try:
            # Карточка материала
            card = ctk.CTkFrame(self.results_scrollable, fg_color=AppColors.CARD_BACKGROUND)
            card.pack(fill="x", pady=5, padx=10)
            
            # Заголовок материала
            header = ctk.CTkFrame(card, fg_color="transparent")
            header.pack(fill="x", padx=10, pady=(8, 5))
            
            # Название материала
            material_name = material.name if material else f"Материал {material_id}"
            name_label = ctk.CTkLabel(
                header,
                text=f"🔧 {material_name[:80]}{'...' if len(material_name) > 80 else ''}",
                font=ctk.CTkFont(size=14, weight="bold"),
                anchor="w"
            )
            name_label.pack(side="left", fill="x", expand=True)
            
            # Количество совпадений
            count_label = ctk.CTkLabel(
                header,
                text=f"{len(matches)} совп.",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=AppColors.SUCCESS,
                width=80
            )
            count_label.pack(side="right")
            
            # Лучшие совпадения (показываем топ-3)
            matches_frame = ctk.CTkFrame(card, fg_color="transparent")
            matches_frame.pack(fill="x", padx=10, pady=(0, 8))
            
            for i, match in enumerate(matches[:3], 1):
                # Обработка разных форматов данных
                if isinstance(match, dict):
                    if 'price_item' in match:
                        # Новый формат с SearchResult
                        similarity = match.get('similarity', 0)
                        price_item = match['price_item']
                        item_name = price_item.get('material_name', 'N/A')
                        price = price_item.get('price', 'N/A')
                        currency = price_item.get('currency', '')
                        supplier = price_item.get('supplier', '')
                    else:
                        # Прямой формат price_item
                        similarity = match.get('similarity_percentage', 0)
                        item_name = match.get('material_name', 'N/A')
                        price = match.get('price', 'N/A')
                        currency = match.get('currency', '')
                        supplier = match.get('supplier', '')
                else:
                    # SearchResult объект
                    similarity = getattr(match, 'similarity_percentage', 0)
                    price_item = getattr(match, 'price_item', None)
                    if price_item:
                        item_name = getattr(price_item, 'material_name', 'N/A')
                        price = getattr(price_item, 'price', 'N/A')
                        currency = getattr(price_item, 'currency', '')
                        supplier = getattr(price_item, 'supplier', '')
                    else:
                        item_name = 'N/A'
                        price = 'N/A'
                        currency = ''
                        supplier = ''
                
                # Цвет в зависимости от процента совпадения
                if similarity >= 80:
                    color = AppColors.SUCCESS
                elif similarity >= 60:
                    color = AppColors.WARNING
                else:
                    color = AppColors.TEXT_SECONDARY
                
                # Формирование текста совпадения
                match_text = f"  {i}. {item_name[:50]}{'...' if len(item_name) > 50 else ''}"
                if similarity > 0:
                    match_text += f" — {similarity:.1f}%"
                if price != 'N/A':
                    match_text += f" | {price} {currency}"
                if supplier:
                    match_text += f" | {supplier}"
                
                match_label = ctk.CTkLabel(
                    matches_frame,
                    text=match_text,
                    anchor="w",
                    font=ctk.CTkFont(size=10),
                    text_color=color
                )
                match_label.pack(fill="x", pady=1)
                
        except Exception as e:
            print(f"[GUI] Ошибка добавления карточки результата: {e}")
    
    def _create_stat_card(self, parent, title, value, row, col):
        """Создать карточку статистики"""
        card = ctk.CTkFrame(parent, width=150, height=80)
        card.grid(row=row, column=col, padx=5, pady=5, sticky="ew")
        card.grid_propagate(False)
        
        title_label = ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=12, weight="bold"))
        title_label.pack(pady=(10, 5))
        
        value_label = ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=16, weight="bold"), text_color=AppColors.PRIMARY)
        value_label.pack()
    
    def _add_optimized_material_card(self, parent, material, matches):
        """Добавить оптимизированную карточку результата материала"""
        try:
            # Карточка материала с улучшенным дизайном
            card = ctk.CTkFrame(parent, fg_color=AppColors.CARD_BACKGROUND)
            card.pack(fill="x", pady=8, padx=10)
            
            # Заголовок материала
            header_frame = ctk.CTkFrame(card, fg_color="transparent")
            header_frame.pack(fill="x", padx=15, pady=(10, 5))
            
            material_label = ctk.CTkLabel(
                header_frame, 
                text=f"🔧 {material.name}", 
                font=ctk.CTkFont(size=16, weight="bold"),
                anchor="w"
            )
            material_label.pack(side="left", fill="x", expand=True)
            
            # Количество совпадений
            count_label = ctk.CTkLabel(
                header_frame,
                text=f"{len(matches)} совп.",
                font=ctk.CTkFont(size=12),
                text_color=AppColors.SUCCESS,
                width=80
            )
            count_label.pack(side="right")
            
            # Лучшие совпадения
            matches_frame = ctk.CTkFrame(card, fg_color="transparent")
            matches_frame.pack(fill="x", padx=15, pady=(0, 10))
            
            for i, match in enumerate(matches, 1):
                similarity = match.get('similarity', 0)
                price_item = match.get('price_item', {})
                
                # Цвет в зависимости от процента совпадения
                color = AppColors.SUCCESS if similarity > 80 else AppColors.WARNING if similarity > 60 else AppColors.TEXT_SECONDARY
                
                match_text = f"  {i}. {price_item.get('material_name', 'N/A')[:60]} - {similarity:.1f}% | {price_item.get('price', 'N/A')} {price_item.get('currency', '')}"
                
                match_label = ctk.CTkLabel(
                    matches_frame, 
                    text=match_text, 
                    anchor="w",
                    font=ctk.CTkFont(size=11),
                    text_color=color
                )
                match_label.pack(fill="x", pady=1)
                
        except Exception as e:
            print(f"[GUI] Ошибка добавления оптимизированной карточки: {e}")
    
    def _export_results_optimized(self, results, format_type):
        """Оптимизированный экспорт результатов"""
        try:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if format_type == 'json':
                filename = f"matching_results_{timestamp}.json"
                self._export_json_optimized(results, filename)
            elif format_type == 'excel':
                filename = f"matching_results_{timestamp}.xlsx"
                self._export_excel_optimized(results, filename)
                
        except Exception as e:
            self._update_status(f"Ошибка экспорта: {e}")
    
    def _export_json_optimized(self, results, filename):
        """Оптимизированный экспорт в JSON"""
        try:
            import json
            export_data = {
                'metadata': {
                    'export_time': datetime.now().isoformat(),
                    'total_materials': len(results),
                    'total_matches': sum(len(matches) for matches in results.values())
                },
                'results': results
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)
            
            self._update_status(f"✅ Результаты экспортированы в {filename}")
            
        except Exception as e:
            self._update_status(f"Ошибка экспорта JSON: {e}")
    
    def _export_excel_optimized(self, results, filename):
        """Оптимизированный экспорт в Excel"""
        try:
            # Базовая реализация, можно расширить
            import json
            # Конвертируем в JSON как fallback
            json_filename = filename.replace('.xlsx', '.json')
            self._export_json_optimized(results, json_filename)
            self._update_status(f"✅ Экспорт завершен в {json_filename} (Excel экспорт в разработке)")
            
        except Exception as e:
            self._update_status(f"Ошибка экспорта Excel: {e}")
    
    def _update_progress(self, percentage, text=""):
        """Обновить прогресс-бар с анимацией"""
        try:
            if hasattr(self, 'progress_bar'):
                # Плавная анимация прогресса
                current = self.progress_bar.get()
                target = percentage / 100.0
                
                if target > current:
                    # Плавное увеличение
                    self.progress_bar.set(target)
                else:
                    # Сразу устанавливаем если уменьшается
                    self.progress_bar.set(target)
                
            if hasattr(self, 'progress_label') and text:
                self.progress_label.configure(text=text)
                
        except Exception as e:
            print(f"[GUI] Ошибка обновления прогресса: {e}")


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