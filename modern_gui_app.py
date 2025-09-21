#!/usr/bin/env python3
"""
Современный GUI с сайдбаром для системы сопоставления материалов
Flat дизайн с минималистичным интерфейсом
"""

import sys
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import json
from pathlib import Path
from datetime import datetime
import webbrowser

# Добавляем src в путь Python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.material_matcher_app import MaterialMatcherApp
from src.utils.json_formatter import MatchingResultFormatter
from src.utils.debug_logger import get_debug_logger, init_debug_logging


class ModernDesignColors:
    """Современная цветовая схема"""
    # Основные цвета
    WHITE = '#FFFFFF'
    LIGHT_GRAY = '#F5F5F5'
    MEDIUM_GRAY = '#E0E0E0'
    DARK_GRAY = '#757575'
    
    # Акцентные цвета
    BLUE_PRIMARY = '#2196F3'
    BLUE_HOVER = '#1976D2'
    GREEN_SUCCESS = '#4CAF50'
    ORANGE_WARNING = '#FF9800'
    RED_ERROR = '#F44336'
    
    # Текст
    TEXT_PRIMARY = '#212121'
    TEXT_SECONDARY = '#757575'
    TEXT_LIGHT = '#FFFFFF'
    
    # Консоль
    CONSOLE_BG = '#1E1E1E'
    CONSOLE_TEXT = '#D4D4D4'
    CONSOLE_SUCCESS = '#4EC9B0'
    CONSOLE_ERROR = '#F44747'
    
    # Тени и границы
    SHADOW = '#D0D0D0'  # Light gray instead of transparent
    BORDER = '#E0E0E0'


