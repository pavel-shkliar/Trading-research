"""Общий helper для запросов к Binance Futures API — используется всеми
download_*.py скриптами, которые тянут данные с Binance, чтобы не
дублировать код запроса в каждом файле."""

import requests

BASE_URL = "https://fapi.binance.com"


def get(endpoint: str, params: dict):
    """Делает GET-запрос к Binance Futures API и возвращает распарсенный JSON.
    Бросает исключение с понятным сообщением, если Binance вернул ошибку."""
    response = requests.get(BASE_URL + endpoint, params=params, timeout=10)
    response.raise_for_status()
    return response.json()
