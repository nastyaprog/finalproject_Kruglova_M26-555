import argparse
import json
import logging
from pathlib import Path

from dotenv import load_dotenv

from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    ValutaTradeError,
)
from valutatrade_hub.core.models import USERS_FILE, User
from valutatrade_hub.core.usecases import (
    buy_currency,
    clear_session,
    get_portfolio,
    get_rate,
    load_session,
    login_user,
    register_user,
    save_session,
    sell_currency,
    show_portfolio,
)
from valutatrade_hub.core.utils import load_json
from valutatrade_hub.infra.logging_config import configure_logging
from valutatrade_hub.parser_service.api_clients import (
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.updater import run_update

load_dotenv()  # загружает .env в переменные окружения

# Вызываем настройку логирования сразу при импорте/старте
configure_logging()

logger = logging.getLogger(__name__)


def _get_current_user() -> User | None:
    user_id = load_session()
    if user_id is None:
        return None
    users = load_json(USERS_FILE)
    user_data = next((u for u in users if u["user_id"] == user_id), None)
    return User.from_dict(user_data) if user_data else None


def cmd_register(args):
    _success, message = register_user(args.username, args.password)
    print(message)


def cmd_login(args):
    user, msg = login_user(args.username, args.password)
    if user:
        save_session(user.user_id)
        print(f"✅ {msg}")
    else:
        print(f"❌ {msg}")


def cmd_show_portfolio(args):
    current_user = _get_current_user()
    if not current_user:
        print("Сначала выполните login")
        return

    portfolio = get_portfolio(current_user.user_id)
    if not portfolio or not portfolio.wallets:
        print("У вас пока нет кошельков.")
        return

    base = args.base or "USD"
    try:
        # Убедись, что show_portfolio принимает base (если нет — добавь параметр)
        result = show_portfolio(portfolio, base=base)
        print(result)
    except ValutaTradeError as e:
        logger.exception("Ошибка при показе портфеля", extra={"action": "SHOW_PORTFOLIO", "user": current_user.username})
        print(str(e))


def cmd_buy(args):
    current_user = _get_current_user()
    if not current_user:
        print("Сначала выполните login")
        return

    try:
        portfolio = get_portfolio(current_user.user_id)
        if not portfolio:
            print("Портфель не найден.")
            return
        result = buy_currency(portfolio, args.currency, args.amount, args.rate)
        print(result)
    except ApiRequestError as e:
        logger.exception(
            "ApiRequestError при покупке валюты", 
            extra={
                "action": "BUY", 
                "user": current_user.username,
                "currency": args.currency, 
                "amount": args.amount,
                "rate": args.rate,
            },
        )
        print(f"{e}\nПопробуйте повторить позже или проверьте подключение к сети.")
    except CurrencyNotFoundError as e:
        logger.exception("CurrencyNotFoundError при покупке", extra={"action": "BUY", "user": current_user.username})
        print(f"{e}\nИспользуйте 'help get-rate' или проверьте список поддерживаемых валютных кодов.")
    except ValutaTradeError as e:
        logger.exception("ValutaTradeError при покупке", extra={"action": "BUY", "user": current_user.username})
        print(str(e))
    except Exception as e:
        logger.exception("Неожиданная ошибка при покупке", extra={"action": "BUY", "user": current_user.username})
        print(f"Произошла непредвиденная ошибка: {e}")


def cmd_sell(args):
    current_user = _get_current_user()
    if not current_user:
        print("Сначала выполните login")
        return

    try:
        portfolio = get_portfolio(current_user.user_id)
        if not portfolio:
            print("Портфель не найден.")
            return
        result = sell_currency(portfolio, args.currency, args.amount, args.rate)
        print(result)
    except ApiRequestError as e:
        logger.exception(
            "ApiRequestError при продаже валюты",
            extra={
                "action": "SELL", 
                "user": current_user.username,
                "currency": args.currency,          # <-- добавить сюда
                "amount": args.amount,
                "rate": args.rate,
            },
        )
        print(f"{e}\nПопробуйте повторить позже или проверьте подключение к сети.")
    except CurrencyNotFoundError as e:
        logger.exception("CurrencyNotFoundError при продаже", extra={"action": "SELL", "user": current_user.username})
        print(f"{e}\nИспользуйте 'help get-rate' или проверьте список поддерживаемых валютных кодов.")
    except ValutaTradeError as e:
        logger.exception("ValutaTradeError при продаже", extra={"action": "SELL", "user": current_user.username})
        print(str(e))
    except Exception as e:
        logger.exception("Неожиданная ошибка при продаже", extra={"action": "SELL", "user": current_user.username})
        print(f"Произошла непредвиденная ошибка: {e}")


def cmd_get_rate(args):
    try:
        rate = get_rate(args.from_currency, args.to_currency)
        if rate is None:
            print(f"Курс не найден для пары {args.from_currency} → {args.to_currency}. Проверьте список поддерживаемых валют.")
        else:
            print(f"Курс {args.from_currency} → {args.to_currency}: {rate:.4f}")
    except CurrencyNotFoundError as e:
        logger.exception("CurrencyNotFoundError в get-rate", extra={"action": "GET_RATE"})
        print(f"{e}")
        print("Используйте 'help get-rate' или проверьте список поддерживаемых валютных кодов.")
    except ApiRequestError as e:
        logger.exception("ApiRequestError в get-rate", extra={"action": "GET_RATE"})
        print(f"{e}\nПопробуйте позже или проверьте сеть.")
    except Exception as e:
        logger.exception("Неожиданная ошибка в get-rate", extra={"action": "GET_RATE"})
        print(f"Ошибка: {e}")


def cmd_logout(args):
    clear_session()
    print("Вы вышли из системы.")

def cmd_update_rates(args):
    clients = []

    if args.source is None or args.source == "coingecko":
        clients.append(CoinGeckoClient())

    if args.source is None or args.source == "exchangerate":
        try:
            clients.append(ExchangeRateApiClient())
        except ValueError as e:
            print(f"⚠️ Не удалось подключить ExchangeRate-API: {e}")
            print("   Для теста используйте: update-rates --source coingecko")
            return

    total_saved, errors = run_update(clients)

    print("✅ Обновление курсов завершено.")
    print(f"   Всего курсов сохранено: {total_saved}")
    if errors > 0:
        print(
            f"⚠️ Возникло ошибок при загрузке: {errors}"
            )

def cmd_show_rates(args):
    path = Path("data/rates.json")
    if not path.exists():
        print("📭 Локальный кеш курсов пуст.")
        print("   Запустите сначала: valutatrade update-rates")
        return

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"❌ Не удалось прочитать кеш курсов: {e}")
        return

    pairs = data.get("pairs", {})
    last_refresh = data.get("last_refresh", "неизвестно")

    filtered = []
    for pair, info in pairs.items():
        # Формат пары: BTC_USD, EUR_USD и т.д.
        parts = pair.split("_", 1)
        if len(parts) != 2:
            continue
        from_c, _to_c = parts

        # Фильтр по валюте FROM
        if args.currency and from_c.upper() != args.currency.upper():
            continue

        filtered.append((pair, info["rate"], info["updated_at"], info["source"]))

    # Сортировка и ограничение по top
    if args.top:
        filtered = sorted(filtered, key=lambda x: x[1], reverse=True)[:args.top]

    if not filtered:
        print("Нет курсов, соответствующих заданным фильтрам.")
        return

    print(f"\n💱 Курсы валют (обновлено: {last_refresh})")
    print("-" * 60)
    for pair, rate, updated, source in filtered:
        print(f"{pair:<12} : {rate:>12.4f}  [{source:<12}] (обновлено: {updated})")
    print("-" * 60)


