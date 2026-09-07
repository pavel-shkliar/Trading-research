"""
Общий модуль для работы с базой данных Postgres.

Все скрипты скачивания данных импортируют отсюда get_connection()
и create_tables() — чтобы не дублировать код подключения в каждом файле.
"""

import os

import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

# Подгружает переменные из файла .env (host, user, password и т.д.)
# в окружение процесса, как будто ты их прописал через set/export вручную.
load_dotenv()


def get_connection():
    """Открывает новое соединение с базой Postgres, используя данные из .env."""
    return psycopg2.connect(
        host=os.environ["POSTGRES_HOST"],
        port=os.environ["POSTGRES_PORT"],
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )


# SQL для создания всех таблиц проекта. Каждая таблица имеет UNIQUE
# ограничение на (symbol, время) — это защита от дублей: если случайно
# попробовать вставить строку, которая уже есть, база её просто проигнорирует
# (см. ON CONFLICT DO NOTHING в скриптах скачивания).
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS candles (
    symbol TEXT NOT NULL,
    open_time TIMESTAMPTZ NOT NULL,
    open DOUBLE PRECISION NOT NULL,
    high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL,
    close DOUBLE PRECISION NOT NULL,
    volume DOUBLE PRECISION NOT NULL,
    trades BIGINT NOT NULL,
    UNIQUE (symbol, open_time)
);

CREATE TABLE IF NOT EXISTS funding_rate (
    symbol TEXT NOT NULL,
    funding_time TIMESTAMPTZ NOT NULL,
    funding_rate DOUBLE PRECISION NOT NULL,
    UNIQUE (symbol, funding_time)
);

CREATE TABLE IF NOT EXISTS open_interest (
    symbol TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    sum_open_interest DOUBLE PRECISION NOT NULL,
    sum_open_interest_value DOUBLE PRECISION NOT NULL,
    UNIQUE (symbol, ts)
);

CREATE TABLE IF NOT EXISTS top_trader_ratio (
    symbol TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    long_account_ratio DOUBLE PRECISION NOT NULL,
    short_account_ratio DOUBLE PRECISION NOT NULL,
    long_short_ratio DOUBLE PRECISION NOT NULL,
    UNIQUE (symbol, ts)
);

CREATE TABLE IF NOT EXISTS taker_volume (
    symbol TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    buy_sell_ratio DOUBLE PRECISION NOT NULL,
    buy_vol DOUBLE PRECISION NOT NULL,
    sell_vol DOUBLE PRECISION NOT NULL,
    UNIQUE (symbol, ts)
);

CREATE TABLE IF NOT EXISTS dvol (
    currency TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    open DOUBLE PRECISION NOT NULL,
    high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL,
    close DOUBLE PRECISION NOT NULL,
    UNIQUE (currency, ts)
);

-- Таблица для посчитанных индикаторов (шаг 4 плана) - в отличие от таблиц
-- выше, тут не "сырые" данные с биржи, а то, что мы сами вычислили поверх
-- них. Отдельная таблица, а не колонки в candles - чтобы можно было
-- пересчитать/удалить индикаторы и переделать заново, не трогая сырые
-- данные.
CREATE TABLE IF NOT EXISTS indicators (
    symbol TEXT NOT NULL,
    date TIMESTAMPTZ NOT NULL,
    rsi_14 DOUBLE PRECISION,
    bb_upper DOUBLE PRECISION,
    bb_mid DOUBLE PRECISION,
    bb_lower DOUBLE PRECISION,
    vwap_20 DOUBLE PRECISION,
    funding_rate_daily_avg DOUBLE PRECISION,
    funding_percentile_90d DOUBLE PRECISION,
    dvol_close DOUBLE PRECISION,
    dvol_percentile_90d DOUBLE PRECISION,
    oi_change_pct DOUBLE PRECISION,
    price_oi_divergence TEXT,
    UNIQUE (symbol, date)
);
"""


def create_tables():
    """Создаёт все таблицы проекта, если их ещё нет (безопасно запускать
    повторно — IF NOT EXISTS не даст ничего сломать)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()


def upsert_rows(table: str, columns: list, rows: list, conflict_columns: list) -> int:
    """
    Массово вставляет строки в таблицу, игнорируя те, что уже есть
    (по UNIQUE-ограничению на conflict_columns).

    table — имя таблицы, columns — список имён столбцов в том же порядке,
    что и значения внутри каждого кортежа rows, conflict_columns —
    по каким столбцам проверять "а такая запись уже есть?" (обычно
    symbol + время).

    Возвращает количество строк, которые пытались вставить (не факт, что
    все реально новые — часть могла быть проигнорирована как дубль).
    """
    if not rows:
        return 0

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            columns_sql = ", ".join(columns)
            conflict_sql = ", ".join(conflict_columns)
            query = (
                f"INSERT INTO {table} ({columns_sql}) VALUES %s "
                f"ON CONFLICT ({conflict_sql}) DO NOTHING"
            )
            execute_values(cur, query, rows)
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def get_last_timestamp(table: str, time_column: str, symbol_column: str, symbol_value: str):
    """Возвращает самое позднее сохранённое время для данного symbol/currency
    в указанной таблице — нужно для инкрементального скачивания (качаем
    только то, чего ещё нет)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT MAX({time_column}) FROM {table} WHERE {symbol_column} = %s",
                (symbol_value,),
            )
            return cur.fetchone()[0]
    finally:
        conn.close()


def get_saved_range(table: str, time_column: str, symbol_column: str, symbol_value: str):
    """Возвращает (самое раннее, самое позднее) сохранённое время для
    данного symbol/currency. Нужно, чтобы правильно докачивать данные
    с ДВУХ сторон: и более старую историю (если раньше скачали только
    недавний тестовый кусок), и более новую (обычное инкрементальное
    обновление). Если данных ещё нет вообще — вернёт (None, None)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT MIN({time_column}), MAX({time_column}) FROM {table} WHERE {symbol_column} = %s",
                (symbol_value,),
            )
            return cur.fetchone()
    finally:
        conn.close()


def read_df(query: str, params: tuple = None):
    """Выполняет SQL-запрос и возвращает результат как pandas DataFrame -
    удобно для скриптов, которые считают индикаторы (compute_indicators.py
    и далее бэктест)."""
    import pandas as pd  # импорт здесь, а не в шапке файла - чтобы модуль
    # db.py оставался лёгким для скриптов, которым pandas не нужен

    conn = get_connection()
    try:
        return pd.read_sql(query, conn, params=params)
    finally:
        conn.close()


if __name__ == "__main__":
    create_tables()
    print("Таблицы созданы (или уже существовали).")
