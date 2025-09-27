#!/usr/bin/env python3
"""
Сверхбыстрый загрузчик JSON с многопоточной обработкой и оптимизациями
Использует ujson для быстрого парсинга и multiprocessing для параллельной обработки
"""

import json
import time
from typing import List, Dict, Any, Callable, Optional
from pathlib import Path
from datetime import datetime
import logging
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import multiprocessing as mp
from functools import partial

# Попытка использовать ujson для ускорения парсинга
try:
    import ujson as fast_json
    JSON_PARSER = "ujson"
except ImportError:
    try:
        import orjson as fast_json
        JSON_PARSER = "orjson"
        # orjson возвращает bytes, нужна конвертация
        def loads(data):
            if isinstance(data, bytes):
                return fast_json.loads(data)
            return fast_json.loads(data.encode())
        fast_json.loads = loads
    except ImportError:
        import json as fast_json
        JSON_PARSER = "json"

from ..models.material import PriceListItem

logger = logging.getLogger(__name__)


def process_chunk(chunk_data: List[Dict[str, Any]], chunk_id: int) -> List[PriceListItem]:
    """
    Обработка чанка данных в отдельном процессе

    Args:
        chunk_data: Список словарей для обработки
        chunk_id: ID чанка для отладки

    Returns:
        Список PriceListItem
    """
    price_items = []

    for item in chunk_data:
        price_item = convert_to_price_item_fast(item)
        if price_item:
            price_items.append(price_item)

    return price_items


def convert_to_price_item_fast(item: Dict[str, Any]) -> Optional[PriceListItem]:
    """
    Быстрая конвертация словаря в PriceListItem
    Оптимизированная версия без сложного маппинга
    """
    try:
        # Быстрое извлечение основных полей
        name = (item.get('name') or
                item.get('material_name') or
                item.get('наименование') or
                item.get('title', ''))

        if not name:
            return None

        # Быстрое создание объекта с минимальными проверками
        return PriceListItem(
            id=str(item.get('id', item.get('_id', ''))),
            name=str(name)[:500],  # Ограничиваем длину
            brand=str(item.get('brand', item.get('бренд', '')))[:100],
            article=str(item.get('article', item.get('артикул', '')))[:100],
            brand_code=str(item.get('brand_code', ''))[:100],
            cli_code=str(item.get('cli_code', ''))[:100],
            material_class=str(item.get('class', item.get('material_class', '')))[:200],
            class_code=str(item.get('class_code', ''))[:50],
            price=float(item.get('price', item.get('цена', 0.0))),
            material_name=str(name)[:500],
            description=str(item.get('description', item.get('описание', '')))[:1000],
            currency=str(item.get('currency', 'RUB'))[:10],
            supplier=str(item.get('supplier', item.get('поставщик', '')))[:200],
            category=item.get('category'),
            unit=item.get('unit'),
            specifications=item.get('specifications', {}),
            updated_at=datetime.now().isoformat()
        )
    except Exception:
        return None


