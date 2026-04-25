import sqlite3

_cursor = None
_conn = None
ECOMMERCE_DB_PATH = "ecommerce.db"


def _ensure_column(cursor, table_name, column_name, column_def):
    existing_columns = [
        row[1] for row in cursor.execute(f"PRAGMA table_info({table_name})").fetchall()
    ]
    if column_name not in existing_columns:
        cursor.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}"
        )


def init_db():
    global _cursor, _conn
    if _conn is not None:
        return _cursor, _conn
    _conn = sqlite3.connect(ECOMMERCE_DB_PATH)
    _cursor = _conn.cursor()

    _cursor.execute("PRAGMA foreign_keys = ON")

    _cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL,
            status TEXT DEFAULT 'pending',
            refund_reason TEXT DEFAULT NULL
        )
        """
    )

    _ensure_column(_cursor, "orders", "refund_reason", "TEXT DEFAULT NULL")

    _conn.commit()
    print(f"Ecommerce database initialized successfully: {ECOMMERCE_DB_PATH}")

    return _cursor, _conn
