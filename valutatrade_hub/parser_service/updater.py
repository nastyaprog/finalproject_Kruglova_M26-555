# valutatrade_hub/parser_service/updater.py
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from valutatrade_hub.infra.settings import SettingsLoader

from .api_clients import BaseApiClient

logger = logging.getLogger(__name__)
settings = SettingsLoader()

def run_update(clients: list[BaseApiClient]) -> tuple[int, int]:
    """
    Опрашивает все клиенты, объединяет курсы и атомарно сохраняет в rates.json.
    Возвращает (total_saved, errors).
    """
    data_dir = settings.get("data_dir", "data")
    rates_path = Path(data_dir) / "rates.json"
    tmp_path = rates_path.with_suffix(".tmp")

    all_rates: dict[str, dict] = {}
    total_saved = 0
    errors = 0

    last_refresh = datetime.now(UTC).isoformat()

    for client in clients:
        try:
            rates = client.fetch_rates()
            for pair, rate in rates.items():
                all_rates[pair] = {
                    "rate": float(rate),
                    "updated_at": last_refresh,
                    "source": client.__class__.__name__,
                }
            total_saved += len(rates)
            logger.info(
                f"Получено курсов от {client.__class__.__name__}: {len(rates)}",
                extra={"action": "UPDATE_RATES"}
            )
        except Exception:
            errors += 1
            logger.exception(
                f"Ошибка при загрузке курсов от {client.__class__.__name__}",
                extra={"action": "UPDATE_RATES"}
            )

    # Атомарная запись: пишем во временный файл, потом переименовываем
    try:
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump({
                "pairs": all_rates,
                "last_refresh": last_refresh,
            }, f, indent=2)

        tmp_path.replace(rates_path)  # атомарное переименование
        logger.info(
            "Курсы успешно сохранены в rates.json",
            extra={"action": "UPDATE_RATES", "total_saved": total_saved, "errors": errors}
        )
    except Exception:
        logger.exception("Ошибка при сохранении кеша курсов", extra={"action": "UPDATE_RATES"})
        raise

    return total_saved, errors
