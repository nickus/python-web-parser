#!/usr/bin/env python3
"""
GUI приложение для системы сопоставления материалов
Предоставляет графический интерфейс для всех основных операций
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


class MaterialMatcherGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Система сопоставления материалов - Material Matcher")
        self.root.geometry("1000x700")
        self.root.minsize(800, 600)
        
        # Стилизация
        style = ttk.Style()
        style.theme_use('clam')
        
        # Переменные
        self.app = None
        self.config = self.load_config()
        self.materials = []
        self.materials_order = []  # Сохраняем исходный порядок материалов
        self.price_items = []
        self.results = {}
        self.selected_variants = {}  # Выбранные варианты для каждого материала {material_id: selected_match}
        
        # Переменные для обнаружения двойного клика
        self.last_click_time = 0
        self.last_click_item = None
        self.double_click_delay = 500  # мсек
        
        # Создаем интерфейс
        self.create_widgets()
        self.check_elasticsearch_status()
        
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
    
    def create_widgets(self):
        """Создание основного интерфейса"""
        # Главное меню
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
        
        # Меню справка
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Справка", menu=help_menu)
        help_menu.add_command(label="Руководство пользователя", command=self.show_help)
        help_menu.add_command(label="О программе", command=self.show_about)
        
        # Основной контейнер
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Создаем Notebook для вкладок
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Вкладка "Быстрый старт"
        self.create_quickstart_tab()
        
        # Вкладка "Загрузка данных"
        self.create_data_tab()
        
        # Вкладка "Сопоставление"
        self.create_matching_tab()
        
        # Вкладка "Результаты"
        self.create_results_tab()
        
        # Вкладка "Поиск"
        self.create_search_tab()
        
        # Статусная панель
        self.create_status_bar()
    
    def create_quickstart_tab(self):
        """Вкладка быстрого старта"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="🚀 Быстрый старт")
        
        # Заголовок
        title = ttk.Label(tab, text="Добро пожаловать в систему сопоставления материалов!", 
                         font=('Arial', 16, 'bold'))
        title.pack(pady=20)
        
        # Статус Elasticsearch
        status_frame = ttk.LabelFrame(tab, text="Статус системы", padding=10)
        status_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.es_status_label = ttk.Label(status_frame, text="Проверка подключения к Elasticsearch...", 
                                        font=('Arial', 10))
        self.es_status_label.pack()
        
        ttk.Button(status_frame, text="Проверить подключение", 
                  command=self.check_elasticsearch).pack(pady=5)
        
        # Быстрые действия
        actions_frame = ttk.LabelFrame(tab, text="Быстрые действия", padding=10)
        actions_frame.pack(fill=tk.X, padx=20, pady=10)
        
        actions_grid = ttk.Frame(actions_frame)
        actions_grid.pack()
        
        # Первая строка кнопок
        row1 = ttk.Frame(actions_grid)
        row1.pack(fill=tk.X, pady=5)
        
        ttk.Button(row1, text="📁 Загрузить материалы", 
                  command=self.load_materials_file, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(row1, text="💰 Загрузить прайс-лист", 
                  command=self.load_pricelist_file, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(row1, text="🔧 Создать индексы", 
                  command=self.setup_indices, width=20).pack(side=tk.LEFT, padx=5)
        
        # Вторая строка кнопок
        row2 = ttk.Frame(actions_grid)
        row2.pack(fill=tk.X, pady=5)
        
        ttk.Button(row2, text="▶️ Запустить сопоставление", 
                  command=self.run_full_matching, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(row2, text="🔍 Поиск материала", 
                  command=lambda: self.notebook.select(4), width=20).pack(side=tk.LEFT, padx=5)  # Переход к вкладке поиска
        ttk.Button(row2, text="📊 Просмотр результатов", 
                  command=lambda: self.notebook.select(3), width=20).pack(side=tk.LEFT, padx=5)  # Переход к результатам
        
        # Информация о системе
        info_frame = ttk.LabelFrame(tab, text="Информация", padding=10)
        info_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        info_text = """
🎯 Система сопоставления материалов помогает найти соответствия между:
   • Вашими материалами (каталог, база данных)
   • Прайс-листами поставщиков

📈 Алгоритм использует многокритериальный анализ:
   • Название материала (вес 40%)
   • Описание (вес 20%)
   • Категория (вес 15%)
   • Бренд (вес 15%)
   • Технические характеристики (вес 10%)

🔧 Для работы требуется Elasticsearch (можно запустить в Docker):
   docker run -d --name elasticsearch -p 9200:9200 -p 9300:9300 -e "discovery.type=single-node" elasticsearch:8.15.1

📁 Поддерживаемые форматы файлов: CSV, Excel (.xlsx), JSON
📋 Форматы экспорта: JSON, CSV, Excel (.xlsx)
        """
        
        info_label = ttk.Label(info_frame, text=info_text.strip(), justify=tk.LEFT, 
                              font=('Arial', 9))
        info_label.pack(anchor=tk.W)
    
    def create_data_tab(self):
        """Вкладка загрузки данных"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="📁 Загрузка данных")
        
        # Материалы
        materials_frame = ttk.LabelFrame(tab, text="Файл материалов", padding=10)
        materials_frame.pack(fill=tk.X, padx=10, pady=5)
        
        materials_row = ttk.Frame(materials_frame)
        materials_row.pack(fill=tk.X)
        
        self.materials_path_var = tk.StringVar()
        ttk.Entry(materials_row, textvariable=self.materials_path_var, width=60).pack(side=tk.LEFT, padx=(0,5))
        ttk.Button(materials_row, text="Обзор...", command=self.load_materials_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(materials_row, text="Загрузить", command=self.load_materials_data).pack(side=tk.LEFT, padx=5)
        
        self.materials_info_label = ttk.Label(materials_frame, text="Материалы не загружены", 
                                             foreground="red")
        self.materials_info_label.pack(anchor=tk.W, pady=(5,0))
        
        # Прайс-лист
        pricelist_frame = ttk.LabelFrame(tab, text="Файл прайс-листа", padding=10)
        pricelist_frame.pack(fill=tk.X, padx=10, pady=5)
        
        pricelist_row = ttk.Frame(pricelist_frame)
        pricelist_row.pack(fill=tk.X)
        
        self.pricelist_path_var = tk.StringVar()
        ttk.Entry(pricelist_row, textvariable=self.pricelist_path_var, width=60).pack(side=tk.LEFT, padx=(0,5))
        ttk.Button(pricelist_row, text="Обзор...", command=self.load_pricelist_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(pricelist_row, text="Загрузить", command=self.load_pricelist_data).pack(side=tk.LEFT, padx=5)
        
        self.pricelist_info_label = ttk.Label(pricelist_frame, text="Прайс-лист не загружен", 
                                             foreground="red")
        self.pricelist_info_label.pack(anchor=tk.W, pady=(5,0))
        
        # Предварительный просмотр
        preview_frame = ttk.LabelFrame(tab, text="Предварительный просмотр", padding=10)
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Создаем Treeview для предпросмотра
        preview_notebook = ttk.Notebook(preview_frame)
        preview_notebook.pack(fill=tk.BOTH, expand=True)
        
        # Вкладка материалы
        materials_preview_frame = ttk.Frame(preview_notebook)
        preview_notebook.add(materials_preview_frame, text="Материалы")
        
        self.materials_tree = ttk.Treeview(materials_preview_frame, height=8)
        materials_scrollbar = ttk.Scrollbar(materials_preview_frame, orient=tk.VERTICAL, 
                                           command=self.materials_tree.yview)
        self.materials_tree.configure(yscrollcommand=materials_scrollbar.set)
        
        self.materials_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        materials_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Вкладка прайс-лист
        pricelist_preview_frame = ttk.Frame(preview_notebook)
        preview_notebook.add(pricelist_preview_frame, text="Прайс-лист")
        
        self.pricelist_tree = ttk.Treeview(pricelist_preview_frame, height=8)
        pricelist_scrollbar = ttk.Scrollbar(pricelist_preview_frame, orient=tk.VERTICAL, 
                                           command=self.pricelist_tree.yview)
        self.pricelist_tree.configure(yscrollcommand=pricelist_scrollbar.set)
        
        self.pricelist_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        pricelist_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Кнопки действий
        actions_frame = ttk.Frame(tab)
        actions_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(actions_frame, text="Индексировать данные", 
                  command=self.index_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(actions_frame, text="Очистить данные", 
                  command=self.clear_data).pack(side=tk.LEFT, padx=5)
    
    def create_matching_tab(self):
        """Вкладка сопоставления"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="⚙️ Сопоставление")
        
        # Параметры сопоставления
        params_frame = ttk.LabelFrame(tab, text="Параметры сопоставления", padding=10)
        params_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Порог похожести
        threshold_row = ttk.Frame(params_frame)
        threshold_row.pack(fill=tk.X, pady=2)
        
        ttk.Label(threshold_row, text="Порог похожести:").pack(side=tk.LEFT)
        self.threshold_var = tk.DoubleVar(value=self.config['matching']['similarity_threshold'])
        threshold_scale = ttk.Scale(threshold_row, from_=0, to=100, 
                                   variable=self.threshold_var, orient=tk.HORIZONTAL)
        threshold_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        self.threshold_label = ttk.Label(threshold_row, text=f"{self.threshold_var.get():.1f}%")
        self.threshold_label.pack(side=tk.LEFT)
        
        threshold_scale.configure(command=self.update_threshold_label)
        
        # Максимальное количество результатов
        max_results_row = ttk.Frame(params_frame)
        max_results_row.pack(fill=tk.X, pady=2)
        
        ttk.Label(max_results_row, text="Макс. результатов на материал:").pack(side=tk.LEFT)
        self.max_results_var = tk.IntVar(value=self.config['matching']['max_results_per_material'])
        max_results_spin = ttk.Spinbox(max_results_row, from_=1, to=50, width=10,
                                      textvariable=self.max_results_var)
        max_results_spin.pack(side=tk.LEFT, padx=10)
        
        # Количество потоков
        workers_row = ttk.Frame(params_frame)
        workers_row.pack(fill=tk.X, pady=2)
        
        ttk.Label(workers_row, text="Количество потоков:").pack(side=tk.LEFT)
        self.workers_var = tk.IntVar(value=self.config['matching']['max_workers'])
        workers_spin = ttk.Spinbox(workers_row, from_=1, to=16, width=10,
                                  textvariable=self.workers_var)
        workers_spin.pack(side=tk.LEFT, padx=10)
        
        # Кнопки управления
        control_frame = ttk.Frame(tab)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.start_button = ttk.Button(control_frame, text="🚀 Запустить сопоставление", 
                                      command=self.run_full_matching, state="disabled")
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(control_frame, text="⏹ Остановить", 
                                     command=self.stop_matching, state="disabled")
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        # Прогресс
        progress_frame = ttk.LabelFrame(tab, text="Прогресс выполнения", padding=10)
        progress_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.progress_var = tk.StringVar(value="Готов к запуску")
        ttk.Label(progress_frame, textvariable=self.progress_var).pack(anchor=tk.W)
        
        self.progress_bar = ttk.Progressbar(progress_frame, mode='indeterminate')
        self.progress_bar.pack(fill=tk.X, pady=5)
        
        # Лог выполнения
        log_frame = ttk.LabelFrame(tab, text="Журнал выполнения", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)
    
    def create_results_tab(self):
        """Вкладка результатов"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="📊 Результаты")
        
        # Статистика
        stats_frame = ttk.LabelFrame(tab, text="Статистика", padding=10)
        stats_frame.pack(fill=tk.X, padx=10, pady=5)
        
        stats_grid = ttk.Frame(stats_frame)
        stats_grid.pack()
        
        # Создаем метки для статистики
        self.stats_labels = {}
        stats_items = [
            ("total_materials", "Всего материалов:"),
            ("materials_with_matches", "С найденными соответствиями:"),
            ("total_matches", "Общее количество соответствий:"),
            ("avg_similarity", "Средняя похожесть:")
        ]
        
        for i, (key, text) in enumerate(stats_items):
            row = i // 2
            col = i % 2
            
            frame = ttk.Frame(stats_grid)
            frame.grid(row=row, column=col, padx=10, pady=2, sticky="w")
            
            ttk.Label(frame, text=text).pack(side=tk.LEFT)
            self.stats_labels[key] = ttk.Label(frame, text="0", font=('Arial', 10, 'bold'))
            self.stats_labels[key].pack(side=tk.LEFT, padx=(5,0))
        
        # Результаты
        results_frame = ttk.LabelFrame(tab, text="Результаты сопоставления", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Создаем дерево результатов с поддержкой выбора
        columns = ("variant_name", "relevance", "price", "supplier", "brand", "category")
        self.results_tree = ttk.Treeview(results_frame, columns=columns, show="tree headings", height=15)
        
        # Настраиваем заголовки
        self.results_tree.heading("#0", text="Материал")
        self.results_tree.heading("variant_name", text="Вариант из прайс-листа")
        self.results_tree.heading("relevance", text="Релевантность")
        self.results_tree.heading("price", text="Цена")
        self.results_tree.heading("supplier", text="Поставщик")
        self.results_tree.heading("brand", text="Бренд")
        self.results_tree.heading("category", text="Категория")
        
        # Настраиваем ширину колонок
        self.results_tree.column("#0", width=200, minwidth=150)
        self.results_tree.column("variant_name", width=250, minwidth=200)
        self.results_tree.column("relevance", width=100, minwidth=80)
        self.results_tree.column("price", width=100, minwidth=80)
        self.results_tree.column("supplier", width=150, minwidth=100)
        self.results_tree.column("brand", width=100, minwidth=80)
        self.results_tree.column("category", width=120, minwidth=100)
        
        # Скроллбары для результатов
        results_v_scroll = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.results_tree.yview)
        results_h_scroll = ttk.Scrollbar(results_frame, orient=tk.HORIZONTAL, command=self.results_tree.xview)
        self.results_tree.configure(yscrollcommand=results_v_scroll.set, xscrollcommand=results_h_scroll.set)
        
        # Размещение результатов
        self.results_tree.grid(row=0, column=0, sticky="nsew")
        results_v_scroll.grid(row=0, column=1, sticky="ns")
        results_h_scroll.grid(row=1, column=0, sticky="ew")
        
        results_frame.grid_rowconfigure(0, weight=1)
        results_frame.grid_columnconfigure(0, weight=1)
        
        # Привязываем обработчики кликов для отладки
        # Используем умный обработчик кликов (определяет одинарные/двойные по времени)
        self.results_tree.bind("<Button-1>", self.on_smart_click)
        
        # Дополнительная отладочная информация
        self.log_message("🔧 Обработчики событий привязаны к дереву результатов")
        
        # Кнопки экспорта
        export_frame = ttk.Frame(tab)
        export_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(export_frame, text="📄 Экспорт всех результатов (JSON)", 
                  command=lambda: self.export_results("json")).pack(side=tk.LEFT, padx=5)
        ttk.Button(export_frame, text="📊 Экспорт всех результатов (CSV)", 
                  command=lambda: self.export_results("csv")).pack(side=tk.LEFT, padx=5)
        ttk.Button(export_frame, text="📋 Экспорт всех результатов (Excel)", 
                  command=lambda: self.export_results("xlsx")).pack(side=tk.LEFT, padx=5)
        
        # Разделитель
        ttk.Separator(export_frame, orient='vertical').pack(side=tk.LEFT, fill='y', padx=10)
        
        ttk.Button(export_frame, text="✅ Экспорт выбранных (Excel)", 
                  command=lambda: self.export_selected_results("xlsx")).pack(side=tk.LEFT, padx=5)
        ttk.Button(export_frame, text="🔄 Сбросить выборы", 
                  command=self.reset_selections).pack(side=tk.LEFT, padx=5)
        ttk.Button(export_frame, text="🔄 Обновить", 
                  command=self.refresh_results).pack(side=tk.RIGHT, padx=5)
    
    def create_search_tab(self):
        """Вкладка поиска"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="🔍 Поиск")
        
        # Поиск материала
        search_frame = ttk.LabelFrame(tab, text="Поиск материала", padding=10)
        search_frame.pack(fill=tk.X, padx=10, pady=5)
        
        search_row = ttk.Frame(search_frame)
        search_row.pack(fill=tk.X)
        
        ttk.Label(search_row, text="Название материала:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_row, textvariable=self.search_var, width=40)
        search_entry.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)
        search_entry.bind('<Return>', lambda e: self.search_material())
        
        ttk.Button(search_row, text="🔍 Найти", command=self.search_material).pack(side=tk.LEFT, padx=5)
        
        # Количество результатов
        results_row = ttk.Frame(search_frame)
        results_row.pack(fill=tk.X, pady=(5,0))
        
        ttk.Label(results_row, text="Показать результатов:").pack(side=tk.LEFT)
        self.search_limit_var = tk.IntVar(value=10)
        ttk.Spinbox(results_row, from_=1, to=50, width=10, 
                   textvariable=self.search_limit_var).pack(side=tk.LEFT, padx=10)
        
        # Результаты поиска
        search_results_frame = ttk.LabelFrame(tab, text="Результаты поиска", padding=10)
        search_results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Создаем дерево для результатов поиска
        search_columns = ("match_name", "similarity", "price", "supplier", "category")
        self.search_tree = ttk.Treeview(search_results_frame, columns=search_columns, 
                                       show="tree headings", height=15)
        
        # Настраиваем заголовки поиска
        self.search_tree.heading("#0", text="№")
        self.search_tree.heading("match_name", text="Найденный материал")
        self.search_tree.heading("similarity", text="Похожесть, %")
        self.search_tree.heading("price", text="Цена")
        self.search_tree.heading("supplier", text="Поставщик")
        self.search_tree.heading("category", text="Категория")
        
        # Настраиваем ширину колонок поиска
        self.search_tree.column("#0", width=50, minwidth=30)
        self.search_tree.column("match_name", width=250, minwidth=200)
        self.search_tree.column("similarity", width=100, minwidth=80)
        self.search_tree.column("price", width=100, minwidth=80)
        self.search_tree.column("supplier", width=150, minwidth=100)
        self.search_tree.column("category", width=120, minwidth=80)
        
        # Скроллбары для поиска
        search_v_scroll = ttk.Scrollbar(search_results_frame, orient=tk.VERTICAL, 
                                       command=self.search_tree.yview)
        search_h_scroll = ttk.Scrollbar(search_results_frame, orient=tk.HORIZONTAL, 
                                       command=self.search_tree.xview)
        self.search_tree.configure(yscrollcommand=search_v_scroll.set, 
                                  xscrollcommand=search_h_scroll.set)
        
        # Размещение поиска
        self.search_tree.grid(row=0, column=0, sticky="nsew")
        search_v_scroll.grid(row=0, column=1, sticky="ns")
        search_h_scroll.grid(row=1, column=0, sticky="ew")
        
        search_results_frame.grid_rowconfigure(0, weight=1)
        search_results_frame.grid_columnconfigure(0, weight=1)
    
    def create_status_bar(self):
        """Создание статусной панели"""
        self.status_frame = ttk.Frame(self.root)
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.status_var = tk.StringVar(value="Готов")
        self.status_label = ttk.Label(self.status_frame, textvariable=self.status_var)
        self.status_label.pack(side=tk.LEFT, padx=5)
        
        # Индикатор Elasticsearch
        self.es_indicator = ttk.Label(self.status_frame, text="●", foreground="red")
        self.es_indicator.pack(side=tk.RIGHT, padx=5)
        
        self.es_status_text = ttk.Label(self.status_frame, text="Elasticsearch: Не подключен")
        self.es_status_text.pack(side=tk.RIGHT, padx=5)
    
    def update_threshold_label(self, value):
        """Обновление метки порога похожести"""
        self.threshold_label.config(text=f"{float(value):.1f}%")
    
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
            self.es_indicator.config(foreground="green")
            self.es_status_text.config(text="Elasticsearch: Подключен")
            self.es_status_label.config(text="✅ Elasticsearch подключен успешно!", foreground="green")
            self.start_button.config(state="normal" if self.materials and self.price_items else "disabled")
        else:
            self.es_indicator.config(foreground="red")
            self.es_status_text.config(text="Elasticsearch: Не подключен")
            error_msg = f"❌ Elasticsearch недоступен"
            if error:
                error_msg += f": {error}"
            self.es_status_label.config(text=error_msg, foreground="red")
            self.start_button.config(state="disabled")
    
    def check_elasticsearch(self):
        """Проверка подключения к Elasticsearch"""
        self.status_var.set("Проверка подключения к Elasticsearch...")
        self.check_elasticsearch_status()
    
    def setup_indices(self):
        """Создание индексов Elasticsearch"""
        def create_indices():
            try:
                if self.app is None:
                    self.app = MaterialMatcherApp(self.config)
                
                self.root.after(0, lambda: self.status_var.set("Создание индексов..."))
                
                if self.app.setup_indices():
                    self.root.after(0, lambda: self.log_message("✅ Индексы созданы успешно!"))
                    self.root.after(0, lambda: self.status_var.set("Готов"))
                else:
                    self.root.after(0, lambda: self.log_message("❌ Ошибка создания индексов!"))
                    self.root.after(0, lambda: self.status_var.set("Ошибка"))
            except Exception as e:
                self.root.after(0, lambda: self.log_message(f"❌ Ошибка: {e}"))
                self.root.after(0, lambda: self.status_var.set("Ошибка"))
        
        threading.Thread(target=create_indices, daemon=True).start()
    
    # Методы для работы с файлами будут добавлены в следующей части...
    
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
    
    def load_materials_data(self):
        """Загрузка данных материалов"""
        if not self.materials_path_var.get():
            messagebox.showerror("Ошибка", "Выберите файл материалов")
            return
        
        def load():
            try:
                if self.app is None:
                    self.app = MaterialMatcherApp(self.config)
                
                self.root.after(0, lambda: self.status_var.set("Загрузка материалов..."))
                
                materials = self.app.load_materials(self.materials_path_var.get())
                if materials:
                    self.materials = materials
                    # Сохраняем исходный порядок материалов
                    self.materials_order = [material.id for material in materials]
                    self.root.after(0, lambda: self.update_materials_info(len(materials)))
                    self.root.after(0, lambda: self.update_materials_preview(materials))
                    self.root.after(0, lambda: self.status_var.set("Готов"))
                    self.root.after(0, self.update_start_button_state)
                else:
                    self.root.after(0, lambda: messagebox.showerror("Ошибка", "Не удалось загрузить материалы"))
                    self.root.after(0, lambda: self.status_var.set("Ошибка"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Ошибка загрузки материалов: {e}"))
                self.root.after(0, lambda: self.status_var.set("Ошибка"))
        
        threading.Thread(target=load, daemon=True).start()
    
    def load_pricelist_data(self):
        """Загрузка данных прайс-листа"""
        if not self.pricelist_path_var.get():
            messagebox.showerror("Ошибка", "Выберите файл прайс-листа")
            return
        
        def load():
            try:
                if self.app is None:
                    self.app = MaterialMatcherApp(self.config)
                
                self.root.after(0, lambda: self.status_var.set("Загрузка прайс-листа..."))
                
                price_items = self.app.load_price_list(self.pricelist_path_var.get())
                if price_items:
                    self.price_items = price_items
                    self.root.after(0, lambda: self.update_pricelist_info(len(price_items)))
                    self.root.after(0, lambda: self.update_pricelist_preview(price_items))
                    self.root.after(0, lambda: self.status_var.set("Готов"))
                    self.root.after(0, self.update_start_button_state)
                else:
                    self.root.after(0, lambda: messagebox.showerror("Ошибка", "Не удалось загрузить прайс-лист"))
                    self.root.after(0, lambda: self.status_var.set("Ошибка"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Ошибка загрузки прайс-листа: {e}"))
                self.root.after(0, lambda: self.status_var.set("Ошибка"))
        
        threading.Thread(target=load, daemon=True).start()
    
    # Остальные методы будут добавлены...
    
    def log_message(self, message):
        """Добавление сообщения в лог"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
    
    def new_project(self):
        """Создание нового проекта"""
        if messagebox.askyesno("Новый проект", "Очистить все данные и начать новый проект?"):
            self.clear_data()
            self.results = {}
            self.refresh_results()
            self.log_message("🔄 Создан новый проект")
    
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
    
    def update_materials_info(self, count):
        """Обновление информации о материалах"""
        self.materials_info_label.config(text=f"Загружено {count} материалов", foreground="green")
    
    def update_pricelist_info(self, count):
        """Обновление информации о прайс-листе"""
        self.pricelist_info_label.config(text=f"Загружено {count} позиций", foreground="green")
    
    def update_materials_preview(self, materials):
        """Обновление предварительного просмотра материалов"""
        # Очищаем дерево
        for item in self.materials_tree.get_children():
            self.materials_tree.delete(item)
        
        # Настраиваем колонки
        columns = ("name", "category", "brand", "description")
        self.materials_tree["columns"] = columns
        self.materials_tree["show"] = "headings"
        
        # Заголовки
        self.materials_tree.heading("name", text="Название")
        self.materials_tree.heading("category", text="Категория")
        self.materials_tree.heading("brand", text="Бренд")
        self.materials_tree.heading("description", text="Описание")
        
        # Ширина колонок
        self.materials_tree.column("name", width=200, minwidth=150)
        self.materials_tree.column("category", width=120, minwidth=80)
        self.materials_tree.column("brand", width=120, minwidth=80)
        self.materials_tree.column("description", width=300, minwidth=200)
        
        # Добавляем первые 100 материалов для предпросмотра
        for material in materials[:100]:
            desc = material.description[:100] + "..." if len(material.description) > 100 else material.description
            self.materials_tree.insert("", tk.END, values=(
                material.name,
                material.category or "",
                material.brand or "",
                desc
            ))
        
        if len(materials) > 100:
            self.materials_tree.insert("", tk.END, values=(
                f"... и еще {len(materials) - 100} материалов",
                "", "", ""
            ))
    
    def update_pricelist_preview(self, price_items):
        """Обновление предварительного просмотра прайс-листа"""
        # Очищаем дерево
        for item in self.pricelist_tree.get_children():
            self.pricelist_tree.delete(item)
        
        # Настраиваем колонки
        columns = ("name", "price", "supplier", "category", "description")
        self.pricelist_tree["columns"] = columns
        self.pricelist_tree["show"] = "headings"
        
        # Заголовки
        self.pricelist_tree.heading("name", text="Материал")
        self.pricelist_tree.heading("price", text="Цена")
        self.pricelist_tree.heading("supplier", text="Поставщик")
        self.pricelist_tree.heading("category", text="Категория")
        self.pricelist_tree.heading("description", text="Описание")
        
        # Ширина колонок
        self.pricelist_tree.column("name", width=200, minwidth=150)
        self.pricelist_tree.column("price", width=100, minwidth=80)
        self.pricelist_tree.column("supplier", width=150, minwidth=100)
        self.pricelist_tree.column("category", width=120, minwidth=80)
        self.pricelist_tree.column("description", width=250, minwidth=200)
        
        # Добавляем первые 100 позиций для предпросмотра
        for item in price_items[:100]:
            desc = item.description[:100] + "..." if len(item.description) > 100 else item.description
            price_str = f"{item.price} {item.currency}" if item.price else "Не указана"
            self.pricelist_tree.insert("", tk.END, values=(
                item.material_name,
                price_str,
                item.supplier or "",
                item.category or "",
                desc
            ))
        
        if len(price_items) > 100:
            self.pricelist_tree.insert("", tk.END, values=(
                f"... и еще {len(price_items) - 100} позиций",
                "", "", "", ""
            ))
    
    def update_start_button_state(self):
        """Обновление состояния кнопки запуска"""
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
    
    def index_data(self):
        """Индексация данных"""
        if not self.materials and not self.price_items:
            messagebox.showwarning("Предупреждение", "Нет данных для индексации")
            return
        
        def index():
            try:
                if self.app is None:
                    self.app = MaterialMatcherApp(self.config)
                
                self.root.after(0, lambda: self.status_var.set("Индексация данных..."))
                self.root.after(0, lambda: self.log_message("🔄 Начинаем индексацию данных..."))
                
                if self.app.index_data(self.materials, self.price_items):
                    self.root.after(0, lambda: self.log_message("✅ Данные успешно проиндексированы!"))
                    self.root.after(0, lambda: self.status_var.set("Готов"))
                    self.root.after(0, self.update_start_button_state)
                else:
                    self.root.after(0, lambda: self.log_message("❌ Ошибка индексации данных!"))
                    self.root.after(0, lambda: self.status_var.set("Ошибка"))
            except Exception as e:
                self.root.after(0, lambda: self.log_message(f"❌ Ошибка индексации: {e}"))
                self.root.after(0, lambda: self.status_var.set("Ошибка"))
        
        threading.Thread(target=index, daemon=True).start()
    
    def clear_data(self):
        """Очистка данных"""
        self.materials = []
        self.materials_order = []
        self.price_items = []
        self.results = {}
        self.selected_variants = {}
        
        # Очищаем интерфейс
        self.materials_path_var.set("")
        self.pricelist_path_var.set("")
        self.materials_info_label.config(text="Материалы не загружены", foreground="red")
        self.pricelist_info_label.config(text="Прайс-лист не загружен", foreground="red")
        
        # Очищаем предпросмотр
        for item in self.materials_tree.get_children():
            self.materials_tree.delete(item)
        for item in self.pricelist_tree.get_children():
            self.pricelist_tree.delete(item)
        
        # Очищаем результаты
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        
        # Обнуляем статистику
        for key in self.stats_labels:
            self.stats_labels[key].config(text="0")
        
        self.start_button.config(state="disabled")
        self.log_message("🧹 Данные очищены")
    
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
                self.root.after(0, lambda: self.progress_bar.start(10))
                self.root.after(0, lambda: self.progress_var.set("Запуск сопоставления..."))
                self.root.after(0, lambda: self.status_var.set("Выполняется сопоставление..."))
                self.root.after(0, lambda: self.log_message("🚀 Начинаем сопоставление материалов..."))
                
                # Запускаем сопоставление
                results = self.app.run_matching(self.materials)
                
                if not self.matching_cancelled:
                    self.results = results
                    self.root.after(0, lambda: self.update_results_display())
                    self.root.after(0, lambda: self.log_message("✅ Сопоставление завершено успешно!"))
                    self.root.after(0, lambda: self.notebook.select(3))  # Переходим к результатам
                else:
                    self.root.after(0, lambda: self.log_message("⏹ Сопоставление отменено пользователем"))
                
            except Exception as e:
                self.root.after(0, lambda: self.log_message(f"❌ Ошибка сопоставления: {e}"))
            finally:
                # Восстанавливаем UI
                self.root.after(0, lambda: self.start_button.config(state="normal"))
                self.root.after(0, lambda: self.stop_button.config(state="disabled"))
                self.root.after(0, lambda: self.progress_bar.stop())
                self.root.after(0, lambda: self.progress_var.set("Готов к запуску"))
                self.root.after(0, lambda: self.status_var.set("Готов"))
        
        threading.Thread(target=matching, daemon=True).start()
    
    def stop_matching(self):
        """Остановка сопоставления"""
        self.matching_cancelled = True
        self.stop_button.config(state="disabled")
        self.log_message("⏹ Останавливаем сопоставление...")
    
    def update_results_display(self):
        """Обновление отображения результатов с топ-7 вариантами"""
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
                
                # Автоматически раскрываем первые 5 материалов
                if formatted_results.index(result) < 5:
                    self.results_tree.item(parent, open=True)
        
        # Настраиваем цветовые теги
        self.results_tree.tag_configure("material", font=('Arial', 10, 'bold'))
        self.results_tree.tag_configure("high", foreground="darkgreen")
        self.results_tree.tag_configure("medium", foreground="darkorange")
        self.results_tree.tag_configure("low", foreground="darkred")
        
        # Обработчик двойного клика уже привязан выше через on_smart_click
    
    def on_variant_select(self, event):
        """Обработка выбора варианта"""
        selection = self.results_tree.selection()
        if selection:
            item = self.results_tree.item(selection[0])
            tags = item.get('tags', [])
            
            # Проверяем, что выбран вариант, а не материал
            for tag in tags:
                if tag.startswith('variant_'):
                    parts = tag.split('_')
                    if len(parts) >= 3:
                        material_id = parts[1]
                        variant_id = parts[2]
                        
                        # Используем форматтер для выбора варианта
                        if hasattr(self, 'formatter'):
                            result = self.formatter.select_variant(material_id, variant_id)
                            if 'error' not in result:
                                self.log_message(f"✅ Выбран вариант {variant_id} для материала {material_id}")
                                # Обновляем визуальное выделение
                                self.highlight_selected_variant(selection[0])
                            else:
                                self.log_message(f"❌ Ошибка выбора: {result['error']}")
    
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
        self.results_tree.tag_configure('selected', background='lightblue', font=('Arial', 10, 'bold'))
    
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
                self.log_message("🔥 ДВОЙНОЙ КЛИК ОБНАРУЖЕН! (определен по времени)")
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
                
                self.log_message(f"🖱️ Одинарный клик: элемент={item}, колонка={column}, регион={region}")
                self.log_message(f"   Родитель: {parent}, Текст: '{item_text}', Теги: {item_tags}")
                if item_values:
                    self.log_message(f"   Значения: {item_values}")
                    
        except Exception as e:
            self.log_message(f"❌ Ошибка в обработке клика: {e}")
    
    def handle_double_click(self, event, item):
        """Обработка двойного клика по варианту из прайс-листа"""
        try:
            # Получаем колонку, по которой кликнули
            column = self.results_tree.identify('column', event.x, event.y)
            
            if not item:
                self.log_message("❌ Не удалось определить элемент для клика")
                return
            
            # Проверяем, что кликнули по варианту (дочерний элемент), а не по материалу
            parent = self.results_tree.parent(item)
            if not parent:  # Кликнули по материалу, а не по варианту
                self.log_message("ℹ️ Клик по материалу (не по варианту)")
                return
            
            # Дополнительная отладочная информация
            self.log_message(f"🔍 Двойной клик: элемент={item}, колонка={column}, родитель={parent}")
        except Exception as e:
            self.log_message(f"❌ Ошибка при обработке клика: {e}")
            return
        
        # Получаем теги элемента для определения material_id и variant_id
        tags = self.results_tree.item(item, 'tags')
        self.log_message(f"🏷️ Теги элемента: {tags}")
        
        variant_tag = None
        for tag in tags:
            if tag.startswith('variant_'):
                variant_tag = tag
                break
        
        if not variant_tag:
            self.log_message(f"❌ Не найден тег варианта в {tags}")
            return
        
        self.log_message(f"✅ Найден тег варианта: {variant_tag}")
        
        # Извлекаем material_id из тега (формат: variant_material_id_variant_id)
        try:
            parts = variant_tag.split('_')
            if len(parts) < 3:
                self.log_message(f"❌ Неверный формат тега: {variant_tag}")
                return
            
            material_id = parts[1]
            variant_id = parts[2]
            
            self.log_message(f"📋 Material ID: {material_id}, Variant ID: {variant_id}")
            
            # Получаем данные выбранного варианта
            values = self.results_tree.item(item, 'values')
            if not values:
                self.log_message(f"❌ Нет значений для элемента {item}")
                return
                
            self.log_message(f"📊 Значения варианта: {values}")
        except Exception as e:
            self.log_message(f"❌ Ошибка при извлечении данных: {e}")
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
        self.update_selected_variant_display(parent, item, variant_name)
        
        # Затем скрываем все остальные варианты для этого материала
        self.hide_other_variants(parent, None)  # None так как selected_item уже удален
        
        # Логируем действие
        material_name = self.results_tree.item(parent, 'text')
        self.log_message(f"✅ Выбран вариант для '{material_name}': {variant_name}")
    
    def hide_other_variants(self, parent_item, selected_item):
        """Скрывает все варианты кроме выбранного"""
        children = list(self.results_tree.get_children(parent_item))
        for child in children:
            if child != selected_item:
                self.results_tree.delete(child)
        
        self.log_message(f"🗑️ Скрыто {len(children)} вариантов для материала")
    
    def update_selected_variant_display(self, parent_item, selected_item, variant_name):
        """Поднимает выбранный вариант на уровень материала в одну строку"""
        # Получаем данные выбранного варианта
        selected_values = self.results_tree.item(selected_item, 'values')
        material_name = self.results_tree.item(parent_item, 'text')
        
        # Обновляем родительский элемент (материал) - добавляем данные варианта
        updated_text = f"{material_name} ➤ {variant_name}"
        
        # Переносим данные варианта на уровень материала
        self.results_tree.item(parent_item, 
                              text=updated_text,
                              values=selected_values)  # Показываем данные варианта в строке материала
        
        # Удаляем дочерний элемент (вариант), так как он теперь на уровне материала
        self.results_tree.delete(selected_item)
        
        # Стилизуем строку материала с выбранным вариантом
        parent_tags = list(self.results_tree.item(parent_item, 'tags'))
        if 'material_with_selection' not in parent_tags:
            parent_tags.append('material_with_selection')
        self.results_tree.item(parent_item, tags=parent_tags)
        
        # Настраиваем стиль для материала с выбранным вариантом
        self.results_tree.tag_configure('material_with_selection', 
                                       background='lightgreen',
                                       font=('Arial', 11, 'bold'),
                                       foreground='darkgreen')
        
        self.log_message(f"📍 Вариант '{variant_name}' поднят на уровень материала")
    
    def refresh_results(self):
        """Обновление результатов"""
        if self.results:
            self.update_results_display()
            self.log_message("🔄 Результаты обновлены")
        else:
            self.log_message("ℹ️ Нет результатов для обновления")
    
    def reset_selections(self):
        """Сброс всех выборов"""
        if not self.selected_variants:
            self.log_message("ℹ️ Нет выборов для сброса")
            return
        
        # Очищаем выборы
        self.selected_variants.clear()
        
        # Обновляем отображение результатов
        self.update_results_display()
        
        self.log_message("🔄 Все выборы сброшены")
    
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
                    self.root.after(0, lambda: self.status_var.set("Экспорт выбранных результатов..."))
                    
                    # Используем основное приложение для экспорта
                    if self.app is None:
                        self.app = MaterialMatcherApp(self.config)
                    
                    # Экспортируем выбранные результаты
                    from src.utils.data_loader import DataExporter
                    DataExporter.export_results_to_xlsx(selected_data, filename)
                    
                    self.root.after(0, lambda: self.log_message(f"✅ Выбранные результаты экспортированы в {filename}"))
                    self.root.after(0, lambda: self.status_var.set("Готов"))
                    self.root.after(0, lambda: messagebox.showinfo("Экспорт", f"Выбранные результаты сохранены в файл:\n{filename}"))
                    
                except Exception as e:
                    self.root.after(0, lambda: self.log_message(f"❌ Ошибка экспорта выбранных: {e}"))
                    self.root.after(0, lambda: self.status_var.set("Ошибка"))
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
                    self.root.after(0, lambda: self.status_var.set(f"Экспорт в {format_type.upper()}..."))
                    
                    # Используем новый форматтер для экспорта
                    if hasattr(self, 'formatter'):
                        # Экспортируем в новом формате JSON
                        success = self.formatter.export_to_json(
                            filename, 
                            include_unselected=True,
                            pretty=True
                        )
                        if success:
                            self.root.after(0, lambda: self.log_message(f"✅ Результаты экспортированы в {filename}"))
                            self.root.after(0, lambda: self.status_var.set("Готов"))
                            self.root.after(0, lambda: messagebox.showinfo("Экспорт", f"Результаты сохранены в файл:\n{filename}"))
                        else:
                            raise Exception("Не удалось сохранить файл")
                    else:
                        # Fallback на старый метод
                        if self.app is None:
                            self.app = MaterialMatcherApp(self.config)
                        self.app.export_results(self.results, filename, format_type)
                        self.root.after(0, lambda: self.log_message(f"✅ Результаты экспортированы в {filename}"))
                        self.root.after(0, lambda: self.status_var.set("Готов"))
                        self.root.after(0, lambda: messagebox.showinfo("Экспорт", f"Результаты сохранены в файл:\n{filename}"))
                        
                except Exception as e:
                    self.root.after(0, lambda: self.log_message(f"❌ Ошибка экспорта: {e}"))
                    self.root.after(0, lambda: self.status_var.set("Ошибка"))
                    self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Ошибка экспорта: {e}"))
            
            threading.Thread(target=export, daemon=True).start()
    
    def search_material(self):
        """Поиск материала"""
        query = self.search_var.get().strip()
        if not query:
            messagebox.showwarning("Предупреждение", "Введите название материала для поиска")
            return
        
        def search():
            try:
                if self.app is None:
                    self.app = MaterialMatcherApp(self.config)
                
                self.root.after(0, lambda: self.status_var.set("Поиск материала..."))
                
                # Используем метод поиска по названию
                matches = self.app.search_material_by_name(query, top_n=self.search_limit_var.get())
                
                self.root.after(0, lambda: self.update_search_results(query, matches))
                self.root.after(0, lambda: self.status_var.set("Готов"))
                
            except Exception as e:
                self.root.after(0, lambda: self.log_message(f"❌ Ошибка поиска: {e}"))
                self.root.after(0, lambda: self.status_var.set("Ошибка"))
        
        threading.Thread(target=search, daemon=True).start()
    
    def update_search_results(self, query, matches):
        """Обновление результатов поиска"""
        # Очищаем дерево результатов поиска
        for item in self.search_tree.get_children():
            self.search_tree.delete(item)
        
        if matches:
            self.log_message(f"🔍 Найдено {len(matches)} соответствий для '{query}'")
            
            for i, match in enumerate(matches, 1):
                price_str = f"{match['price_item']['price']} {match['price_item']['currency']}" if match['price_item']['price'] else "Не указана"
                
                self.search_tree.insert("", tk.END, text=str(i), values=(
                    match['price_item']['material_name'],
                    f"{match['similarity_percentage']:.1f}%",
                    price_str,
                    match['price_item']['supplier'] or "",
                    match['price_item']['category'] or ""
                ))
        else:
            self.log_message(f"❌ Соответствий для '{query}' не найдено")
            self.search_tree.insert("", tk.END, text="", values=(
                "Соответствия не найдены", "", "", "", ""
            ))


def main():
    """Запуск GUI приложения"""
    root = tk.Tk()
    app = MaterialMatcherGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()