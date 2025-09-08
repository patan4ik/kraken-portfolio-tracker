# api.py
import krakenex
import time
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
        self, method: str, data: Optional[dict] = None, max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Универсальный вызов Kraken API с повторными попытками при ошибках.
        """
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
                    time.sleep(2 * attempt)
                    continue

                return response.get("result", {})

            except Exception as e:
                print(f"[EXCEPTION] {e} (попытка {attempt}/{max_retries})")
                time.sleep(2 * attempt)

        raise RuntimeError(
            f"Не удалось выполнить запрос {method} после {max_retries} попыток"
        )

    # -----------------------
    # Методы API
    # -----------------------

    def get_assets(self) -> Dict[str, Any]:
        """Получить список всех активов (Assets)."""
        return self._call("Assets")

    def get_asset_pairs(self) -> Dict[str, Any]:
        """Получить список всех торговых пар (AssetPairs)."""
        return self._call("AssetPairs")

    def get_ticker(self, pair: str) -> Dict[str, Any]:
        """Получить тикер по торговой паре (например, XXBTZEUR)."""
        return self._call("Ticker", {"pair": pair})

    def get_balance(self) -> Dict[str, Any]:
        """Получить баланс аккаунта."""
        return self._call("Balance")

    def get_ledgers(self, since: Optional[int] = None) -> Dict[str, Any]:
        """Получить леджер (все операции)."""
        data = {"since": since} if since else {}
        return self._call("Ledgers", data)
