# api.py
import krakenex
import time
import random
from typing import Any, Dict, Optional

# Список методов Kraken, которые требуют авторизации
PRIVATE_METHODS = {
    "Balance",
    "TradeBalance",
    "OpenOrders",
    "ClosedOrders",
    "Ledgers",
    "QueryLedgers",
    "AddOrder",
    "CancelOrder",
}


class KrakenAPI:
    """
    Обёртка для работы с Kraken API.
    Инкапсулирует krakenex и повторные попытки при ошибках.
    """

    def __init__(self, api_key: str, api_secret: str):
        self.api = krakenex.API(key=api_key, secret=api_secret)

    def _call(
        self, method: str, data: Optional[dict] = None, max_retries: int = 5
    ) -> Dict[str, Any]:
        """Универсальный вызов Kraken API с ретраями и бэкоффом"""
        if data is None:
            data = {}

        for attempt in range(1, max_retries + 1):
            try:
                # Выбираем публичный или приватный метод
                if method in PRIVATE_METHODS:
                    response = self.api.query_private(method, data)
                else:
                    response = self.api.query_public(method, data)

                if response.get("error"):
                    print(
                        f"[API ERROR] {response['error']} (попытка {attempt}/{max_retries})"
                    )
                    # backoff: экспоненциально + случайность
                    wait = (2**attempt) + random.uniform(2.5, 7.0)
                    print(f"[BACKOFF] Жду {wait:.1f} сек...")
                    time.sleep(wait)
                    continue

                return response.get("result", {})

            except Exception as e:
                print(f"[EXCEPTION] {e} (попытка {attempt}/{max_retries})")
                wait = (2**attempt) + random.uniform(2.5, 7.0)
                print(f"[BACKOFF] Жду {wait:.1f} сек...")
                time.sleep(wait)

        raise RuntimeError(
            f"Не удалось выполнить запрос {method} после {max_retries} попыток"
        )

    # -----------------------
    # API methods
    # -----------------------

    def get_assets(self) -> Dict[str, Any]:
        return self._call("Assets")

    def get_asset_pairs(self) -> Dict[str, Any]:
        return self._call("AssetPairs")

    def get_ticker(self, pair: str) -> Dict[str, Any]:
        return self._call("Ticker", {"pair": pair})

    def get_balance(self) -> Dict[str, Any]:
        return self._call("Balance")

    def get_ledgers(
        self, since: Optional[int] = None, ofs: Optional[int] = None
    ) -> Dict[str, Any]:
        """Получить леджер (с пагинацией и параметром since)."""
        data = {}
        if since is not None:
            data["since"] = since
        if ofs is not None:
            data["ofs"] = ofs
        return self._call("Ledgers", data)
