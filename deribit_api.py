"""Shared HTTP client for the public Deribit API (options metrics)."""

import requests

BASE_URL = "https://www.deribit.com/api/v2"


def get(endpoint: str, params: dict):
    response = requests.get(BASE_URL + endpoint, params=params, timeout=10)
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise RuntimeError(f"Deribit API error: {payload['error']}")
    return payload["result"]
