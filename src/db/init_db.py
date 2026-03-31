import sqlite3

_cursor = None
_conn = None


def init_db():
    global _cursor, _conn
    if _conn is not None:
        return _cursor, _conn

    _conn = sqlite3.connect("orders.db")
    _cursor = _conn.cursor()
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
    # Migration guard: add refund_reason if table already exists without it
    existing_columns = [
        row[1] for row in _cursor.execute("PRAGMA table_info(orders)").fetchall()
    ]
    if "refund_reason" not in existing_columns:
        _cursor.execute("ALTER TABLE orders ADD COLUMN refund_reason TEXT DEFAULT NULL")
    _conn.commit()
    print("Table 'orders' initialized successfully.")
    return _cursor, _conn
