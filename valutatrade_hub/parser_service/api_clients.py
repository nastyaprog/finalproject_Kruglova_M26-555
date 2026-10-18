# valutatrade_hub/parser_service/api_clients.py
from abc import ABC, abstractmethod

import requests

from .config import config


class ApiRequestError(Exception):
    pass

class BaseApiClient(ABC):
    @abstractmethod
    def fetch_rates(self) -> dict[str, float]:
        pass

class CoinGeckoClient(BaseApiClient):
    def __init__(self):
        self.url = config.COINGECKO_URL
        self.timeout = config.REQUEST_TIMEOUT
        ids = list(config.CRYPTO_ID_MAP.values())
        self.ids_str = ",".join(ids)
        self.vs_currencies = config.BASE_CURRENCY.lower()

    def fetch_rates(self) -> dict[str, float]:
        params = {
            "ids": self.ids_str,
            "vs_currencies": self.vs_currencies,
        }
        try:
            resp = requests.get(self.url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as e:
            raise ApiRequestError(f"CoinGecko network error: {e}") from e
        except ValueError as e:
            raise ApiRequestError("CoinGecko returned invalid JSON") from e

        rates = {}
        for code, id_name in config.CRYPTO_ID_MAP.items():
            coin_data = data.get(id_name, {})
            rate = coin_data.get(config.BASE_CURRENCY.lower())
            if rate is not None:
                rates[f"{code}_{config.BASE_CURRENCY}"] = float(rate)
        return rates

class ExchangeRateApiClient(BaseApiClient):
    def __init__(self):
        if not config.EXCHANGERATE_API_KEY:
            raise ValueError("EXCHANGERATE_API_KEY not set in environment")
        self.base_url = f"{config.EXCHANGERATE_API_URL}/{config.EXCHANGERATE_API_KEY}"
        self.timeout = config.REQUEST_TIMEOUT

    def fetch_rates(self) -> dict[str, float]:
        url = f"{self.base_url}/latest/{config.BASE_CURRENCY}"
        try:
            resp = requests.get(url, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as e:
            raise ApiRequestError(f"ExchangeRate-API network error: {e}") from e
        except ValueError as e:
            raise ApiRequestError("ExchangeRate-API returned invalid JSON") from e

        if data.get("result") != "success":
            raise ApiRequestError(f"ExchangeRate-API error: {data.get('error-type', 'unknown')}")

        rates_dict = data.get("rates", {})
        rates = {}
        base = config.BASE_CURRENCY
        for currency in config.FIAT_CURRENCIES:
            rate = rates_dict.get(currency)
            if rate is not None:
                rates[f"{currency}_{base}"] = float(rate)
        return rates
