"""Общий helper для запросов к публичному Deribit API — опционные метрики."""

import requests

BASE_URL = "https://www.deribit.com/api/v2"


def get(endpoint: str, params: dict):
    """Делает GET-запрос к Deribit API и возвращает поле "result" ответа."""
    response = requests.get(BASE_URL + endpoint, params=params, timeout=10)
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise RuntimeError(f"Deribit API error: {payload['error']}")
    return payload["result"]
