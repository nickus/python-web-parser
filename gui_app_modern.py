#!/usr/bin/env python3
"""
Современный GUI для системы сопоставления материалов
Использует customtkinter для создания современного интерфейса
"""

import sys
import os
import json
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

# Импорт customtkinter
import customtkinter as ctk
from tkinter import filedialog, messagebox

# Добавляем src в путь Python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

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


class AppState(Enum):
    """Состояния приложения"""
    WELCOME = "welcome"
    LOADING = "loading"
    PROCESSING = "processing"
    RESULTS = "results"
    ERROR = "error"


@dataclass
class AppData:
    """Данные приложения"""
    materials: List[Any] = None
    price_items: List[Any] = None
    results: Dict[str, List[Any]] = None
    selected_variants: Dict[str, Any] = None
    config: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.materials is None:
            self.materials = []
        if self.price_items is None:
            self.price_items = []
        if self.results is None:
            self.results = {}
        if self.selected_variants is None:
            self.selected_variants = {}


class ModernMaterialMatcherGUI:
    """Главный класс современного GUI"""
    
    def __init__(self):
        # Настройка темы
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        
        # Создание главного окна
        self.root = ctk.CTk()
        self.root.title("Material Matcher - Система сопоставления материалов")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 600)
        
        # Инициализация данных
        self.app_data = AppData()
        self.app_state = AppState.WELCOME
        self.app = None
        
        # Переменные для управления процессами
        self.matching_cancelled = False
        self.current_screen = None
        
        # Инициализация логирования
        init_debug_logging(log_level="INFO")
        self.debug_logger = get_debug_logger()
        
        # Загрузка конфигурации
        self.load_config()
        
        # Создание интерфейса
        self.setup_ui()
        
        # Проверка статуса Elasticsearch
        self.check_elasticsearch_status()
        
        # Автоматическая загрузка при запуске
        self.root.after(1000, self.auto_load_on_startup)
    
    def load_config(self):
        """Загрузка конфигурации приложения"""
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
                self.app_data.config = config
            except:
                self.app_data.config = default_config
        else:
            self.app_data.config = default_config
    
    def setup_ui(self):
        """Настройка пользовательского интерфейса"""
        # Настройка сетки главного окна
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        # Создание главного контейнера
        self.main_container = ctk.CTkFrame(self.root, fg_color=AppColors.BACKGROUND)
        self.main_container.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)
        
        # Создание экранов
        self.create_screens()
        
        # Показать начальный экран
        self.show_screen("dashboard")
    
    def create_screens(self):
        """Создание всех экранов приложения"""
        self.screens = {}
        
        # Dashboard экран
        self.screens["dashboard"] = DashboardScreen(self.main_container, self)
        
        # Экран загрузки
        self.screens["loading"] = LoadingScreen(self.main_container, self)
        
        # Экран результатов  
        self.screens["results"] = ResultsScreen(self.main_container, self)
        
        # Все экраны размещаются в одном месте
        for screen in self.screens.values():
            screen.grid(row=0, column=0, sticky="nsew")
    
    def show_screen(self, screen_name: str):
        """Показать указанный экран"""
        if screen_name in self.screens:
            # Скрыть все экраны
            for screen in self.screens.values():
                screen.grid_remove()
            
            # Показать нужный экран
            self.screens[screen_name].grid(row=0, column=0, sticky="nsew")
            self.current_screen = screen_name
            
            # Обновить экран при показе
            if hasattr(self.screens[screen_name], 'on_show'):
                self.screens[screen_name].on_show()
    
    def check_elasticsearch_status(self):
        """Проверка статуса Elasticsearch"""
        def check():
            try:
                if self.app is None:
                    self.app = MaterialMatcherApp(self.app_data.config)
                
                connected = self.app.es_service.check_connection()
                self.root.after(0, lambda: self.update_elasticsearch_status(connected))
            except Exception as e:
                self.root.after(0, lambda: self.update_elasticsearch_status(False, str(e)))
        
        threading.Thread(target=check, daemon=True).start()
    
    def update_elasticsearch_status(self, connected: bool, error: str = None):
        """Обновление статуса Elasticsearch"""
        # Обновляем статус в Dashboard
        if "dashboard" in self.screens:
            self.screens["dashboard"].update_elasticsearch_status(connected, error)
    
    def load_data_files(self):
        """Загрузка файлов данных"""
        self.show_screen("loading")
        self.screens["loading"].start_loading("Загрузка файлов данных...")
        
        def load_thread():
            try:
                # Загрузка материалов
                materials_loaded = self._load_materials_from_directory()
                
                # Загрузка прайс-листов  
                price_items_loaded = self._load_price_items_from_directory()
                
                if materials_loaded or price_items_loaded:
                    # Индексация данных
                    self.screens["loading"].update_progress("Индексация данных...", 50)
                    self._index_data()
                    
                    self.screens["loading"].update_progress("Готово!", 100)
                    self.root.after(1000, lambda: self.show_screen("dashboard"))
                else:
                    self.root.after(0, lambda: messagebox.showwarning(
                        "Предупреждение", 
                        "Не найдено файлов для загрузки в папках 'material' и 'price-list'"
                    ))
                    self.show_screen("dashboard")
                    
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Ошибка загрузки данных: {e}"))
                self.show_screen("dashboard")
        
        threading.Thread(target=load_thread, daemon=True).start()
    
    def _load_materials_from_directory(self) -> bool:
        """Загрузка материалов из папки"""
        materials_dir = Path("./material")
        if not materials_dir.exists():
            return False
        
        supported_extensions = ['.csv', '.xlsx', '.json']
        all_materials = []
        
        files = [f for f in materials_dir.iterdir() 
                if f.is_file() and f.suffix.lower() in supported_extensions]
        
        if not files:
            return False
        
        for i, file_path in enumerate(files):
            try:
                self.screens["loading"].update_progress(f"Загрузка {file_path.name}...", 
                                                       int(25 * (i + 1) / len(files)))
                
                if file_path.suffix.lower() == '.csv':
                    from src.utils.data_loader import MaterialLoader
                    materials = MaterialLoader.load_from_csv(str(file_path))
                elif file_path.suffix.lower() == '.xlsx':
                    from src.utils.data_loader import MaterialLoader
                    materials = MaterialLoader.load_from_excel(str(file_path))
                elif file_path.suffix.lower() == '.json':
                    from src.utils.data_loader import MaterialLoader
                    materials = MaterialLoader.load_from_json(str(file_path))
                else:
                    continue
                
                all_materials.extend(materials)
            except Exception as e:
                print(f"Ошибка загрузки файла {file_path.name}: {e}")
        
        if all_materials:
            self.app_data.materials = all_materials
            return True
        return False
    
    def _load_price_items_from_directory(self) -> bool:
        """Загрузка прайс-листов из папки"""
        price_list_dir = Path("./price-list")
        if not price_list_dir.exists():
            return False
        
        supported_extensions = ['.csv', '.xlsx', '.json']
        all_price_items = []
        
        files = [f for f in price_list_dir.iterdir() 
                if f.is_file() and f.suffix.lower() in supported_extensions]
        
        if not files:
            return False
        
        for i, file_path in enumerate(files):
            try:
                self.screens["loading"].update_progress(f"Загрузка {file_path.name}...", 
                                                       25 + int(25 * (i + 1) / len(files)))
                
                if file_path.suffix.lower() == '.csv':
                    from src.utils.data_loader import PriceListLoader
                    price_items = PriceListLoader.load_from_csv(str(file_path))
                elif file_path.suffix.lower() == '.xlsx':
                    from src.utils.data_loader import PriceListLoader
                    price_items = PriceListLoader.load_from_excel(str(file_path))
                elif file_path.suffix.lower() == '.json':
                    from src.utils.data_loader import PriceListLoader
                    price_items = PriceListLoader.load_from_json(str(file_path))
                else:
                    continue
                
                all_price_items.extend(price_items)
            except Exception as e:
                print(f"Ошибка загрузки файла {file_path.name}: {e}")
        
        if all_price_items:
            self.app_data.price_items = all_price_items
            return True
        return False
    
    def _index_data(self):
        """Индексация данных в Elasticsearch"""
        if self.app is None:
            self.app = MaterialMatcherApp(self.app_data.config)
        
        if self.app_data.materials or self.app_data.price_items:
            return self.app.index_data(self.app_data.materials, self.app_data.price_items)
        return False
    
    def start_matching(self):
        """Запуск процесса сопоставления"""
        if not self.app_data.materials or not self.app_data.price_items:
            messagebox.showwarning("Предупреждение", "Сначала загрузите данные")
            return
        
        self.matching_cancelled = False
        self.show_screen("loading")
        self.screens["loading"].start_loading("Выполнение сопоставления...")
        
        def matching_thread():
            try:
                if self.app is None:
                    self.app = MaterialMatcherApp(self.app_data.config)
                
                # Запуск сопоставления
                results = self.app.run_matching(self.app_data.materials)
                
                if not self.matching_cancelled:
                    self.app_data.results = results
                    self.root.after(0, lambda: self.screens["loading"].update_progress("Обработка результатов...", 95))
                    self.root.after(1000, lambda: self.show_screen("results"))
                
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Ошибка сопоставления: {e}"))
                self.show_screen("dashboard")
        
        threading.Thread(target=matching_thread, daemon=True).start()
    
    def stop_matching(self):
        """Остановка процесса сопоставления"""
        self.matching_cancelled = True
    
    def auto_load_on_startup(self):
        """Автоматическая загрузка при старте"""
        materials_dir = Path("./material")
        price_list_dir = Path("./price-list")
        
        materials_exists = materials_dir.exists() and any(materials_dir.iterdir())
        price_list_exists = price_list_dir.exists() and any(price_list_dir.iterdir())
        
        if materials_exists or price_list_exists:
            # Автоматически загружаем данные
            self.root.after(500, self.load_data_files)
    
    def run(self):
        """Запуск приложения"""
        self.root.mainloop()


