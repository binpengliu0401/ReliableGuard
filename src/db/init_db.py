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
            status TEXT DEFAULT 'pending')
    """
    )
    _conn.commit()
    print("Table 'orders' created successfully.")
    return _cursor, _conn
