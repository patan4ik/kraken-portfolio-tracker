# config.py
import os


def load_keyfile(path="kraken.key"):
    """
    Загружает API ключи для Kraken.
    Сначала пытается из файла kraken.key (две строки: key, secret), Если файла нет — пробует загрузить из переменных окружения KRAKEN_API_KEY и KRAKEN_API_SECRET.
    Возвращает кортеж (api_key, api_secret).
    Выбрасывает RuntimeError с понятным сообщением, если ключи не найдены.
    """
    # 1️⃣ Попытка загрузки из файла - try from file
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            #        lines = [l.strip() for l in f.read().splitlines() if l.strip()]
            lines = [line.strip() for line in f.read().splitlines() if line.strip()]
        if len(lines) >= 2:
            return lines[0], lines[1]
        else:
            raise RuntimeError(
                f"{path} Файл найден, но не содержит два непустых значения (API key и secret).\n"
                f"{path} File exists but doesn't contain two non-empty lines (API key/secret)."
            )

    # 2️⃣ Попытка из переменных окружения - fallback: env vars
    api_key = os.getenv("KRAKEN_API_KEY")
    api_secret = os.getenv("KRAKEN_API_SECRET")
    if api_key and api_secret:
        return api_key, api_secret

    # 3️⃣ Если ничего нет — информативное сообщение - final message
    msg = (
        "API ключи Kraken не найдены.\n"
        f"1) Создайте файл {path} с двумя строками: <API key> и <API secret>\n"
        "   или\n"
        "2) Задайте переменные окружения KRAKEN_API_KEY и KRAKEN_API_SECRET\n"
        "После этого перезапустите скрипт.\n"
        "FYI: kraken.key missing and KRAKEN_API_KEY/KRAKEN_API_SECRET not set."
    )
    raise RuntimeError(msg)
