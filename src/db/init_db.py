import sqlite3

_cursor = None
_conn = None


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
    _conn = sqlite3.connect("reliableguard.db")
    _cursor = _conn.cursor()

    _cursor.execute("PRAGMA foreign_keys = ON")

    # orders
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

    # Migration guard: orders.refund_reason
    _ensure_column(_cursor, "orders", "refund_reason", "TEXT DEFAULT NULL")

    # paper
    _cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS papers (
            paper_id TEXT PRIMARY KEY,
            pdf_path TEXT NOT NULL,
            title TEXT DEFAULT '',
            status TEXT DEFAULT 'pending'
        )
        """
    )
    _ensure_column(_cursor, "papers", "title", "TEXT DEFAULT ''")
    _ensure_column(_cursor, "papers", "status", "TEXT DEFAULT 'pending'")

    # Reference
    _cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS refs (
            ref_id INTEGER PRIMARY KEY AUTOINCREMENT,
            paper_id TEXT NOT NULL,
            title TEXT DEFAULT '',
            authors TEXT DEFAULT '[]',
            doi TEXT DEFAULT NULL,
            journal TEXT DEFAULT '',
            year INTEGER,
            doi_status TEXT DEFAULT 'pending',
            authors_status TEXT DEFAULT 'pending',
            journal_status TEXT DEFAULT 'pending',
            FOREIGN KEY (paper_id) REFERENCES papers(paper_id)
        )
        """
    )

    # Migration guard
    _ensure_column(_cursor, "refs", "title", "TEXT DEFAULT ''")
    _ensure_column(_cursor, "refs", "authors", "TEXT DEFAULT '[]'")
    _ensure_column(_cursor, "refs", "doi", "TEXT DEFAULT NULL")
    _ensure_column(_cursor, "refs", "journal", "TEXT DEFAULT ''")
    _ensure_column(_cursor, "refs", "year", "INTEGER")
    _ensure_column(_cursor, "refs", "doi_status", "TEXT DEFAULT 'pending'")
    _ensure_column(_cursor, "refs", "authors_status", "TEXT DEFAULT 'pending'")
    _ensure_column(_cursor, "refs", "journal_status", "TEXT DEFAULT 'pending'")

    _conn.commit()
    print("Database initialized successfully.")

    return _cursor, _conn
