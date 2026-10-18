"""Настройка логирования для ValutaTrade Hub."""

import logging
from pathlib import Path


def configure_logging(log_file: str = "logs/actions.log", level: str = "INFO") -> None:
    """
    Настраивает логирование: файл с ротацией, формат сообщений.

    Args:
        log_file: Путь к файлу лога.
        level: Уровень логирования (INFO, DEBUG и т.д.).
    """
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        filename=log_path,
        level=getattr(logging, level.upper(), logging.INFO),
        format=(
            "%(asctime)s %(levelname)-8s "
            "action=%(action)s "
            "message=%(message)s"
        ),
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
