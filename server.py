"""
Home Tracker MCP Server
-----------------------
Tools:
  1. log_expense
  2. get_summary
  3. add_note
  4. get_notes
  5. delete_note
  6. send_weekly_digest
  7. send_alert
"""

import os
from datetime import datetime, timedelta, date

from dotenv import load_dotenv
load_dotenv()

from mcp.server.fastmcp import FastMCP
from db import (
    init_db,
    insert_expense,
    query_expenses,
    summary_by_category,
    insert_note,
    fetch_notes,
    remove_note,
)
from email_utils import (
    send_weekly_digest as email_weekly_digest,
    send_alert as email_alert,
)

# ── Bootstrap ────────────────────────────────────────────────────────────────
init_db()

MY_EMAIL   = os.getenv("MY_EMAIL", "")
WIFE_EMAIL = os.getenv("WIFE_EMAIL", "")

mcp = FastMCP("home-tracker")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _all_recipients(to_me: bool, to_wife: bool) -> list[str]:
    recipients = []
    if to_me and MY_EMAIL:
        recipients.append(MY_EMAIL)
    if to_wife and WIFE_EMAIL:
        recipients.append(WIFE_EMAIL)
    return recipients


# ── Tool 1: log_expense ──────────────────────────────────────────────────────

@mcp.tool()
def log_expense(
    amount: float,
    category: str,
    description: str = "",
    date: str = "",
    added_by: str = "me",
) -> dict:
    """
    Log a household expense.

    Args:
        amount:      Dollar amount (e.g. 45.50)
        category:    Category label (e.g. groceries, utilities, dining, rent)
        description: Optional short note about the purchase
        date:        Date in YYYY-MM-DD format; defaults to today
        added_by:    Who logged it — 'me' or 'wife'

    Returns:
        Confirmation with the new expense ID.
    """
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    row_id = insert_expense(amount, category, description, date, added_by)
    return {
        "ok": True,
        "id": row_id,
        "message": f"Logged ${amount:.2f} under '{category}' on {date}."
    }


# ── Tool 2: get_summary ──────────────────────────────────────────────────────

@mcp.tool()
def get_summary(period: str = "month") -> dict:
    """
    Get a spending summary broken down by category.

    Args:
        period: 'week' for the last 7 days, 'month' for the current calendar
                month, or a custom range as 'YYYY-MM-DD:YYYY-MM-DD'

    Returns:
        Period label, category breakdown, and grand total.
    """
    today = date.today()

    if period == "week":
        start = (today - timedelta(days=6)).isoformat()
        end   = today.isoformat()
        label = f"Week of {start} – {end}"
    elif period == "month":
        start = today.replace(day=1).isoformat()
        end   = today.isoformat()
        label = today.strftime("%B %Y")
    elif ":" in period:
        start, end = period.split(":", 1)
        label = f"{start} to {end}"
    else:
        return {"ok": False, "error": "period must be 'week', 'month', or 'YYYY-MM-DD:YYYY-MM-DD'"}

    breakdown = summary_by_category(start, end)
    grand_total = round(sum(r["total"] for r in breakdown), 2)

    return {
        "ok": True,
        "period": label,
        "start": start,
        "end": end,
        "breakdown": breakdown,
        "total": grand_total,
    }


# ── Tool 3: add_note ─────────────────────────────────────────────────────────

@mcp.tool()
def add_note(
    content: str,
    author: str = "me",
    tag: str = "",
) -> dict:
    """
    Add a shared note visible to both you and your wife.

    Args:
        content: The note text
        author:  Who wrote it — 'me' or 'wife'
        tag:     Optional label, e.g. 'reminder', 'budget', 'grocery'

    Returns:
        Confirmation with the new note ID.
    """
    tag_val = tag if tag else None
    row_id = insert_note(content, author, tag_val)
    return {"ok": True, "id": row_id, "message": "Note saved."}


# ── Tool 4: get_notes ────────────────────────────────────────────────────────

@mcp.tool()
def get_notes(
    limit: int = 10,
    author: str = "",
    tag: str = "",
) -> dict:
    """
    Retrieve shared notes, newest first.

    Args:
        limit:  Max number of notes to return (default 10)
        author: Filter by author — 'me' or 'wife' (leave blank for all)
        tag:    Filter by tag label (leave blank for all)

    Returns:
        List of matching notes.
    """
    notes = fetch_notes(
        limit=limit,
        author=author if author else None,
        tag=tag if tag else None,
    )
    return {"ok": True, "count": len(notes), "notes": notes}


# ── Tool 5: delete_note ──────────────────────────────────────────────────────

@mcp.tool()
def delete_note(note_id: int) -> dict:
    """
    Delete a note by its ID.

    Args:
        note_id: The ID of the note to remove (get IDs via get_notes)

    Returns:
        Success or not-found message.
    """
    deleted = remove_note(note_id)
    if deleted:
        return {"ok": True, "message": f"Note {note_id} deleted."}
    return {"ok": False, "message": f"No note found with ID {note_id}."}


# ── Tool 6: send_weekly_digest ───────────────────────────────────────────────

@mcp.tool()
def send_weekly_digest(
    period: str = "week",
    to_me: bool = True,
    to_wife: bool = True,
) -> dict:
    """
    Email a formatted spending summary to you and/or your wife.

    Args:
        period:   Same as get_summary — 'week', 'month', or 'YYYY-MM-DD:YYYY-MM-DD'
        to_me:    Send to your email address
        to_wife:  Send to your wife's email address

    Returns:
        Send result with recipient list.
    """
    summary = get_summary(period)
    if not summary["ok"]:
        return summary

    recipients = _all_recipients(to_me, to_wife)
    if not recipients:
        return {"ok": False, "error": "No recipients configured. Set MY_EMAIL / WIFE_EMAIL in .env"}

    result = email_weekly_digest(
        period_label=summary["period"],
        total=summary["total"],
        breakdown=summary["breakdown"],
        recipients=recipients,
    )
    return result


# ── Tool 7: send_alert ───────────────────────────────────────────────────────

@mcp.tool()
def send_alert(
    title: str,
    message: str,
    amount: float = 0.0,
    to_me: bool = True,
    to_wife: bool = True,
) -> dict:
    """
    Send a one-off alert email — useful for big purchases or budget warnings.

    Args:
        title:    Short subject/title for the alert (e.g. 'Big purchase logged')
        message:  Body of the alert
        amount:   Optional dollar amount to include (0.0 to omit)
        to_me:    Send to your email address
        to_wife:  Send to your wife's email address

    Returns:
        Send result with recipient list.
    """
    recipients = _all_recipients(to_me, to_wife)
    if not recipients:
        return {"ok": False, "error": "No recipients configured. Set MY_EMAIL / WIFE_EMAIL in .env"}

    result = email_alert(
        title=title,
        message=message,
        amount=amount if amount > 0 else None,
        recipients=recipients,
    )
    return result


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="stdio")
