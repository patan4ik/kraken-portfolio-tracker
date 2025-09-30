# src/config.py
import os

# Каталог, куда складываются все отчёты, базы и историю
DATA_DIR = "balances_history"

# Для совместимости с balances.py
BALANCES_HISTORY_DIR = DATA_DIR

# Создаём папку, если её нет (иначе start.py и тесты могут падать)
os.makedirs(DATA_DIR, exist_ok=True)

# Default parameters
DEFAULT_PAGE_SIZE = 50  # Пагинация (размер страницы у Kraken API)
DEFAULT_DAYS = 7  # Сколько дней назад тянуть данные по умолчанию
DEFAULT_DELAY_MIN = 1.0  # Задержка между страницами (секунды)
DEFAULT_DELAY_MAX = 2.5  # Задержка между страницами (секунды)