class ModernMaterialMatcherGUI:
    def __init__(self, root):
        self.root = root
        self.setup_window()
        self.setup_variables()
        self.setup_styles()
        self.create_layout()
        self.init_backend()
        
    def setup_window(self):
        """Настройка главного окна"""
        self.root.title("Material Matcher - Modern UI")
        self.root.geometry("1400x900")
        self.root.minsize(1200, 700)
        self.root.configure(bg=ModernDesignColors.WHITE)
        
    def setup_variables(self):
        """Инициализация переменных"""
        self.app = None
        self.config = self.load_config()
        self.materials = []
        self.materials_order = []
        self.price_items = []
        self.results = {}
        self.selected_variants = {}
        
        # Переменные для двойного клика
        self.last_click_time = 0
        self.last_click_item = None
        self.double_click_delay = 500
        
        # Текущая активная секция
        self.current_section = "load_match"
        
        # Переменные для сопоставления
        self.matching_cancelled = False
        
        # Инициализируем логгер
        init_debug_logging(log_level="INFO")
        self.debug_logger = get_debug_logger()
        
        # Переменные конфигурации для совместимости
        self.threshold_var = tk.DoubleVar(value=self.config['matching']['similarity_threshold'])
        self.max_results_var = tk.IntVar(value=self.config['matching']['max_results_per_material'])
        self.workers_var = tk.IntVar(value=self.config['matching']['max_workers'])
        
        # Дополнительные переменные для совместимости с оригинальным GUI
        self.materials_path_var = tk.StringVar()
        self.pricelist_path_var = tk.StringVar()
        
    def load_config(self):
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
        
    def setup_styles(self):
        """Настройка современных стилей"""
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Стили фреймов
        self.style.configure('Sidebar.TFrame',
            background=ModernDesignColors.LIGHT_GRAY,
            relief='flat')
        
        self.style.configure('Header.TFrame',
            background=ModernDesignColors.WHITE,
            relief='flat')
        
        self.style.configure('Content.TFrame',
            background=ModernDesignColors.WHITE,
            relief='flat')
            
        self.style.configure('Card.TFrame',
            background=ModernDesignColors.WHITE,
            relief='solid',
            borderwidth=1)
        
        # Стили кнопок
        self.style.configure('Sidebar.TButton',
            background=ModernDesignColors.LIGHT_GRAY,
            foreground=ModernDesignColors.TEXT_PRIMARY,
            borderwidth=0,
            focuscolor='none',
            font=('Segoe UI', 11),
            anchor='w',
            padding=(20, 15))
            
        self.style.map('Sidebar.TButton',
            background=[('active', ModernDesignColors.MEDIUM_GRAY)])
            
        self.style.configure('SidebarActive.TButton',
            background=ModernDesignColors.BLUE_PRIMARY,
            foreground=ModernDesignColors.TEXT_LIGHT,
            borderwidth=0,
            focuscolor='none',
            font=('Segoe UI', 11, 'bold'),
            anchor='w',
            padding=(20, 15))
            
        self.style.configure('Primary.TButton',
            background=ModernDesignColors.BLUE_PRIMARY,
            foreground=ModernDesignColors.TEXT_LIGHT,
            borderwidth=0,
            focuscolor='none',
            font=('Segoe UI', 10, 'bold'),
            padding=(15, 8))
            
        self.style.map('Primary.TButton',
            background=[('active', ModernDesignColors.BLUE_HOVER)])
            
        self.style.configure('Secondary.TButton',
            background=ModernDesignColors.MEDIUM_GRAY,
            foreground=ModernDesignColors.TEXT_PRIMARY,
            borderwidth=0,
            focuscolor='none',
            font=('Segoe UI', 10),
            padding=(15, 8))
            
        self.style.configure('Success.TButton',
            background=ModernDesignColors.GREEN_SUCCESS,
            foreground=ModernDesignColors.TEXT_LIGHT,
            borderwidth=0,
            focuscolor='none',
            font=('Segoe UI', 10, 'bold'),
            padding=(15, 8))
            
        # Стили меток
        self.style.configure('Header.TLabel',
            background=ModernDesignColors.WHITE,
            foreground=ModernDesignColors.TEXT_PRIMARY,
            font=('Segoe UI', 16, 'bold'))
            
        self.style.configure('CardTitle.TLabel',
            background=ModernDesignColors.WHITE,
            foreground=ModernDesignColors.TEXT_PRIMARY,
            font=('Segoe UI', 14, 'bold'))
            
        self.style.configure('Subtitle.TLabel',
            background=ModernDesignColors.WHITE,
            foreground=ModernDesignColors.TEXT_SECONDARY,
            font=('Segoe UI', 10))
            
        self.style.configure('Status.TLabel',
            background=ModernDesignColors.WHITE,
            foreground=ModernDesignColors.TEXT_SECONDARY,
            font=('Segoe UI', 9))
            
        # Стили прогресс-бара
        self.style.configure('Modern.Horizontal.TProgressbar',
            background=ModernDesignColors.GREEN_SUCCESS,
            troughcolor=ModernDesignColors.MEDIUM_GRAY,
            borderwidth=0,
            lightcolor=ModernDesignColors.GREEN_SUCCESS,
            darkcolor=ModernDesignColors.GREEN_SUCCESS)
            
        # Стили TreeView
        self.style.configure('Modern.Treeview',
            background=ModernDesignColors.WHITE,
            foreground=ModernDesignColors.TEXT_PRIMARY,
            fieldbackground=ModernDesignColors.WHITE,
            borderwidth=0,
            font=('Segoe UI', 10))
            
        self.style.configure('Modern.Treeview.Heading',
            background=ModernDesignColors.LIGHT_GRAY,
            foreground=ModernDesignColors.TEXT_PRIMARY,
            font=('Segoe UI', 10, 'bold'),
            relief='flat',
            borderwidth=1)
            
    def create_layout(self):
        """Создание основного макета"""
        # Создаем меню
        self.create_menu()
        
        # Заголовок
        self.create_header()
        
        # Основной контейнер
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Сайдбар
        self.create_sidebar(main_container)
        
        # Область контента
        self.create_content_area(main_container)
        
    def create_header(self):
        """Создание современного заголовка"""
        header = ttk.Frame(self.root, style='Header.TFrame', height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        # Левая часть - название приложения
        left_frame = ttk.Frame(header, style='Header.TFrame')
        left_frame.pack(side=tk.LEFT, padx=20, pady=15)
        
        ttk.Label(left_frame, text="🔍 Material Matcher", 
                 style='Header.TLabel').pack(side=tk.LEFT)
        
        # Правая часть - утилиты
        right_frame = ttk.Frame(header, style='Header.TFrame')
        right_frame.pack(side=tk.RIGHT, padx=20, pady=15)
        
        # Индикатор подключения к Elasticsearch
        self.connection_frame = ttk.Frame(right_frame, style='Header.TFrame')
        self.connection_frame.pack(side=tk.RIGHT, padx=(0, 15))
        
        self.es_indicator = ttk.Label(self.connection_frame, text="●", 
                                     foreground=ModernDesignColors.RED_ERROR,
                                     font=('Segoe UI', 12, 'bold'),
                                     background=ModernDesignColors.WHITE)
        self.es_indicator.pack(side=tk.LEFT)
        
        self.es_status_label = ttk.Label(self.connection_frame, text="Elasticsearch: Не подключен",
                                        font=('Segoe UI', 9),
                                        foreground=ModernDesignColors.TEXT_SECONDARY,
                                        background=ModernDesignColors.WHITE)
        self.es_status_label.pack(side=tk.LEFT, padx=(5, 0))
        
        # Кнопки утилит
        ttk.Button(right_frame, text="⚙️", style='Secondary.TButton',
                  command=self.show_settings, width=3).pack(side=tk.RIGHT, padx=(0, 5))
        ttk.Button(right_frame, text="❓", style='Secondary.TButton',
                  command=self.show_help, width=3).pack(side=tk.RIGHT, padx=(0, 5))
                  
        # Разделительная линия
        separator = ttk.Frame(self.root, height=1, style='Content.TFrame')
        separator.pack(fill=tk.X)
        separator.configure(relief='solid', borderwidth=1)
        
    def create_sidebar(self, parent):
        """Создание сайдбара с навигацией"""
        sidebar = ttk.Frame(parent, style='Sidebar.TFrame', width=250)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)
        
        # Заголовок навигации
        nav_header = ttk.Frame(sidebar, style='Sidebar.TFrame')
        nav_header.pack(fill=tk.X, pady=(30, 20), padx=20)
        
        ttk.Label(nav_header, text="Навигация", 
                 font=('Segoe UI', 12, 'bold'),
                 foreground=ModernDesignColors.TEXT_PRIMARY,
                 background=ModernDesignColors.LIGHT_GRAY).pack(anchor=tk.W)
        
        # Кнопки навигации
        self.nav_buttons = {}
        
        nav_items = [
            ("load_match", "📁 Load & Match", "Загрузка и сопоставление"),
            ("results", "📊 Results", "Результаты сопоставления"),
            ("logs", "📄 Log", "Журнал выполнения")
        ]
        
        for section_id, text, tooltip in nav_items:
            btn = ttk.Button(sidebar, text=text, 
                           command=lambda s=section_id: self.switch_section(s))
            btn.pack(fill=tk.X, padx=10, pady=2)
            self.nav_buttons[section_id] = btn
            
        # Устанавливаем активную секцию
        self.update_nav_buttons()
        
    def create_content_area(self, parent):
        """Создание области контента"""
        # Контейнер для контента
        self.content_container = ttk.Frame(parent, style='Content.TFrame')
        self.content_container.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Создаем все секции
        self.sections = {}
        self.sections["load_match"] = self.create_load_match_section()
        self.sections["results"] = self.create_results_section()
        self.sections["logs"] = self.create_logs_section()
        
        # Показываем активную секцию
        self.show_current_section()
        
    def create_load_match_section(self):
        """Секция загрузки и сопоставления"""
        section = ttk.Frame(self.content_container, style='Content.TFrame')
        
        # Заголовок секции
        title_frame = ttk.Frame(section, style='Content.TFrame')
        title_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Label(title_frame, text="Загрузка и сопоставление материалов", 
                 style='CardTitle.TLabel').pack(side=tk.LEFT)
                 
        # Карточка загрузки материалов
        self.create_materials_card(section)
        
        # Карточка загрузки прайс-листов
        self.create_pricelist_card(section)
        
        # Карточка управления сопоставлением
        self.create_matching_control_card(section)
        
        # Карточка прогресса
        self.create_progress_card(section)
        
        return section
        
    def create_materials_card(self, parent):
        """Карточка загрузки материалов"""
        card = self.create_card(parent, "📋 Материалы", "Загрузите файл с материалами для сопоставления")
        
        # Кнопка загрузки
        btn_frame = ttk.Frame(card, style='Card.TFrame')
        btn_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(btn_frame, text="📁 Выбрать файл материалов", 
                  style='Primary.TButton',
                  command=self.load_materials_auto).pack(side=tk.LEFT, padx=(0, 10))
                  
        ttk.Button(btn_frame, text="📂 Выбрать один файл", 
                  style='Secondary.TButton',
                  command=self.load_materials_file).pack(side=tk.LEFT)
                  
        # Статус
        self.materials_status = ttk.Label(btn_frame, text="Файл не выбран", 
                                         style='Status.TLabel')
        self.materials_status.pack(side=tk.LEFT, padx=(15, 0))
        
    def create_pricelist_card(self, parent):
        """Карточка загрузки прайс-листов"""
        card = self.create_card(parent, "💰 Прайс-листы", "Загрузите файлы прайс-листов поставщиков")
        
        # Кнопка загрузки
        btn_frame = ttk.Frame(card, style='Card.TFrame')
        btn_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(btn_frame, text="📄 Выбрать прайс-листы", 
                  style='Primary.TButton',
                  command=self.load_pricelist_auto).pack(side=tk.LEFT, padx=(0, 10))
                  
        ttk.Button(btn_frame, text="📃 Выбрать один файл", 
                  style='Secondary.TButton',
                  command=self.load_pricelist_file).pack(side=tk.LEFT)
                  
        # Статус
        self.pricelist_status = ttk.Label(btn_frame, text="Файлы не выбраны", 
                                         style='Status.TLabel')
        self.pricelist_status.pack(side=tk.LEFT, padx=(15, 0))
        
    def create_matching_control_card(self, parent):
        """Карточка управления сопоставлением"""
        card = self.create_card(parent, "🚀 Управление сопоставлением", "Запуск и остановка процесса сопоставления")
        
        # Кнопки управления
        controls = ttk.Frame(card, style='Card.TFrame')
        controls.pack(fill=tk.X, pady=10)
        
        self.start_button = ttk.Button(controls, text="▶️ Запустить сопоставление", 
                                     style='Success.TButton',
                                     command=self.run_full_matching,
                                     state="disabled")
        self.start_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.stop_button = ttk.Button(controls, text="⏹️ Остановить", 
                                    style='Secondary.TButton',
                                    command=self.stop_matching,
                                    state="disabled")
        self.stop_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Кнопки дополнительных действий
        ttk.Button(controls, text="🗂️ Индексировать", 
                  style='Secondary.TButton',
                  command=self.index_data).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(controls, text="🗑️ Очистить", 
                  style='Secondary.TButton',
                  command=self.clear_data).pack(side=tk.RIGHT)
        
    def create_progress_card(self, parent):
        """Карточка прогресса"""
        card = self.create_card(parent, "📊 Прогресс выполнения", "Текущий статус операций")
        
        # Текст статуса
        self.progress_var = tk.StringVar(value="Готов к запуску")
        self.progress_label = ttk.Label(card, textvariable=self.progress_var,
                                       font=('Segoe UI', 11, 'bold'),
                                       foreground=ModernDesignColors.TEXT_PRIMARY,
                                       background=ModernDesignColors.WHITE)
        self.progress_label.pack(pady=(10, 5))
        
        # Прогресс-бар
        self.progress_bar = ttk.Progressbar(card, mode='determinate', 
                                           style='Modern.Horizontal.TProgressbar')
        self.progress_bar.pack(fill=tk.X, padx=10, pady=(0, 15))
        
    def create_results_section(self):
        """Секция результатов"""
        section = ttk.Frame(self.content_container, style='Content.TFrame')
        
        # Заголовок
        title_frame = ttk.Frame(section, style='Content.TFrame')
        title_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Label(title_frame, text="Результаты сопоставления", 
                 style='CardTitle.TLabel').pack(side=tk.LEFT)
                 
        # Карточка статистики
        self.create_statistics_card(section)
        
        # Карточка таблицы результатов
        self.create_results_table_card(section)
        
        # Карточка экспорта
        self.create_export_card(section)
        
        return section
        
    def create_statistics_card(self, parent):
        """Карточка статистики"""
        card = self.create_card(parent, "📈 Статистика", "Сводная информация по результатам")
        
        # Сетка статистики
        stats_frame = ttk.Frame(card, style='Card.TFrame')
        stats_frame.pack(fill=tk.X, pady=10)
        
        # Создаем метки для статистики
        self.stats_labels = {}
        stats_items = [
            ("total_materials", "Всего материалов:"),
            ("materials_with_matches", "С соответствиями:"),
            ("total_matches", "Общих соответствий:"),
            ("avg_similarity", "Средняя похожесть:")
        ]
        
        for i, (key, text) in enumerate(stats_items):
            row = i // 2
            col = i % 2
            
            stat_frame = ttk.Frame(stats_frame, style='Card.TFrame')
            stat_frame.grid(row=row, column=col, padx=20, pady=5, sticky="w")
            
            ttk.Label(stat_frame, text=text, 
                     font=('Segoe UI', 10),
                     foreground=ModernDesignColors.TEXT_SECONDARY,
                     background=ModernDesignColors.WHITE).pack(side=tk.LEFT)
            self.stats_labels[key] = ttk.Label(stat_frame, text="0", 
                                              font=('Segoe UI', 10, 'bold'),
                                              foreground=ModernDesignColors.BLUE_PRIMARY,
                                              background=ModernDesignColors.WHITE)
            self.stats_labels[key].pack(side=tk.LEFT, padx=(10, 0))
            
    def create_results_table_card(self, parent):
        """Карточка таблицы результатов"""
        card = self.create_card(parent, "📋 Таблица результатов", "Подробные результаты сопоставления", expand=True)
        
        # Контейнер для TreeView и скроллбаров
        tree_frame = ttk.Frame(card)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Создаем TreeView
        columns = ("variant_name", "relevance", "price", "supplier", "brand", "category")
        self.results_tree = ttk.Treeview(tree_frame, columns=columns, show="tree headings", 
                                        style='Modern.Treeview')
        
        # Настройка заголовков
        self.results_tree.heading("#0", text="Материал")
        self.results_tree.heading("variant_name", text="Вариант из прайс-листа")  
        self.results_tree.heading("relevance", text="Релевантность")
        self.results_tree.heading("price", text="Цена")
        self.results_tree.heading("supplier", text="Поставщик")
        self.results_tree.heading("brand", text="Бренд")
        self.results_tree.heading("category", text="Категория")
        
        # Настройка колонок
        self.results_tree.column("#0", width=200, minwidth=150)
        self.results_tree.column("variant_name", width=250, minwidth=200)
        self.results_tree.column("relevance", width=100, minwidth=80)
        self.results_tree.column("price", width=100, minwidth=80)
        self.results_tree.column("supplier", width=150, minwidth=100)
        self.results_tree.column("brand", width=100, minwidth=80)
        self.results_tree.column("category", width=120, minwidth=100)
        
        # Скроллбары
        v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.results_tree.yview)
        h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.results_tree.xview)
        self.results_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Размещение с помощью grid внутри tree_frame
        self.results_tree.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        # Привязываем обработчики
        self.results_tree.bind("<Button-1>", self.on_smart_click)
        
    def create_export_card(self, parent):
        """Карточка экспорта"""
        card = self.create_card(parent, "💾 Экспорт", "Экспорт результатов в различные форматы")
        
        # Кнопки экспорта
        export_frame = ttk.Frame(card, style='Card.TFrame')
        export_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(export_frame, text="📊 Экспорт всех (Excel)", 
                  style='Primary.TButton',
                  command=lambda: self.export_results("xlsx")).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(export_frame, text="✅ Экспорт выбранных (Excel)", 
                  style='Success.TButton',
                  command=lambda: self.export_selected_results("xlsx")).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(export_frame, text="🔄 Сбросить выборы", 
                  style='Secondary.TButton',
                  command=self.reset_selections).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(export_frame, text="🔄 Обновить", 
                  style='Secondary.TButton',
                  command=self.refresh_results).pack(side=tk.RIGHT)
        
    def create_logs_section(self):
        """Секция логов"""
        section = ttk.Frame(self.content_container, style='Content.TFrame')
        
        # Заголовок
        title_frame = ttk.Frame(section, style='Content.TFrame')
        title_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Label(title_frame, text="Журнал выполнения", 
                 style='CardTitle.TLabel').pack(side=tk.LEFT)
                 
        # Карточка логов
        self.create_console_card(section)
        
        return section
        
    def create_console_card(self, parent):
        """Консольная карточка логов"""
        card = self.create_card(parent, "📄 Журнал выполнения", "Подробный лог всех операций", expand=True)
        
        # Кнопки управления
        controls = ttk.Frame(card, style='Card.TFrame')
        controls.pack(fill=tk.X, padx=10, pady=(10, 0))
        
        ttk.Button(controls, text="📋 Копировать", 
                  style='Secondary.TButton',
                  command=self.copy_log_to_clipboard).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(controls, text="🗑️ Очистить", 
                  style='Secondary.TButton',
                  command=self.clear_log).pack(side=tk.LEFT)
        
        # Консольное окно
        console_frame = ttk.Frame(card, style='Card.TFrame')
        console_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.log_text = tk.Text(console_frame,
                               bg=ModernDesignColors.CONSOLE_BG,
                               fg=ModernDesignColors.CONSOLE_TEXT,
                               font=('Consolas', 10),
                               insertbackground=ModernDesignColors.CONSOLE_TEXT,
                               selectbackground=ModernDesignColors.BLUE_PRIMARY,
                               wrap=tk.WORD)
                               
        # Настройка тегов для подсветки
        self.log_text.tag_configure("INFO", foreground=ModernDesignColors.CONSOLE_TEXT)
        self.log_text.tag_configure("SUCCESS", foreground=ModernDesignColors.CONSOLE_SUCCESS)
        self.log_text.tag_configure("ERROR", foreground=ModernDesignColors.CONSOLE_ERROR)
        self.log_text.tag_configure("WARNING", foreground=ModernDesignColors.ORANGE_WARNING)
        
        # Скроллбар для консоли
        console_scroll = ttk.Scrollbar(console_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=console_scroll.set)
        
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        console_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
    def create_card(self, parent, title, subtitle="", expand=False):
        """Создание карточки с заголовком"""
        card_container = ttk.Frame(parent, style='Content.TFrame')
        if expand:
            card_container.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        else:
            card_container.pack(fill=tk.X, pady=(0, 15))
        
        # Создаем эффект тени (простая рамка)
        shadow_frame = tk.Frame(card_container, bg=ModernDesignColors.SHADOW, height=2)
        shadow_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        card = ttk.Frame(card_container, style='Card.TFrame')
        card.pack(fill=tk.BOTH, expand=True)
        
        # Заголовок карточки
        header = ttk.Frame(card, style='Card.TFrame')
        header.pack(fill=tk.X, padx=20, pady=(20, 10))
        
        title_label = ttk.Label(header, text=title, 
                               font=('Segoe UI', 12, 'bold'),
                               foreground=ModernDesignColors.TEXT_PRIMARY,
                               background=ModernDesignColors.WHITE)
        title_label.pack(side=tk.LEFT)
        
        if subtitle:
            subtitle_label = ttk.Label(header, text=subtitle, 
                                      style='Subtitle.TLabel')
            subtitle_label.pack(side=tk.LEFT, padx=(15, 0))
            
        return card
    
    def create_menu(self):
        """Создание главного меню"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # Меню файл
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Файл", menu=file_menu)
        file_menu.add_command(label="Новый проект", command=self.new_project)
        file_menu.add_separator()
        file_menu.add_command(label="Экспорт результатов...", command=self.export_results)
        file_menu.add_separator()
        file_menu.add_command(label="Выход", command=self.root.quit)
        
        # Меню инструменты
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Инструменты", menu=tools_menu)
        tools_menu.add_command(label="Настройки", command=self.show_settings)
        tools_menu.add_command(label="Проверить Elasticsearch", command=self.check_elasticsearch)
        tools_menu.add_command(label="Создать индексы", command=self.setup_indices)
        tools_menu.add_separator()
        tools_menu.add_command(label="📋 Копировать логи отладки", command=self.copy_debug_logs)
        tools_menu.add_command(label="📄 Показать окно логов", command=self.show_debug_logs_window)
        
        # Меню справка
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Справка", menu=help_menu)
        help_menu.add_command(label="Руководство пользователя", command=self.show_help)
        help_menu.add_command(label="О программе", command=self.show_about)
    
    # Методы навигации
    def switch_section(self, section_id):
        """Переключение между секциями"""
        self.current_section = section_id
        self.update_nav_buttons()
        self.show_current_section()
        
    def update_nav_buttons(self):
        """Обновление стилей кнопок навигации"""
        for section_id, btn in self.nav_buttons.items():
            if section_id == self.current_section:
                btn.configure(style='SidebarActive.TButton')
            else:
                btn.configure(style='Sidebar.TButton')
                
    def show_current_section(self):
        """Показ текущей секции"""
        # Скрываем все секции
        for section in self.sections.values():
            section.pack_forget()
            
        # Показываем активную секцию
        if self.current_section in self.sections:
            self.sections[self.current_section].pack(fill=tk.BOTH, expand=True)
    
    def init_backend(self):
        """Инициализация backend-части"""
        self.check_elasticsearch_status()
        # Автоматически загружаем файлы при запуске
        self.root.after(1000, self.auto_load_on_startup)
        
    # =================== BACKEND FUNCTIONALITY METHODS ===================
    
    def new_project(self):
        """Создание нового проекта"""
        if messagebox.askyesno("Новый проект", "Очистить все данные и начать новый проект?"):
            self.clear_data()
            self.results = {}
            self.refresh_results()
            self.log_message("Создан новый проект", "INFO")
    
    def show_settings(self):
        """Показать окно настроек"""
        messagebox.showinfo("Настройки", "Окно настроек будет добавлено в следующей версии")
    
    def show_help(self):
        """Показать справку"""
        help_text = """
