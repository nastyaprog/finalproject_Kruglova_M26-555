"""Бизнес-логика приложения: регистрация, вход, операции с портфелем."""

import json
from pathlib import Path

from valutatrade_hub.core.models import (
    PORTFOLIOS_FILE,
    RATES_FILE,
    USERS_FILE,
    Portfolio,
    User,
    Wallet,
)
from valutatrade_hub.core.utils import load_json, save_json

DATA_DIR = Path("data")


SESSION_FILE = Path(".current_session.json")


def save_session(user_id: int) -> None:
    """Сохраняет ID текущего пользователя в локальный файл."""
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump({"user_id": user_id}, f)


def load_session() -> int | None:
    """Загружает ID текущего пользователя из файла."""
    if not SESSION_FILE.exists():
        return None
    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("user_id")
    except (json.JSONDecodeError, OSError):
        return None


def clear_session() -> None:
    """Очищает сессию (можно вызывать при logout)."""
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()


def _get_next_user_id() -> int:
    """Вычисляет следующий доступный ID пользователя.

    Возвращает 1, если пользователей нет, иначе максимум + 1.

    Returns:
        Новый уникальный ID.
    """
    users = load_json(USERS_FILE)
    if not users:
        return 1
    return max(u["user_id"] for u in users) + 1


def register_user(username: str, password: str) -> tuple[bool, str]:
    """Регистрирует нового пользователя в системе."""
    if len(password) < 4:
        return False, "Пароль должен быть не короче 4 символов."

    users = load_json(USERS_FILE)
    if any(u["username"] == username for u in users):
        return False, f"Имя пользователя '{username}' уже занято."

    user_id = _get_next_user_id()

    # Вся магия с солью и хешем происходит внутри create_new -> change_password
    new_user = User.create_new(user_id, username, password)

    users.append(new_user.to_dict())
    save_json(USERS_FILE, users)

    # Логика создания портфеля (остается без изменений)
    portfolios = load_json(PORTFOLIOS_FILE)
    portfolios.append({"user_id": user_id, "wallets": {}})
    save_json(PORTFOLIOS_FILE, portfolios)

    # Стартовый баланс
    portfolio = get_portfolio(user_id)
    if portfolio:
        usd_wallet = _ensure_usd_wallet(portfolio)
        usd_wallet.deposit(1000.0)
        save_portfolio(portfolio)

    return True, f"Пользователь '{username}' зарегистрирован (id={user_id})."


def login_user(username: str, password: str) -> tuple[User | None, str]:
    """Выполняет вход пользователя в систему.

    Находит пользователя по имени, проверяет хеш пароля.

    Args:
        username: Имя пользователя.
        password: Введённый пароль.

    Returns:
        Кортеж (объект User или None, сообщение об успехе/ошибке).
    """
    users = load_json(USERS_FILE)
    user_data = next((u for u in users if u["username"] == username), None)
    if not user_data:
        return None, "Пользователь не найден."

    user = User.from_dict(user_data)
    if not user.verify_password(password):
        return None, "Неверный пароль."

    return user, "Успешный вход."


def get_portfolio(user_id: int) -> Portfolio | None:
    """Получает портфель пользователя по ID.

    Загружает данные из portfolios.json и восстанавливает объект Portfolio.

    Args:
        user_id: ID пользователя.

    Returns:
        Объект Portfolio или None, если не найден.
    """
    portfolios = load_json(PORTFOLIOS_FILE)
    data = next((p for p in portfolios if p["user_id"] == user_id), None)
    if not data:
        return None
    return Portfolio.from_dict(data)


def save_portfolio(portfolio: Portfolio) -> None:
    """Сохраняет обновлённый портфель в portfolios.json.

    Заменяет старую запись по user_id на новую.

    Args:
        portfolio: Объект Portfolio для сохранения.
    """
    portfolios = load_json(PORTFOLIOS_FILE)
    # Удаляем старую запись
    portfolios = [p for p in portfolios if p["user_id"] != portfolio.user_id]
    portfolios.append(portfolio.to_dict())
    save_json(PORTFOLIOS_FILE, portfolios)


def _ensure_usd_wallet(portfolio: Portfolio) -> Wallet:
    """Гарантирует наличие USD-кошелька в портфеле.

    Если кошелька нет — создаёт с балансом 0.0.

    Args:
        portfolio: Портфель пользователя.

    Returns:
        Объект USD-кошелька.
    """
    portfolio.add_currency("USD")
    wallet = portfolio.get_wallet("USD")
    if wallet is None:
        # На практике не должно происходить из-за add_currency
        raise RuntimeError("Не удалось создать USD-кошелёк.")
    return wallet


