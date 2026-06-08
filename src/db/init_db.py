import os
import sqlite3

_cursor = None
_conn = None
# DB file path, optionally per-process isolated via RG_DB_SUFFIX. Sharded/parallel
# record runs each set a distinct suffix (e.g. RG_DB_SUFFIX=shard0) so they never
# share the same SQLite file. Read at import; set the env var before launching.
_DB_SUFFIX = os.environ.get("RG_DB_SUFFIX", "")
ECOMMERCE_DB_PATH = f"ecommerce.{_DB_SUFFIX}.db" if _DB_SUFFIX else "ecommerce.db"


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

    # Inventory table for the clean state-local F4 supplementary experiment. A quantity
    # field whose post-value is plausible on its own, so a false-success no-op is only
    # detectable by the pre/post state-transition check (not by an answer-local claim).
    _cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS inventory (
            product_id INTEGER PRIMARY KEY,
            name TEXT,
            stock INTEGER
        )
        """
    )
    if _cursor.execute("SELECT COUNT(*) FROM inventory").fetchone()[0] == 0:
        _cursor.executemany(
            "INSERT INTO inventory(product_id, name, stock) VALUES(?, ?, ?)",
            [(1, "Widget", 10), (2, "Gadget", 25), (3, "Gizmo", 7),
             (4, "Sprocket", 100), (5, "Cog", 50)],
        )

    _conn.commit()
    print(f"Ecommerce database initialized successfully: {ECOMMERCE_DB_PATH}")

    return _cursor, _conn