Руководство пользователя - Система сопоставления материалов

1. ПОДГОТОВКА:
   • Убедитесь что Elasticsearch запущен
   • Подготовьте файлы материалов и прайс-листов (CSV, Excel, JSON)

2. ЗАГРУЗКА ДАННЫХ:
   • Перейдите на вкладку "Загрузка данных"
   • Выберите файл материалов и нажмите "Загрузить"
   • Выберите файл прайс-листа и нажмите "Загрузить"
   • Проверьте предварительный просмотр
   • Нажмите "Индексировать данные"

3. СОПОСТАВЛЕНИЕ:
   • Перейдите на вкладку "Сопоставление"
   • Настройте параметры (порог похожести, кол-во результатов)
   • Нажмите "Запустить сопоставление"

4. РЕЗУЛЬТАТЫ:
   • Просмотрите результаты на вкладке "Результаты"
   • Экспортируйте в JSON, CSV или Excel при необходимости

5. ПОИСК:
   • Используйте вкладку "Поиск" для поиска конкретных материалов
        """
        
        help_window = tk.Toplevel(self.root)
        help_window.title("Справка")
        help_window.geometry("600x500")
        
        text_widget = scrolledtext.ScrolledText(help_window, wrap=tk.WORD)
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text_widget.insert(tk.END, help_text.strip())
        text_widget.config(state=tk.DISABLED)
    
    def show_about(self):
        """Показать информацию о программе"""
        messagebox.showinfo("О программе", 
            "Система сопоставления материалов v1.0\n\n"
            "Программа для автоматического поиска соответствий\n"
            "между материалами и прайс-листами поставщиков.\n\n"
            "Использует Elasticsearch и алгоритмы машинного обучения\n"
            "для высокоточного сопоставления.\n\n"
            "© 2025 Material Matcher")
    
    def load_materials_auto(self):
        """Автоматическая загрузка всех файлов материалов из папки material"""
        materials_dir = os.path.join(os.getcwd(), "material")
        
        # Проверяем существование папки
        if not os.path.exists(materials_dir):
            messagebox.showerror("Ошибка", f"Папка 'material' не найдена!\nОжидается: {materials_dir}")
            return
        
        # Ищем все поддерживаемые файлы
        supported_extensions = ['.csv', '.xlsx', '.json']
        material_files = []
        
        for file in os.listdir(materials_dir):
            file_path = os.path.join(materials_dir, file)
            if os.path.isfile(file_path):
                _, ext = os.path.splitext(file.lower())
                if ext in supported_extensions:
                    material_files.append(file_path)
        
        if not material_files:
            messagebox.showwarning("Предупреждение", 
                                 f"В папке 'material' не найдено файлов материалов!\n"
                                 f"Поддерживаемые форматы: {', '.join(supported_extensions)}")
            return
        
        self.load_materials_from_directory(materials_dir)
    
    def load_pricelist_auto(self):
        """Автоматическая загрузка всех файлов прайс-листов из папки price-list"""
        pricelist_dir = os.path.join(os.getcwd(), "price-list")
        
        # Проверяем существование папки
        if not os.path.exists(pricelist_dir):
            messagebox.showerror("Ошибка", f"Папка 'price-list' не найдена!\nОжидается: {pricelist_dir}")
            return
        
        # Ищем все поддерживаемые файлы
        supported_extensions = ['.csv', '.xlsx', '.json']
        pricelist_files = []
        
        for file in os.listdir(pricelist_dir):
            file_path = os.path.join(pricelist_dir, file)
            if os.path.isfile(file_path):
                _, ext = os.path.splitext(file.lower())
                if ext in supported_extensions:
                    pricelist_files.append(file_path)
        
        if not pricelist_files:
            messagebox.showwarning("Предупреждение", 
                                 f"В папке 'price-list' не найдено файлов прайс-листов!\n"
                                 f"Поддерживаемые форматы: {', '.join(supported_extensions)}")
            return
        
        self.load_pricelist_from_directory(pricelist_dir)
    
    def load_materials_from_directory(self, directory_path):
        """Загрузка всех файлов материалов из указанной папки"""
        try:
            self.progress_var.set("Загружаем материалы из папки...")
            
            def load_materials_thread():
                all_materials = []
                supported_extensions = ['.csv', '.xlsx', '.json']
                
                # Получаем все файлы
                material_files = []
                for file in os.listdir(directory_path):
                    file_path = os.path.join(directory_path, file)
                    if os.path.isfile(file_path):
                        _, ext = os.path.splitext(file.lower())
                        if ext in supported_extensions:
                            material_files.append((file, file_path))
                
                if not material_files:
                    messagebox.showwarning("Предупреждение", "Не найдено файлов для загрузки!")
                    return
                
                # Настраиваем прогресс
                self.root.after(0, lambda: setattr(self.progress_bar, 'maximum', len(material_files)))
                
                # Загружаем каждый файл
                for i, (filename, file_path) in enumerate(material_files):
                    self.root.after(0, lambda f=filename: self.progress_var.set(f"Загружаем: {f}"))
                    try:
                        if file_path.endswith('.csv'):
                            from src.utils.data_loader import MaterialLoader
                            materials = MaterialLoader.load_from_csv(file_path)
                        elif file_path.endswith('.xlsx'):
                            from src.utils.data_loader import MaterialLoader
                            materials = MaterialLoader.load_from_excel(file_path)
                        elif file_path.endswith('.json'):
                            from src.utils.data_loader import MaterialLoader
                            materials = MaterialLoader.load_from_json(file_path)
                        else:
                            continue
                        
                        all_materials.extend(materials)
                        self.root.after(0, lambda v=i+1: setattr(self.progress_bar, 'value', v))
                        self.root.update_idletasks()
                        
                    except Exception as e:
                        self.log_message(f"Ошибка загрузки файла {filename}: {e}", "ERROR")
                        continue
                
                # Сохраняем результаты
                self.materials = all_materials
                self.materials_order = [m.id for m in all_materials]
                
                # Обновляем интерфейс
                self.root.after(0, lambda: self.update_materials_status(len(all_materials)))
                self.root.after(0, lambda: self.progress_var.set(f"Загружено материалов: {len(all_materials)} из {len(material_files)} файлов"))
            
            # Запускаем в потоке
            thread = threading.Thread(target=load_materials_thread, daemon=True)
            thread.start()
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при загрузке материалов:\n{str(e)}")
            self.progress_var.set("Готов")
    
    def load_pricelist_from_directory(self, directory_path):
        """Загрузка всех файлов прайс-листов из указанной папки"""
        try:
            self.progress_var.set("Загружаем прайс-листы из папки...")
            
            def load_pricelist_thread():
                all_price_items = []
                supported_extensions = ['.csv', '.xlsx', '.json']
                
                # Получаем все файлы
                pricelist_files = []
                for file in os.listdir(directory_path):
                    file_path = os.path.join(directory_path, file)
                    if os.path.isfile(file_path):
                        _, ext = os.path.splitext(file.lower())
                        if ext in supported_extensions:
                            pricelist_files.append((file, file_path))
                
                if not pricelist_files:
                    messagebox.showwarning("Предупреждение", "Не найдено файлов для загрузки!")
                    return
                
                # Настраиваем прогресс
                self.root.after(0, lambda: setattr(self.progress_bar, 'maximum', len(pricelist_files)))
                
                # Загружаем каждый файл
                for i, (filename, file_path) in enumerate(pricelist_files):
                    self.root.after(0, lambda f=filename: self.progress_var.set(f"Загружаем: {f}"))
                    try:
                        if file_path.endswith('.csv'):
                            from src.utils.data_loader import PriceListLoader
                            price_items = PriceListLoader.load_from_csv(file_path)
                        elif file_path.endswith('.xlsx'):
                            from src.utils.data_loader import PriceListLoader
                            price_items = PriceListLoader.load_from_excel(file_path)
                        elif file_path.endswith('.json'):
                            from src.utils.data_loader import PriceListLoader
                            price_items = PriceListLoader.load_from_json(file_path)
                        else:
                            continue
                        
                        all_price_items.extend(price_items)
                        self.root.after(0, lambda v=i+1: setattr(self.progress_bar, 'value', v))
                        self.root.update_idletasks()
                        
                    except Exception as e:
                        self.log_message(f"Ошибка загрузки файла {filename}: {e}", "ERROR")
                        continue
                
                # Сохраняем результаты
                self.price_items = all_price_items
                
                # Обновляем интерфейс
                self.root.after(0, lambda: self.update_pricelist_status(len(all_price_items)))
                self.root.after(0, lambda: self.progress_var.set(f"Загружено позиций прайс-листа: {len(all_price_items)} из {len(pricelist_files)} файлов"))
            
            # Запускаем в потоке
            thread = threading.Thread(target=load_pricelist_thread, daemon=True)
            thread.start()
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при загрузке прайс-листов:\n{str(e)}")
            self.progress_var.set("Готов")
    
    def update_materials_status(self, count):
        """Обновление статуса материалов"""
        self.materials_status.config(text=f"Загружено {count} материалов", 
                                    foreground=ModernDesignColors.GREEN_SUCCESS)
        self.update_start_button_state()
    
    def update_pricelist_status(self, count):
        """Обновление статуса прайс-листов"""
        self.pricelist_status.config(text=f"Загружено {count} позиций", 
                                    foreground=ModernDesignColors.GREEN_SUCCESS)
        self.update_start_button_state()
    
    def update_start_button_state(self):
        """Обновление состояния кнопки запуска"""
        self.log_message(f"Проверка кнопки: materials={len(self.materials) if self.materials else 0}, price_items={len(self.price_items) if self.price_items else 0}, app={self.app is not None}")
        
        if self.materials and self.price_items and self.app:
            # Проверяем подключение к Elasticsearch в отдельном потоке
            def check():
                try:
                    connected = self.app.es_service.check_connection()
                    self.root.after(0, lambda: self._set_start_button_state(connected))
                except:
                    self.root.after(0, lambda: self._set_start_button_state(False))
            
            threading.Thread(target=check, daemon=True).start()
        else:
            self.start_button.config(state="disabled")
    
    def _set_start_button_state(self, es_connected):
        """Установка состояния кнопки запуска"""
        if self.materials and self.price_items and es_connected:
            self.start_button.config(state="normal")
        else:
            self.start_button.config(state="disabled")
    
    def run_full_matching(self):
        """Запуск полного сопоставления"""
        if not self.materials or not self.price_items:
            messagebox.showerror("Ошибка", "Загрузите материалы и прайс-лист")
            return
        
        # Обновляем конфигурацию
        self.config['matching']['similarity_threshold'] = self.threshold_var.get()
        self.config['matching']['max_results_per_material'] = self.max_results_var.get()
        self.config['matching']['max_workers'] = self.workers_var.get()
        
        self.matching_cancelled = False
        
        def matching():
            try:
                if self.app is None:
                    self.app = MaterialMatcherApp(self.config)
                
                # Обновляем UI
                self.root.after(0, lambda: self.start_button.config(state="disabled"))
                self.root.after(0, lambda: self.stop_button.config(state="normal"))
                self.root.after(0, lambda: self.progress_bar.start(10) if hasattr(self, 'progress_bar') and self.progress_bar else None)
                self.root.after(0, lambda: self.progress_var.set("Запуск сопоставления..."))
                self.root.after(0, lambda: self.log_message("Начинаем сопоставление материалов...", "INFO"))
                
                # Запускаем сопоставление
                results = self.app.run_matching(self.materials)
                
                if not self.matching_cancelled:
                    self.results = results
                    self.root.after(0, lambda: self.update_results_display())
                    self.root.after(0, lambda: self.log_message("Сопоставление завершено успешно!", "SUCCESS"))
                    self.root.after(0, lambda: self.switch_section("results"))  # Переходим к результатам
                else:
                    self.root.after(0, lambda: self.log_message("Сопоставление отменено пользователем", "WARNING"))
                
            except Exception as e:
                self.root.after(0, lambda: self.log_message(f"Ошибка сопоставления: {e}", "ERROR"))
            finally:
                # Восстанавливаем UI
                self.root.after(0, lambda: self.start_button.config(state="normal"))
                self.root.after(0, lambda: self.stop_button.config(state="disabled"))
                self.root.after(0, lambda: self.progress_bar.stop() if hasattr(self, 'progress_bar') and self.progress_bar else None)
                self.root.after(0, lambda: self.progress_var.set("Готов к запуску"))
        
        threading.Thread(target=matching, daemon=True).start()
    
    def stop_matching(self):
        """Остановка сопоставления"""
        self.matching_cancelled = True
        self.stop_button.config(state="disabled")
        self.log_message("Останавливаем сопоставление...", "WARNING")
    
    def index_data(self, show_warning=True):
        """Индексация данных"""
        if not self.materials and not self.price_items:
            if show_warning:
                messagebox.showwarning("Предупреждение", "Нет данных для индексации")
            return False
        
        def index():
            try:
                if self.app is None:
                    self.app = MaterialMatcherApp(self.config)
                
                self.root.after(0, lambda: self.progress_var.set("Индексация данных..."))
                self.root.after(0, lambda: self.log_message("Начинаем индексацию данных...", "INFO"))
                
                if self.app.index_data(self.materials, self.price_items):
                    self.root.after(0, lambda: self.log_message("Данные успешно проиндексированы!", "SUCCESS"))
                    self.root.after(0, lambda: self.progress_var.set("Готов"))
                    self.root.after(0, self.update_start_button_state)
                else:
                    self.root.after(0, lambda: self.log_message("Ошибка индексации данных!", "ERROR"))
                    self.root.after(0, lambda: self.progress_var.set("Ошибка"))
            except Exception as e:
                self.root.after(0, lambda: self.log_message(f"Ошибка индексации: {e}", "ERROR"))
                self.root.after(0, lambda: self.progress_var.set("Ошибка"))
        
        threading.Thread(target=index, daemon=True).start()
        return True
    
    def clear_data(self):
        """Очистка данных"""
        self.materials = []
        self.materials_order = []
        self.price_items = []
        self.results = {}
        self.selected_variants = {}
        
        # Очищаем интерфейс
        self.materials_status.config(text="Файл не выбран", 
                                    foreground=ModernDesignColors.TEXT_SECONDARY)
        self.pricelist_status.config(text="Файлы не выбраны", 
                                    foreground=ModernDesignColors.TEXT_SECONDARY)
        
        # Очищаем результаты
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        
        # Обнуляем статистику
        for key in self.stats_labels:
            self.stats_labels[key].config(text="0")
        
        self.start_button.config(state="disabled")
        self.log_message("Данные очищены", "INFO")
    
    def check_elasticsearch_status(self):
        """Проверка статуса Elasticsearch"""
        def check():
            try:
                if self.app is None:
                    self.app = MaterialMatcherApp(self.config)
                
                if self.app.es_service.check_connection():
                    self.root.after(0, lambda: self.update_es_status(True))
                else:
                    self.root.after(0, lambda: self.update_es_status(False))
            except Exception as e:
                self.root.after(0, lambda: self.update_es_status(False, str(e)))
        
        threading.Thread(target=check, daemon=True).start()
    
    def update_es_status(self, connected, error=None):
        """Обновление статуса Elasticsearch"""
        if connected:
            self.es_indicator.config(foreground=ModernDesignColors.GREEN_SUCCESS)
            self.es_status_label.config(text="Elasticsearch: Подключен")
            self.start_button.config(state="normal" if self.materials and self.price_items else "disabled")
        else:
            self.es_indicator.config(foreground=ModernDesignColors.RED_ERROR)
            self.es_status_label.config(text="Elasticsearch: Не подключен")
            self.start_button.config(state="disabled")
            if error:
                self.log_message(f"Elasticsearch недоступен: {error}", "ERROR")
    
    def auto_load_on_startup(self):
        """Автоматическая загрузка файлов при запуске программы"""
        self.log_message("Запуск автоматической загрузки файлов...", "INFO")
        
        materials_dir = Path("./material")
        pricelist_dir = Path("./price-list")
        
        # Проверяем наличие папок
        materials_exists = materials_dir.exists() and any(materials_dir.iterdir())
        pricelist_exists = pricelist_dir.exists() and any(pricelist_dir.iterdir())
        
        if not materials_exists and not pricelist_exists:
            self.log_message("Папки material и price-list пусты или не найдены. Автозагрузка пропущена.", "INFO")
            return
        
        def auto_load_thread():
            try:
                # Загружаем материалы если есть файлы
                if materials_exists:
                    self.root.after(0, lambda: self.progress_var.set("Автозагрузка материалов..."))
                    self.load_materials_from_directory(materials_dir)
                    self.root.after(0, lambda: self.log_message("Материалы автоматически загружены", "SUCCESS"))
                
                # Небольшая пауза между загрузками
                import time
                time.sleep(0.5)
                
                # Загружаем прайс-листы если есть файлы
                if pricelist_exists:
                    self.root.after(0, lambda: self.progress_var.set("Автозагрузка прайс-листов..."))
                    self.load_pricelist_from_directory(pricelist_dir)
                    self.root.after(0, lambda: self.log_message("Прайс-листы автоматически загружены", "SUCCESS"))
                
                # Пауза перед автоматической индексацией
                time.sleep(1.0)
                
                # Автоматическая индексация если есть данные
                if self.materials or self.price_items:
                    self.root.after(0, lambda: self.log_message("Запуск автоматической индексации...", "INFO"))
                    self.root.after(0, lambda: self.index_data(show_warning=False))
                    self.root.after(0, lambda: self.log_message("Система готова к работе!", "SUCCESS"))
                    # Добавляем паузу и проверку кнопки после индексации
                    time.sleep(2.0)
                    self.root.after(0, self.update_start_button_state)
                    # Принудительная проверка кнопки через таймер
                    self.root.after(3000, self.update_start_button_state)
                else:
                    self.root.after(0, lambda: self.progress_var.set("Готов"))
                    
            except Exception as e:
                self.root.after(0, lambda: self.log_message(f"Ошибка автозагрузки: {e}", "ERROR"))
                self.root.after(0, lambda: self.progress_var.set("Ошибка"))
        
        # Запускаем автозагрузку в отдельном потоке
        threading.Thread(target=auto_load_thread, daemon=True).start()
    
    def check_elasticsearch(self):
        """Проверка подключения к Elasticsearch"""
        self.progress_var.set("Проверка подключения к Elasticsearch...")
        self.check_elasticsearch_status()
    
    def setup_indices(self):
        """Создание индексов Elasticsearch"""
        def create_indices():
            try:
                if self.app is None:
                    self.app = MaterialMatcherApp(self.config)
                
                self.root.after(0, lambda: self.progress_var.set("Создание индексов..."))
                
                if self.app.setup_indices():
                    self.root.after(0, lambda: self.log_message("Индексы созданы успешно!", "SUCCESS"))
                    self.root.after(0, lambda: self.progress_var.set("Готов"))
                else:
                    self.root.after(0, lambda: self.log_message("Ошибка создания индексов!", "ERROR"))
                    self.root.after(0, lambda: self.progress_var.set("Ошибка"))
            except Exception as e:
                self.root.after(0, lambda: self.log_message(f"Ошибка: {e}", "ERROR"))
                self.root.after(0, lambda: self.progress_var.set("Ошибка"))
        
        threading.Thread(target=create_indices, daemon=True).start()
    
    def load_materials_file(self):
        """Выбор файла материалов"""
        filename = filedialog.askopenfilename(
            title="Выберите файл материалов",
            filetypes=[
                ("Все поддерживаемые", "*.csv;*.xlsx;*.json"),
                ("CSV файлы", "*.csv"),
                ("Excel файлы", "*.xlsx"),
                ("JSON файлы", "*.json"),
                ("Все файлы", "*.*")
            ]
        )
        if filename:
            self.materials_path_var.set(filename)
            self.load_materials_data_from_file(filename)
    
    def load_pricelist_file(self):
        """Выбор файла прайс-листа"""
        filename = filedialog.askopenfilename(
            title="Выберите файл прайс-листа",
            filetypes=[
                ("Все поддерживаемые", "*.csv;*.xlsx;*.json"),
                ("CSV файлы", "*.csv"),
                ("Excel файлы", "*.xlsx"),
                ("JSON файлы", "*.json"),
                ("Все файлы", "*.*")
            ]
        )
        if filename:
            self.pricelist_path_var.set(filename)
            self.load_pricelist_data_from_file(filename)
    
    def load_materials_data_from_file(self, file_path):
        """Загрузка данных материалов из файла"""
        def load():
            try:
                if self.app is None:
                    self.app = MaterialMatcherApp(self.config)
                
                self.root.after(0, lambda: self.progress_var.set("Загрузка материалов..."))
                
                materials = self.app.load_materials(file_path)
                if materials:
                    self.materials = materials
                    # Сохраняем исходный порядок материалов
                    self.materials_order = [material.id for material in materials]
                    self.root.after(0, lambda: self.update_materials_status(len(materials)))
                    self.root.after(0, lambda: self.progress_var.set("Готов"))
                    self.root.after(0, self.update_start_button_state)
                else:
                    self.root.after(0, lambda: messagebox.showerror("Ошибка", "Не удалось загрузить материалы"))
                    self.root.after(0, lambda: self.progress_var.set("Ошибка"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Ошибка загрузки материалов: {e}"))
                self.root.after(0, lambda: self.progress_var.set("Ошибка"))
        
        threading.Thread(target=load, daemon=True).start()
    
    def load_pricelist_data_from_file(self, file_path):
        """Загрузка данных прайс-листа из файла"""
        def load():
            try:
                if self.app is None:
                    self.app = MaterialMatcherApp(self.config)
                
                self.root.after(0, lambda: self.progress_var.set("Загрузка прайс-листа..."))
                
                price_items = self.app.load_price_list(file_path)
                if price_items:
                    self.price_items = price_items
                    self.root.after(0, lambda: self.update_pricelist_status(len(price_items)))
                    self.root.after(0, lambda: self.progress_var.set("Готов"))
                    self.root.after(0, self.update_start_button_state)
                else:
                    self.root.after(0, lambda: messagebox.showerror("Ошибка", "Не удалось загрузить прайс-лист"))
                    self.root.after(0, lambda: self.progress_var.set("Ошибка"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Ошибка загрузки прайс-листа: {e}"))
                self.root.after(0, lambda: self.progress_var.set("Ошибка"))
        
        threading.Thread(target=load, daemon=True).start()
    
    # =================== RESULTS AND UI METHODS ===================
    
    def update_results_display(self):
        """Обновление отображения результатов с топ-7 вариантами"""
        self.log_message("НАЧАЛО update_results_display()", "INFO")
        
        # Сохраняем состояние раскрытия всех материалов
        expanded_materials = set()
        for item in self.results_tree.get_children():
            material_name = self.results_tree.item(item, 'text')
            # Материал считается раскрытым если у него есть дочерние элементы И он открыт
            # ИЛИ если у него нет дочерних элементов (значит был выбран вариант)
            has_children = len(self.results_tree.get_children(item)) > 0
            is_open = self.results_tree.item(item, 'open')
            
            if (has_children and is_open) or not has_children:
                # Очищаем от стрелочки, если она есть (материалы с выбранными вариантами)
                clean_name = material_name.split(' > ')[0] if ' > ' in material_name else material_name
                expanded_materials.add(clean_name)
                self.log_message(f"   Сохраняю как раскрытый: '{clean_name}' (дети: {has_children}, открыт: {is_open})")
        
        # Очищаем дерево результатов
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        
        # Используем форматтер для структурирования результатов
        self.formatter = MatchingResultFormatter(max_matches=7)
        formatted_results = self.formatter.format_matching_results(self.results, self.materials_order)
        
        # Вычисляем статистику
        stats = self.formatter.get_statistics()
        
        # Обновляем статистику
        self.stats_labels["total_materials"].config(text=str(stats["total_materials"]))
        self.stats_labels["materials_with_matches"].config(text=str(stats["materials_with_matches"]))
        self.stats_labels["total_matches"].config(text=str(stats["total_variants_found"]))
        self.stats_labels["avg_similarity"].config(text=f"{stats['average_relevance']*100:.1f}%")
        
        # Заполняем результаты с топ-7 вариантами для каждого материала
        # Если нет сохраненного состояния, значит это первый запуск - раскрываем все
        if not expanded_materials:
            expanded_materials = set([result["material_name"] for result in formatted_results])
        
        for result in formatted_results:
            material_name = result["material_name"]
            matches = result["matches"]
            
            if matches:
                # Добавляем материал как родительский узел
                parent = self.results_tree.insert("", tk.END, 
                    text=material_name,
                    tags=("material",)
                )
                
                # Добавляем топ-7 вариантов (максимум)
                for i, match in enumerate(matches[:7], 1):
                    # Форматируем данные для отображения
                    variant_name = match["variant_name"]
                    relevance = f"{match['relevance']*100:.1f}%"
                    price = f"{match['price']:.2f} RUB" if match['price'] > 0 else "Не указана"
                    supplier = match["supplier"] or "Не указан"
                    brand = match["brand"] or "-"
                    category = match.get("category", "-")
                    
                    # Определяем цветовую индикацию по релевантности
                    tag = "high" if match['relevance'] > 0.7 else "medium" if match['relevance'] > 0.4 else "low"
                    
                    # Добавляем вариант как дочерний элемент
                    child = self.results_tree.insert(parent, tk.END, 
                        values=(variant_name, relevance, price, supplier, brand, category),
                        tags=(tag, f"variant_{result['material_id']}_{match['variant_id']}")
                    )
                
                # Автоматически раскрываем все материалы (новые) или восстанавливаем состояние (обновление)
                should_expand = material_name in expanded_materials if expanded_materials else True
                self.results_tree.item(parent, open=should_expand)
                if should_expand:
                    self.log_message(f"   Раскрываю материал: '{material_name}'")
        
        # Настраиваем цветовые теги
        self.results_tree.tag_configure("material", font=('Segoe UI', 10, 'bold'))
        self.results_tree.tag_configure("high", foreground=ModernDesignColors.BLUE_PRIMARY)
        self.results_tree.tag_configure("medium", foreground=ModernDesignColors.ORANGE_WARNING)
        self.results_tree.tag_configure("low", foreground=ModernDesignColors.RED_ERROR)
    
    def on_smart_click(self, event):
        """Умный обработчик кликов - определяет одинарные и двойные клики по времени"""
        import time
        
        try:
            item = self.results_tree.identify('item', event.x, event.y)
            current_time = int(time.time() * 1000)  # время в миллисекундах
            
            if not item:
                return
                
            # Проверяем, является ли это двойным кликом
            if (item == self.last_click_item and 
                current_time - self.last_click_time < self.double_click_delay):
                
                # Это двойной клик!
                self.log_message("ДВОЙНОЙ КЛИК ОБНАРУЖЕН! (определен по времени)", "INFO")
                self.handle_double_click(event, item)
                
                # Сбрасываем данные клика чтобы избежать тройного клика
                self.last_click_item = None
                self.last_click_time = 0
                
            else:
                # Это одинарный клик - сохраняем данные для следующего клика
                self.last_click_item = item
                self.last_click_time = current_time
                
                # Отладочная информация для одинарного клика
                column = self.results_tree.identify('column', event.x, event.y)
                region = self.results_tree.identify('region', event.x, event.y)
                parent = self.results_tree.parent(item)
                item_text = self.results_tree.item(item, 'text')
                item_values = self.results_tree.item(item, 'values')
                item_tags = self.results_tree.item(item, 'tags')
                
                self.log_message(f"Одинарный клик: элемент={item}, колонка={column}, регион={region}")
                if item_values:
                    self.log_message(f"   Значения: {item_values}")
                    
        except Exception as e:
            self.log_message(f"Ошибка в обработке клика: {e}", "ERROR")
    
    def handle_double_click(self, event, item):
        """Обработка двойного клика по варианту из прайс-листа"""
        try:
            # Получаем колонку, по которой кликнули
            column = self.results_tree.identify('column', event.x, event.y)
            
            if not item:
                self.log_message("Не удалось определить элемент для клика", "ERROR")
                return
            
            # Проверяем, что кликнули по варианту (дочерний элемент), а не по материалу
            parent = self.results_tree.parent(item)
            if not parent:  # Кликнули по материалу, а не по варианту
                self.log_message("Клик по материалу (не по варианту)", "INFO")
                return
            
            # Дополнительная отладочная информация
            self.log_message(f"Двойной клик: элемент={item}, колонка={column}, родитель={parent}")
        except Exception as e:
            self.log_message(f"Ошибка при обработке клика: {e}", "ERROR")
            return
        
        # Получаем теги элемента для определения material_id и variant_id
        tags = self.results_tree.item(item, 'tags')
        self.log_message(f"Теги элемента: {tags}")
        
        variant_tag = None
        for tag in tags:
            if tag.startswith('variant_'):
                variant_tag = tag
                break
        
        if not variant_tag:
            self.log_message(f"Не найден тег варианта в {tags}", "ERROR")
            return
        
        self.log_message(f"Найден тег варианта: {variant_tag}")
        
        # Извлекаем material_id из тега (формат: variant_material_id_variant_id)
        try:
            parts = variant_tag.split('_')
            if len(parts) < 3:
                self.log_message(f"Неверный формат тега: {variant_tag}", "ERROR")
                return
            
            material_id = parts[1]
            variant_id = parts[2]
            
            self.log_message(f"Material ID: {material_id}, Variant ID: {variant_id}")
            
            # Получаем данные выбранного варианта
            values = self.results_tree.item(item, 'values')
            if not values:
                self.log_message(f"Нет значений для элемента {item}", "ERROR")
                return
                
            self.log_message(f"Значения варианта: {values}")
        except Exception as e:
            self.log_message(f"Ошибка при извлечении данных: {e}", "ERROR")
            return
        
        variant_name = values[0]  # Название варианта
        relevance = values[1]     # Релевантность
        price = values[2]         # Цена
        supplier = values[3]      # Поставщик
        brand = values[4]         # Бренд
        category = values[5]      # Категория
        
        # Сохраняем выбранный вариант
        self.selected_variants[material_id] = {
            'variant_id': variant_id,
            'variant_name': variant_name,
            'relevance': relevance,
            'price': price,
            'supplier': supplier,
            'brand': brand,
            'category': category,
            'item_id': item
        }
        
        # Сначала обновляем отображение выбранного варианта (поднимаем его на уровень материала)
        self.log_message("НАЧИНАЮ обновление выбранного варианта...")
        self.update_selected_variant_display(parent, item, variant_name)
        
        # ДАЕМ ВРЕМЯ ПОЛЬЗОВАТЕЛЮ УВИДЕТЬ ИЗМЕНЕНИЯ, затем схлопываем
        self.log_message("Даём время увидеть изменения перед схлопыванием...")
        self.root.after(100, lambda: self.delayed_collapse(parent, item))
        
        # Логируем действие
        material_name = self.results_tree.item(parent, 'text')
        self.log_message(f"Выбран вариант для '{material_name}': {variant_name}", "SUCCESS")
    
    def delayed_collapse(self, parent_item, selected_item):
        """ОТЛОЖЕННОЕ СХЛОПЫВАНИЕ: Даём время пользователю увидеть изменения"""
        self.log_message("Автоматическое схлопывание материала после выбора")
        self.hide_other_variants(parent_item, selected_item)
    
    def hide_other_variants(self, parent_item, selected_item):
        """ФИНАЛЬНОЕ РЕШЕНИЕ: НИЧЕГО НЕ ДЕЛАЕМ с вариантами - только схлопываем материал"""
        
        # Получаем всех дочерних элементов только для подсчета
        children = list(self.results_tree.get_children(parent_item))
        
        # НЕ ТРОГАЕМ ВАРИАНТЫ ВООБЩЕ! Даже визуально не изменяем
        # Просто схлопываем материал чтобы скрыть все варианты
        self.results_tree.item(parent_item, open=False)
        
        self.log_message(f"ФИНАЛЬНОЕ РЕШЕНИЕ: Просто схлопываем материал (скрываем {len(children)} вариантов)")
        self.log_message("Варианты НЕ изменены, НЕ удалены, НЕ модифицированы")  
        self.log_message("Надеемся что другие материалы останутся нетронутыми")
    
    def update_selected_variant_display(self, parent_item, selected_item, variant_name):
        """РЕШЕНИЕ БЕЗ ИЗМЕНЕНИЯ СТРУКТУРЫ: Только визуальное выделение через теги"""
        # Получаем данные для логирования
        selected_values = self.results_tree.item(selected_item, 'values')
        material_name = self.results_tree.item(parent_item, 'text')
        
        # КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: Копируем данные выбранного варианта в строку материала
        if selected_values:
            # Обновляем values родительского материала данными выбранного варианта
            self.results_tree.item(parent_item, values=selected_values)
            self.log_message(f"ДАННЫЕ ВАРИАНТА перенесены в строку материала: {selected_values}")
        
        # 1. ВЫДЕЛЯЕМ выбранный вариант цветом
        current_tags = list(self.results_tree.item(selected_item, 'tags'))
        if 'selected_variant' not in current_tags:
            current_tags.append('selected_variant')
            self.results_tree.item(selected_item, tags=current_tags)
        
        # 2. ВЫДЕЛЯЕМ материал как имеющий выбор
        parent_tags = list(self.results_tree.item(parent_item, 'tags'))
        if 'material_with_selection' not in parent_tags:
            parent_tags.append('material_with_selection')
            self.results_tree.item(parent_item, tags=parent_tags)
        
        # 3. Настраиваем стили для визуального выделения
        self.results_tree.tag_configure('selected_variant', background='lightblue', font=('Segoe UI', 10, 'bold'))
        self.results_tree.tag_configure('material_with_selection', background='lightblue', font=('Segoe UI', 11, 'bold'))
        
        self.log_message("ВИЗУАЛЬНОЕ ВЫДЕЛЕНИЕ: Материал и вариант выделены цветом")
        self.log_message("Структура TreeView НЕ изменена - материалы не схлопнутся!")
        
        # Стилизуем строку материала с выбранным вариантом
        parent_tags = list(self.results_tree.item(parent_item, 'tags'))
        if 'material_with_selection' not in parent_tags:
            parent_tags.append('material_with_selection')
        self.results_tree.item(parent_item, tags=parent_tags)
        
        # Настраиваем стиль для материала с выбранным вариантом
        self.results_tree.tag_configure('material_with_selection', 
                                       background='lightblue',
                                       font=('Segoe UI', 11, 'bold'),
                                       foreground=ModernDesignColors.BLUE_PRIMARY)
        
        self.log_message(f"Вариант '{variant_name}' поднят на уровень материала")
    
    def refresh_results(self):
        """Обновление результатов"""
        if self.results:
            self.update_results_display()
            self.log_message("Результаты обновлены", "INFO")
        else:
            self.log_message("Нет результатов для обновления", "INFO")
    
    def reset_selections(self):
        """Сброс всех выборов"""
        if not self.selected_variants:
            self.log_message("Нет выборов для сброса", "INFO")
            return
        
        # Очищаем выборы
        self.selected_variants.clear()
        
        # Обновляем отображение результатов
        self.update_results_display()
        
        self.log_message("Все выборы сброшены", "INFO")
    
    # =================== EXPORT METHODS ===================
    
    def export_selected_results(self, format_type="xlsx"):
        """Экспорт выбранных результатов"""
        if not self.selected_variants:
            messagebox.showwarning("Предупреждение", "Не выбрано ни одного варианта")
            return
        
        # Формируем данные выбранных результатов
        selected_data = []
        for material_id, selected in self.selected_variants.items():
            # Находим соответствующий материал и результат поиска
            for material_id_key, search_results in self.results.items():
                if material_id_key == material_id:
                    # Находим материал
                    material = None
                    for m in self.materials:
                        if m.id == material_id:
                            material = m
                            break
                    
                    if material:
                        # Находим выбранный результат поиска
                        for result in search_results:
                            if result.price_item.id == selected['variant_id']:
                                selected_data.append(result.to_dict())
                                break
                    break
        
        if not selected_data:
            messagebox.showwarning("Предупреждение", "Не удалось найти данные для выбранных вариантов")
            return
        
        # Выбираем файл для сохранения
        filename = filedialog.asksaveasfilename(
            title="Сохранить выбранные результаты",
            defaultextension=".xlsx",
            filetypes=[("Excel файлы", "*.xlsx"), ("Все файлы", "*.*")]
        )
        
        if filename:
            def export():
                try:
                    self.progress_var.set("Экспорт выбранных результатов...")
                    
                    # Используем основное приложение для экспорта
                    if self.app is None:
                        self.app = MaterialMatcherApp(self.config)
                    
                    # Экспортируем выбранные результаты
                    from src.utils.data_loader import DataExporter
                    DataExporter.export_results_to_xlsx(selected_data, filename)
                    
                    self.root.after(0, lambda: self.log_message(f"Выбранные результаты экспортированы в {filename}", "SUCCESS"))
                    self.root.after(0, lambda: self.progress_var.set("Готов"))
                    self.root.after(0, lambda: messagebox.showinfo("Экспорт", f"Выбранные результаты сохранены в файл:\n{filename}"))
                    
                except Exception as e:
                    self.root.after(0, lambda: self.log_message(f"Ошибка экспорта выбранных: {e}", "ERROR"))
                    self.root.after(0, lambda: self.progress_var.set("Ошибка"))
                    self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Ошибка экспорта выбранных результатов: {e}"))
            
            threading.Thread(target=export, daemon=True).start()
    
    def export_results(self, format_type="json"):
        """Экспорт результатов"""
        if not self.results:
            messagebox.showwarning("Предупреждение", "Нет результатов для экспорта")
            return
        
        # Выбираем файл для сохранения
        if format_type == "json":
            filename = filedialog.asksaveasfilename(
                title="Сохранить результаты",
                defaultextension=".json",
                filetypes=[("JSON файлы", "*.json"), ("Все файлы", "*.*")]
            )
        elif format_type == "csv":
            filename = filedialog.asksaveasfilename(
                title="Сохранить результаты",
                defaultextension=".csv",
                filetypes=[("CSV файлы", "*.csv"), ("Все файлы", "*.*")]
            )
        elif format_type == "xlsx":
            filename = filedialog.asksaveasfilename(
                title="Сохранить результаты",
                defaultextension=".xlsx",
                filetypes=[("Excel файлы", "*.xlsx"), ("Все файлы", "*.*")]
            )
        else:
            filename = filedialog.asksaveasfilename(
                title="Сохранить результаты",
                defaultextension=".json",
                filetypes=[("JSON файлы", "*.json"), ("Все файлы", "*.*")]
            )
        
        if filename:
            def export():
                try:
                    self.progress_var.set(f"Экспорт в {format_type.upper()}...")
                    
                    # Используем новый форматтер для экспорта
                    if hasattr(self, 'formatter'):
                        # Экспортируем в новом формате JSON
                        success = self.formatter.export_to_json(
                            filename, 
                            include_unselected=True,
                            pretty=True
                        )
                        if success:
                            self.root.after(0, lambda: self.log_message(f"Результаты экспортированы в {filename}", "SUCCESS"))
                            self.root.after(0, lambda: self.progress_var.set("Готов"))
                            self.root.after(0, lambda: messagebox.showinfo("Экспорт", f"Результаты сохранены в файл:\n{filename}"))
                        else:
                            raise Exception("Не удалось сохранить файл")
                    else:
                        # Fallback на старый метод
                        if self.app is None:
                            self.app = MaterialMatcherApp(self.config)
                        self.app.export_results(self.results, filename, format_type)
                        self.root.after(0, lambda: self.log_message(f"Результаты экспортированы в {filename}", "SUCCESS"))
                        self.root.after(0, lambda: self.progress_var.set("Готов"))
                        self.root.after(0, lambda: messagebox.showinfo("Экспорт", f"Результаты сохранены в файл:\n{filename}"))
                        
                except Exception as e:
                    self.root.after(0, lambda: self.log_message(f"Ошибка экспорта: {e}", "ERROR"))
                    self.root.after(0, lambda: self.progress_var.set("Ошибка"))
                    self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Ошибка экспорта: {e}"))
            
            threading.Thread(target=export, daemon=True).start()
    
    # =================== LOGGING AND UTILITY METHODS ===================
    
    def copy_log_to_clipboard(self):
        """Копирование содержимого лога в буфер обмена"""
        try:
            log_content = self.log_text.get("1.0", tk.END)
            self.root.clipboard_clear()
            self.root.clipboard_append(log_content)
            self.root.update()  # Применяем изменения буфера обмена
            messagebox.showinfo("Успешно", "Лог скопирован в буфер обмена!")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось скопировать лог: {e}")
    
    def clear_log(self):
        """Очистка лога"""
        if messagebox.askyesno("Подтверждение", "Очистить весь лог?"):
            self.log_text.delete("1.0", tk.END)
            self.log_message("Лог очищен", "INFO")
    
    def log_message(self, message, level="INFO"):
        """Добавление сообщения в лог с подсветкой синтаксиса"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] [{level}] {message}\n"
        
        # Определяем цвет и тег для разных уровней
        if level == "ERROR":
            tag = "ERROR"
        elif level == "SUCCESS":
            tag = "SUCCESS" 
        elif level == "WARNING":
            tag = "WARNING"
        else:
            tag = "INFO"
        
        # Добавляем сообщение с соответствующим тегом
        self.log_text.insert(tk.END, formatted_message, tag)
        self.log_text.see(tk.END)
    
    def copy_debug_logs(self):
        """Копирование логов отладки в буфер обмена"""
        try:
            logs_content = self.debug_logger.get_log_content("main")
            self.root.clipboard_clear()
            self.root.clipboard_append(logs_content)
            messagebox.showinfo("Готово", 
                              f"Логи отладки скопированы в буфер обмена.\n"
                              f"Размер: {len(logs_content)} символов")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при копировании логов: {str(e)}")
    
    def show_debug_logs_window(self):
        """Показать окно с логами отладки"""
        try:
            # Создаем новое окно
            logs_window = tk.Toplevel(self.root)
            logs_window.title("Логи отладки")
            logs_window.geometry("800x600")
            
            # Создаем вкладки для разных типов логов
            notebook = ttk.Notebook(logs_window)
            notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Основные логи
            main_frame = ttk.Frame(notebook)
            notebook.add(main_frame, text="Основные логи")
            
            main_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, font=('Consolas', 10))
            main_text.pack(fill=tk.BOTH, expand=True)
            
            main_logs = self.debug_logger.get_log_content("main")
            main_text.insert(tk.END, main_logs)
            
            # Детальные логи сопоставления
            detailed_frame = ttk.Frame(notebook)
            notebook.add(detailed_frame, text="Детальные логи сопоставления")
            
            detailed_text = scrolledtext.ScrolledText(detailed_frame, wrap=tk.WORD, font=('Consolas', 9))
            detailed_text.pack(fill=tk.BOTH, expand=True)
            
            detailed_logs = self.debug_logger.get_log_content("detailed")
            detailed_text.insert(tk.END, detailed_logs)
            
            # Кнопки управления
            button_frame = ttk.Frame(logs_window)
            button_frame.pack(fill=tk.X, padx=10, pady=5)
            
            ttk.Button(button_frame, text="📋 Копировать основные логи", 
                      command=lambda: self._copy_text_to_clipboard(main_logs, "основные логи")).pack(side=tk.LEFT, padx=5)
            
            ttk.Button(button_frame, text="📋 Копировать детальные логи", 
                      command=lambda: self._copy_text_to_clipboard(detailed_logs, "детальные логи")).pack(side=tk.LEFT, padx=5)
            
            ttk.Button(button_frame, text="🔄 Обновить", 
                      command=lambda: self._refresh_logs_window(main_text, detailed_text)).pack(side=tk.LEFT, padx=5)
            
            ttk.Button(button_frame, text="🗑️ Очистить логи", 
                      command=lambda: self._clear_debug_logs(main_text, detailed_text)).pack(side=tk.LEFT, padx=5)
            
            ttk.Button(button_frame, text="Закрыть", 
                      command=logs_window.destroy).pack(side=tk.RIGHT, padx=5)
                      
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при открытии окна логов: {str(e)}")
    
    def _copy_text_to_clipboard(self, text, description):
        """Вспомогательный метод для копирования текста в буфер обмена"""
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            messagebox.showinfo("Готово", 
                              f"{description.capitalize()} скопированы в буфер обмена.\n"
                              f"Размер: {len(text)} символов")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при копировании: {str(e)}")
    
    def _refresh_logs_window(self, main_text, detailed_text):
        """Обновление содержимого окна логов"""
        try:
            # Обновляем основные логи
            main_text.delete(1.0, tk.END)
            main_logs = self.debug_logger.get_log_content("main")
            main_text.insert(tk.END, main_logs)
            
            # Обновляем детальные логи
            detailed_text.delete(1.0, tk.END)
            detailed_logs = self.debug_logger.get_log_content("detailed")
            detailed_text.insert(tk.END, detailed_logs)
            
            messagebox.showinfo("Готово", "Логи обновлены")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при обновлении логов: {str(e)}")
    
    def _clear_debug_logs(self, main_text, detailed_text):
        """Очистка файлов логов"""
        if messagebox.askyesno("Подтверждение", 
                              "Вы уверены, что хотите очистить все лог-файлы?\n"
                              "Это действие нельзя отменить."):
            try:
                self.debug_logger.clear_logs()
                
                # Очищаем текстовые поля
                main_text.delete(1.0, tk.END)
                detailed_text.delete(1.0, tk.END)
                
                messagebox.showinfo("Готово", "Лог-файлы очищены")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Ошибка при очистке логов: {str(e)}")
    
    def update_threshold_label(self, value):
        """Обновление метки порога похожести (для совместимости)"""
        # В современном интерфейсе порог настраивается через конфиг
        self.threshold_var.set(float(value))
    
    def search_material(self):
        """Поиск материала"""
        # Этот метод будет доступен если понадобится поиск
        query = messagebox.askstring("Поиск материала", "Введите название материала для поиска:")
        if not query:
            return
        
        def search():
            try:
                if self.app is None:
                    self.app = MaterialMatcherApp(self.config)
                
                self.root.after(0, lambda: self.progress_var.set("Поиск материала..."))
                
                # Используем метод поиска по названию
                matches = self.app.search_material_by_name(query, top_n=10)
                
                if matches:
                    self.root.after(0, lambda: self.log_message(f"Найдено {len(matches)} соответствий для '{query}'", "SUCCESS"))
                    # Здесь можно добавить отображение результатов поиска
                else:
                    self.root.after(0, lambda: self.log_message(f"Соответствий для '{query}' не найдено", "WARNING"))
                    
                self.root.after(0, lambda: self.progress_var.set("Готов"))
                
            except Exception as e:
                self.root.after(0, lambda: self.log_message(f"Ошибка поиска: {e}", "ERROR"))
                self.root.after(0, lambda: self.progress_var.set("Ошибка"))
        
        threading.Thread(target=search, daemon=True).start()
    
    def update_search_results(self, query, matches):
        """Обновление результатов поиска (заглушка для совместимости)"""
        if matches:
            self.log_message(f"Найдено {len(matches)} соответствий для '{query}'", "SUCCESS")
            for i, match in enumerate(matches, 1):
                price_str = f"{match['price_item']['price']} {match['price_item']['currency']}" if match['price_item']['price'] else "Не указана"
                self.log_message(f"{i}. {match['price_item']['material_name']} - {match['similarity_percentage']:.1f}% - {price_str}")
        else:
            self.log_message(f"Соответствий для '{query}' не найдено", "WARNING")
    
    def load_materials_data(self):
        """Загрузка данных материалов (совместимость со старым интерфейсом)"""
        if not self.materials_path_var.get():
            messagebox.showerror("Ошибка", "Выберите файл материалов")
            return
        self.load_materials_data_from_file(self.materials_path_var.get())
    
    def load_pricelist_data(self):
        """Загрузка данных прайс-листа (совместимость со старым интерфейсом)"""
        if not self.pricelist_path_var.get():
            messagebox.showerror("Ошибка", "Выберите файл прайс-листа")
            return
        self.load_pricelist_data_from_file(self.pricelist_path_var.get())
    
    def update_materials_info(self, count):
        """Обновление информации о материалах (совместимость со старым интерфейсом)"""
        self.update_materials_status(count)
    
    def update_pricelist_info(self, count):
        """Обновление информации о прайс-листе (совместимость со старым интерфейсом)"""
        self.update_pricelist_status(count)
    
    # ================ COMPATIBILITY METHODS ================
    
    def highlight_selected_variant(self, item_id):
        """Визуальное выделение выбранного варианта"""
        # Снимаем предыдущие выделения для родительского материала
        parent_id = self.results_tree.parent(item_id)
        for child in self.results_tree.get_children(parent_id):
            self.results_tree.item(child, tags=self.results_tree.item(child)['tags'])
        
        # Добавляем тег выбранного варианта
        current_tags = list(self.results_tree.item(item_id)['tags'])
        if 'selected' not in current_tags:
            current_tags.append('selected')
        self.results_tree.item(item_id, tags=current_tags)
        self.results_tree.tag_configure('selected', 
                                       background=ModernDesignColors.BLUE_PRIMARY, 
                                       font=('Segoe UI', 10, 'bold'),
                                       foreground=ModernDesignColors.TEXT_LIGHT)
    
    def create_widgets(self):
        """Создание виджетов (совместимость со старым интерфейсом)"""
        # В современном интерфейсе это делается через create_layout()
        self.create_layout()
    
    def create_main_tab(self):
        """Создание главной вкладки (совместимость со старым интерфейсом)"""
        # В современном интерфейсе это делается через create_load_match_section()
        return self.create_load_match_section()
    
    def create_results_tab(self):
        """Создание вкладки результатов (совместимость со старым интерфейсом)"""
        # В современном интерфейсе это делается через create_results_section()
        return self.create_results_section()
    
    def create_status_bar(self):
        """Создание статусной панели (совместимость со старым интерфейсом)"""
        # В современном интерфейсе статус интегрирован в заголовок
        pass


def main():
    root = tk.Tk()
    app = ModernMaterialMatcherGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()