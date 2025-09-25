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
from src.utils.debug_logger import get_debug_logger, init_debug_logging
from src.ui.modern_table_view import ModernTableView
from src.services.etm_api_service import get_etm_service


class MaterialMatcherGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Система сопоставления материалов - Material Matcher")
        self.root.geometry("1000x700")
        self.root.minsize(800, 600)
        
        # Стилизация
        style = ttk.Style()
        style.theme_use('clam')
        
        # Настраиваем цветовые теги для Treeview
        # Сохраняем ссылку на стиль для дальнейшего использования
        self.style = style
        
        # Переменные
        self.app = None
        self.config = self.load_config()
        self.materials = []
        self.materials_order = []  # Сохраняем исходный порядок материалов
        self.price_items = []
        self.results = {}
        self.selected_variants = {}  # Выбранные варианты для каждого материала {material_id: selected_match}
        self.selected_pricelist_files = []  # Список выбранных файлов прайс-листов
        
        # Используется только древовидный режим просмотра результатов
        self.view_mode = "tree"  # Добавляем недостающий атрибут

        # Переменные для обнаружения двойного клика
        self.last_click_time = 0
        self.last_click_item = None
        self.double_click_delay = 500  # мсек
        
        # Инициализируем систему отладочного логирования
        init_debug_logging(log_level="INFO")
        self.debug_logger = get_debug_logger()
        
        # Создаем интерфейс
        self.create_widgets()
        self.check_elasticsearch_status()
        
        # Автоматически загружаем файлы при запуске
        self.root.after(1000, self.auto_load_on_startup)  # Задержка для инициализации GUI
        
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
                "max_results_per_material": 4,
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
        tools_menu.add_separator()
        tools_menu.add_command(label="📋 Копировать логи отладки", command=self.copy_debug_logs)
        tools_menu.add_command(label="📄 Показать окно логов", command=self.show_debug_logs_window)
        
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
        
        # Главная вкладка (объединенные загрузка и сопоставление)
        self.create_main_tab()
        
        # Вкладка "Результаты"
        self.create_results_tab()
        
        # Статусная панель
        self.create_status_bar()
    
    
    def create_main_tab(self):
        """Главная вкладка - загрузка данных и сопоставление"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="📁 Загрузка и сопоставление")
        
        # === СЕКЦИЯ ЗАГРУЗКИ ДАННЫХ ===
        
        # Материалы
        materials_frame = ttk.LabelFrame(tab, text="Файл материалов", padding=10)
        materials_frame.pack(fill=tk.X, padx=10, pady=2)
        
        materials_row = ttk.Frame(materials_frame)
        materials_row.pack(fill=tk.X)
        
        self.materials_path_var = tk.StringVar()
        ttk.Button(materials_row, text="📁 Выбрать и загрузить материалы",
                  command=self.load_materials_file, width=30).pack(side=tk.LEFT, padx=5)
        
        self.materials_info_label = ttk.Label(materials_row, text="Материалы не загружены", 
                                             foreground="red")
        self.materials_info_label.pack(side=tk.LEFT, padx=(10,0))
        
        # Прайс-лист
        pricelist_frame = ttk.LabelFrame(tab, text="Файл прайс-листа", padding=10)
        pricelist_frame.pack(fill=tk.X, padx=10, pady=2)
        
        pricelist_row = ttk.Frame(pricelist_frame)
        pricelist_row.pack(fill=tk.X)
        
        self.pricelist_path_var = tk.StringVar()
        ttk.Button(pricelist_row, text="📄 Выбрать прайс-листы (можно несколько)",
                  command=self.load_pricelist_file, width=35).pack(side=tk.LEFT, padx=5)
        
        self.pricelist_info_label = ttk.Label(pricelist_row, text="Прайс-лист не загружен", 
                                             foreground="red")
        self.pricelist_info_label.pack(side=tk.LEFT, padx=(10,0))
        
        
        # Кнопки действий загрузки
        actions_frame = ttk.Frame(tab)
        actions_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(actions_frame, text="Индексировать данные", 
                  command=self.index_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(actions_frame, text="Очистить данные", 
                  command=self.clear_data).pack(side=tk.LEFT, padx=5)
        
        # === СЕКЦИЯ СОПОСТАВЛЕНИЯ ===
        
        # Скрытые параметры (используем значения по умолчанию из конфига)
        self.threshold_var = tk.DoubleVar(value=self.config['matching']['similarity_threshold'])
        self.max_results_var = tk.IntVar(value=self.config['matching']['max_results_per_material'])
        self.workers_var = tk.IntVar(value=self.config['matching']['max_workers'])
        
        # Кнопки управления сопоставлением
        control_frame = ttk.Frame(tab)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.start_button = ttk.Button(control_frame, text="[START] Запустить сопоставление", 
                                      command=self.run_full_matching, state="disabled")
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(control_frame, text="[STOP] Остановить", 
                                     command=self.stop_matching, state="disabled")
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        # Прогресс
        progress_frame = ttk.LabelFrame(tab, text="Прогресс выполнения", padding=10)
        progress_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.progress_var = tk.StringVar(value="Готов к запуску")
        ttk.Label(progress_frame, textvariable=self.progress_var).pack(anchor=tk.W)
        
        self.progress_bar = ttk.Progressbar(progress_frame, mode='determinate')
        self.progress_bar.pack(fill=tk.X, pady=5)
        
        # Лог выполнения
        log_frame = ttk.LabelFrame(tab, text="Журнал выполнения", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Кнопки для управления логом
        log_buttons_frame = ttk.Frame(log_frame)
        log_buttons_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(log_buttons_frame, text="📋 Копировать весь лог", 
                  command=self.copy_log_to_clipboard).pack(side=tk.LEFT, padx=5)
        ttk.Button(log_buttons_frame, text="🗑️ Очистить лог", 
                  command=self.clear_log).pack(side=tk.LEFT, padx=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=8, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)
    
    def create_results_tab(self):
        """Вкладка результатов"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="📊 Результаты")
        
        # Результаты
        results_frame = ttk.LabelFrame(tab, text="Результаты сопоставления", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Переключатель режимов просмотра
        view_controls_frame = ttk.Frame(results_frame)
        view_controls_frame.pack(fill=tk.X, pady=(0, 10))

        # Кнопки управления
        auto_select_btn = ttk.Button(view_controls_frame, text="🎯 Автовыбор",
                                   command=self.auto_select_all_variants)
        auto_select_btn.pack(side=tk.LEFT, padx=(0, 10))

        expand_all_btn = ttk.Button(view_controls_frame, text="📂 Раскрыть все",
                                  command=self.expand_all_materials)
        expand_all_btn.pack(side=tk.LEFT, padx=(0, 10))

        update_prices_btn = ttk.Button(view_controls_frame, text="💰 Обновить цены ETM",
                                     command=self.update_etm_prices)
        update_prices_btn.pack(side=tk.LEFT)
        
        # Контейнер для результатов
        self.results_container = ttk.Frame(results_frame)
        self.results_container.pack(fill=tk.BOTH, expand=True)
        
        # Создаем дерево результатов с поддержкой выбора
        # Добавляем столбцы материалов (голубые) и прайс-листа (розовые)
        columns = ("material_code", "material_manufacturer",
                  "variant_name", "price_article", "price_brand", "relevance",
                  "etm_code", "price")
        
        # Настраиваем Excel-like стиль для Treeview
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Excel.Treeview",
                       background="white",
                       fieldbackground="white",
                       bordercolor="black",
                       borderwidth=1,
                       relief="solid",
                       font=('Segoe UI', 9))
        style.configure("Excel.Treeview.Heading",
                       background="#E0E0E0",
                       bordercolor="black",
                       borderwidth=1,
                       relief="solid",
                       font=('Segoe UI', 9, 'bold'),
                       foreground="black")

        # Настраиваем стили для выделения строк
        style.map("Excel.Treeview",
                 background=[('selected', '#4A90E2')],
                 foreground=[('selected', 'white')])

        # Дополнительные стили для выделения выбранных вариантов
        style.configure("Excel.Treeview.Item",
                       background="white",
                       foreground="black")
        style.configure("Excel.Treeview.Selected",
                       background="#E6FFE6",
                       foreground="darkgreen",
                       font=('Segoe UI', 9, 'bold'))
        style.configure("Excel.Treeview.MaterialWithSelection",
                       background="#E6F3FF",
                       foreground="darkblue",
                       font=('Segoe UI', 9, 'bold'))
        
        self.results_tree = ttk.Treeview(self.results_container, columns=columns, show="tree headings", height=15, style="Excel.Treeview")
        
        # Настраиваем профессиональные заголовки (Excel-style)
        self.results_tree.heading("#0", text="Наименование материала")
        # Материал (источник)
        self.results_tree.heading("material_code", text="Код обор.")
        self.results_tree.heading("material_manufacturer", text="Изготовитель")
        # Прайс-лист (найденные варианты)
        self.results_tree.heading("variant_name", text="Название (прайс)")
        self.results_tree.heading("price_article", text="Артикул")
        self.results_tree.heading("price_brand", text="Бренд")
        self.results_tree.heading("relevance", text="Релевантность %")
        # Коммерческая информация
        self.results_tree.heading("etm_code", text="КОД ETM")
        self.results_tree.heading("price", text="Цена")
        
        # Настраиваем ширину колонок (Excel-style)
        self.results_tree.column("#0", width=280, minwidth=220, anchor="w")  # Наименования материала (увеличено)
        # Материал (источник)
        self.results_tree.column("material_code", width=100, minwidth=80, anchor="center")
        self.results_tree.column("material_manufacturer", width=130, minwidth=100, anchor="w")
        # Прайс-лист (найденные варианты)
        self.results_tree.column("variant_name", width=220, minwidth=180, anchor="w")
        self.results_tree.column("price_article", width=130, minwidth=100, anchor="center")
        self.results_tree.column("price_brand", width=110, minwidth=90, anchor="w")
        self.results_tree.column("relevance", width=90, minwidth=70, anchor="center")
        # Коммерческая информация
        self.results_tree.column("etm_code", width=100, minwidth=80, anchor="center")
        self.results_tree.column("price", width=110, minwidth=90, anchor="e")
        
        # Настраиваем Excel-like цветовые теги
        self.results_tree.tag_configure("material_columns",
                                       background="#F0F8FF",  # Светло-голубой для материалов (более приглушенный)
                                       font=('Segoe UI', 9))
        self.results_tree.tag_configure("price_columns",
                                       background="#FFF8F0",  # Светло-персиковый для прайс-листа (более приглушенный)
                                       font=('Segoe UI', 9))
        self.results_tree.tag_configure("selected_variant",
                                       background="#E6FFE6",
                                       foreground="#006400",  # Темно-зеленый для выбранных
                                       font=('Segoe UI', 9, 'bold'))
        self.results_tree.tag_configure("material_with_selection",
                                       background="#E6F3FF",
                                       foreground="#003D82",  # Темно-синий для материалов с выбором
                                       font=('Segoe UI', 9, 'bold'))

        # Настраиваем теги для релевантности (Excel-like цвета)
        self.results_tree.tag_configure("high",
                                       background="#E6F7E6",  # Светло-зеленый фон
                                       foreground="#006400",  # Темно-зеленый текст
                                       font=('Segoe UI', 9, 'bold'))
        self.results_tree.tag_configure("medium",
                                       background="#FFF8E1",  # Светло-желтый фон
                                       foreground="#FF8C00",  # Темно-оранжевый текст
                                       font=('Segoe UI', 9))
        self.results_tree.tag_configure("low",
                                       background="#FFE6E6",  # Светло-красный фон
                                       foreground="#B22222",  # Темно-красный текст
                                       font=('Segoe UI', 9))
        
        # Скроллбары для результатов
        results_v_scroll = ttk.Scrollbar(self.results_container, orient=tk.VERTICAL, command=self.results_tree.yview)
        results_h_scroll = ttk.Scrollbar(self.results_container, orient=tk.HORIZONTAL, command=self.results_tree.xview)
        self.results_tree.configure(yscrollcommand=results_v_scroll.set, xscrollcommand=results_h_scroll.set)
        
        # Размещение результатов
        self.results_tree.grid(row=0, column=0, sticky="nsew")
        results_v_scroll.grid(row=0, column=1, sticky="ns")
        results_h_scroll.grid(row=1, column=0, sticky="ew")
        
        # Конфигурация сетки контейнера результатов
        self.results_container.grid_rowconfigure(0, weight=1)
        self.results_container.grid_columnconfigure(0, weight=1)
        
        # Убираем создание табличного вида - используется только древовидный режим
        
        # Привязываем обработчики кликов для отладки
        # Используем умный обработчик кликов (определяет одинарные/двойные по времени)
        self.results_tree.bind("<Button-1>", self.on_smart_click)
        
        # Дополнительная отладочная информация
        self.log_message("🔧 Обработчики событий привязаны к дереву результатов")
        
    
    
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
            self.start_button.config(state="normal" if self.materials and self.price_items else "disabled")
        else:
            self.es_indicator.config(foreground="red")
            self.es_status_text.config(text="Elasticsearch: Не подключен")
            error_msg = f"[ERROR] Elasticsearch недоступен"
            if error:
                error_msg += f": {error}"
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
                    self.root.after(0, lambda: self.log_message("[OK] Индексы созданы успешно!"))
                    self.root.after(0, lambda: self.status_var.set("Готов"))
                else:
                    self.root.after(0, lambda: self.log_message("[ERROR] Ошибка создания индексов!"))
                    self.root.after(0, lambda: self.status_var.set("Ошибка"))
            except Exception as e:
                self.root.after(0, lambda: self.log_message(f"[ERROR] Ошибка: {e}"))
                self.root.after(0, lambda: self.status_var.set("Ошибка"))
        
        threading.Thread(target=create_indices, daemon=True).start()
    
    # Методы для работы с файлами будут добавлены в следующей части...
    
    def load_materials_file(self):
        """Выбор файла материалов"""
        filename = filedialog.askopenfilename(
            parent=self.root,
            title="Выберите файл материалов",
            initialdir=os.getcwd(),
            filetypes=[
                ("Все поддерживаемые", "*.csv;*.xlsx;*.json"),
                ("CSV файлы", "*.csv"),
                ("Excel файлы", "*.xlsx"),
                ("JSON файлы", "*.json"),
                ("Все файлы", "*.*")
            ]
        )
        if filename:
            # Сбрасываем предыдущие данные
            self.materials = []
            self.materials_order = []
            self.results = {}
            self.selected_variants = {}

            # Очищаем результаты в интерфейсе
            if hasattr(self, 'results_tree') and self.results_tree:
                for item in self.results_tree.get_children():
                    self.results_tree.delete(item)

            # Сбрасываем статус материалов (но оставляем прайс-лист как есть)
            self.materials_info_label.config(text="Материалы не загружены", foreground="red")

            self.materials_path_var.set(filename)
            self.log_message(f"[INFO] Сброшены предыдущие данные, выбран новый файл: {os.path.basename(filename)}")

            # Запускаем загрузку выбранного файла
            threading.Thread(target=self.load_materials_data, daemon=True).start()
    
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
        
        # Устанавливаем путь к первому файлу (для совместимости)
        self.materials_path_var.set(material_files[0])
        self.load_materials_from_directory(materials_dir)  # Загружаем из всей папки
    
    def load_pricelist_file(self):
        """Выбор файлов прайс-листа (поддержка множественного выбора)"""
        filenames = filedialog.askopenfilenames(
            parent=self.root,
            title="Выберите файлы прайс-листа (можно выбрать несколько)",
            initialdir=os.getcwd(),
            filetypes=[
                ("Все поддерживаемые", "*.csv;*.xlsx;*.json"),
                ("CSV файлы", "*.csv"),
                ("Excel файлы", "*.xlsx"),
                ("JSON файлы", "*.json"),
                ("Все файлы", "*.*")
            ]
        )
        if filenames:
            # Сбрасываем предыдущие данные прайс-листа
            self.price_items = []
            self.results = {}
            self.selected_variants = {}

            # Очищаем результаты в интерфейсе
            if hasattr(self, 'results_tree') and self.results_tree:
                for item in self.results_tree.get_children():
                    self.results_tree.delete(item)

            # Сбрасываем статус прайс-листа
            self.pricelist_info_label.config(text="Прайс-лист не загружен", foreground="red")

            # Сохраняем все выбранные файлы (для совместимости используем первый файл в pricelist_path_var)
            self.pricelist_path_var.set(filenames[0])
            self.selected_pricelist_files = list(filenames)  # Сохраняем все файлы

            file_count = len(filenames)
            file_names = ", ".join([os.path.basename(f) for f in filenames])
            self.log_message(f"[INFO] Сброшены предыдущие данные, выбрано файлов прайс-листа: {file_count}")
            self.log_message(f"[INFO] Файлы: {file_names}")

            # Запускаем загрузку всех выбранных файлов
            threading.Thread(target=self.load_multiple_pricelist_files, daemon=True).start()

    def load_multiple_pricelist_files(self):
        """Загрузка нескольких файлов прайс-листа"""
        if not hasattr(self, 'selected_pricelist_files') or not self.selected_pricelist_files:
            self.root.after(0, lambda: messagebox.showerror("Ошибка", "Не выбраны файлы прайс-листа"))
            return

        try:
            if self.app is None:
                self.app = MaterialMatcherApp(self.config)

            self.root.after(0, lambda: self.status_var.set("Загрузка прайс-листов..."))

            all_price_items = []
            loaded_files = []
            total_files = len(self.selected_pricelist_files)

            for i, file_path in enumerate(self.selected_pricelist_files, 1):
                try:
                    self.root.after(0, lambda f=file_path, curr=i, total=total_files:
                        self.status_var.set(f"Загрузка файла {curr}/{total}: {os.path.basename(f)}..."))

                    self.root.after(0, lambda f=file_path:
                        self.log_message(f"[INFO] Загрузка прайс-листа: {os.path.basename(f)}"))

                    # Загружаем прайс-лист из файла
                    price_items = self.app.load_price_list(file_path)

                    if price_items:
                        all_price_items.extend(price_items)
                        loaded_files.append(os.path.basename(file_path))
                        self.root.after(0, lambda f=file_path, count=len(price_items):
                            self.log_message(f"[SUCCESS] Загружено {count} позиций из {os.path.basename(f)}"))
                    else:
                        self.root.after(0, lambda f=file_path:
                            self.log_message(f"[WARNING] Не удалось загрузить данные из {os.path.basename(f)}"))

                except Exception as e:
                    self.root.after(0, lambda f=file_path, err=str(e):
                        self.log_message(f"[ERROR] Ошибка загрузки {os.path.basename(f)}: {err}"))
                    continue

            if all_price_items:
                # Убираем дубликаты по ID (если есть)
                unique_items = {}
                for item in all_price_items:
                    unique_items[item.id] = item
                final_items = list(unique_items.values())

                self.price_items = final_items

                # Обновляем информацию в интерфейсе
                def update_ui():
                    total_items = len(final_items)
                    files_info = f"{len(loaded_files)} файлов: {', '.join(loaded_files)}"
                    self.update_pricelist_info(total_items)
                    self.pricelist_info_label.config(
                        text=f"Загружено {total_items} позиций из {files_info}",
                        foreground="green"
                    )
                    self.status_var.set("Готов")
                    self.update_start_button_state()

                self.root.after(0, update_ui)
                self.root.after(0, lambda: self.log_message(
                    f"[SUCCESS] Загружены прайс-листы: {len(final_items)} уникальных позиций из {len(loaded_files)} файлов"))

            else:
                self.root.after(0, lambda: messagebox.showerror("Ошибка", "Не удалось загрузить данные ни из одного файла"))
                self.root.after(0, lambda: self.status_var.set("Ошибка"))

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Ошибка загрузки прайс-листов: {e}"))
            self.root.after(0, lambda: self.status_var.set("Ошибка"))

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
        
        # Устанавливаем путь к первому файлу (для совместимости)
        self.pricelist_path_var.set(pricelist_files[0])
        self.load_pricelist_from_directory(pricelist_dir)  # Загружаем из всей папки
    
    def load_materials_from_directory(self, directory_path):
        """Загрузка всех файлов материалов из указанной папки"""
        try:
            self.status_var.set("Загружаем материалы из папки...")
            
            # Создаем и запускаем поток для загрузки
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
                self.progress_var.set(0)
                self.progress_bar['maximum'] = len(material_files)
                
                # Загружаем каждый файл
                for i, (filename, file_path) in enumerate(material_files):
                    self.root.after(0, lambda f=filename: self.status_var.set(f"Загружаем: {f}"))
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
                        self.progress_var.set(i + 1)
                        self.root.update_idletasks()
                        
                    except Exception as e:
                        print(f"Ошибка загрузки файла {filename}: {e}")
                        continue
                
                # Сохраняем результаты
                self.materials = all_materials
                self.materials_order = [m.id for m in all_materials]
                
                # Обновляем интерфейс
                self.root.after(0, lambda: self.update_materials_info(len(all_materials)))
                self.root.after(0, lambda: self.status_var.set(f"Загружено материалов: {len(all_materials)} из {len(material_files)} файлов"))
            
            # Запускаем в потоке
            thread = threading.Thread(target=load_materials_thread)
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при загрузке материалов:\n{str(e)}")
            self.status_var.set("Готов")
    
    def load_pricelist_from_directory(self, directory_path):
        """Загрузка всех файлов прайс-листов из указанной папки"""
        try:
            self.status_var.set("Загружаем прайс-листы из папки...")
            
            # Создаем и запускаем поток для загрузки
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
                self.progress_var.set(0)
                self.progress_bar['maximum'] = len(pricelist_files)
                
                # Загружаем каждый файл
                for i, (filename, file_path) in enumerate(pricelist_files):
                    self.root.after(0, lambda f=filename: self.status_var.set(f"Загружаем: {f}"))
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
                        self.progress_var.set(i + 1)
                        self.root.update_idletasks()
                        
                    except Exception as e:
                        print(f"Ошибка загрузки файла {filename}: {e}")
                        continue
                
                # Сохраняем результаты
                self.price_items = all_price_items
                
                # Обновляем интерфейс
                self.root.after(0, lambda: self.update_pricelist_info(len(all_price_items)))
                self.root.after(0, lambda: self.status_var.set(f"Загружено позиций прайс-листа: {len(all_price_items)} из {len(pricelist_files)} файлов"))
            
            # Запускаем в потоке
            thread = threading.Thread(target=load_pricelist_thread)
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при загрузке прайс-листов:\n{str(e)}")
            self.status_var.set("Готов")
    
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
                    self.root.after(0, lambda: self.status_var.set("Готов"))
                    self.root.after(0, self.update_start_button_state)
                    # Обновляем предпросмотр с небольшой задержкой для улучшения восприятия скорости
                    self.root.after(100, lambda: self.update_materials_preview(materials))
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
                    self.root.after(0, lambda: self.status_var.set("Готов"))
                    self.root.after(0, self.update_start_button_state)
                    # Обновляем предпросмотр с небольшой задержкой для улучшения восприятия скорости
                    self.root.after(100, lambda: self.update_pricelist_preview(price_items))
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
            self.log_message("🗑️ Лог очищен")
    
    def new_project(self):
        """Создание нового проекта"""
        if messagebox.askyesno("Новый проект", "Очистить все данные и начать новый проект?"):
            self.clear_data()
            self.results = {}
            self.refresh_results()
            self.log_message("[INFO] Создан новый проект")
    
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
    
    
    
    def update_start_button_state(self):
        """Обновление состояния кнопки запуска"""
        self.log_message(f"[DEBUG] Проверка кнопки: materials={len(self.materials) if self.materials else 0}, price_items={len(self.price_items) if self.price_items else 0}, app={self.app is not None}")
        
        if self.materials and self.price_items and self.app:
            # Проверяем bypass mode или подключение к Elasticsearch
            def check():
                try:
                    # Проверяем bypass mode
                    if hasattr(self.app, 'matching_service') and hasattr(self.app.matching_service, 'bypass_elasticsearch') and self.app.matching_service.bypass_elasticsearch:
                        self.root.after(0, lambda: self._set_start_button_state(True, True))  # bypass_mode=True
                        return
                    
                    # Проверяем обычное подключение к Elasticsearch
                    connected = self.app.es_service.check_connection()
                    self.root.after(0, lambda: self._set_start_button_state(connected, False))
                except:
                    self.root.after(0, lambda: self._set_start_button_state(False, False))
            
            threading.Thread(target=check, daemon=True).start()
        else:
            self.start_button.config(state="disabled")
    
    def _set_start_button_state(self, es_connected, bypass_mode=False):
        """Установка состояния кнопки запуска"""
        if self.materials and self.price_items and (es_connected or bypass_mode):
            self.start_button.config(state="normal")
            if bypass_mode:
                self.log_message(f"[DEBUG] Кнопка активирована в режиме обхода!")
            else:
                self.log_message(f"[DEBUG] Кнопка активирована с Elasticsearch!")
        else:
            self.start_button.config(state="disabled")
    
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
                
                self.root.after(0, lambda: self.status_var.set("Индексация данных..."))
                self.root.after(0, lambda: self.log_message("[INFO] Начинаем индексацию данных..."))
                
                if self.app.index_data(self.materials, self.price_items):
                    self.root.after(0, lambda: self.log_message("[OK] Данные успешно проиндексированы!"))
                    self.root.after(0, lambda: self.status_var.set("Готов"))
                    self.root.after(0, self.update_start_button_state)
                else:
                    self.root.after(0, lambda: self.log_message("[WARNING] Ошибка индексации Elasticsearch! Пробуем режим обхода..."))
                    
                    # Пробуем режим обхода Elasticsearch
                    if self.price_items and self.app.enable_bypass_mode(self.price_items):
                        self.root.after(0, lambda: self.log_message("[OK] Режим обхода Elasticsearch активирован! Система работает в памяти."))
                        self.root.after(0, lambda: self.status_var.set("Готов (режим обхода)"))
                        # Дожидаемся завершения и активируем кнопку
                        self.root.after(100, self.update_start_button_state)
                        self.root.after(500, self.update_start_button_state)  # Дублируем для надежности
                    else:
                        self.root.after(0, lambda: self.log_message("[ERROR] Не удалось активировать режим обхода!"))
                        self.root.after(0, lambda: self.status_var.set("Ошибка"))
            except Exception as e:
                self.root.after(0, lambda: self.log_message(f"[ERROR] Ошибка индексации: {e}"))
                self.root.after(0, lambda: self.status_var.set("Ошибка"))
                
                # Попробуем bypass mode даже при исключении
                try:
                    if self.price_items and hasattr(self, 'app') and self.app:
                        if self.app.enable_bypass_mode(self.price_items):
                            self.root.after(0, lambda: self.log_message("[OK] Bypass mode активирован после ошибки!"))
                            self.root.after(0, lambda: self.status_var.set("Готов (режим обхода)"))
                            self.root.after(100, self.update_start_button_state)
                            self.root.after(500, self.update_start_button_state)  # Дублируем для надежности
                except Exception as bypass_error:
                    self.root.after(0, lambda: self.log_message(f"[ERROR] Bypass mode failed: {bypass_error}"))
        
        threading.Thread(target=index, daemon=True).start()
        return True
    
    def clear_data(self):
        """Очистка данных"""
        self.materials = []
        self.materials_order = []
        self.price_items = []
        self.results = {}
        self.selected_variants = {}
        self.selected_pricelist_files = []

        # Очищаем интерфейс
        self.materials_path_var.set("")
        self.pricelist_path_var.set("")
        self.materials_info_label.config(text="Материалы не загружены", foreground="red")
        self.pricelist_info_label.config(text="Прайс-лист не загружен", foreground="red")
        
        # Очищаем предпросмотр
        # Предварительный просмотр удален из интерфейса
        
        # Очищаем результаты
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        
        
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
                self.root.after(0, lambda: self.progress_bar.start(10) if hasattr(self, 'progress_bar') and self.progress_bar else None)
                self.root.after(0, lambda: self.progress_var.set("Запуск сопоставления..."))
                self.root.after(0, lambda: self.status_var.set("Выполняется сопоставление..."))
                self.root.after(0, lambda: self.log_message("[START] Начинаем сопоставление материалов..."))
                
                # Запускаем сопоставление
                self.root.after(0, lambda: self.log_message(f"[DEBUG] Передаем {len(self.materials)} материалов в run_matching"))
                results = self.app.run_matching(self.materials)
                
                self.root.after(0, lambda: self.log_message(f"[DEBUG] Получили результаты: {type(results)}, количество ключей: {len(results) if results else 0}"))
                
                if results:
                    # Посчитаем общее количество найденных результатов
                    total_matches = sum(len(matches) for matches in results.values())
                    self.root.after(0, lambda: self.log_message(f"[DEBUG] Общее количество соответствий: {total_matches}"))
                
                if not self.matching_cancelled:
                    self.results = results
                    self.root.after(0, lambda: self.update_results_display())
                    if results:
                        self.root.after(0, lambda: self.log_message("[OK] Сопоставление завершено успешно!"))
                        self.root.after(0, lambda: self.notebook.select(1))  # Переходим к результатам
                    else:
                        self.root.after(0, lambda: self.log_message("[WARNING] Сопоставление завершено, но результатов не найдено"))
                else:
                    self.root.after(0, lambda: self.log_message("[STOP] Сопоставление отменено пользователем"))
                
            except Exception as e:
                self.root.after(0, lambda: self.log_message(f"[ERROR] Ошибка сопоставления: {e}"))
            finally:
                # Восстанавливаем UI
                self.root.after(0, lambda: self.start_button.config(state="normal"))
                self.root.after(0, lambda: self.stop_button.config(state="disabled"))
                self.root.after(0, lambda: self.progress_bar.stop() if hasattr(self, 'progress_bar') and self.progress_bar else None)
                self.root.after(0, lambda: self.progress_var.set("Готов к запуску"))
                self.root.after(0, lambda: self.status_var.set("Готов"))
        
        threading.Thread(target=matching, daemon=True).start()
    
    def stop_matching(self):
        """Остановка сопоставления"""
        self.matching_cancelled = True
        self.stop_button.config(state="disabled")
        self.log_message("[STOP] Останавливаем сопоставление...")
    
    def update_results_display(self):
        """Обновление отображения результатов с топ-7 вариантами"""
        # DEBUG: Добавляем счетчик вызовов
        if not hasattr(self, '_update_display_call_count'):
            self._update_display_call_count = 0
        self._update_display_call_count += 1
        
        self.log_message(f"[DEBUG] === ВЫЗОВ update_results_display #{self._update_display_call_count} ===")
        self.log_message(f"[DEBUG] Существует ли self.results: {hasattr(self, 'results')}")
        if hasattr(self, 'results'):
            self.log_message(f"[DEBUG] Размер self.results: {len(self.results) if self.results else 0}")
        self.log_message("[INFO] НАЧАЛО update_results_display()")
        
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
                self.log_message(f"   📋 Сохраняю как раскрытый: '{clean_name}' (дети: {has_children}, открыт: {is_open})")
        
        # Очищаем дерево результатов
        current_items = self.results_tree.get_children()
        self.log_message(f"[DEBUG] Удаляем {len(current_items)} элементов из дерева")
        for item in current_items:
            self.results_tree.delete(item)
        
        # Используем форматтер для структурирования результатов
        self.formatter = MatchingResultFormatter(max_matches=7)
        
        # DEBUG: Проверяем размеры исходных данных
        self.log_message(f"[DEBUG] Количество материалов в self.results: {len(self.results)}")
        self.log_message(f"[DEBUG] Количество материалов в self.materials_order: {len(self.materials_order) if self.materials_order else 0}")

        # КРИТИЧЕСКИЙ АНАЛИЗ: Проверяем исходные данные self.results
        for i, (material_id, search_results) in enumerate(list(self.results.items())[:2]):  # Первые 2 материала
            self.log_message(f"[DEBUG] === ИСХОДНЫЕ ДАННЫЕ МАТЕРИАЛ {i+1} ===")
            self.log_message(f"[DEBUG] Material ID: {material_id}")
            self.log_message(f"[DEBUG] Количество SearchResult объектов: {len(search_results)}")

            for j, search_result in enumerate(search_results[:3]):  # Первые 3 результата
                price_item = search_result.price_item
                self.log_message(f"[DEBUG]   SearchResult {j+1}:")
                self.log_message(f"[DEBUG]     price_item.id: '{price_item.id}'")
                self.log_message(f"[DEBUG]     price_item.name: '{price_item.name[:50]}...'")
                self.log_message(f"[DEBUG]     price_item.material_name: '{price_item.material_name}'")

                if not price_item.id or price_item.id.strip() == "":
                    self.log_message(f"[DEBUG]     ⚠️ НАЙДЕНА ПРОБЛЕМА: price_item.id пустой в исходных данных!")
                break  # Только первый результат для краткости
        
        formatted_results = self.formatter.format_matching_results(self.results, self.materials_order, self.materials)

        # DEBUG: Проверяем размер отформатированных результатов
        self.log_message(f"[DEBUG] Количество отформатированных результатов: {len(formatted_results)}")

        # ДЕТАЛЬНЫЙ АНАЛИЗ ДАННЫХ ФОРМАТТЕРА (первые 2 материала)
        for i, result in enumerate(formatted_results[:2]):
            material_id = result.get("material_id")
            material_name = result.get("material_name")
            matches = result.get("matches", [])
            self.log_message(f"[DEBUG] === МАТЕРИАЛ {i+1} ===")
            self.log_message(f"[DEBUG] ID: {material_id}, Название: '{material_name}'")
            self.log_message(f"[DEBUG] Количество вариантов: {len(matches)}")

            for j, match in enumerate(matches[:3]):  # Первые 3 варианта
                variant_id = match.get("variant_id", "")
                variant_name = match.get("variant_name", "")
                self.log_message(f"[DEBUG]   Вариант {j+1}: variant_id='{variant_id}', name='{variant_name[:50]}...'")
                if not variant_id or variant_id.strip() == "":
                    self.log_message(f"[DEBUG]   ⚠️ ПРОБЛЕМА: variant_id пустой в отформатированных данных!")
        
        # Вычисляем статистику
        stats = self.formatter.get_statistics()
        
        
        # Заполняем результаты с топ-7 вариантами для каждого материала
        # Если нет сохраненного состояния, значит это первый запуск - раскрываем все
        if not expanded_materials:
            expanded_materials = set([result["material_name"] for result in formatted_results])
        
        for i, result in enumerate(formatted_results):
            material_name = result["material_name"]
            material_id = result["material_id"]
            matches = result["matches"]
            
            # DEBUG: Логируем каждый материал при отображении
            self.log_message(f"[DEBUG] Материал {i+1}: ID={material_id}, название={material_name[:50]}...")
            
            if matches:
                # Получаем данные материала для родительской строки
                material_data = None
                for material in self.materials:
                    if material.id == result['material_id']:
                        material_data = material
                        break
                
                # Подготавливаем данные материала для родительской строки с fallback из лучшего match
                material_code = "-"
                material_manufacturer = "-"
                
                if material_data:
                    material_code = material_data.equipment_code or ""
                    material_manufacturer = material_data.manufacturer or ""

                    # Код оборудования и изготовитель берутся только из файла материалов, без резервной логики
                
                # Если все еще пустые, ставим прочерк
                material_code = material_code or "-"
                material_manufacturer = material_manufacturer or "-"
                
                # Добавляем материал как родительский узел с данными материала
                parent = self.results_tree.insert("", tk.END, 
                    text=f"{i+1}. {material_name}",
                    values=(
                        material_code,          # material_code (голубой)
                        material_manufacturer,  # material_manufacturer (голубой)
                        "",                    # variant_name (пусто для родителя)
                        "",                    # price_article (пусто для родителя)
                        "",                    # price_brand (пусто для родителя)
                        "",                    # relevance (пусто для родителя)
                        "",                    # etm_code (пусто для родителя)
                        ""                     # price (пусто для родителя)
                    ),
                    tags=("material", "material_columns")
                )
                
                # Добавляем топ-7 вариантов (максимум)
                for i, match in enumerate(matches[:7], 1):
                    # Форматируем данные для отображения
                    variant_name = match["variant_name"]
                    relevance = f"{match['relevance']*100:.1f}%"
                    price = f"{match['price']:.2f} RUB" if match['price'] > 0 else "Не указана"
                    
                    # Данные материала (голубые столбцы) - пустые для вариантов прайс-листа
                    material_code = ""
                    material_manufacturer = ""
                    
                    # Данные прайс-листа (розовые столбцы)
                    price_brand = match.get("brand", "-") or "-"
                    price_article = match.get("article", "-") or "-"

                    # Всегда используем столбец variant_id для ETM кода
                    variant_id = match.get("variant_id", "")

                    # ДОПОЛНИТЕЛЬНАЯ ДИАГНОСТИКА ДЛЯ ETM КОДА
                    if i < 3:  # Логируем только первые 3 варианта
                        self.log_message(f"[ETM DEBUG] Вариант {i+1}:")
                        self.log_message(f"[ETM DEBUG]   match keys: {list(match.keys())}")
                        self.log_message(f"[ETM DEBUG]   variant_id raw: {repr(variant_id)}")
                        self.log_message(f"[ETM DEBUG]   variant_id type: {type(variant_id)}")

                        # Проверим также другие возможные поля с ID
                        alternative_ids = []
                        for key in ['id', 'article', 'brand_code', 'cli_code']:
                            value = match.get(key, "")
                            if value and str(value).strip():
                                alternative_ids.append(f"{key}={repr(value)}")

                        if alternative_ids:
                            self.log_message(f"[ETM DEBUG]   alternative_ids: {', '.join(alternative_ids)}")

                    if variant_id and str(variant_id).strip():
                        etm_code = str(variant_id).strip()
                    else:
                        # ИСПРАВЛЕНИЕ: Если variant_id пустой, попробуем альтернативные поля
                        etm_code = "-"

                        # Пробуем найти ID в других полях (приоритет: article -> id -> brand_code)
                        for fallback_key in ['article', 'id', 'brand_code']:
                            fallback_value = match.get(fallback_key, "")
                            if fallback_value and str(fallback_value).strip():
                                etm_code = str(fallback_value).strip()
                                if i < 3:  # Логируем только первые 3
                                    self.log_message(f"[ETM FIX] Используем {fallback_key} как ETM код: '{etm_code}'")
                                break

                    if i < 3:
                        self.log_message(f"[DEBUG] Заполнение таблицы - материал {material_name}, вариант {i+1}:")
                        self.log_message(f"[DEBUG]   variant_id: '{variant_id}'")
                        self.log_message(f"[DEBUG]   В столбце КОД ETM будет отображаться: '{etm_code}'")
                    
                    # Определяем цветовую индикацию по релевантности
                    tag = "high" if match['relevance'] > 0.7 else "medium" if match['relevance'] > 0.4 else "low"
                    
                    # Добавляем теги для цветового выделения (только прайс-лист)
                    color_tags = [tag, "price_columns"]
                    
                    # Добавляем вариант как дочерний элемент с новой структурой столбцов
                    child = self.results_tree.insert(parent, tk.END, 
                        values=(
                            material_code,          # material_code (голубой)
                            material_manufacturer,  # material_manufacturer (голубой)
                            variant_name,          # variant_name (розовый)
                            price_article,         # price_article (розовый)
                            price_brand,           # price_brand (розовый)
                            relevance,             # relevance (розовый)
                            etm_code,              # etm_code (КОД ETM)
                            price                  # price
                        ),
                        tags=tuple(color_tags + [f"variant_{result['material_id']}_{i}"])
                    )
                
                # Автоматически раскрываем все материалы (новые) или восстанавливаем состояние (обновление)
                should_expand = material_name in expanded_materials if expanded_materials else True
                self.results_tree.item(parent, open=should_expand)
                if should_expand:
                    self.log_message(f"   [OK] Раскрываю материал: '{material_name}'")
        
        # Настраиваем цветовые теги
        # Теги уже настроены в create_results_tab с Excel-like стилями
        
        # Обработчик двойного клика уже привязан выше через on_smart_click
        
        # Обновляем табличный вид если он активен (пока используется только древовидный режим)
        # if self.view_mode == "table":
        #     self.update_table_view_data()
    
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
                                self.log_message(f"[OK] Выбран вариант {variant_id} для материала {material_id}")
                                # Обновляем визуальное выделение
                                self.highlight_selected_variant(selection[0])
                            else:
                                self.log_message(f"[ERROR] Ошибка выбора: {result['error']}")
    
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
            self.log_message(f"[ERROR] Ошибка в обработке клика: {e}")
    
    def handle_double_click(self, event, item):
        """Обработка двойного клика по варианту из прайс-листа"""
        try:
            # Получаем колонку, по которой кликнули
            column = self.results_tree.identify('column', event.x, event.y)
            
            if not item:
                self.log_message("[ERROR] Не удалось определить элемент для клика")
                return
            
            # Проверяем, что кликнули по варианту (дочерний элемент), а не по материалу
            parent = self.results_tree.parent(item)
            if not parent:  # Кликнули по материалу, а не по варианту
                self.log_message("ℹ️ Клик по материалу (не по варианту)")
                return
            
            # Дополнительная отладочная информация
            self.log_message(f"[SEARCH] Двойной клик: элемент={item}, колонка={column}, родитель={parent}")
        except Exception as e:
            self.log_message(f"[ERROR] Ошибка при обработке клика: {e}")
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
            self.log_message(f"[ERROR] Не найден тег варианта в {tags}")
            return
        
        self.log_message(f"[OK] Найден тег варианта: {variant_tag}")
        
        # Извлекаем material_id из тега (формат: variant_material_id_variant_id)
        try:
            parts = variant_tag.split('_')
            if len(parts) < 3:
                self.log_message(f"[ERROR] Неверный формат тега: {variant_tag}")
                return
            
            material_id = parts[1]
            variant_id = parts[2]
            
            self.log_message(f"📋 Material ID: {material_id}, Variant ID: {variant_id}")
            
            # Получаем данные выбранного варианта
            values = self.results_tree.item(item, 'values')
            if not values:
                self.log_message(f"[ERROR] Нет значений для элемента {item}")
                return
                
            self.log_message(f"📊 Значения варианта: {values}")
        except Exception as e:
            self.log_message(f"[ERROR] Ошибка при извлечении данных: {e}")
            return
        
        # Правильные индексы для извлечения данных варианта из values
        # Структура: ('material_code', 'material_manufacturer', 'variant_name', 'price_article', 'price_brand', 'relevance', 'etm_code', 'price')
        variant_name = values[2] if len(values) > 2 else ""     # Название варианта
        article = values[3] if len(values) > 3 else ""          # Артикул
        brand = values[4] if len(values) > 4 else ""            # Бренд
        relevance = values[5] if len(values) > 5 else ""        # Процент похожести
        etm_code = values[6] if len(values) > 6 else ""         # КОД ETM (id товара)
        price = values[7] if len(values) > 7 else ""            # Цена
        
        # Сохраняем выбранный вариант
        self.selected_variants[material_id] = {
            'variant_id': variant_id,
            'variant_name': variant_name,
            'relevance': relevance,
            'price': price,
            'brand': brand,
            'article': article,
            'etm_code': etm_code,
            'item_id': item
        }
        
        # Сначала обновляем отображение выбранного варианта (поднимаем его на уровень материала)
        self.log_message("🔧 НАЧИНАЮ обновление выбранного варианта...")
        self.update_selected_variant_display(parent, item, variant_name)
        
        # ДАЕМ ВРЕМЯ ПОЛЬЗОВАТЕЛЮ УВИДЕТЬ ИЗМЕНЕНИЯ, затем схлопываем
        self.log_message("⏳ Даём время увидеть изменения перед схлопыванием...")
        self.root.after(100, lambda: self.delayed_collapse(parent, item))
        
        # КОРНЕВОЕ РЕШЕНИЕ: Больше не нужно принудительное раскрытие,
        # так как мы не удаляем элементы, а только схлопываем выбранный материал
        self.log_message("[OK] КОРНЕВОЕ РЕШЕНИЕ: Другие материалы остаются нетронутыми")
        
        # Логируем действие
        material_name = self.results_tree.item(parent, 'text')
        self.log_message(f"[OK] Выбран вариант для '{material_name}': {variant_name}")
    
    def delayed_collapse(self, parent_item, selected_item):
        """ОТЛОЖЕННОЕ СХЛОПЫВАНИЕ: Даём время пользователю увидеть изменения"""
        self.log_message("📁 Автоматическое схлопывание материала после выбора")
        self.hide_other_variants(parent_item, selected_item)
    
    def hide_other_variants(self, parent_item, selected_item):
        """ФИНАЛЬНОЕ РЕШЕНИЕ: НИЧЕГО НЕ ДЕЛАЕМ с вариантами - только схлопываем материал"""
        
        # Получаем всех дочерних элементов только для подсчета
        children = list(self.results_tree.get_children(parent_item))
        
        # НЕ ТРОГАЕМ ВАРИАНТЫ ВООБЩЕ! Даже визуально не изменяем
        # Просто схлопываем материал чтобы скрыть все варианты
        self.results_tree.item(parent_item, open=False)
        
        self.log_message(f"📁 ФИНАЛЬНОЕ РЕШЕНИЕ: Просто схлопываем материал (скрываем {len(children)} вариантов)")
        self.log_message("🚫 Варианты НЕ изменены, НЕ удалены, НЕ модифицированы")  
        self.log_message("🤞 Надеемся что другие материалы останутся нетронутыми")
    
    # Старые функции принудительного раскрытия удалены - они больше не нужны
    # благодаря корневому решению проблемы схлопывания
    
    def update_selected_variant_display(self, parent_item, selected_item, variant_name):
        """Обновление визуального отображения выбранного варианта"""
        try:
            # Получаем данные выбранного варианта
            selected_values = self.results_tree.item(selected_item, 'values')
            material_name = self.results_tree.item(parent_item, 'text')

            if not selected_values:
                self.log_message("[ERROR] Нет данных варианта для обновления")
                return

            # Создаем новые values для материала, сохраняя правильную структуру
            # Обновляем только колонки с данными варианта (название, бренд, артикул, похожесть, etm_code, цена)
            current_material_values = list(self.results_tree.item(parent_item, 'values'))

            # Обновляем данные материала данными выбранного варианта
            if len(current_material_values) >= 8 and len(selected_values) >= 8:
                # Копируем данные варианта в соответствующие позиции материала
                # Структура: (material_code, material_manufacturer, variant_name, price_brand, price_article, relevance, etm_code, price)
                current_material_values[2] = selected_values[2]   # Название варианта
                current_material_values[3] = selected_values[3]   # Бренд
                current_material_values[4] = selected_values[4]   # Артикул
                current_material_values[5] = selected_values[5]   # Похожесть
                current_material_values[6] = selected_values[6]   # КОД ETM
                current_material_values[7] = selected_values[7]   # Цена

                # Обновляем строку материала
                self.results_tree.item(parent_item, values=current_material_values)
                self.log_message(f"📊 ДАННЫЕ ВАРИАНТА перенесены в строку материала")

                # Заголовок материала остается без изменений

            # Визуальное выделение выбранного варианта
            selected_tags = list(self.results_tree.item(selected_item, 'tags'))
            if 'selected_variant' not in selected_tags:
                selected_tags.append('selected_variant')
                self.results_tree.item(selected_item, tags=selected_tags)

            # Визуальное выделение материала с выбором
            parent_tags = list(self.results_tree.item(parent_item, 'tags'))
            if 'material_with_selection' not in parent_tags:
                parent_tags.append('material_with_selection')
                self.results_tree.item(parent_item, tags=parent_tags)

            # Стили уже настроены в create_results_tab с Excel-like дизайном

            self.log_message(f"🎨 ВИЗУАЛЬНОЕ ВЫДЕЛЕНИЕ: Материал и вариант выделены цветом")
            self.log_message(f"[OK] Структура TreeView НЕ изменена - материалы не схлопнутся!")
            self.log_message(f"📍 Вариант '{variant_name}' поднят на уровень материала")

        except Exception as e:
            self.log_message(f"[ERROR] Ошибка при обновлении отображения: {e}")
    
    def refresh_results(self):
        """Обновление результатов"""
        if self.results:
            self.update_results_display()
            self.log_message("[INFO] Результаты обновлены")
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
        
        self.log_message("[INFO] Все выборы сброшены")
    
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
                    
                    self.root.after(0, lambda: self.log_message(f"[OK] Выбранные результаты экспортированы в {filename}"))
                    self.root.after(0, lambda: self.status_var.set("Готов"))
                    self.root.after(0, lambda: messagebox.showinfo("Экспорт", f"Выбранные результаты сохранены в файл:\n{filename}"))
                    
                except Exception as e:
                    self.root.after(0, lambda: self.log_message(f"[ERROR] Ошибка экспорта выбранных: {e}"))
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
                            self.root.after(0, lambda: self.log_message(f"[OK] Результаты экспортированы в {filename}"))
                            self.root.after(0, lambda: self.status_var.set("Готов"))
                            self.root.after(0, lambda: messagebox.showinfo("Экспорт", f"Результаты сохранены в файл:\n{filename}"))
                        else:
                            raise Exception("Не удалось сохранить файл")
                    else:
                        # Fallback на старый метод
                        if self.app is None:
                            self.app = MaterialMatcherApp(self.config)
                        self.app.export_results(self.results, filename, format_type)
                        self.root.after(0, lambda: self.log_message(f"[OK] Результаты экспортированы в {filename}"))
                        self.root.after(0, lambda: self.status_var.set("Готов"))
                        self.root.after(0, lambda: messagebox.showinfo("Экспорт", f"Результаты сохранены в файл:\n{filename}"))
                        
                except Exception as e:
                    self.root.after(0, lambda: self.log_message(f"[ERROR] Ошибка экспорта: {e}"))
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
                self.root.after(0, lambda: self.log_message(f"[ERROR] Ошибка поиска: {e}"))
                self.root.after(0, lambda: self.status_var.set("Ошибка"))
        
        threading.Thread(target=search, daemon=True).start()
    
    def update_search_results(self, query, matches):
        """Обновление результатов поиска"""
        # Очищаем дерево результатов поиска
        for item in self.search_tree.get_children():
            self.search_tree.delete(item)
        
        if matches:
            self.log_message(f"[SEARCH] Найдено {len(matches)} соответствий для '{query}'")
            
            for i, match in enumerate(matches, 1):
                price_str = f"{match['price_item']['price']} {match['price_item']['currency']}" if match['price_item']['price'] else "Не указана"
                
                self.search_tree.insert("", tk.END, text=str(i), values=(
                    match['price_item']['material_name'],
                    f"{match['similarity_percentage']:.1f}%",
                    price_str
                ))
        else:
            self.log_message(f"[ERROR] Соответствий для '{query}' не найдено")
            self.search_tree.insert("", tk.END, text="", values=(
                "Соответствия не найдены", "", ""
            ))


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

    def auto_select_all_variants(self):
        """Автоматический выбор наиболее релевантных вариантов для всех материалов"""
        try:
            if not hasattr(self, 'results_tree') or not self.results_tree.get_children():
                messagebox.showwarning("Предупреждение", "Нет результатов для автовыбора")
                return

            selected_count = 0
            total_materials = 0

            self.log_message("[DEBUG] Начинаем автоматический выбор вариантов...")

            # Проходим по всем материалам (родительским элементам)
            for material_item in self.results_tree.get_children():
                material_text = self.results_tree.item(material_item, 'text')
                total_materials += 1

                # Получаем дочерние элементы (варианты)
                variants = self.results_tree.get_children(material_item)
                self.log_message(f"[DEBUG] Материал '{material_text[:50]}...': найдено {len(variants)} вариантов")

                if variants:
                    # Находим вариант с наивысшей релевантностью
                    best_variant = None
                    best_relevance = -1

                    for i, variant_item in enumerate(variants):
                        values = self.results_tree.item(variant_item, 'values')
                        self.log_message(f"[DEBUG]   Вариант {i+1}: values length = {len(values)}")
                        if len(values) > 5:
                            self.log_message(f"[DEBUG]   Значения варианта: {values}")
                            try:
                                relevance_str = str(values[5])  # Индекс 5 - колонка relevance
                                self.log_message(f"[DEBUG]   Строка релевантности: '{relevance_str}'")

                                if relevance_str and relevance_str != '':
                                    # Убираем возможные символы процента и пробелы
                                    relevance_clean = relevance_str.strip().replace('%', '')
                                    relevance = float(relevance_clean)
                                    self.log_message(f"[DEBUG]   Релевантность как число: {relevance}")

                                    if relevance > best_relevance:
                                        best_relevance = relevance
                                        best_variant = variant_item
                                        self.log_message(f"[DEBUG]   Новый лучший вариант с релевантностью {relevance}")
                            except (ValueError, IndexError) as ex:
                                self.log_message(f"[DEBUG]   Ошибка парсинга релевантности: {ex}")
                                continue

                    # Выбираем лучший вариант
                    if best_variant:
                        self.log_message(f"[DEBUG] Выбираем лучший вариант с релевантностью {best_relevance}")

                        # Имитируем двойной клик по лучшему варианту
                        try:
                            # Создаем фиктивный объект события
                            class FakeEvent:
                                def __init__(self):
                                    self.x = 0
                                    self.y = 0

                            fake_event = FakeEvent()

                            # Вызываем обработчик двойного клика
                            self.handle_double_click(fake_event, best_variant)
                            selected_count += 1
                            self.log_message(f"[OK] Вариант успешно выбран автоматически")
                        except Exception as e:
                            self.log_message(f"[ERROR] Ошибка при автоматическом выборе варианта: {e}")
                    else:
                        self.log_message(f"[DEBUG] Лучший вариант не найден для материала")

            self.log_message(f"[OK] Автоматически выбрано {selected_count} из {total_materials} материалов")
            messagebox.showinfo("Готово", f"Автоматически выбрано {selected_count} из {total_materials} наиболее релевантных вариантов")

        except Exception as e:
            self.log_message(f"[ERROR] Ошибка при автовыборе: {e}")
            import traceback
            self.log_message(f"[ERROR] Traceback: {traceback.format_exc()}")
            messagebox.showerror("Ошибка", f"Ошибка при автовыборе: {str(e)}")

    def expand_all_materials(self):
        """Раскрытие всех материалов в дереве результатов"""
        try:
            if not hasattr(self, 'results_tree') or not self.results_tree.get_children():
                messagebox.showwarning("Предупреждение", "Нет результатов для раскрытия")
                return

            expanded_count = 0

            # Раскрываем все родительские элементы (материалы)
            for material_item in self.results_tree.get_children():
                if self.results_tree.get_children(material_item):  # Есть дочерние элементы
                    self.results_tree.item(material_item, open=True)
                    expanded_count += 1

            self.log_message(f"[OK] Раскрыто {expanded_count} материалов")
            messagebox.showinfo("Готово", f"Раскрыто {expanded_count} материалов")

        except Exception as e:
            self.log_message(f"[ERROR] Ошибка при раскрытии: {e}")
            messagebox.showerror("Ошибка", f"Ошибка при раскрытии материалов: {str(e)}")

    def update_etm_prices(self):
        """Обновление цен через ETM API"""
        try:
            if not hasattr(self, 'results_tree') or not self.results_tree.get_children():
                messagebox.showwarning("Предупреждение", "Нет результатов для обновления цен")
                return

            # Собираем все коды ETM из таблицы
            etm_codes = self._collect_etm_codes()
            if not etm_codes:
                messagebox.showinfo("Информация", "Не найдены коды ETM для обновления цен")
                return

            self.log_message(f"[INFO] Начинаем обновление цен для {len(etm_codes)} кодов ETM...")

            # Запускаем обновление цен в отдельном потоке
            threading.Thread(
                target=self._update_prices_thread,
                args=(etm_codes,),
                daemon=True
            ).start()

        except Exception as e:
            self.log_message(f"[ERROR] Ошибка при запуске обновления цен: {e}")
            messagebox.showerror("Ошибка", f"Ошибка при обновлении цен: {str(e)}")


    def _collect_etm_codes(self):
        """Сбор всех кодов ETM из таблицы результатов"""
        etm_codes = set()
        total_rows_with_etm = 0  # Общее количество строк с ETM кодами
        all_etm_codes = []       # Все коды (включая дубликаты)
        total_rows_checked = 0   # Общее количество проверенных строк

        self.log_message(f"[DEBUG] Начинаем сбор ETM кодов из таблицы...")

        for material_item in self.results_tree.get_children():
            self.log_message(f"[DEBUG] Проверяем материал: {self.results_tree.item(material_item, 'text')}")
            # Проходим по вариантам каждого материала
            for variant_item in self.results_tree.get_children(material_item):
                total_rows_checked += 1
                values = self.results_tree.item(variant_item, 'values')
                self.log_message(f"[DEBUG]   Строка {total_rows_checked}: values = {values}")

                if len(values) > 6:  # Проверяем наличие столбца etm_code
                    etm_code = str(values[6]).strip()  # Индекс 6 - столбец КОД ETM
                    self.log_message(f"[DEBUG]   ETM код в позиции 6: '{etm_code}'")

                    if etm_code and etm_code != '' and etm_code != '-':
                        etm_codes.add(etm_code)  # Уникальные коды
                        all_etm_codes.append(etm_code)  # Все коды
                        total_rows_with_etm += 1
                        self.log_message(f"[DEBUG]   ✓ Принят ETM код: {etm_code}")
                    else:
                        self.log_message(f"[DEBUG]   ✗ Отклонен ETM код: '{etm_code}' (пустой или прочерк)")
                else:
                    self.log_message(f"[DEBUG]   ✗ Недостаточно столбцов: {len(values)} (нужно > 6)")

        self.log_message(f"[DEBUG] Проверено строк всего: {total_rows_checked}")

        unique_count = len(etm_codes)
        self.log_message(f"[DEBUG] Статистика ETM кодов:")
        self.log_message(f"[DEBUG]   Общее количество строк с ETM кодами: {total_rows_with_etm}")
        self.log_message(f"[DEBUG]   Уникальных ETM кодов: {unique_count}")

        if total_rows_with_etm != unique_count:
            self.log_message(f"[DEBUG]   НАЙДЕНЫ ДУБЛИКАТЫ! Разница: {total_rows_with_etm - unique_count}")

            # Показываем примеры дубликатов
            from collections import Counter
            code_counts = Counter(all_etm_codes)
            duplicates = {code: count for code, count in code_counts.items() if count > 1}
            if duplicates:
                self.log_message(f"[DEBUG]   Примеры дубликатов: {dict(list(duplicates.items())[:5])}")

        return list(etm_codes)

    def _update_prices_thread(self, etm_codes):
        """Фоновое обновление цен через ETM API"""
        try:
            etm_service = get_etm_service()

            self.log_message(f"[DEBUG] ETM коды для запроса ({len(etm_codes)} шт.): {etm_codes[:5]}...")

            # Создаем прогресс-диалог
            self._show_progress_dialog("Обновление цен ETM", len(etm_codes))

            # Сначала проверяем доступность ETM API сервера
            self.log_message(f"[DEBUG] Проверяем доступность ETM API сервера...")
            if not etm_service.check_connectivity():
                error_msg = "ETM API сервер недоступен. Проверьте интернет-соединение и попробуйте позже."
                self.log_message(f"[ERROR] {error_msg}")
                self.root.after(0, lambda: messagebox.showerror("Ошибка соединения", error_msg))
                return

            # Запрашиваем цены
            self.log_message(f"[DEBUG] Сервер доступен, запрашиваем цены через ETM API...")
            prices = etm_service.get_prices(
                etm_codes,
                progress_callback=self._update_progress
            )

            self.log_message(f"[DEBUG] Получен ответ от ETM API: {len(prices)} записей")
            if prices:
                # Подсчитываем успешные и неудачные результаты
                successful_prices = {k: v for k, v in prices.items() if v.get('status') == 'success' and v.get('price', 0) > 0}
                failed_prices = {k: v for k, v in prices.items() if v.get('status') != 'success'}

                self.log_message(f"[DEBUG] Успешных цен: {len(successful_prices)}, неудачных: {len(failed_prices)}")
                self.log_message(f"[DEBUG] Примеры успешных: {dict(list(successful_prices.items())[:2])}")
                if failed_prices:
                    self.log_message(f"[DEBUG] Примеры неудачных: {dict(list(failed_prices.items())[:2])}")
            else:
                self.log_message(f"[DEBUG] Пустой ответ от ETM API")

            # Обновляем цены в таблице
            updated_count = self.root.after(0, self._apply_prices_to_table, prices)

        except Exception as e:
            from src.services.etm_api_service import EtmApiError
            if isinstance(e, EtmApiError):
                # Показываем понятную ошибку ETM API
                error_msg = f"Ошибка ETM API: {str(e)}"
                self.log_message(f"[ERROR] {error_msg}")
                self.root.after(0, lambda: messagebox.showerror("Ошибка ETM API", str(e)))
            else:
                # Общая ошибка
                self.log_message(f"[ERROR] Неожиданная ошибка при обновлении цен: {e}")
                import traceback
                self.log_message(f"[ERROR] Traceback: {traceback.format_exc()}")
                self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Неожиданная ошибка обновления цен: {str(e)}"))
        finally:
            # Закрываем прогресс-диалог
            self.root.after(0, self._close_progress_dialog)

    def _show_progress_dialog(self, title, total):
        """Показ диалога прогресса"""
        self.progress_dialog = tk.Toplevel(self.root)
        self.progress_dialog.title(title)
        self.progress_dialog.geometry("400x120")
        self.progress_dialog.transient(self.root)
        self.progress_dialog.grab_set()

        # Центрируем диалог
        self.progress_dialog.geometry("+%d+%d" % (
            self.root.winfo_rootx() + 100,
            self.root.winfo_rooty() + 100
        ))

        frame = ttk.Frame(self.progress_dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        self.progress_label = ttk.Label(frame, text="Подготовка...")
        self.progress_label.pack(pady=(0, 10))

        self.progress_bar = ttk.Progressbar(frame, length=300, mode='determinate')
        self.progress_bar.pack(fill=tk.X)
        self.progress_bar['maximum'] = total

    def _update_progress(self, current, total, message):
        """Обновление прогресса"""
        def update():
            if hasattr(self, 'progress_dialog') and self.progress_dialog.winfo_exists():
                self.progress_label.config(text=message)
                self.progress_bar['value'] = current

        self.root.after(0, update)

    def _close_progress_dialog(self):
        """Закрытие диалога прогресса"""
        if hasattr(self, 'progress_dialog'):
            self.progress_dialog.destroy()

    def _apply_prices_to_table(self, prices):
        """Применение обновленных цен к таблице"""
        rows_updated_with_prices = 0  # Строк с реальными ценами
        rows_updated_with_dashes = 0  # Строк с прочерками
        total_rows_processed = 0      # Общее количество обработанных строк
        unique_codes_with_prices = set()  # Уникальные коды с ценами

        try:
            self.log_message(f"[DEBUG] Начинаем применение цен к таблице...")
            self.log_message(f"[DEBUG] Получено ответов от API: {len(prices)}")

            for material_item in self.results_tree.get_children():
                # Проходим по вариантам каждого материала
                for variant_item in self.results_tree.get_children(material_item):
                    values = list(self.results_tree.item(variant_item, 'values'))
                    if len(values) > 7:  # Проверяем наличие столбцов
                        etm_code = str(values[6]).strip()  # Индекс 6 - КОД ETM

                        if etm_code in prices:
                            total_rows_processed += 1
                            price_data = prices[etm_code]

                            if price_data['status'] == 'success' and price_data.get('price', 0) > 0:
                                # Есть цена - показываем её
                                new_price = f"{price_data['price']:.2f} {price_data['currency']}"
                                values[7] = new_price  # Индекс 7 - столбец цены
                                rows_updated_with_prices += 1
                                unique_codes_with_prices.add(etm_code)
                            else:
                                # Нет цены - показываем прочерк
                                values[7] = "-"
                                rows_updated_with_dashes += 1

                            # Обновляем строку в таблице
                            self.results_tree.item(variant_item, values=values)

            # Детальная статистика
            unique_codes_requested = len(prices)
            unique_codes_with_prices_count = len(unique_codes_with_prices)

            self.log_message(f"[OK] СТАТИСТИКА ОБНОВЛЕНИЯ:")
            self.log_message(f"[OK]   Уникальных кодов запрошено: {unique_codes_requested}")
            self.log_message(f"[OK]   Уникальных кодов с ценами: {unique_codes_with_prices_count}")
            self.log_message(f"[OK]   Строк в таблице обработано: {total_rows_processed}")
            self.log_message(f"[OK]   Строк обновлено с ценами: {rows_updated_with_prices}")
            self.log_message(f"[OK]   Строк помечено прочерком: {rows_updated_with_dashes}")

            # Разъяснение, если есть разница между строками и кодами
            if total_rows_processed > unique_codes_requested:
                self.log_message(f"[INFO] В таблице есть дубликаты кодов - это нормально")

            if rows_updated_with_prices > 0:
                messagebox.showinfo("Готово",
                    f"Получено {unique_codes_with_prices_count} уникальных цен из ETM API\n" +
                    f"Обновлено {rows_updated_with_prices} строк в таблице\n" +
                    f"(обработано {total_rows_processed} строк, {rows_updated_with_dashes} без цен)")
            else:
                messagebox.showwarning("Результат",
                    f"Цены не получены\n" +
                    f"Запрошено {unique_codes_requested} кодов, обработано {total_rows_processed} строк\n" +
                    f"Все строки помечены прочерками")

        except Exception as e:
            self.log_message(f"[ERROR] Ошибка при применении цен: {e}")
            messagebox.showerror("Ошибка", f"Ошибка при применении цен: {str(e)}")

    def auto_load_on_startup(self):
        """Автоматическая загрузка файлов при запуске программы"""
        self.log_message("[INFO] Запуск автоматической загрузки файлов...")
        
        materials_dir = Path("./material")
        pricelist_dir = Path("./price-list")
        
        # Проверяем наличие папок
        materials_exists = materials_dir.exists() and any(materials_dir.iterdir())
        pricelist_exists = pricelist_dir.exists() and any(pricelist_dir.iterdir())
        
        if not materials_exists and not pricelist_exists:
            self.log_message("[INFO] Папки material и price-list пусты или не найдены. Автозагрузка пропущена.")
            return
        
        def auto_load_thread():
            try:
                # Загружаем материалы если есть файлы
                if materials_exists:
                    self.root.after(0, lambda: self.status_var.set("Автозагрузка материалов..."))
                    self.load_materials_from_directory(materials_dir)
                    self.root.after(0, lambda: self.log_message("[OK] Материалы автоматически загружены"))
                
                # Небольшая пауза между загрузками
                import time
                time.sleep(0.5)
                
                # Загружаем прайс-листы если есть файлы
                if pricelist_exists:
                    self.root.after(0, lambda: self.status_var.set("Автозагрузка прайс-листов..."))
                    self.load_pricelist_from_directory(pricelist_dir)
                    self.root.after(0, lambda: self.log_message("[OK] Прайс-листы автоматически загружены"))
                
                # Пауза перед автоматической индексацией
                time.sleep(1.0)
                
                # Автоматическая индексация если есть данные
                if self.materials or self.price_items:
                    self.root.after(0, lambda: self.log_message("[INFO] Запуск автоматической индексации..."))
                    self.root.after(0, lambda: self.index_data(show_warning=False))
                    self.root.after(0, lambda: self.log_message("[OK] Система готова к работе!"))
                    # Добавляем паузу и проверку кнопки после индексации
                    time.sleep(2.0)
                    self.root.after(0, self.update_start_button_state)
                    # Принудительная проверка кнопки через таймер
                    self.root.after(3000, self.update_start_button_state)
                else:
                    self.root.after(0, lambda: self.status_var.set("Готов"))
                    
            except Exception as e:
                self.root.after(0, lambda: self.log_message(f"[ERROR] Ошибка автозагрузки: {e}"))
                self.root.after(0, lambda: self.status_var.set("Ошибка"))
        
        # Запускаем автозагрузку в отдельном потоке
        threading.Thread(target=auto_load_thread, daemon=True).start()

    # Методы переключения режимов просмотра удалены - используется только древовидный режим
    
    # Метод обновления табличного вида удален - используется только древовидный режим


def main():
    """Запуск GUI приложения"""
    try:
        root = tk.Tk()
        app = MaterialMatcherGUI(root)
        root.mainloop()
    except Exception as e:
        print(f"[ERROR] GUI crashed: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")


if __name__ == "__main__":
    main()