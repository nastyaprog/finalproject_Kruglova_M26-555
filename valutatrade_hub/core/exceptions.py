"""Модуль пользовательских исключений для ValutaTrade Hub."""


class ValutaTradeError(Exception):
    """Базовый класс исключений проекта."""
    pass


class InsufficientFundsError(ValutaTradeError):
    """Ошибка: недостаточно средств на кошельке."""

    def __init__(self, available: float, required: float, code: str) -> None:
        """
        Args:
            available: Доступный баланс.
            required: Требуемая сумма.
            code: Код валюты.
        """
        message = (
            f"Недостаточно средств: доступно {available:.4f} {code}, "
            f"требуется {required:.4f} {code}"
        )
        super().__init__(message)
        self.available = available
        self.required = required
        self.code = code


class CurrencyNotFoundError(ValutaTradeError):
    """Ошибка: неизвестная валюта."""

    def __init__(self, code: str) -> None:
        """
        Args:
            code: Неизвестный код валюты.
        """
        message = f"Неизвестная валюта '{code}'"
        super().__init__(message)
        self.code = code


class ApiRequestError(ValutaTradeError):
    """Ошибка при обращении к внешнему API (или к локальному источнику курсов)."""

    def __init__(self, reason: str) -> None:
        """
        Args:
            reason: Причина ошибки.
        """
        message = f"Ошибка при обращении к внешнему API: {reason}"
        super().__init__(message)
        self.reason = reason
