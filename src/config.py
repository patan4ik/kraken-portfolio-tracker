# config.py
import os
from keys import load_keys  # our new secure storage (keyring + encrypted file)

DATA_DIR = "balances_history"

# Default parameters
DEFAULT_PAGE_SIZE = 50  # Пагинация (размер страницы у Kraken API)
DEFAULT_DAYS = 7  # Сколько дней назад тянуть данные по умолчанию
DEFAULT_DELAY_MIN = 1.0  # Задержка между страницами (секунды)
DEFAULT_DELAY_MAX = 2.5  # Задержка между страницами (секунды)


def load_keyfile(path="kraken.key"):
    """
    Load Kraken API keys in order of preference:
    1) From secure storage via keys.py (encrypted file / keyring).
    2) From local file `kraken.key` (two lines: key, secret).
    3) From environment variables KRAKEN_API_KEY / KRAKEN_API_SECRET.
    If all methods fail, raise RuntimeError with a clear message.
    """
    # 1️⃣ Try secure storage (preferred)
    try:
        return load_keys()
    except RuntimeError:
        pass  # fall through if not configured

    # 2️⃣ Try plain file
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.read().splitlines() if line.strip()]
        if len(lines) >= 2:
            return lines[0], lines[1]
        else:
            raise RuntimeError(
                f"{path} exists but does not contain two non-empty lines (API key and secret)."
            )

    # 3️⃣ Try environment variables
    api_key = os.getenv("KRAKEN_API_KEY")
    api_secret = os.getenv("KRAKEN_API_SECRET")
    if api_key and api_secret:
        return api_key, api_secret

    # 4️⃣ Final error
    msg = (
        "❌ Kraken API keys not found.\n"
        f"1) Store them securely using keys.py helper (preferred)\n"
        f"   python -c \"from keys import save_keys; save_keys('API_KEY','API_SECRET')\"\n"
        f"2) Or create a file {path} with two lines: <API key> and <API secret>\n"
        "3) Or set environment variables KRAKEN_API_KEY and KRAKEN_API_SECRET\n"
        "After that, restart the script."
    )
    raise RuntimeError(msg)

    # def load_keyfile(path="kraken.key"):
    """
    Загружает API ключи для Kraken.
    Сначала пытается из файла kraken.key (две строки: key, secret), Если файла нет — пробует загрузить из переменных окружения KRAKEN_API_KEY и KRAKEN_API_SECRET.
    Возвращает кортеж (api_key, api_secret).
    Выбрасывает RuntimeError с понятным сообщением, если ключи не найдены.
    """
    # 1️⃣ Попытка загрузки из файла - try from file
    """
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
    """
