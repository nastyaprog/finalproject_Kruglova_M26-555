# ValutaTrade Hub

Консольное приложение-симулятор валютного кошелька. Реализует базовый цикл работы пользователя: регистрация, авторизация, операции с портфелем, покупка/продажа валюты с проверкой баланса.

---

## Возможности

- **Регистрация и авторизация пользователей** — создание аккаунта, вход, выход, защита от повторного создания пользователя.
- **Мультивалютный портфель** — хранение нескольких валют, проверка остатков перед операциями.
- **Покупка/продажа валюты** — операции по заданному курсу, валидация баланса (нельзя продать больше, чем есть).
- **Просмотр портфеля и курсов** — команда `show-portfolio` для отображения активов, `get-rate` для получения курса.
- **Логирование операций** — все действия фиксируются в лог-файле с контекстом (действие, пользователь, валюта, сумма и т.д.).

> ⚠️ **Важно для тестирования:** проверка актуальности курсов временно отключена флагом `DEBUG_SKIP_RATE_CHECK = True` в `valutatrade_hub/core/usecases.py`. Это сделано для возможности тестирования потока операций без реального API. Перед финальным ревью флаг следует убрать или заменить на полноценную логику кэширования курсов.

---

## Запуск

```bash
uv run python -m valutatrade_hub.cli.interface --help

## Структура проекта
valutatrade_hub/cli/interface.py — точка входа CLI, настройка argparse, обработка команд.
valutatrade_hub/core/usecases.py — бизнес-логика (покупка, продажа, валидации, сохранение портфеля).
valutatrade_hub/infra/logging_config.py — конфигурация логирования.
valutatrade_hub/decorators.py — декораторы для трассировки действий (@log_action).

## Требования и зависимости
Python 3.12+
Управление зависимостями и запуском через uv
Линтер: ruff

## Основные команды CLI

register	Регистрация нового пользователя	uv run python -m valutatrade_hub.cli.interface register --username testuser --password 12345
login	Вход в систему	uv run python -m valutatrade_hub.cli.interface login --username testuser --password 12345
logout	Выход из системы	uv run python -m valutatrade_hub.cli.interface logout
buy	Покупка валюты по курсу	uv run python -m valutatrade_hub.cli.interface buy BTC 0.005 --rate 50000
sell	Продажа валюты по курсу	uv run python -m valutatrade_hub.cli.interface sell BTC 0.002 --rate 50000
show-portfolio	Просмотр текущего портфеля	uv run python -m valutatrade_hub.cli.interface show-portfolio
get-rate	Получение актуального курса	uv run python -m valutatrade_hub.cli.interface get-rate