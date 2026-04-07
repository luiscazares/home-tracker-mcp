import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "home_tracker.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS expenses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            amount      REAL    NOT NULL,
            category    TEXT    NOT NULL,
            description TEXT,
            date        TEXT    NOT NULL,
            added_by    TEXT    DEFAULT 'me'
        );

        CREATE TABLE IF NOT EXISTS notes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            content     TEXT    NOT NULL,
            author      TEXT    NOT NULL DEFAULT 'me',
            tag         TEXT,
            created_at  TEXT    NOT NULL
        );
    """)
    conn.commit()
    conn.close()


# ── Expenses ────────────────────────────────────────────────────────────────

def insert_expense(amount: float, category: str, description: str,
                   date: str, added_by: str) -> int:
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO expenses (amount, category, description, date, added_by) "
        "VALUES (?, ?, ?, ?, ?)",
        (amount, category.lower(), description, date, added_by)
    )
    conn.commit()
    row_id = c.lastrowid
    conn.close()
    return row_id # type: ignore


def query_expenses(start_date: str, end_date: str) -> list[dict]:
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM expenses WHERE date BETWEEN ? AND ? ORDER BY date ASC",
        (start_date, end_date)
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def summary_by_category(start_date: str, end_date: str) -> list[dict]:
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """
        SELECT category,
               COUNT(*)        AS count,
               ROUND(SUM(amount), 2) AS total
        FROM   expenses
        WHERE  date BETWEEN ? AND ?
        GROUP  BY category
        ORDER  BY total DESC
        """,
        (start_date, end_date)
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


# ── Notes ───────────────────────────────────────────────────────────────────

def insert_note(content: str, author: str, tag: str | None) -> int:
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO notes (content, author, tag, created_at) VALUES (?, ?, ?, ?)",
        (content, author, tag, datetime.now().isoformat(timespec="seconds"))
    )
    conn.commit()
    row_id = c.lastrowid
    conn.close()
    return row_id # type: ignore


def fetch_notes(limit: int = 20, author: str | None = None,
                tag: str | None = None) -> list[dict]:
    conn = get_conn()
    c = conn.cursor()
    filters, params = [], []
    if author:
        filters.append("author = ?")
        params.append(author)
    if tag:
        filters.append("tag = ?")
        params.append(tag)
    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    c.execute(
        f"SELECT * FROM notes {where} ORDER BY created_at DESC LIMIT ?",
        params + [limit]
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def remove_note(note_id: int) -> bool:
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    conn.commit()
    deleted = c.rowcount > 0
    conn.close()
    return deleted
