"""
Модуль моделей: User, Wallet, Portfolio.
Реализует бизнес-сущности с валидацией, инкапсуляцией и сериализацией.
"""

import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Any

DATA_DIR = Path("data")
USERS_FILE = DATA_DIR / "users.json"
PORTFOLIOS_FILE = DATA_DIR / "portfolios.json"
RATES_FILE = DATA_DIR / "rates.json"


class User:
    """Пользователь системы: хранит данные, управляет паролем и предоставляет
    информацию о профиле."""

    def __init__(
        self,
        user_id: int,
        username: str,
        hashed_password: str,
        salt: str,
        registration_date: str,
    ) -> None:
        """Инициализирует пользователя всеми необходимыми атрибутами.

        Args:
            user_id: Уникальный идентификатор пользователя.
            username: Имя пользователя (не пустое).
            hashed_password: Хеш пароля (строка).
            salt: Соль для хеширования (строка).
            registration_date: Дата регистрации в формате ISO.
        """
        self._user_id = user_id
        self._username = username
        self._hashed_password = hashed_password
        self._salt = salt
        self._registration_date = registration_date

    @classmethod
    def create_new(cls, user_id: int, username: str, password: str) -> "User":
        """Создает нового пользователя, генерируя соль и хеш для пароля.

        Args:
            user_id: Уникальный ID.
            username: Имя пользователя.
            password: Сырой пароль (будет захеширован).

        Returns:
            Экземпляр User с готовым хешем.
        """
        user = cls(
            user_id=user_id,
            username=username,
            hashed_password="",
            salt="",
            registration_date=datetime.now().isoformat(),
        )
        user.change_password(password)
        return user

    @property
    def user_id(self) -> int:
        """Возвращает уникальный идентификатор пользователя."""
        return self._user_id

    @property
    def username(self) -> str:
        """Возвращает имя пользователя."""
        return self._username

    @username.setter
    def username(self, value: str) -> None:
        """Устанавливает имя пользователя с проверкой на пустоту.

        Raises:
            ValueError: Если значение пустое или состоит только из пробелов.
        """
        if not value or not value.strip():
            raise ValueError("Имя пользователя не может быть пустым.")
        self._username = value.strip()

    @property
    def hashed_password(self) -> str:
        """Возвращает хеш пароля (для внутреннего использования)."""
        return self._hashed_password

    @property
    def salt(self) -> str:
        """Возвращает соль пользователя."""
        return self._salt

    @property
    def registration_date(self) -> str:
        """Возвращает дату регистрации."""
        return self._registration_date

    def get_user_info(self) -> dict[str, Any]:
        """Формирует словарь с публичной информацией о пользователе.

        Returns:
            Словарь с полями user_id, username, registration_date.
        """
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date,
        }

    def change_password(self, new_password: str) -> None:
        """Изменяет пароль пользователя: генерирует новую соль и обновляет хеш.

        Args:
            new_password: Новый пароль (длина >= 4 символов).

        Raises:
            ValueError: Если пароль слишком короткий.
        """
        if len(new_password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов.")
        self._salt = os.urandom(16).hex()
        self._hashed_password = self._hash_password(new_password, self._salt)

    def verify_password(self, password: str) -> bool:
        """Проверяет введённый пароль на соответствие сохранённому хешу.

        Args:
            password: Пароль для проверки.

        Returns:
            True, если пароль совпадает; иначе False.
        """
        return self._hash_password(password, self._salt) == self._hashed_password

    @staticmethod
    def _hash_password(password: str, salt: str) -> str:
        """Вычисляет односторонний хеш пароля с солью.

        Args:
            password: Исходный пароль.
            salt: Случайная соль.

        Returns:
            Шестнадцатеричная строка хеша SHA-256.
        """
        return hashlib.sha256((password + salt).encode()).hexdigest()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "User":
        """Создаёт экземпляр User из словаря (например, из JSON).

        Args:
            data: Словарь с полями пользователя.

        Returns:
            Экземпляр класса User.
        """
        return cls(
            user_id=data["user_id"],
            username=data["username"],
            hashed_password=data["hashed_password"],
            salt=data["salt"],
            registration_date=data["registration_date"],
        )

    def to_dict(self) -> dict[str, Any]:
        """Преобразует объект User в словарь для сохранения в JSON.

        Returns:
            Словарь со всеми атрибутами пользователя.
        """
        return {
            "user_id": self._user_id,
            "username": self._username,
            "hashed_password": self._hashed_password,
            "salt": self._salt,
            "registration_date": self._registration_date,
        }


class Wallet:
    """Кошелёк для одной валюты: управляет балансом, пополнением и снятием."""

    def __init__(
            self, 
            currency: str, 
            balance: float = 0.0, 
        ) -> None:
        """Инициализирует кошелёк с кодом валюты и начальным балансом.

        Args:
            currency_code: Код валюты (приводится к верхнему регистру).
            balance: Начальный баланс (по умолчанию 0.0).
        """
        self.currency_code = currency.upper()
        self._balance = balance

    @property
    def balance(self) -> float:
        """Возвращает текущий баланс кошелька."""
        return self._balance

    @balance.setter
    def balance(self, value: float) -> None:
        """Устанавливает баланс с валидацией типа и знака.

        Args:
            value: Новое значение баланса.

        Raises:
            TypeError: Если значение не число.
            ValueError: Если баланс отрицательный.
        """
        if not isinstance(value, (int, float)):
            raise TypeError("Баланс должен быть числом.")
        if value < 0:
            raise ValueError("Баланс не может быть отрицательным.")
        self._balance = float(value)

    def deposit(self, amount: float) -> None:
        """Пополняет баланс кошелька.

        Args:
            amount: Сумма пополнения (должна быть > 0).

        Raises:
            ValueError: Если сумма не положительная.
        """
        if not isinstance(amount, (int, float)):
            raise TypeError("Сумма должна быть числом.")
        if amount <= 0:
            raise ValueError("Сумма пополнения должна быть положительной.")
        self._balance += float(amount)

    def withdraw(self, amount: float) -> None:
        """Снимает средства с кошелька при достаточном балансе.

        Args:
            amount: Сумма снятия (должна быть > 0).

        Raises:
            ValueError: Если сумма не положительная или превышает баланс.
        """
        if not isinstance(amount, (int, float)) or amount <= 0:
            raise ValueError("Сумма снятия должна быть положительным числом.")
        if amount > self._balance:
            raise ValueError("Недостаточно средств.")
        self._balance -= amount

    def get_balance_info(self) -> str:
        """Возвращает строковое представление баланса для отображения.

        Returns:
            Строка вида 'USD: 123.4567'.
        """
        return f"{self.currency_code}: {self._balance:.4f}"

    def to_dict(self) -> dict[str, Any]:
        """Сериализует кошелёк в словарь.

        Returns:
            Словарь с currency_code и balance.
        """
        return {"currency_code": self.currency_code, "balance": self._balance}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Wallet":
        """Восстанавливает кошелёк из словаря.

        Args:
            data: Словарь с полями currency_code и balance.

        Returns:
            Экземпляр Wallet.
        """
                # В JSON сохраняется currency_code, а не currency
        return cls(currency=data["currency_code"], balance=data["balance"])


class Portfolio:
    """Портфель пользователя: управляет набором кошельков и рассчитывает
    общую стоимость активов."""

    def __init__(self, user_id: int, wallets: dict[str, Wallet] | None = None) -> None:
        """Инициализирует портфель с идентификатором пользователя.

        Args:
            user_id: ID владельца портфеля.
            wallets: Опциональный словарь кошельков (по умолчанию пустой).
        """
        self._user_id = user_id
        self._wallets: dict[str, Wallet] = wallets if wallets is not None else {}

    @property
    def user_id(self) -> int:
        """Возвращает ID пользователя, которому принадлежит портфель."""
        return self._user_id

    @property
    def wallets(self) -> dict[str, Wallet]:
        """Возвращает копию словаря кошельков для безопасного доступа.

        Returns:
            Копия словаря {код_валюты: объект Wallet}.
        """
        return self._wallets.copy()

    def add_currency(self, currency_code: str) -> Wallet:
        """Добавляет новую валюту в портфель, если её ещё нет."""
        # 1. Нормализуем регистр сразу
        currency_code = currency_code.upper()
    
        # 2. Если уже есть — возвращаем существующий
        if currency_code in self._wallets:
            return self._wallets[currency_code]

        # 3. Создаём новый кошелёк: в параметр currency передаём значение из переменной currency_code
        new_wallet = Wallet(currency=currency_code, balance=0.0)
    
        # 4. Кладем в словарь по ключу currency_code (он уже в верхнем регистре)
        self._wallets[currency_code] = new_wallet
    
        return new_wallet


    def get_wallet(self, currency_code: str) -> Wallet | None:
        """Получает кошелёк по коду валюты.

        Args:
            currency_code: Код валюты.

        Returns:
            Объект Wallet или None, если не найден.
        """
        return self._wallets.get(currency_code.upper())

    def get_total_value(self, base_currency: str = "USD") -> float:
        """Рассчитывает общую стоимость портфеля в базовой валюте.

        Использует фиксированный набор курсов (заглушку). В будущем можно
        заменить на данные из rates.json или API.

        Args:
            base_currency: Код базовой валюты для конвертации.

        Returns:
            Общая стоимость портфеля в указанной валюте.
        """
        exchange_rates = {  # это тестовые заглушки курсов для демонстрации логики.
        # В реальном проекте курсы берутся из rates.json / Parser Service.
            "EUR_USD": 1.08,
            "BTC_USD": 60000.0,
            "RUB_USD": 0.011,
            "ETH_USD": 3500.0,
            "USD_USD": 1.0,
        }
        total = 0.0
        for code, wallet in self._wallets.items():
            if code == base_currency:
                total += wallet.balance
                continue

            rate_key = f"{code}_{base_currency}"
            if rate_key in exchange_rates:
                total += wallet.balance * exchange_rates[rate_key]
            else:
                rate_key_rev = f"{base_currency}_{code}"
                if rate_key_rev in exchange_rates:
                    total += wallet.balance / exchange_rates[rate_key_rev]
        return total

    def to_dict(self) -> dict[str, Any]:
        """Сериализует портфель в словарь для JSON.

        Returns:
            Словарь с user_id и кошельками.
        """
        return {
            "user_id": self._user_id,
            "wallets": {k: v.to_dict() for k, v in self._wallets.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Portfolio":
        """Восстанавливает портфель из словаря.

        Args:
            data: Словарь с user_id и кошельками.

        Returns:
            Экземпляр Portfolio.
        """
        wallets = {k: Wallet.from_dict(v) for k, v in data["wallets"].items()}
        return cls(user_id=data["user_id"], wallets=wallets)
