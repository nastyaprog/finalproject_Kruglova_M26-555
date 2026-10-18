"""Утилиты для работы с JSON-файлами: загрузка и сохранение данных."""

import json
from pathlib import Path


def load_json(path: Path) -> list:
    """Загружает список данных из JSON-файла.

    Если файл не существует или содержит некорректный JSON, возвращает
    пустой список.

    Args:
        path: Путь к JSON-файлу.

    Returns:
        Список данных или пустой список при ошибке.
    """
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def save_json(path: Path, data: list) -> None:
    """Сохраняет список данных в JSON-файл с отступами.

    Автоматически создаёт родительские директории, если они отсутствуют.

    Args:
        path: Путь к файлу.
        data: Список данных для записи.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