def _load_rates() -> dict[str, float]:
    """Загружает курсы валют из rates.json.

    Возвращает плоский словарь: ключ 'EUR_USD' -> значение rate.

    Returns:
        Словарь курсов.
    """
    rates = load_json(RATES_FILE)
    if not isinstance(rates, dict):
        return {}

    result = {}
    for k, v in rates.items():
        if k in ("source", "last_refresh"):
            continue
        if isinstance(v, dict) and "rate" in v:
            result[k] = float(v["rate"])
    return result


def buy_currency(
    portfolio: Portfolio,
    currency: str,
    amount: float,
    price_per_unit: float | None = None,
) -> str:
    """Покупает валюту за USD согласно ТЗ.

    Списывает сумму в USD с USD-кошелька, начисляет купленную валюту.
    Цена за единицу может быть передана явно или взята из rates.json.

    Args:
        portfolio: Портфель пользователя.
        currency: Код покупаемой валюты (например, 'BTC').
        amount: Количество единиц валюты для покупки.
        price_per_unit: Цена одной единицы в USD. Если None — берётся из rates.json.

    Returns:
        Сообщение об успешной операции.

    Raises:
        ValueError: Если недостаточно USD или параметры некорректны.
    """
    if amount <= 0:
        raise ValueError("Сумма покупки должна быть положительной.")

    usd_wallet = _ensure_usd_wallet(portfolio)

    # Получаем цену
    if price_per_unit is None:
        rates = _load_rates()
        pair = f"{currency}_USD"
        if pair not in rates:
            raise ValueError(f"Курс для пары {pair} не найден.")
        price_per_unit = rates[pair]

    total_cost = amount * price_per_unit
    if usd_wallet.balance < total_cost:
        raise ValueError(
            f"Недостаточно USD: требуется {total_cost:.2f}, доступно {usd_wallet.balance:.2f}."
        )

    # Списываем USD
    usd_wallet.withdraw(total_cost)

    # Начисляем купленную валюту
    portfolio.add_currency(currency)
    target_wallet = portfolio.get_wallet(currency)
    if target_wallet is None:
        raise RuntimeError("Не удалось получить кошелёк целевой валюты.")
    target_wallet.deposit(amount)

    save_portfolio(portfolio)
    return (
        f"Покупка выполнена: {amount:.4f} {currency} по цене {price_per_unit:.4f} "
        f"USD за единицу. Списано {total_cost:.2f} USD."
    )


def sell_currency(
    portfolio: Portfolio,
    currency: str,
    amount: float,
    price_per_unit: float | None = None,
) -> str:
    """Продаёт валюту и зачисляет USD на счёт согласно ТЗ.

    Списывает указанную валюту, начисляет эквивалент в USD.

    Args:
        portfolio: Портфель пользователя.
        currency: Код продаваемой валюты.
        amount: Количество единиц для продажи.
        price_per_unit: Цена одной единицы в USD. Если None — берётся из rates.json.

    Returns:
        Сообщение об успешной операции.

    Raises:
        ValueError: Если валюта отсутствует или недостаточно баланса.
    """
    if amount <= 0:
        raise ValueError("Сумма продажи должна быть положительной.")

    wallet = portfolio.get_wallet(currency)
    if wallet is None or wallet.balance < amount:
        raise ValueError(
            f"Недостаточно {currency}: требуется {amount:.4f}, доступно "
            f"{0.0 if wallet is None else wallet.balance:.4f}."
        )

    # Получаем цену
    if price_per_unit is None:
        rates = _load_rates()
        pair = f"{currency}_USD"
        if pair not in rates:
            raise ValueError(f"Курс для пары {pair} не найден.")
        price_per_unit = rates[pair]

    revenue = amount * price_per_unit

    # Списываем валюту
    wallet.withdraw(amount)

    # Зачисляем USD
    usd_wallet = _ensure_usd_wallet(portfolio)
    usd_wallet.deposit(revenue)

    save_portfolio(portfolio)
    return (
        f"Продажа выполнена: {amount:.4f} {currency}. Начислено {revenue:.2f} USD "
        f"(по курсу {price_per_unit:.4f} USD за единицу)."
    )


def show_portfolio(portfolio: Portfolio) -> str:
    """Формирует читаемое представление портфеля.

    Включает список кошельков и общую стоимость в USD.

    Args:
        portfolio: Портфель пользователя.

    Returns:
        Строка с информацией о портфеле.
    """
    lines = []
    lines.append("Портфель:")
    for wallet in portfolio.wallets.values():
        lines.append(f"  {wallet.get_balance_info()}")

    total = portfolio.get_total_value("USD")
    lines.append(f"Общая стоимость портфеля: {total:.2f} USD")
    return "\n".join(lines)


def get_rate(from_currency: str, to_currency: str) -> float | None:
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()

    rates = _load_rates()

    # Простой случай: к USD
    if to_currency == "USD":
        return rates.get(f"{from_currency}_USD")

    # Обратный случай: из USD
    if from_currency == "USD":
        rate = rates.get(f"USD_{to_currency}")
        return 1 / rate if rate else None

    return None
