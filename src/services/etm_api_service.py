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

    def __init__(self, base_url: str = "https://ipro.etm.ru", timeout: int = 30):
        """
        Инициализация ETM API сервиса

        Args:
            base_url: Базовый URL ETM API
            timeout: Таймаут для запросов в секундах
        """
        self.base_url = base_url
        self.timeout = timeout
        self.session = requests.Session()
        self.session_id = None
        self.login = "81134380uai"
        self.password = "hbQE8d28"

    def authenticate(self) -> bool:
        """
        Авторизация в ETM API

        Returns:
            bool: True если авторизация успешна, False в противном случае
        """
        try:
            login_url = f"{self.base_url}/api/v1/user/login"
            params = {
                'log': self.login,
                'pwd': self.password
            }

            logger.info(f"Авторизация в ETM API: {login_url}")
            response = self.session.get(login_url, params=params, timeout=self.timeout)

            if response.status_code == 200:
                data = response.json()
                # Session находится в data.session
                if 'data' in data and 'session' in data['data']:
                    self.session_id = data['data']['session']
                    logger.info(f"ETM API: Авторизация успешна, session: {self.session_id}")
                    return True
                else:
                    logger.error(f"ETM API: Отсутствует session в ответе: {data}")
                    return False
            else:
                logger.error(f"ETM API: Ошибка авторизации {response.status_code}: {response.text}")
                return False

        except (requests.RequestException, requests.Timeout) as e:
            logger.error(f"ETM API: Ошибка сети при авторизации: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"ETM API: Неожиданная ошибка авторизации: {str(e)}")
            return False

    def check_connectivity(self) -> bool:
        """
        Проверяет доступность ETM API сервера через авторизацию

        Returns:
            bool: True если сервер доступен, False в противном случае
        """
        return self.authenticate()

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

        # Проверяем авторизацию
        if not self.session_id:
            if not self.authenticate():
                raise EtmApiError("Не удалось авторизоваться в ETM API")

        try:
            prices = {}
            total_codes = len(etm_codes)

            # Обрабатываем коды пакетами до 50 штук
            batch_size = 50
            for i in range(0, total_codes, batch_size):
                batch = etm_codes[i:i + batch_size]

                # Реальный запрос к ETM API
                batch_prices = self._fetch_prices_batch(batch)
                prices.update(batch_prices)

                # Обновляем прогресс
                if progress_callback:
                    progress = min(i + batch_size, total_codes)
                    progress_callback(progress, total_codes)

                # Задержка 1.1 секунды между пакетными запросами
                time.sleep(1.1)

            return prices

        except requests.RequestException as e:
            raise EtmApiError(f"Ошибка запроса к ETM API: {str(e)}")
        except Exception as e:
            raise EtmApiError(f"Неожиданная ошибка ETM API: {str(e)}")

    def _fetch_prices_batch(self, etm_codes: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Получает цены для пакета ETM кодов через реальный ETM API

        Args:
            etm_codes: Список ETM кодов (до 50 штук)

        Returns:
            Dict: Цены для указанных кодов
        """
        if not self.session_id:
            logger.error("ETM API: Нет активной сессии для запроса цен")
            return {}

        try:
            # Формируем строку с кодами через %2C (URL-encoded запятая)
            codes_string = "%2C".join(etm_codes)

            # URL для запроса цен: https://ipro.etm.ru/api/v1/goods/{codes}/price?type=etm&session-id={session}
            price_url = f"{self.base_url}/api/v1/goods/{codes_string}/price"
            params = {
                'type': 'etm',
                'session-id': self.session_id
            }

            logger.info(f"ETM API: Запрос цен для {len(etm_codes)} кодов")
            response = self.session.get(price_url, params=params, timeout=self.timeout)

            if response.status_code == 200:
                data = response.json()
                batch_prices = {}

                # Проверяем правильную структуру ответа ETM API
                if (isinstance(data, dict) and
                    'data' in data and
                    'rows' in data['data'] and
                    isinstance(data['data']['rows'], list)):

                    # Создаем словарь для быстрого поиска по gdscode
                    rows_by_code = {}
                    for row in data['data']['rows']:
                        if 'gdscode' in row:
                            rows_by_code[str(row['gdscode'])] = row

                    # Обрабатываем каждый запрошенный код
                    for code in etm_codes:
                        if str(code) in rows_by_code:
                            row_data = rows_by_code[str(code)]
                            # Извлекаем цену из поля pricewnds
                            price = row_data.get('pricewnds')

                            batch_prices[code] = {
                                'price': price,
                                'currency': 'RUB',
                                'availability': 'В наличии' if price and price > 0 else 'Нет цены',
                                'last_updated': time.strftime('%Y-%m-%d %H:%M:%S'),
                                'raw_data': row_data  # Сохраняем полные данные для отладки
                            }
                        else:
                            # Код не найден в ответе
                            batch_prices[code] = {
                                'price': None,
                                'currency': 'RUB',
                                'availability': 'Не найден',
                                'last_updated': time.strftime('%Y-%m-%d %H:%M:%S')
                            }

                    logger.info(f"ETM API: Получены цены для {len(batch_prices)} кодов из {len(data['data']['rows'])} строк")
                    return batch_prices
                else:
                    logger.error(f"ETM API: Неожиданная структура ответа: {data}")
                    return {}
            else:
                logger.error(f"ETM API: Ошибка запроса цен {response.status_code}: {response.text}")
                return {}

        except requests.RequestException as e:
            logger.error(f"ETM API: Ошибка сети при запросе цен: {str(e)}")
            return {}
        except Exception as e:
            logger.error(f"ETM API: Неожиданная ошибка при запросе цен: {str(e)}")
            return {}


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