"""Декораторы для трассировки доменных операций."""

import logging
from functools import wraps

logger = logging.getLogger(__name__)

def log_action(action_name: str):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Собираем контекст из kwargs (там будут currency, amount и т.п.)
            extra_ctx = {
                "action": action_name,
                "user": kwargs.get("user"),
                "currency": kwargs.get("currency"),
                "amount": kwargs.get("amount"),
                "rate": kwargs.get("rate"),
                "base": kwargs.get("base"),
                "result": None,
                "error_type": None,
                "error_msg": None,
            }

            logger.info("START", extra=extra_ctx)

            try:
                result = func(*args, **kwargs)
                extra_ctx["result"] = str(result) if result is not None else "OK"
                logger.info("END OK", extra=extra_ctx)
                return result
            except Exception as e:
                extra_ctx["error_type"] = type(e).__name__
                extra_ctx["error_msg"] = str(e)
                logger.exception("END ERROR", extra=extra_ctx)
                raise
        return wrapper
    return decorator