"""Конфигурация проекта: Singleton SettingsLoader."""
import os
from pathlib import Path
from typing import Any, ClassVar, Optional, Self


class SettingsLoader:
    """Singleton для загрузки и доступа к настройкам проекта."""

    _instance: Optional["SettingsLoader"] = None

    # Дефолтные значения (можно переопределить из файла/pyproject.toml)
    _defaults: ClassVar[dict[str, Any]] = {
        "data_dir": "data",
        "rates_ttl_seconds": 3600, #fallback
        "default_base_currency": "USD",
        "log_file": "logs/actions.log",
        "log_level": "INFO",
    }

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        """Гарантирует существование только одного экземпляра класса."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # Инициализация при первом создании
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Ленивая инициализация конфигурации."""
        if getattr(self, "_initialized", False):
            return
        self._config: dict[str, Any] = self._defaults.copy()
        self._initialized = True

        # загрузка из .env с приоритетом над дефолтами ---
        # rates_ttl_seconds
        ttl_env = os.getenv("RATES_TTL_SECONDS")
        if ttl_env is not None:
            try:
                self._config["rates_ttl_seconds"] = int(ttl_env)
            except ValueError:
                pass  # fallback на дефолт, если в .env мусор

        # data_dir
        data_dir_env = os.getenv("DATA_DIR")
        if data_dir_env:
            self._config["data_dir"] = data_dir_env

        # log_file
        log_file_env = os.getenv("LOG_FILE")
        if log_file_env:
            self._config["log_file"] = log_file_env

    def get(self, key: str, default: Any = None) -> Any:
        """
        Получает значение настройки по ключу.

        Args:
            key: Ключ настройки.
            default: Значение по умолчанию, если ключ не найден.

        Returns:
            Значение настройки или default.
        """
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Устанавливает значение настройки (для тестов/динамической настройки).

        Args:
            key: Ключ.
            value: Значение.
        """
        self._config[key] = value

    def reload(self) -> None:
        """Перезагружает конфигурацию (заглушка)."""
        # В будущем: повторная загрузка из файлов/pyproject.toml

    @property
    def data_dir(self) -> Path:
        """Возвращает путь к директории данных."""
        return Path(self.get("data_dir", "data"))

    @property
    def rates_ttl_seconds(self) -> int:
        """TTL для кэша курсов валют в секундах."""
        return int(self.get("rates_ttl_seconds", 3600))
