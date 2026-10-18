"""Бизнес-логика приложения: регистрация, вход, операции с портфелем."""
import json
from datetime import datetime
from pathlib import Path

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import (
    CurrencyNotFoundError,
    InsufficientFundsError,
)
from valutatrade_hub.core.models import (
    PORTFOLIOS_FILE,
    USERS_FILE,
    Portfolio,
    User,
    Wallet,
)
from valutatrade_hub.core.utils import load_json, save_json
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.settings import SettingsLoader

# Создаём единственный экземпляр настроек (Singleton)
settings = SettingsLoader()

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
    """Регистрирует нового пользователя в системе.

    Args:
        username: Имя пользователя.
        password: Пароль (длина >= 4 символов).

    Returns:
        Кортеж (успех, сообщение).
    """
    if len(password) < 4:
        return False, "Пароль должен быть не короче 4 символов."

    users = load_json(USERS_FILE)
    if any(u["username"] == username for u in users):
        return False, f"Имя пользователя '{username}' уже занято."

    user_id = _get_next_user_id()
    new_user = User.create_new(user_id, username, password)
    users.append(new_user.to_dict())
    save_json(USERS_FILE, users)

    # Создаём портфель сразу с USD-кошельком и стартовым балансом
    usd_wallet = Wallet(currency="USD", balance=1000.0)
    portfolio = Portfolio(user_id=user_id, wallets={"USD": usd_wallet})
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


def _load_rates() -> dict:
    """Загружает курсы валют из rates.json.

    Возвращает полный JSON-объект:
    {
      "pairs": { "BTC_USD": { "rate": ..., "updated_at": ... } },
      "last_refresh": "..."
    }

    Returns:
        Словарь с данными курсов.
    """
    path = Path("data/rates.json")
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _is_rates_fresh(rates: dict) -> bool:
    """Проверяет, не устарели ли курсы (TTL из SettingsLoader).

    Args:
        rates: Данные курсов.

    Returns:
        True, если курсы свежие.
    """
    last_refresh = rates.get("last_refresh")
    if not last_refresh:
        return False
    
    # Обработка возможных форматов ISO (с Z или без)
    clean_time = last_refresh.replace("Z", "+00:00")
    try:
        refresh_ts = datetime.fromisoformat(clean_time)
    except ValueError:
        return False

    ttl_seconds = settings.get("rates_ttl_seconds")
    now = datetime.now(refresh_ts.tzinfo) if refresh_ts.tzinfo else datetime.now()
    age = (now - refresh_ts).total_seconds()
    return age <= ttl_seconds

@log_action("BUY")
def buy_currency(
    portfolio: Portfolio,
    currency: str,
    amount: float,
    price_per_unit: float | None = None,
) -> str:
    """
    Покупает валюту за USD.

    Логика:
      1. Валидирует валюту через реестр (выбросит CurrencyNotFoundError при ошибке).
      2. Если цена не передана — берёт из rates.json (ключ вида "BTC_USD").
      3. Проверяет баланс USD-кошелька.
      4. Списывает USD, зачисляет целевую валюту.
      5. Сохраняет обновлённый портфель в portfolios.json.

    Args:
        portfolio: Портфель пользователя.
        currency: Код покупаемой валюты (например, "BTC", "EUR").
        amount: Количество единиц валюты для покупки.
        price_per_unit: Цена одной единицы в USD. Если None — берётся из rates.json.

    Returns:
        Сообщение об успешной операции.

    Raises:
        ValueError: Если amount <= 0 или цена некорректна.
        CurrencyNotFoundError: Если валюта неизвестна или курс не найден.
        InsufficientFundsError: Если недостаточно USD на балансе.
    """
    if amount <= 0:
        raise ValueError("Сумма покупки должна быть положительной.")

    # 1. Валидация валюты через реестр (выбросит CurrencyNotFoundError при ошибке)
    get_currency(currency)

    usd_wallet = _ensure_usd_wallet(portfolio)

    # 2. Получение курса с проверкой свежести
    rates_data = _load_rates()
    pair = f"{currency.upper()}_USD"

    # Достаём пары из ключа "pairs", если он есть
    pairs = rates_data.get("pairs", {})

    if price_per_unit is None:
        if pair not in pairs:
            raise CurrencyNotFoundError(f"Курс для пары {pair} не найден.")
        price_per_unit = pairs[pair]["rate"]

    total_cost = amount * price_per_unit

    # 3. Проверка баланса и выброс исключения при нехватке
    if usd_wallet.balance < total_cost:
        raise InsufficientFundsError(
            available=usd_wallet.balance,
            required=total_cost,
            code="USD"
        )

    # 4. Проведение операции
    usd_wallet.withdraw(total_cost)
    portfolio.add_currency(currency.upper())
    target_wallet = portfolio.get_wallet(currency.upper())

    if target_wallet is None:
        # Это защита от логических ошибок
        raise RuntimeError(f"Кошелёк для {currency.upper()} не был создан.")

    target_wallet.deposit(amount)

    # 5. Сохранение
    save_portfolio(portfolio)

    return (f"Покупка выполнена: {amount:.4f} {currency.upper()} "
            f"по курсу {price_per_unit:.4f} USD/ед. "
            f"Списано: {total_cost:.2f} USD.")

