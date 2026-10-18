"""
Модуль валют: абстрактный базовый класс Currency и наследники FiatCurrency, CryptoCurrency.
Фабрика get_currency() и реестр поддерживаемых валют.
"""

from abc import ABC, abstractmethod

from valutatrade_hub.core.exceptions import CurrencyNotFoundError


class Currency(ABC):
    """Абстрактный базовый класс валюты с унифицированным интерфейсом."""

    def __init__(self, code: str, name: str) -> None:
        """
        Инициализирует валюту.

        Args:
            code: ISO-код или тикер (верхний регистр, 2–5 символов).
            name: Человекочитаемое имя валюты.

        Raises:
            ValueError: Если код не соответствует требованиям.
        """
        code_upper = code.strip().upper()
        if not (2 <= len(code_upper) <= 5) or not code_upper.isalnum():
            raise ValueError(f"Некорректный код валюты: '{code}'. Требуется 2–5 букв/цифр.")
        if not name or not name.strip():
            raise ValueError("Имя валюты не может быть пустым.")

        self._code = code_upper
        self._name = name.strip()

    @property
    def code(self) -> str:
        """Возвращает код валюты (в верхнем регистре)."""
        return self._code

    @property
    def name(self) -> str:
        """Возвращает имя валюты."""
        return self._name

    @abstractmethod
    def get_display_info(self) -> str:
        """
        Возвращает человекочитаемую строку для UI/логов.

        Returns:
            Строковое представление валюты.
        """


class FiatCurrency(Currency):
    """Валюта фиатного типа (государственная валюта)."""

    def __init__(self, code: str, name: str, issuing_country: str) -> None:
        """
        Инициализирует фиатную валюту.

        Args:
            code: Код валюты.
            name: Имя валюты.
            issuing_country: Страна или зона эмиссии.
        """
        super().__init__(code, name)
        if not issuing_country or not issuing_country.strip():
            raise ValueError("Страна эмиссии не может быть пустой.")
        self._issuing_country = issuing_country.strip()

    def get_display_info(self) -> str:
        """
        Возвращает строку вида: [FIAT] USD — US Dollar (Issuing: United States).

        Returns:
            Строковое представление фиатной валюты.
        """
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self._issuing_country})"


class CryptoCurrency(Currency):
    """Криптовалюта с техническими атрибутами."""

    def __init__(
        self,
        code: str,
        name: str,
        algorithm: str,
        market_cap: float,
    ) -> None:
        """
        Инициализирует криптовалюту.

        Args:
            code: Код криптовалюты.
            name: Имя криптовалюты.
            algorithm: Алгоритм консенсуса/хеширования.
            market_cap: Рыночная капитализация.
        """
        super().__init__(code, name)
        if not algorithm or not algorithm.strip():
            raise ValueError("Алгоритм не может быть пустым.")
        if market_cap < 0:
            raise ValueError("Рыночная капитализация не может быть отрицательной.")
        self._algorithm = algorithm.strip()
        self._market_cap = market_cap

    def get_display_info(self) -> str:
        """
        Возвращает строку вида: [CRYPTO] BTC — Bitcoin (Algo: SHA-256, MCAP: 1.12e12).

        Returns:
            Строковое представление криптовалюты.
        """
        # Форматируем капитализацию: если очень большая — экспоненциальный вид
        mcap_str = f"{self._market_cap:.2e}" if self._market_cap >= 1e9 else f"{self._market_cap:.0f}"
        return (
            f"[CRYPTO] {self.code} — {self.name} "
            f"(Algo: {self._algorithm}, MCAP: {mcap_str})"
        )


# Реестр валют (можно вынести в отдельный файл конфигурации)
_CURRENCIES: dict[str, Currency] = {
    "USD": FiatCurrency("USD", "US Dollar", "United States"),
    "EUR": FiatCurrency("EUR", "Euro", "Eurozone"),
    "GBP": FiatCurrency("GBP", "British Pound", "United Kingdom"),
    "RUB": FiatCurrency("RUB", "Russian Ruble", "Russia"),
    "BTC": CryptoCurrency("BTC", "Bitcoin", "SHA-256", 1.2e12),
    "ETH": CryptoCurrency("ETH", "Ethereum", "Ethash", 4.5e11),
}


def get_currency(code: str) -> Currency:
    """
    Возвращает экземпляр валюты по коду.

    Args:
        code: Код валюты (регистронезависим).

    Returns:
        Экземпляр Currency.

    Raises:
        CurrencyNotFoundError: Если валюта с таким кодом неизвестна.
    """
    code_upper = code.strip().upper()
    currency = _CURRENCIES.get(code_upper)
    if currency is None:
        raise CurrencyNotFoundError(f"Неизвестная валюта '{code}'")
    return currency
