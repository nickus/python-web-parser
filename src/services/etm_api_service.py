#!/usr/bin/env python3
"""
ETM API сервис для получения актуальных цен на материалы
Предоставляет интерфейс для работы с внешним API ETM системы
"""

import requests
import time
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class EtmApiError(Exception):
    """Кастомное исключение для ошибок ETM API"""
    pass


class EtmApiService:
    """Сервис для работы с ETM API"""

    def __init__(self, base_url: str = "https://api.etm.ru", timeout: int = 30):
        """
        Инициализация ETM API сервиса

        Args:
            base_url: Базовый URL ETM API
            timeout: Таймаут для запросов в секундах
        """
        self.base_url = base_url
        self.timeout = timeout
        self.session = requests.Session()

    def check_connectivity(self) -> bool:
        """
        Проверяет доступность ETM API сервера

        Returns:
            bool: True если сервер доступен, False в противном случае
        """
        try:
            # Простая проверка доступности сервера
            response = self.session.get(
                f"{self.base_url}/ping",
                timeout=self.timeout
            )
            return response.status_code == 200
        except (requests.RequestException, requests.Timeout):
            logger.warning("ETM API сервер недоступен")
            return False

    def get_prices_by_codes(self, etm_codes: List[str], progress_callback=None) -> Dict[str, Dict[str, Any]]:
        """
        Получает цены по списку ETM кодов

        Args:
            etm_codes: Список ETM кодов для запроса цен
            progress_callback: Функция обратного вызова для отслеживания прогресса

        Returns:
            Dict: Словарь с ценами по ETM кодам

        Raises:
            EtmApiError: При ошибках запроса к API
        """
        if not etm_codes:
            return {}

        try:
            prices = {}
            total_codes = len(etm_codes)

            # Обрабатываем коды пакетами для оптимизации
            batch_size = 50
            for i in range(0, total_codes, batch_size):
                batch = etm_codes[i:i + batch_size]

                # Имитируем запрос к API (заглушка)
                # В реальной реализации здесь будет запрос к ETM API
                batch_prices = self._fetch_prices_batch(batch)
                prices.update(batch_prices)

                # Обновляем прогресс
                if progress_callback:
                    progress = min(i + batch_size, total_codes)
                    progress_callback(progress, total_codes)

                # Небольшая задержка для избежания перегрузки API
                time.sleep(0.1)

            return prices

        except requests.RequestException as e:
            raise EtmApiError(f"Ошибка запроса к ETM API: {str(e)}")
        except Exception as e:
            raise EtmApiError(f"Неожиданная ошибка ETM API: {str(e)}")

    def _fetch_prices_batch(self, etm_codes: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Получает цены для пакета ETM кодов

        Args:
            etm_codes: Список ETM кодов

        Returns:
            Dict: Цены для указанных кодов
        """
        # Заглушка для демонстрации
        # В реальной реализации здесь будет HTTP запрос к ETM API
        batch_prices = {}

        for code in etm_codes:
            # Имитируем получение цены
            batch_prices[code] = {
                'price': round(100.0 + hash(code) % 10000, 2),  # Случайная цена
                'currency': 'RUB',
                'availability': 'В наличии',
                'last_updated': time.strftime('%Y-%m-%d %H:%M:%S')
            }

        return batch_prices


# Глобальный экземпляр сервиса
_etm_service_instance: Optional[EtmApiService] = None


def get_etm_service() -> EtmApiService:
    """
    Получает глобальный экземпляр ETM API сервиса

    Returns:
        EtmApiService: Экземпляр сервиса
    """
    global _etm_service_instance

    if _etm_service_instance is None:
        _etm_service_instance = EtmApiService()

    return _etm_service_instance


def configure_etm_service(base_url: str = None, timeout: int = None) -> None:
    """
    Настраивает параметры ETM API сервиса

    Args:
        base_url: Новый базовый URL
        timeout: Новый таймаут
    """
    global _etm_service_instance

    kwargs = {}
    if base_url is not None:
        kwargs['base_url'] = base_url
    if timeout is not None:
        kwargs['timeout'] = timeout

    _etm_service_instance = EtmApiService(**kwargs)