@log_action("SELL")
def sell_currency(
    portfolio: Portfolio,
    currency: str,
    amount: float,
    price_per_unit: float | None = None,
) -> str:
    """Продаёт валюту и зачисляет USD на счёт.

    Args:
        portfolio: Портфель пользователя.
        currency: Код продаваемой валюты.
        amount: Количество единиц для продажи.
        price_per_unit: Цена одной единицы в USD. Если None — берётся из rates.json.

    Returns:
        Сообщение об успешной операции.

    Raises:
        ValueError: Если amount <= 0 или цена некорректна.
        CurrencyNotFoundError: Если курс не найден.
        InsufficientFundsError: Если недостаточно валюты на балансе.
        ApiRequestError: Если курсы устарели.
    """
     # 1. Валидация суммы
    if amount <= 0:
        raise ValueError("Сумма продажи должна быть положительным числом.")

    # 2. Валидация валюты через реестр (выбросит CurrencyNotFoundError при ошибке)
    get_currency(currency)

    currency_code = currency.upper()

    # 3. Проверка наличия кошелька и баланса
    wallet = portfolio.get_wallet(currency_code)
    if wallet is None:
        # Для удобства можно автоматически создать пустой кошелёк, но по ТЗ 
        # лучше явно сказать, что валюты нет. Оставим явную ошибку.
        raise CurrencyNotFoundError(f"У вас нет кошелька для валюты '{currency_code}'. Сначала купите её.")

    if wallet.balance < amount:
        raise InsufficientFundsError(
            available=wallet.balance,
            required=amount,
            code=currency_code
        )

    rates_data = _load_rates()

    # 4. Проверка свежести кеша
    if not _is_rates_fresh(rates_data):
        from valutatrade_hub.core.exceptions import ApiRequestError
        raise ApiRequestError(
            "Курсы валют устарели. Требуется обновление через Parser Service."
            )

    currency_code = currency.upper()
    pair = f"{currency_code}_USD"
    
    # Достаём пары
    pairs = rates_data.get("pairs", {})

    if price_per_unit is None:
        if pair not in pairs:
            raise CurrencyNotFoundError(f"Курс для пары {pair} не найден.")
        price_per_unit = pairs[pair]["rate"]

    revenue_usd = amount * price_per_unit

    # 5. Проведение операции
    # Списываем валюту из кошелька продавца
    wallet.withdraw(amount)

    # Начисляем USD на USD-кошелёк (создаём, если нет)
    usd_wallet = portfolio.add_currency("USD")  # add_currency должен возвращать объект Wallet
    usd_wallet.deposit(revenue_usd)

    # 6. Сохранение портфеля
    save_portfolio(portfolio)

    return (
        f"Продажа выполнена: {amount:.4f} {currency_code} по курсу {price_per_unit:.4f} USD/ед.\n"
        f"Изменения в портфеле:\n"
        f"- {currency_code}: было {wallet.balance + amount:.4f} → стало {wallet.balance:.4f}\n"
        f"- USD: начислено {revenue_usd:.2f} USD\n"
        f"Оценочная выручка: {revenue_usd:.2f} USD"
    )

def show_portfolio(portfolio: Portfolio, base: str = "USD") -> str:
    """Формирует читаемое представление портфеля.

    Включает список кошельков и общую стоимость в базовой валюте.

    Args:
        portfolio: Портфель пользователя.
        base: Базовая валюта для конвертации (по умолчанию USD).

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
    """Возвращает курс конвертации через USD (если нет прямого).

    Args:
        from_currency: Валюта ОТ.
        to_currency: Валюта ДО.

    Returns:
        Курс конвертации или None, если не найден.
    """
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()

    rates = _load_rates()

    # Прямой курс к USD
    if to_currency == "USD":
        return rates.get(f"{from_currency}_USD")

    # Обратный курс из USD
    if from_currency == "USD":
        rate = rates.get(f"USD_{to_currency}")
        return 1 / rate if rate else None

    # Кросс-курс через USD
    rate_from_usd = rates.get(f"{from_currency}_USD")
    rate_to_usd = rates.get(f"USD_{to_currency}")
    if rate_from_usd is None or rate_to_usd is None:
        return None

    return rate_from_usd * rate_to_usd