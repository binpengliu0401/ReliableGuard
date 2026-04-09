from src.tools.reference_service import init_reference_db


def reset_reference_env():
    conn = init_reference_db()
    conn.execute('DELETE FROM "references"')
    conn.execute("DELETE FROM papers")
    conn.commit()
    conn.close()
    print("[ENV] Reset complete - reference tables cleared")


if __name__ == "__main__":
    reset_reference_env()
