import sqlite3

def init_db():
    conn = sqlite3.connect("orders.db")
    cursor = conn.cursor()
    cursor.execute(
        """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount REAL,
                status TEXT DEFAULT 'pending'
            )
        """
    )
    conn.commit()
    print("Table 'orders' created successfully.")
    return cursor, conn