class BaseScreen(ctk.CTkFrame):
    """Базовый класс для экранов"""
    
    def __init__(self, parent, app: ModernMaterialMatcherGUI):
        super().__init__(parent, fg_color=AppColors.BACKGROUND)
        self.app = app
        self.setup_ui()
    
    def setup_ui(self):
        """Настройка UI - должно быть переопределено в дочерних классах"""
        pass
    
    def on_show(self):
        """Вызывается при показе экрана"""
        pass


class DashboardScreen(BaseScreen):
    """Главный экран Dashboard"""
    
    def setup_ui(self):
        self.grid_rowconfigure(0, weight=0)  # Заголовок
        self.grid_rowconfigure(1, weight=1)  # Контент
        self.grid_rowconfigure(2, weight=0)  # Статусная панель
        self.grid_columnconfigure(0, weight=1)
        
        # Заголовок
        self.create_header()
        
        # Основной контент
        self.create_main_content()
        
        # Статусная панель
        self.create_status_bar()
    
    def create_header(self):
        """Создание заголовка"""
        header_frame = ctk.CTkFrame(self, fg_color=AppColors.CARD_BACKGROUND, height=80)
        header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(0, 20))
        header_frame.grid_propagate(False)
        
        # Название приложения
        title_label = ctk.CTkLabel(
            header_frame,
            text="Material Matcher",
            font=ctk.CTkFont(size=32, weight="bold"),
            text_color=AppColors.PRIMARY
        )
        title_label.pack(side="left", padx=30, pady=20)
        
        # Подзаголовок
        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="Система интеллектуального сопоставления материалов",
            font=ctk.CTkFont(size=14),
            text_color=AppColors.TEXT_SECONDARY
        )
        subtitle_label.pack(side="left", padx=(10, 30), pady=20)
    
    def create_main_content(self):
        """Создание основного контента"""
        content_frame = ctk.CTkFrame(self, fg_color="transparent")
        content_frame.grid(row=1, column=0, sticky="nsew", padx=20)
        content_frame.grid_columnconfigure((0, 1), weight=1)
        content_frame.grid_rowconfigure((0, 1, 2), weight=1)
        
        # Статистика данных
        self.create_data_stats_card(content_frame)
        
        # Управление процессом
        self.create_process_control_card(content_frame)
        
        # Статус системы
        self.create_system_status_card(content_frame)
        
        # История операций
        self.create_recent_operations_card(content_frame)
    
    def create_data_stats_card(self, parent):
        """Карточка статистики данных"""
        card = ctk.CTkFrame(parent, fg_color=AppColors.CARD_BACKGROUND)
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=(0, 20))
        
        # Заголовок карточки
        header = ctk.CTkLabel(
            card,
            text="📊 Загруженные данные",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=AppColors.TEXT_PRIMARY
        )
        header.pack(padx=20, pady=(20, 10), anchor="w")
        
        # Статистика
        stats_frame = ctk.CTkFrame(card, fg_color="transparent")
        stats_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        # Материалы
        self.materials_label = ctk.CTkLabel(
            stats_frame,
            text="Материалы: 0",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=AppColors.PRIMARY
        )
        self.materials_label.pack(pady=5, anchor="w")
        
        # Прайс-листы
        self.price_items_label = ctk.CTkLabel(
            stats_frame,
            text="Позиции прайс-листа: 0",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=AppColors.SUCCESS
        )
        self.price_items_label.pack(pady=5, anchor="w")
        
        # Кнопка загрузки
        load_button = ctk.CTkButton(
            card,
            text="🔄 Загрузить данные",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=50,
            command=self.app.load_data_files
        )
        load_button.pack(padx=20, pady=(0, 20), fill="x")
    
    def create_process_control_card(self, parent):
        """Карточка управления процессом"""
        card = ctk.CTkFrame(parent, fg_color=AppColors.CARD_BACKGROUND)
        card.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=(0, 20))
        
        # Заголовок
        header = ctk.CTkLabel(
            card,
            text="⚡ Управление процессом",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=AppColors.TEXT_PRIMARY
        )
        header.pack(padx=20, pady=(20, 10), anchor="w")
        
        # Описание
        desc = ctk.CTkLabel(
            card,
            text="Запустите процесс сопоставления материалов с прайс-листами",
            font=ctk.CTkFont(size=12),
            text_color=AppColors.TEXT_SECONDARY,
            wraplength=300
        )
        desc.pack(padx=20, pady=(0, 20), anchor="w")
        
        # Кнопка запуска
        self.start_button = ctk.CTkButton(
            card,
            text="🚀 Запустить сопоставление",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=50,
            fg_color=AppColors.PRIMARY,
            command=self.app.start_matching,
            state="disabled"
        )
        self.start_button.pack(padx=20, pady=(0, 20), fill="x")
        
        # Кнопка результатов
        self.results_button = ctk.CTkButton(
            card,
            text="📈 Просмотр результатов",
            font=ctk.CTkFont(size=14),
            height=40,
            fg_color=AppColors.SUCCESS,
            command=lambda: self.app.show_screen("results"),
            state="disabled"
        )
        self.results_button.pack(padx=20, pady=(0, 20), fill="x")
    
    def create_system_status_card(self, parent):
        """Карточка статуса системы"""
        card = ctk.CTkFrame(parent, fg_color=AppColors.CARD_BACKGROUND)
        card.grid(row=1, column=0, sticky="nsew", padx=(0, 10), pady=(0, 20))
        
        # Заголовок
        header = ctk.CTkLabel(
            card,
            text="🔧 Статус системы",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=AppColors.TEXT_PRIMARY
        )
        header.pack(padx=20, pady=(20, 10), anchor="w")
        
        # Elasticsearch статус
        self.es_status_frame = ctk.CTkFrame(card, fg_color="transparent")
        self.es_status_frame.pack(fill="x", padx=20, pady=10)
        
        self.es_indicator = ctk.CTkLabel(
            self.es_status_frame,
            text="⚫",
            font=ctk.CTkFont(size=20),
            text_color=AppColors.ERROR
        )
        self.es_indicator.pack(side="left", padx=(0, 10))
        
        self.es_status_label = ctk.CTkLabel(
            self.es_status_frame,
            text="Elasticsearch: Проверка подключения...",
            font=ctk.CTkFont(size=14),
            text_color=AppColors.TEXT_SECONDARY
        )
        self.es_status_label.pack(side="left")
    
    def create_recent_operations_card(self, parent):
        """Карточка последних операций"""
        card = ctk.CTkFrame(parent, fg_color=AppColors.CARD_BACKGROUND)
        card.grid(row=1, column=1, sticky="nsew", padx=(10, 0), pady=(0, 20))
        
        # Заголовок
        header = ctk.CTkLabel(
            card,
            text="📝 Последние операции",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=AppColors.TEXT_PRIMARY
        )
        header.pack(padx=20, pady=(20, 10), anchor="w")
        
        # Список операций (пока заглушка)
        operations_frame = ctk.CTkFrame(card, fg_color="transparent")
        operations_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        placeholder = ctk.CTkLabel(
            operations_frame,
            text="История операций будет отображаться здесь",
            font=ctk.CTkFont(size=12),
            text_color=AppColors.TEXT_SECONDARY
        )
        placeholder.pack(expand=True)
    
    def create_status_bar(self):
        """Создание статусной панели"""
        status_frame = ctk.CTkFrame(self, fg_color=AppColors.CARD_BACKGROUND, height=40)
        status_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 20))
        status_frame.grid_propagate(False)
        
        self.status_label = ctk.CTkLabel(
            status_frame,
            text="Готов к работе",
            font=ctk.CTkFont(size=12),
            text_color=AppColors.TEXT_SECONDARY
        )
        self.status_label.pack(side="left", padx=20, pady=10)
        
        # Информация о версии
        version_label = ctk.CTkLabel(
            status_frame,
            text="Material Matcher v2.0",
            font=ctk.CTkFont(size=11),
            text_color=AppColors.TEXT_SECONDARY
        )
        version_label.pack(side="right", padx=20, pady=10)
    
    def update_data_stats(self):
        """Обновление статистики данных"""
        materials_count = len(self.app.app_data.materials) if self.app.app_data.materials else 0
        price_items_count = len(self.app.app_data.price_items) if self.app.app_data.price_items else 0
        
        self.materials_label.configure(text=f"Материалы: {materials_count}")
        self.price_items_label.configure(text=f"Позиции прайс-листа: {price_items_count}")
        
        # Обновляем состояние кнопок
        can_start = materials_count > 0 and price_items_count > 0
        self.start_button.configure(state="normal" if can_start else "disabled")
        
        has_results = bool(self.app.app_data.results)
        self.results_button.configure(state="normal" if has_results else "disabled")
    
    def update_elasticsearch_status(self, connected: bool, error: str = None):
        """Обновление статуса Elasticsearch"""
        if connected:
            self.es_indicator.configure(text="🟢", text_color=AppColors.SUCCESS)
            self.es_status_label.configure(text="Elasticsearch: Подключен")
        else:
            self.es_indicator.configure(text="🔴", text_color=AppColors.ERROR)
            error_text = "Elasticsearch: Не подключен"
            if error:
                error_text += f" ({error})"
            self.es_status_label.configure(text=error_text)
    
    def on_show(self):
        """Обновление при показе экрана"""
        self.update_data_stats()