def load_json_fast(file_path: str,
                  progress_callback: Optional[Callable] = None,
                  chunk_size: int = 50000,
                  max_workers: Optional[int] = None) -> List[PriceListItem]:
    """
    Сверхбыстрая загрузка JSON с многопоточной обработкой

    Args:
        file_path: Путь к JSON файлу
        progress_callback: Функция для отображения прогресса
        chunk_size: Размер чанка для параллельной обработки
        max_workers: Количество потоков (по умолчанию CPU count)

    Returns:
        Список PriceListItem
    """
    print(f"[INFO] Запуск сверхбыстрого загрузчика JSON (парсер: {JSON_PARSER})")
    start_time = time.time()

    # Определяем количество процессоров
    if max_workers is None:
        max_workers = min(mp.cpu_count(), 8)  # Ограничиваем максимум 8 процессами

    print(f"[INFO] Используется {max_workers} потоков для обработки")

    try:
        # Этап 1: Быстрое чтение файла
        load_start = time.time()
        with open(file_path, 'r', encoding='utf-8') as file:
            data = fast_json.load(file)
        load_time = time.time() - load_start

        if not isinstance(data, list):
            print("[ERROR] JSON файл должен содержать массив объектов")
            return []

        total_items = len(data)
        print(f"[INFO] Файл загружен за {load_time:.2f}с, найдено {total_items} записей")

        # Этап 2: Разделение на чанки
        chunks = []
        for i in range(0, total_items, chunk_size):
            chunk = data[i:i + chunk_size]
            chunks.append(chunk)

        print(f"[INFO] Данные разделены на {len(chunks)} чанков по {chunk_size} записей")

        # Этап 3: Параллельная обработка
        process_start = time.time()
        all_price_items = []
        processed_items = 0

        # Используем ThreadPoolExecutor для I/O операций или ProcessPoolExecutor для CPU-intensive
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Запускаем все чанки на обработку
            future_to_chunk = {
                executor.submit(process_chunk, chunk, i): i
                for i, chunk in enumerate(chunks)
            }

            # Собираем результаты по мере готовности
            for future in future_to_chunk:
                chunk_id = future_to_chunk[future]
                try:
                    chunk_results = future.result()
                    all_price_items.extend(chunk_results)
                    processed_items += len(chunks[chunk_id])

                    # Обновляем прогресс
                    if progress_callback:
                        elapsed = time.time() - start_time
                        progress_callback(processed_items, total_items, f"{elapsed:.2f}сек")

                    print(f"[INFO] Обработан чанк {chunk_id + 1}/{len(chunks)} "
                          f"({processed_items}/{total_items} записей)")

                except Exception as e:
                    print(f"[ERROR] Ошибка обработки чанка {chunk_id}: {e}")

        process_time = time.time() - process_start
        total_time = time.time() - start_time

        print(f"[OK] Сверхбыстрая загрузка завершена:")
        print(f"     - Загружено: {len(all_price_items)} записей")
        print(f"     - Время загрузки файла: {load_time:.2f}с")
        print(f"     - Время обработки: {process_time:.2f}с")
        print(f"     - Общее время: {total_time:.2f}с")
        print(f"     - Скорость: {len(all_price_items) / total_time:.0f} записей/сек")

        return all_price_items

    except Exception as e:
        print(f"[ERROR] Критическая ошибка в сверхбыстром загрузчике: {e}")
        # Fallback на стандартную загрузку
        return load_json_standard_fallback(file_path, progress_callback)


def load_json_standard_fallback(file_path: str,
                               progress_callback: Optional[Callable] = None) -> List[PriceListItem]:
    """
    Стандартная загрузка как fallback
    """
    print(f"[INFO] Использование стандартного fallback загрузчика")
    start_time = time.time()

    with open(file_path, 'r', encoding='utf-8') as file:
        data = json.load(file)

    if not isinstance(data, list):
        return []

    price_items = []
    total_items = len(data)

    for i, item in enumerate(data):
        price_item = convert_to_price_item_fast(item)
        if price_item:
            price_items.append(price_item)

        # Обновляем прогресс каждые 10000 записей
        if progress_callback and (i + 1) % 10000 == 0:
            elapsed = time.time() - start_time
            progress_callback(i + 1, total_items, f"{elapsed:.2f}сек")

    elapsed_time = time.time() - start_time
    print(f"[OK] Стандартная загрузка завершена: {len(price_items)} записей за {elapsed_time:.2f} секунд")

    return price_items


def install_fast_json_parsers():
    """
    Устанавливает быстрые JSON парсеры
    """
    try:
        import subprocess
        import sys

        print("[INFO] Установка быстрых JSON парсеров...")

        # Устанавливаем ujson (самый быстрый)
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "ujson"])
            print("[OK] ujson установлен успешно")
        except:
            print("[WARNING] Не удалось установить ujson")

        # Устанавливаем orjson как альтернативу
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "orjson"])
            print("[OK] orjson установлен успешно")
        except:
            print("[WARNING] Не удалось установить orjson")

    except Exception as e:
        print(f"[ERROR] Ошибка установки быстрых парсеров: {e}")


if __name__ == "__main__":
    # Тест загрузчика
    import sys
    if len(sys.argv) > 1:
        test_file = sys.argv[1]

        def test_progress(current, total, message):
            print(f"Прогресс: {current}/{total} ({message})")

        start = time.time()
        items = load_json_fast(test_file, test_progress)
        end = time.time()

        print(f"\nФинальный результат:")
        print(f"Загружено: {len(items)} записей")
        print(f"Время: {end - start:.2f} секунд")
        print(f"Скорость: {len(items) / (end - start):.0f} записей/сек")