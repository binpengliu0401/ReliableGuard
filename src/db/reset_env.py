from src.domain.ecommerce.tools import cursor, conn


def reset_env():
    cursor.execute("DELETE FROM orders")  # type: ignore
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='orders'")  # type: ignore
    conn.commit()
    print("[ENV]    Reset complete - orders table cleared, ID sequence reset")


if __name__ == "__main__":
    reset_env()