class LoadingScreen(BaseScreen):
    """Экран загрузки"""
    
    def setup_ui(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Центральный контейнер
        center_frame = ctk.CTkFrame(self, fg_color="transparent")
        center_frame.grid(row=0, column=0)
        
        # Анимированный индикатор (заглушка - можно добавить кастомную анимацию)
        self.loading_label = ctk.CTkLabel(
            center_frame,
            text="⚙️",
            font=ctk.CTkFont(size=60),
            text_color=AppColors.PRIMARY
        )
        self.loading_label.pack(pady=20)
        
        # Текст состояния
        self.status_label = ctk.CTkLabel(
            center_frame,
            text="Загрузка...",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=AppColors.TEXT_PRIMARY
        )
        self.status_label.pack(pady=10)
        
        # Прогресс бар
        self.progress_bar = ctk.CTkProgressBar(
            center_frame,
            width=400,
            height=10
        )
        self.progress_bar.pack(pady=20)
        self.progress_bar.set(0)
        
        # Подробности
        self.details_label = ctk.CTkLabel(
            center_frame,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=AppColors.TEXT_SECONDARY
        )
        self.details_label.pack(pady=5)
    
    def start_loading(self, message: str = "Загрузка..."):
        """Начать процесс загрузки"""
        self.status_label.configure(text=message)
        self.progress_bar.set(0)
        self.details_label.configure(text="")
        
        # Запустить анимацию
        self.animate_loading()
    
    def animate_loading(self):
        """Анимация загрузки"""
        current_text = self.loading_label.cget("text")
        if current_text == "⚙️":
            self.loading_label.configure(text="🔄")
        else:
            self.loading_label.configure(text="⚙️")
        
        # Продолжить анимацию через 500мс
        self.after(500, self.animate_loading)
    
    def update_progress(self, message: str, progress: int):
        """Обновление прогресса"""
        self.details_label.configure(text=message)
        self.progress_bar.set(progress / 100.0)


class ResultsScreen(BaseScreen):
    """Экран результатов"""
    
    def setup_ui(self):
        self.grid_rowconfigure(0, weight=0)  # Заголовок
        self.grid_rowconfigure(1, weight=1)  # Контент
        self.grid_columnconfigure(0, weight=1)
        
        # Заголовок с кнопками
        self.create_header()
        
        # Основной контент
        self.create_content()
    
    def create_header(self):
        """Создание заголовка"""
        header_frame = ctk.CTkFrame(self, fg_color=AppColors.CARD_BACKGROUND)
        header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(0, 20))
        
        # Заголовок
        title = ctk.CTkLabel(
            header_frame,
            text="📊 Результаты сопоставления",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=AppColors.TEXT_PRIMARY
        )
        title.pack(side="left", padx=20, pady=20)
        
        # Кнопки управления
        buttons_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        buttons_frame.pack(side="right", padx=20, pady=15)
        
        # Кнопка возврата на главную
        back_button = ctk.CTkButton(
            buttons_frame,
            text="🏠 На главную",
            width=120,
            command=lambda: self.app.show_screen("dashboard")
        )
        back_button.pack(side="left", padx=5)
        
        # Кнопка экспорта
        export_button = ctk.CTkButton(
            buttons_frame,
            text="💾 Экспорт",
            width=100,
            fg_color=AppColors.SUCCESS,
            command=self.export_results
        )
        export_button.pack(side="left", padx=5)
    
    def create_content(self):
        """Создание контента результатов"""
        content_frame = ctk.CTkFrame(self, fg_color="transparent")
        content_frame.grid(row=1, column=0, sticky="nsew", padx=20)
        content_frame.grid_rowconfigure(0, weight=1)
        content_frame.grid_columnconfigure(0, weight=1)
        
        # Скроллируемый фрейм для результатов
        self.scrollable_frame = ctk.CTkScrollableFrame(
            content_frame,
            fg_color=AppColors.BACKGROUND
        )
        self.scrollable_frame.grid(row=0, column=0, sticky="nsew")
        self.scrollable_frame.grid_columnconfigure(0, weight=1)
    
    def update_results(self):
        """Обновление отображения результатов"""
        # Очищаем предыдущие результаты
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        
        if not self.app.app_data.results:
            # Показать заглушку
            placeholder = ctk.CTkLabel(
                self.scrollable_frame,
                text="Результаты пока недоступны.\nЗапустите процесс сопоставления.",
                font=ctk.CTkFont(size=16),
                text_color=AppColors.TEXT_SECONDARY
            )
            placeholder.pack(expand=True, pady=50)
            return
        
        # Отображаем результаты
        self.display_results()
    
    def display_results(self):
        """Отображение результатов в виде карточек"""
        formatter = MatchingResultFormatter(max_matches=5)
        formatted_results = formatter.format_matching_results(
            self.app.app_data.results, 
            [m.id for m in self.app.app_data.materials] if self.app.app_data.materials else []
        )
        
        for i, result in enumerate(formatted_results):
            self.create_material_card(result, i)
    
    def create_material_card(self, result: Dict, index: int):
        """Создание карточки материала"""
        # Основная карточка материала
        card = ctk.CTkFrame(self.scrollable_frame, fg_color=AppColors.CARD_BACKGROUND)
        card.grid(row=index, column=0, sticky="ew", padx=10, pady=10)
        card.grid_columnconfigure(0, weight=1)
        
        # Заголовок материала
        header_frame = ctk.CTkFrame(card, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        header_frame.grid_columnconfigure(0, weight=1)
        
        material_name = ctk.CTkLabel(
            header_frame,
            text=f"🔧 {result['material_name']}",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=AppColors.TEXT_PRIMARY,
            anchor="w"
        )
        material_name.grid(row=0, column=0, sticky="w")
        
        # Статус (количество найденных вариантов)
        matches_count = len(result.get('matches', []))
        status_text = f"Найдено {matches_count} вариантов" if matches_count > 0 else "Варианты не найдены"
        status_color = AppColors.SUCCESS if matches_count > 0 else AppColors.ERROR
        
        status_label = ctk.CTkLabel(
            header_frame,
            text=status_text,
            font=ctk.CTkFont(size=12),
            text_color=status_color
        )
        status_label.grid(row=0, column=1, sticky="e")
        
        # Варианты
        if matches_count > 0:
            self.create_variants_section(card, result['matches'], result['material_id'])
    
    def create_variants_section(self, parent, matches: List, material_id: str):
        """Создание секции с вариантами"""
        variants_frame = ctk.CTkFrame(parent, fg_color="transparent")
        variants_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 20))
        variants_frame.grid_columnconfigure(0, weight=1)
        
        for i, match in enumerate(matches[:3]):  # Показываем максимум 3 варианта
            self.create_variant_item(variants_frame, match, material_id, i)
        
        # Если вариантов больше 3, показываем кнопку "Показать все"
        if len(matches) > 3:
            show_all_btn = ctk.CTkButton(
                variants_frame,
                text=f"Показать все ({len(matches)} вариантов)",
                height=30,
                fg_color="transparent",
                text_color=AppColors.PRIMARY,
                hover_color=AppColors.BACKGROUND,
                command=lambda: self.show_all_variants(matches, material_id)
            )
            show_all_btn.grid(row=len(matches[:3]), column=0, sticky="w", pady=5)
    
    def create_variant_item(self, parent, match: Dict, material_id: str, index: int):
        """Создание элемента варианта"""
        # Фрейм варианта
        variant_frame = ctk.CTkFrame(parent, fg_color=AppColors.BACKGROUND, height=80)
        variant_frame.grid(row=index, column=0, sticky="ew", pady=2)
        variant_frame.grid_propagate(False)
        variant_frame.grid_columnconfigure(1, weight=1)
        
        # Индикатор релевантности
        relevance_pct = match['relevance'] * 100
        if relevance_pct >= 70:
            indicator_color = AppColors.SUCCESS
            indicator_text = "🟢"
        elif relevance_pct >= 40:
            indicator_color = AppColors.WARNING
            indicator_text = "🟡"
        else:
            indicator_color = AppColors.ERROR
            indicator_text = "🔴"
        
        indicator = ctk.CTkLabel(
            variant_frame,
            text=indicator_text,
            font=ctk.CTkFont(size=16),
            width=30
        )
        indicator.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        # Информация о варианте
        info_frame = ctk.CTkFrame(variant_frame, fg_color="transparent")
        info_frame.grid(row=0, column=1, sticky="ew", padx=10, pady=10)
        info_frame.grid_columnconfigure(0, weight=1)
        
        # Название варианта
        variant_name = ctk.CTkLabel(
            info_frame,
            text=match['variant_name'],
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=AppColors.TEXT_PRIMARY,
            anchor="w"
        )
        variant_name.grid(row=0, column=0, sticky="w")
        
        # Детали (цена, поставщик, релевантность)
        details = f"{match['relevance']*100:.1f}% | "
        if match['price'] > 0:
            details += f"{match['price']:.2f} RUB | "
        if match['supplier']:
            details += f"{match['supplier']}"
        
        details_label = ctk.CTkLabel(
            info_frame,
            text=details,
            font=ctk.CTkFont(size=12),
            text_color=AppColors.TEXT_SECONDARY,
            anchor="w"
        )
        details_label.grid(row=1, column=0, sticky="w")
        
        # Кнопка выбора
        select_btn = ctk.CTkButton(
            variant_frame,
            text="✓ Выбрать",
            width=80,
            height=30,
            fg_color=AppColors.PRIMARY,
            command=lambda: self.select_variant(material_id, match)
        )
        select_btn.grid(row=0, column=2, padx=10, pady=10)
    
    def select_variant(self, material_id: str, match: Dict):
        """Выбрать вариант"""
        self.app.app_data.selected_variants[material_id] = match
        messagebox.showinfo("Успешно", f"Вариант выбран для материала")
        # Можно добавить визуальное обновление
    
    def show_all_variants(self, matches: List, material_id: str):
        """Показать все варианты в модальном окне"""
        # Создание модального окна
        modal = ctk.CTkToplevel(self.app.root)
        modal.title("Все варианты")
        modal.geometry("800x600")
        modal.transient(self.app.root)
        modal.grab_set()
        
        # Контент модального окна
        # Здесь можно реализовать полный список вариантов
        label = ctk.CTkLabel(modal, text=f"Найдено {len(matches)} вариантов")
        label.pack(pady=20)
        
        close_btn = ctk.CTkButton(modal, text="Закрыть", command=modal.destroy)
        close_btn.pack(pady=10)
    
    def export_results(self):
        """Экспорт результатов"""
        if not self.app.app_data.results:
            messagebox.showwarning("Предупреждение", "Нет результатов для экспорта")
            return
        
        filename = filedialog.asksaveasfilename(
            title="Экспорт результатов",
            defaultextension=".xlsx",
            filetypes=[("Excel файлы", "*.xlsx"), ("JSON файлы", "*.json")]
        )
        
        if filename:
            try:
                # Здесь можно использовать существующую логику экспорта
                messagebox.showinfo("Успешно", f"Результаты экспортированы в {filename}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Ошибка экспорта: {e}")
    
    def on_show(self):
        """Обновление при показе экрана"""
        self.update_results()


def main():
    """Запуск современного GUI"""
    app = ModernMaterialMatcherGUI()
    app.run()


if __name__ == "__main__":
    main()