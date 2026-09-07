"""Shared HTTP client for the Binance Futures API."""

import requests

BASE_URL = "https://fapi.binance.com"


def get(endpoint: str, params: dict):
    response = requests.get(BASE_URL + endpoint, params=params, timeout=10)
    response.raise_for_status()
    return response.json()
