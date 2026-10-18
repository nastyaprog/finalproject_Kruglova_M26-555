import argparse
import logging
from valutatrade_hub.infra.logging_config import configure_logging
from valutatrade_hub.core.usecases import clear_session, save_session
from valutatrade_hub.core.models import USERS_FILE, User
from valutatrade_hub.core.usecases import (
    buy_currency,
    get_portfolio,
    get_rate,
    load_session,
    login_user,
    register_user,
    sell_currency,
    show_portfolio,
)
from valutatrade_hub.core.utils import load_json
from valutatrade_hub.core.exceptions import ValutaTradeError, ApiRequestError, CurrencyNotFoundError

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
    success, message = register_user(args.username, args.password)
    print(message)


def cmd_login(args):
    user, message = login_user(args.username, args.password)
    if user:
        save_session(user.user_id)
        print(f"Вы вошли как '{user.username}'")
    else:
        print(message)


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
                "action": "BUY", 
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


def main():
    parser = argparse.ArgumentParser(prog="valutatrade-hub")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_register = subparsers.add_parser("register", help="Зарегистрировать нового пользователя")
    p_register.add_argument("--username", required=True, help="Имя пользователя")
    p_register.add_argument("--password", required=True, help="Пароль")
    p_register.set_defaults(func=cmd_register)

    p_login = subparsers.add_parser("login", help="Войти в систему")
    p_login.add_argument("--username", required=True, help="Имя пользователя")
    p_login.add_argument("--password", required=True, help="Пароль")
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

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
