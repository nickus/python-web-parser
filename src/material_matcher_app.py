#!/usr/bin/env python3
"""
Приложение для поиска материалов с процентом похожести
Основной интерфейс для работы с системой сопоставления материалов и прайс-листов
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List
import time

from .models.material import Material, PriceListItem
from .services.elasticsearch_service_optimized import OptimizedElasticsearchService
from .services.fast_similarity_service import FastSimilarityService
from .services.optimized_matching_service import OptimizedMatchingService
from .utils.data_loader_fixed import MaterialLoader, PriceListLoader
from .utils.data_loader import DataExporter


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('material_matcher.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Подавляем избыточные логи от Elasticsearch
logging.getLogger('elastic_transport').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)

logger = logging.getLogger(__name__)


class MaterialMatcherApp:
    """Главный класс приложения для сопоставления материалов"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Инициализация приложения
        
        Args:
            config: Конфигурация приложения
        """
        self.config = config or self._get_default_config()
        
        # Используем оптимизированные сервисы для улучшенной производительности
        es_config = self.config.get('elasticsearch', {})
        self.es_service = OptimizedElasticsearchService(
            host=es_config.get('host', 'localhost'),
            port=es_config.get('port', 9200),
            username=es_config.get('username'),
            password=es_config.get('password'),
            bulk_size=es_config.get('bulk_size', 1000),
            max_workers=es_config.get('max_workers', 4)
        )

        self.similarity_service = FastSimilarityService()
        self.matching_service = OptimizedMatchingService(self.es_service, self.similarity_service)
        
        logger.info("MaterialMatcher application initialized successfully")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Получение оптимизированной конфигурации по умолчанию"""
        return {
            'elasticsearch': {
                'host': 'localhost',
                'port': 9200,
                # ОПТИМИЗАЦИЯ 21: Оптимальные настройки bulk операций
                'bulk_size': 750,  # Увеличено с 500 до 750 для лучшей производительности
                'max_workers': 4   # 4 потока оптимально для большинства машин
            },
            'matching': {
                'similarity_threshold': 20.0,
                'max_results_per_material': 4,
                'max_workers': 4
            }
        }
    
    def setup_indices(self) -> bool:
        """Создание индексов в Elasticsearch"""
        logger.info("Setting up Elasticsearch indices...")

        # Используем метод оптимизированного сервиса
        price_list_success = self.es_service.create_optimized_price_list_index()

        if price_list_success:
            logger.info("Indices created successfully")
            return True
        else:
            logger.error("Failed to create indices")
            return False
    
    def load_materials(self, file_path: str, file_format: str = 'auto') -> List[Material]:
        """
        Загрузка материалов из файла
        
        Args:
            file_path: Путь к файлу с материалами
            file_format: Формат файла ('csv', 'excel', 'json', 'auto')
            
        Returns:
            Список загруженных материалов
        """
        logger.info(f"Loading materials from {file_path}")
        
        path = Path(file_path)
        if not path.exists():
            logger.error(f"File not found: {file_path}")
            return []
        
        # Автоопределение формата
        if file_format == 'auto':
            extension = path.suffix.lower()
            if extension in ['.csv']:
                file_format = 'csv'
            elif extension in ['.xlsx', '.xls']:
                file_format = 'excel'
            elif extension in ['.json']:
                file_format = 'json'
            else:
                logger.error(f"Unsupported file format: {extension}")
                return []
        
        try:
            if file_format == 'csv':
                materials = MaterialLoader.load_from_csv(str(path))
            elif file_format == 'excel':
                materials = MaterialLoader.load_from_excel(str(path))
            elif file_format == 'json':
                materials = MaterialLoader.load_from_json(str(path))
            else:
                logger.error(f"Unsupported format: {file_format}")
                return []
            
            logger.info(f"Loaded {len(materials)} materials")
            return materials
            
        except Exception as e:
            logger.error(f"Error loading materials: {e}")
            return []
    
    def load_price_list(self, file_path: str, file_format: str = 'auto') -> List[PriceListItem]:
        """
        Загрузка прайс-листа из файла
        
        Args:
            file_path: Путь к файлу с прайс-листом
            file_format: Формат файла ('csv', 'excel', 'json', 'auto')
            
        Returns:
            Список загруженных элементов прайс-листа
        """
        logger.info(f"Loading price list from {file_path}")
        
        path = Path(file_path)
        if not path.exists():
            logger.error(f"File not found: {file_path}")
            return []
        
        # Автоопределение формата
        if file_format == 'auto':
            extension = path.suffix.lower()
            if extension in ['.csv']:
                file_format = 'csv'
            elif extension in ['.xlsx', '.xls']:
                file_format = 'excel'
            elif extension in ['.json']:
                file_format = 'json'
            else:
                logger.error(f"Unsupported file format: {extension}")
                return []
        
        try:
            if file_format == 'csv':
                price_items = PriceListLoader.load_from_csv(str(path))
            elif file_format == 'excel':
                price_items = PriceListLoader.load_from_excel(str(path))
            elif file_format == 'json':
                # Принудительно включаем оптимизацию для больших JSON файлов
                file_size_mb = path.stat().st_size / (1024 * 1024)
                use_optimized = file_size_mb > 5  # Файлы больше 5MB
                price_items = PriceListLoader.load_from_json(str(path), use_optimized=use_optimized)
            else:
                logger.error(f"Unsupported format: {file_format}")
                return []
            
            logger.info(f"Loaded {len(price_items)} price list items")
            return price_items
            
        except Exception as e:
            logger.error(f"Error loading price list: {e}")
            return []
    
    def enable_bypass_mode(self, price_items: List[PriceListItem]) -> bool:
        """
        Включает режим работы без Elasticsearch с данными в памяти
        
        Args:
            price_items: Список элементов прайс-листа для работы в памяти
            
        Returns:
            True если режим успешно включен
        """
        try:
            logger.info(f"Enabling bypass mode with {len(price_items)} price list items")
            
            # Пересоздаем matching service с данными в памяти
            # ВНИМАНИЕ: Оптимизированный сервис НЕ поддерживает bypass mode
            # так как он всегда использует Elasticsearch правильно
            logger.warning("Bypass mode not recommended with optimized service - performance is already optimal")
            self.matching_service = OptimizedMatchingService(
                self.es_service,
                self.similarity_service
            )
            
            logger.info("Bypass mode enabled successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error enabling bypass mode: {e}")
            return False
    
    def index_data(self, materials: List[Material] = None, price_items: List[PriceListItem] = None) -> bool:
        """
        ОПТИМИЗИРОВАННАЯ индексация данных в Elasticsearch с мониторингом производительности
        
        Args:
            materials: Список материалов для индексации
            price_items: Список элементов прайс-листа для индексации
            
        Returns:
            True если индексация прошла успешно
        """
        success = True
        total_start_time = time.time()
        
        # Проверка подключения к Elasticsearch
        if not self.es_service.check_connection():
            logger.error("Elasticsearch connection failed")
            return False
        
        logger.info(f"Starting optimized bulk indexing (bulk_size={self.es_service.bulk_size}, workers={self.es_service.max_workers})")
        
        if materials:
            logger.info(f"Bulk indexing {len(materials)} materials...")
            materials_start = time.time()
            # Материалы больше не индексируются в оптимизированной версии
            # так как поиск происходит только по прайс-листу
            logger.info("Skipping materials indexing (not needed in optimized version)")
            if False:  # Отключаем индексацию материалов
                success = False
            else:
                materials_time = time.time() - materials_start
                logger.info(f"Materials indexing completed in {materials_time:.2f}s")
        
        if price_items:
            logger.info(f"Bulk indexing {len(price_items)} price list items...")
            price_start = time.time()
            if not self.es_service.index_price_list_optimized(price_items):
                success = False
            else:
                price_time = time.time() - price_start
                logger.info(f"Price list indexing completed in {price_time:.2f}s")
        
        # Оптимизация индексов происходит автоматически в оптимизированной версии
        
        total_time = time.time() - total_start_time
        
        # Логирование статистики производительности
        if success:
            logger.info("=== Статистика производительности ===")
            logger.info(f"Total indexing time: {total_time:.2f}s")
            if price_items:
                logger.info(f"Documents indexed: {len(price_items)}")
                logger.info(f"Average docs/sec: {len(price_items) / total_time:.1f}")
        
        return success
    
    def run_matching(self, materials: List[Material] = None, price_items: List[PriceListItem] = None, 
                     similarity_threshold: float = None, max_results: int = None, 
                     progress_callback=None, **kwargs) -> Dict[str, List]:
        """
        Запуск процесса сопоставления материалов с прайс-листом
        
        Args:
            materials: Список материалов для сопоставления (если None, загружаются все из индекса)
            price_items: Список элементов прайс-листа (не используется в текущей реализации, так как данные загружаются из индекса)
            similarity_threshold: Порог схожести для фильтрации результатов
            max_results: Максимальное количество результатов на материал
            progress_callback: Функция для отслеживания прогресса
            **kwargs: Дополнительные параметры для совместимости с GUI
            
        Returns:
            Результаты сопоставления
        """
        if materials is None:
            logger.info("Loading all materials from index...")
            try:
                es_materials = self.es_service.get_all_materials()
                materials = [Material.from_dict(item['_source']) for item in es_materials]
                logger.info(f"Loaded {len(materials)} materials from Elasticsearch")
            except Exception as e:
                logger.warning(f"Failed to load materials from Elasticsearch: {e}")
                # В режиме обхода материалы должны быть переданы в метод
                # Если не переданы, пытаемся получить из matching_service
                if hasattr(self.matching_service, '_cached_materials'):
                    materials = self.matching_service._cached_materials
                    logger.info(f"Using {len(materials)} cached materials from bypass mode")
                else:
                    materials = []
        
        if not materials:
            logger.warning("No materials found for matching")
            return {}
        
        logger.info(f"Starting matching process for {len(materials)} materials...")
        start_time = time.time()
        
        # Получение параметров из конфигурации или переданных аргументов
        if similarity_threshold is None:
            similarity_threshold = self.config.get('matching', {}).get('similarity_threshold', 20.0)
        if max_results is None:
            max_results = self.config.get('matching', {}).get('max_results_per_material', 4)
        max_workers = self.config.get('matching', {}).get('max_workers', 4)
        
        results = self.matching_service.match_materials_batch(
            materials,
            similarity_threshold=similarity_threshold,
            max_results_per_material=max_results,
            max_workers=max_workers,
            progress_callback=progress_callback
        )
        
        end_time = time.time()
        logger.info(f"Matching completed in {end_time - start_time:.2f} seconds")
        
        # Получение статистики
        stats = self.matching_service.get_matching_statistics(results)
        logger.info(f"Matching statistics: {stats}")
        
        return results
    
    def export_results(self, results: Dict[str, List], output_path: str, export_format: str = 'json'):
        """
        Экспорт результатов в файл
        
        Args:
            results: Результаты сопоставления
            output_path: Путь для сохранения результатов
            export_format: Формат экспорта ('json', 'csv')
        """
        logger.info(f"Exporting results to {output_path}")
        
        # Преобразуем результаты в словари
        export_data = []
        for material_id, matches in results.items():
            for match in matches:
                export_data.append(match.to_dict())
        
        try:
            if export_format == 'json':
                DataExporter.export_results_to_json(export_data, output_path)
            elif export_format == 'csv':
                DataExporter.export_results_to_csv(export_data, output_path)
            elif export_format == 'xlsx':
                DataExporter.export_results_to_xlsx(export_data, output_path)
            else:
                logger.error(f"Unsupported export format: {export_format}")
                return
            
            logger.info(f"Results exported successfully to {output_path}")
            
        except Exception as e:
            logger.error(f"Error exporting results: {e}")
    
    def get_material_matches(self, material_id: str, top_n: int = 5) -> List[Dict[str, Any]]:
        """
        Получение соответствий для конкретного материала
        
        Args:
            material_id: ID материала
            top_n: Количество лучших результатов
            
        Returns:
            Список соответствий
        """
        material_data = self.es_service.get_material_by_id(material_id)
        if not material_data:
            logger.error(f"Material with ID {material_id} not found")
            return []
        
        material = Material.from_dict(material_data['_source'])
        matches = self.matching_service.find_best_matches_for_material(material, top_n)
        
        return [match.to_dict() for match in matches]
    
    def search_material_by_name(self, material_name: str, top_n: int = 10) -> List[Dict[str, Any]]:
        """
        Поиск соответствий для материала по названию
        
        Args:
            material_name: Название материала для поиска
            top_n: Количество лучших результатов
            
        Returns:
            Список соответствий
        """
        # В оптимизированной версии используем прямой поиск
        try:
            # Проверяем, есть ли метод быстрого поиска в matching_service
            if hasattr(self.matching_service, 'search_material_by_name'):
                return self.matching_service.search_material_by_name(
                    material_name, top_n,
                    self.config.get('matching', {}).get('similarity_threshold', 20.0)
                )
            else:
                # Fallback для старого API
                # Используем название и как description для лучшего сопоставления
                material = Material(
                    id="search_temp",
                    name=material_name,
                    description=material_name  # Дублируем название в description для поиска
                )

                threshold = self.config.get('matching', {}).get('similarity_threshold', 20.0)
                matches = self.matching_service.match_material_with_price_list(
                    material,
                    similarity_threshold=threshold,
                    max_results=top_n
                )

                return [match.to_dict() for match in matches]
            
        except Exception as e:
            logger.error(f"Error searching material by name '{material_name}': {e}")
            return []