def main():
    parser = argparse.ArgumentParser(prog="valutatrade-hub")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_register = subparsers.add_parser("register", help="Зарегистрировать нового пользователя")
    p_register.add_argument("username", help="Имя пользователя")
    p_register.add_argument("password", help="Пароль")
    p_register.set_defaults(func=cmd_register)

    p_login = subparsers.add_parser("login", help="Войти в систему")
    p_login.add_argument("username", help="Имя пользователя")
    p_login.add_argument("password", help="Пароль")
    p_login.set_defaults(func=cmd_login)

    p_logout = subparsers.add_parser("logout", help="Выйти из системы")
    p_logout.set_defaults(func=cmd_logout)

    p_portfolio = subparsers.add_parser("show-portfolio", help="Показать портфель")
    p_portfolio.add_argument("--base", default="USD", help="Базовая валюта для конвертации")
    p_portfolio.set_defaults(func=cmd_show_portfolio)

    p_buy = subparsers.add_parser("buy", help="Купить валюту")
    p_buy.add_argument("currency", help="Код валюты (например, BTC, EUR)")
    p_buy.add_argument("amount", type=float, help="Количество единиц")
    p_buy.add_argument("--rate", type=float, default=None, help="Цена за единицу в USD (опционально)")
    p_buy.set_defaults(func=cmd_buy)

    p_sell = subparsers.add_parser("sell", help="Продать валюту")
    p_sell.add_argument("currency", help="Код валюты")
    p_sell.add_argument("amount", type=float, help="Количество единиц")
    p_sell.add_argument("--rate", type=float, default=None, help="Цена за единицу в USD (опционально)")
    p_sell.set_defaults(func=cmd_sell)

    p_rate = subparsers.add_parser("get-rate", help="Получить курс конвертации")
    p_rate.add_argument("from_currency", help="Валюта ОТ")
    p_rate.add_argument("to_currency", help="Валюта ДО")
    p_rate.set_defaults(func=cmd_get_rate)

    # --- НОВЫЕ КОМАНДЫ ДЛЯ PARSER SERVICE ---

    p_update = subparsers.add_parser("update-rates", help="Обновить курсы валют из внешних API")
    p_update.add_argument(
        "--source",
        choices=["coingecko", "exchangerate"],
        help="Обновить только из указанного источника (coingecko / exchangerate)"
    )
    p_update.set_defaults(func=cmd_update_rates)

    p_show = subparsers.add_parser("show-rates", help="Показать актуальные курсы из кеша")
    p_show.add_argument("--currency", help="Фильтр по валюте (FROM), например BTC")
    p_show.add_argument("--top", type=int, help="Показать N самых дорогих курсов")
    p_show.set_defaults(func=cmd_show_rates)


    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
