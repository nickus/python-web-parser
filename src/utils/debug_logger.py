import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import json


class DebugLogger:
    """
    Продвинутый логгер для отладки процесса сопоставления материалов
    """
    
    def __init__(self, log_level: str = "INFO", log_to_console: bool = True, log_to_file: bool = True):
        self.logger_name = "MaterialMatcherDebug"
        self.logger = logging.getLogger(self.logger_name)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        # Очищаем существующие обработчики
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Создаем директорию для логов
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # Формат сообщений
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(funcName)-20s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Консольный вывод
        if log_to_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
        
        # Файловый вывод
        if log_to_file:
            # Основной лог-файл
            main_log_file = log_dir / f"material_matcher_debug_{datetime.now().strftime('%Y%m%d')}.log"
            file_handler = logging.FileHandler(main_log_file, encoding='utf-8')
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
            
            # Детальный лог только для сопоставлений
            self.detailed_log_file = log_dir / f"matching_details_{datetime.now().strftime('%Y%m%d')}.log"
            self.detailed_handler = logging.FileHandler(self.detailed_log_file, encoding='utf-8')
            detailed_formatter = logging.Formatter(
                '%(asctime)s | MATCH | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            self.detailed_handler.setFormatter(detailed_formatter)
            self.detailed_handler.setLevel(logging.DEBUG)
        
        self.logger.info(f"=== DebugLogger инициализирован (уровень: {log_level}) ===")
    
    def log_matching_process(self, material_name: str, price_item_name: str, 
                           similarities: Dict[str, float], total_similarity: float,
                           details: Optional[Dict[str, Any]] = None):
        """
        Детальное логирование процесса сопоставления
        """
        message_parts = [
            f"СОПОСТАВЛЕНИЕ:",
            f"  Материал: '{material_name}'",
            f"  Прайс-позиция: '{price_item_name}'",
            f"  Общая схожесть: {total_similarity:.2f}%",
            f"  Детали схожести:"
        ]
        
        for field, similarity in similarities.items():
            message_parts.append(f"    - {field}: {similarity:.3f} ({similarity*100:.1f}%)")
        
        if details:
            message_parts.append("  Дополнительные детали:")
            for key, value in details.items():
                if isinstance(value, (dict, list)):
                    message_parts.append(f"    - {key}: {json.dumps(value, ensure_ascii=False, indent=6)}")
                else:
                    message_parts.append(f"    - {key}: {value}")
        
        message = "\n".join(message_parts)
        
        # Логируем в основной лог
        self.logger.info(f"Сопоставление: {material_name} <-> {price_item_name} = {total_similarity:.1f}%")
        
        # Логируем детали в специальный файл
        if hasattr(self, 'detailed_handler'):
            detailed_logger = logging.getLogger(f"{self.logger_name}_detailed")
            detailed_logger.setLevel(logging.DEBUG)
            if not detailed_logger.handlers:
                detailed_logger.addHandler(self.detailed_handler)
            detailed_logger.debug(message)
    
    def log_normalization(self, original_text: str, normalized_text: str):
        """
        Логирование процесса нормализации текста
        """
        if original_text != normalized_text:
            self.logger.debug(f"НОРМАЛИЗАЦИЯ: '{original_text}' -> '{normalized_text}'")
    
    def log_encoding_detection(self, file_path: str, detected_encoding: str, confidence: float):
        """
        Логирование определения кодировки файла
        """
        self.logger.info(f"КОДИРОВКА: {file_path} определена как {detected_encoding} (уверенность: {confidence:.2f})")
    
    def log_file_loading(self, file_path: str, items_loaded: int, loading_time: float):
        """
        Логирование загрузки файлов
        """
        self.logger.info(f"ЗАГРУЗКА: {file_path} - загружено {items_loaded} элементов за {loading_time:.2f}с")
    
    def log_elasticsearch_query(self, material_name: str, query: Dict[str, Any], results_count: int):
        """
        Логирование запросов к Elasticsearch
        """
        self.logger.debug(f"ES ЗАПРОС для '{material_name}': найдено {results_count} результатов")
        self.logger.debug(f"ES QUERY: {json.dumps(query, ensure_ascii=False, indent=2)}")
    
    def log_performance_metrics(self, operation: str, duration: float, items_processed: int = None):
        """
        Логирование метрик производительности
        """
        if items_processed:
            items_per_sec = items_processed / duration if duration > 0 else 0
            self.logger.info(f"ПРОИЗВОДИТЕЛЬНОСТЬ: {operation} - {duration:.2f}с, {items_processed} элементов, {items_per_sec:.1f} элементов/сек")
        else:
            self.logger.info(f"ПРОИЗВОДИТЕЛЬНОСТЬ: {operation} - {duration:.2f}с")
    
    def log_error(self, error_type: str, error_message: str, context: Optional[Dict[str, Any]] = None):
        """
        Логирование ошибок с контекстом
        """
        message_parts = [f"ОШИБКА ({error_type}): {error_message}"]
        
        if context:
            message_parts.append("Контекст:")
            for key, value in context.items():
                message_parts.append(f"  - {key}: {value}")
        
        self.logger.error("\n".join(message_parts))
    
    def get_log_content(self, log_type: str = "main") -> str:
        """
        Получение содержимого лог-файла для копирования
        """
        try:
            if log_type == "detailed" and hasattr(self, 'detailed_log_file'):
                with open(self.detailed_log_file, 'r', encoding='utf-8') as f:
                    return f.read()
            else:
                # Находим основной лог-файл
                log_dir = Path("logs")
                main_log_files = list(log_dir.glob(f"material_matcher_debug_{datetime.now().strftime('%Y%m%d')}*.log"))
                if main_log_files:
                    with open(main_log_files[0], 'r', encoding='utf-8') as f:
                        return f.read()
        except Exception as e:
            self.logger.error(f"Ошибка при чтении лог-файла: {e}")
            return f"Ошибка при чтении лог-файла: {e}"
        
        return "Лог-файл не найден"
    
    def clear_logs(self):
        """
        Очистка лог-файлов
        """
        try:
            log_dir = Path("logs")
            for log_file in log_dir.glob("*.log"):
                log_file.unlink()
            self.logger.info("Лог-файлы очищены")
        except Exception as e:
            self.logger.error(f"Ошибка при очистке лог-файлов: {e}")


# Глобальный экземпляр логгера
debug_logger = None

def get_debug_logger(log_level: str = "INFO") -> DebugLogger:
    """
    Получение глобального экземпляра отладочного логгера
    """
    global debug_logger
    if debug_logger is None:
        debug_logger = DebugLogger(log_level=log_level)
    return debug_logger

def init_debug_logging(log_level: str = "INFO", log_to_console: bool = True, log_to_file: bool = True):
    """
    Инициализация системы отладочного логирования
    """
    global debug_logger
    debug_logger = DebugLogger(log_level=log_level, log_to_console=log_to_console, log_to_file=log_to_file)
    return debug_logger