def create_sample_config() -> Dict[str, Any]:
    """
    ОПТИМИЗАЦИЯ 26: Создание оптимизированного примера конфигурации
    """
    return {
        "elasticsearch": {
            "host": "localhost",
            "port": 9200,
            "username": None,
            "password": None,
            # ПРОИЗВОДИТЕЛЬНОСТЬ: Оптимизированные настройки для bulk операций
            "bulk_size": 750,      # Увеличенный размер батча для лучшей производительности
            "max_workers": 4       # 4 потока оптимально для большинства систем
        },
        "matching": {
            "similarity_threshold": 20.0,
            "max_results_per_material": 4,
            "max_workers": 4
        },
        # МОНИТОРИНГ: Дополнительные настройки для отслеживания производительности
        "performance": {
            "log_detailed_stats": True,        # Подробная статистика производительности
            "optimize_after_indexing": True,   # Автоматическая оптимизация после индексации
            "health_check_before_indexing": True  # Проверка здоровья кластера перед индексацией
        }
    }


def main():
    """Главная функция для запуска приложения из командной строки"""
    parser = argparse.ArgumentParser(description="Material Matching Application")
    
    parser.add_argument('--config', type=str, help='Path to configuration file')
    parser.add_argument('--materials', type=str, help='Path to materials file')
    parser.add_argument('--price-list', type=str, help='Path to price list file')
    parser.add_argument('--output', type=str, default='results.json', help='Output file path')
    parser.add_argument('--format', type=str, choices=['json', 'csv', 'xlsx'], default='json', help='Output format')
    parser.add_argument('--setup', action='store_true', help='Setup Elasticsearch indices')
    parser.add_argument('--threshold', type=float, default=20.0, help='Similarity threshold (0-100)')
    
    args = parser.parse_args()
    
    # Загрузка конфигурации
    config = None
    if args.config and Path(args.config).exists():
        with open(args.config, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    # Обновление конфигурации из аргументов командной строки
    if config is None:
        config = create_sample_config()
    
    if args.threshold:
        config['matching']['similarity_threshold'] = args.threshold
    
    # Инициализация приложения
    app = MaterialMatcherApp(config)
    
    # Создание индексов если требуется
    if args.setup:
        if not app.setup_indices():
            sys.exit(1)
    
    # Загрузка и индексация данных
    materials = []
    price_items = []
    
    if args.materials:
        materials = app.load_materials(args.materials)
        if not materials:
            sys.exit(1)
    
    if args.price_list:
        price_items = app.load_price_list(args.price_list)
        if not price_items:
            sys.exit(1)
    
    if materials or price_items:
        if not app.index_data(materials, price_items):
            logger.error("Failed to index data")
            sys.exit(1)
    
    # Запуск сопоставления
    if materials:
        results = app.run_matching(materials)
        
        if results:
            app.export_results(results, args.output, args.format)
            logger.info(f"Process completed. Results saved to {args.output}")
        else:
            logger.warning("No results to export")
    else:
        logger.info("No materials provided for matching")


if __name__ == '__main__':
    main()