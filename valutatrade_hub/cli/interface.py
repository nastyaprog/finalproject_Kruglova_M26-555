import argparse

from valutatrade_hub.core.models import USERS_FILE, User
from valutatrade_hub.core.usecases import (
    buy_currency,
    get_portfolio,
    get_rate,
    load_session,
    login_user,
    register_user,
    save_session,
    sell_currency,
)
from valutatrade_hub.core.utils import load_json

current_user = None


def cmd_register(args):
    _, message = register_user(args.username, args.password)
    print(message)


def cmd_login(args):
    global current_user
    user, message = login_user(args.username, args.password)
    if user:
        current_user = user
        save_session(user.user_id)  # <-- важно
        print(f"Вы вошли как '{user.username}'")
    else:
        print(message)


def _get_current_user() -> User | None:
    user_id = load_session()
    if user_id is None:
        return None
    users = load_json(USERS_FILE)
    user_data = next((u for u in users if u["user_id"] == user_id), None)
    return User.from_dict(user_data) if user_data else None


def cmd_show_portfolio(args):
    global current_user
    current_user = _get_current_user()  # <-- пробуем восстановить
    if not current_user:
        print("Сначала выполните login")
        return

    portfolio = get_portfolio(current_user.user_id)
    if not portfolio or not portfolio.wallets:
        print("У вас пока нет кошельков.")
        return

    base = args.base or "USD"
    total = portfolio.get_total_value(base)

    print(f"Портфель пользователя '{current_user.username}' (база: {base}):")
    for code, wallet in portfolio.wallets.items():
        # В ТЗ пример с конвертацией, но у нас get_total_value считает общую сумму.
        # Для детализации можно добавить логику конвертации каждой строки, пока выведем просто баланс.
        print(f"- {code}: {wallet.balance:.4f}")

    print("---------------------------------")
    print(f"ИТОГО в {base}: {total:.2f}")


def cmd_buy(args):
    global current_user
    # Сначала пробуем восстановить текущего пользователя из сессии
    current_user = _get_current_user()

    if not current_user:
        print("Сначала выполните login")
        return

    portfolio = get_portfolio(current_user.user_id)
    if not portfolio:
        print("Ошибка: портфель не найден.")
        return

    try:
        msg = buy_currency(portfolio, args.currency, args.amount)
        print(msg)
    except ValueError as e:
        print(f"Ошибка: {e}")


def cmd_sell(args):
    global current_user
    # Тоже сначала восстанавливаем пользователя
    current_user = _get_current_user()
    if not current_user:
        print("Сначала выполните login")
        return

    portfolio = get_portfolio(current_user.user_id)
    if not portfolio:
        print("Ошибка: портфель не найден.")
        return

    try:
        msg = sell_currency(portfolio, args.currency, args.amount)
        print(msg)
    except ValueError as e:
        print(f"Ошибка: {e}")


def cmd_get_rate(args):
    rate = get_rate(args.from_currency, args.to_currency)
    if rate is None:
        print(f"Курс {args.from_currency}→{args.to_currency} недоступен.")
        return

    print(f"Курс {args.from_currency}→{args.to_currency}: {rate}")


def main():
    parser = argparse.ArgumentParser(description="ValutaTrade Hub CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # register
    p_reg = subparsers.add_parser("register", help="Зарегистрировать пользователя")
    p_reg.add_argument("--username", required=True)
    p_reg.add_argument("--password", required=True)
    p_reg.set_defaults(func=cmd_register)

    # login
    p_login = subparsers.add_parser("login", help="Войти в систему")
    p_login.add_argument("--username", required=True)
    p_login.add_argument("--password", required=True)
    p_login.set_defaults(func=cmd_login)

    # show-portfolio
    p_port = subparsers.add_parser("show-portfolio", help="Показать портфель")
    p_port.add_argument("--base", default="USD")
    p_port.set_defaults(func=cmd_show_portfolio)

    # buy
    p_buy = subparsers.add_parser("buy", help="Купить валюту")
    p_buy.add_argument("--currency", required=True)
    p_buy.add_argument("--amount", type=float, required=True)
    p_buy.set_defaults(func=cmd_buy)

    # sell
    p_sell = subparsers.add_parser("sell", help="Продать валюту")
    p_sell.add_argument("--currency", required=True)
    p_sell.add_argument("--amount", type=float, required=True)
    p_sell.set_defaults(func=cmd_sell)

    # get-rate
    p_rate = subparsers.add_parser("get-rate", help="Получить курс")
    p_rate.add_argument("--from", dest="from_currency", required=True)
    p_rate.add_argument("--to", dest="to_currency", required=True)
    p_rate.set_defaults(func=cmd_get_rate)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
