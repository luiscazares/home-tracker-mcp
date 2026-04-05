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
    send_notes_summary as email_notes_summary,

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
        amount:      Dollar amount (e.g. 45.50). Must be positive.
        category:    Category label (e.g. groceries, utilities, dining, rent).
                     Will be normalized to lowercase with whitespace trimmed.
        description: Optional short note about the purchase (max 200 chars).
        date:        Date in YYYY-MM-DD format; defaults to today.
        added_by:    Who logged it — 'me' or 'wife'.

    Returns:
        Confirmation dict with ok, id, and message.

    Raises:
        ValueError: If amount is not positive or date format is invalid.
    """
    # ── Validate amount ───────────────────────────────────────────────────────
    if amount <= 0:
        return {
            "ok": False,
            "error": f"Invalid amount: ${amount:.2f}. Amount must be positive."
        }

    # ── Normalize category ────────────────────────────────────────────────────
    normalized_category = category.lower().strip()
    if not normalized_category:
        return {
            "ok": False,
            "error": "Category cannot be empty. Please provide a valid category name."
        }

    # ── Trim and limit description ────────────────────────────────────────────
    description = description.strip()[:200] if description else ""

    # ── Validate and normalize date ───────────────────────────────────────────
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    try:
        # Validate date format by parsing it
        parsed_date = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return {
            "ok": False,
            "error": f"Invalid date format '{date}'. Use YYYY-MM-DD format."
        }

    # ── Validate added_by ─────────────────────────────────────────────────────
    valid_authors = {"me", "wife"}
    normalized_author = added_by.lower().strip()
    if normalized_author not in valid_authors:
        return {
            "ok": False,
            "error": f"Invalid author '{added_by}'. Must be 'me' or 'wife'."
        }

    # ── Insert into database ──────────────────────────────────────────────────
    row_id = insert_expense(amount, normalized_category, description, date, normalized_author)

    return {
        "ok": True,
        "id": row_id,
        "amount": amount,
        "category": normalized_category,
        "date": date,
        "message": f"Logged ${amount:.2f} under '{normalized_category}' on {date}."
    }


# ── Tool 2: get_summary ──────────────────────────────────────────────────────

@mcp.tool()
def get_summary(period: str = "month") -> dict:
    """
    Get a spending summary broken down by category.

    Args:
        period: Time period to summarize. Options:
            - 'week': Last 7 days including today
            - 'month': Current calendar month (1st day to today)
            - 'YYYY-MM-DD:YYYY-MM-DD': Custom date range (inclusive)

    Returns:
        Dict with ok flag, period label, start/end dates, category breakdown, and grand total.

    Raises:
        ValueError: If period is invalid or date range cannot be parsed.
    """
    today = date.today()

    # ── Normalize input ───────────────────────────────────────────────────────
    normalized_period = period.strip().lower() if period else "month"

    # ── Handle predefined periods ──────────────────────────────────────────────
    if normalized_period == "week":
        start = (today - timedelta(days=6)).isoformat()
        end   = today.isoformat()
        label = f"Week of {start} – {end}"
    elif normalized_period == "month":
        start = today.replace(day=1).isoformat()
        end   = today.isoformat()
        label = today.strftime("%B %Y")

    # ── Handle custom date ranges ──────────────────────────────────────────────
    elif ":" in period:
        range_parts = period.split(":", 1)
        if len(range_parts) != 2:
            return {
                "ok": False,
                "error": f"Invalid date range '{period}'. Format must be 'YYYY-MM-DD:YYYY-MM-DD'."
            }
        start_str, end_str = [p.strip() for p in range_parts]

        # Validate date format
        try:
            start_date = datetime.strptime(start_str, "%Y-%m-%d")
            end_date = datetime.strptime(end_str, "%Y-%m-%d")
        except ValueError as e:
            return {
                "ok": False,
                "error": f"Invalid date format. Expected YYYY-MM-DD, got: '{period}'."
            }

        start = start_str
        end = end_str
        label = f"{start} to {end}"

    else:
        return {
            "ok": False,
            "error": f"Unknown period '{period}'. Use 'week', 'month', or 'YYYY-MM-DD:YYYY-MM-DD'."
        }

    # ── Query database ────────────────────────────────────────────────────────
    try:
        breakdown = summary_by_category(start, end)
    except Exception as e:
        return {
            "ok": False,
            "error": f"Database query failed: {str(e)}"
        }

    # ── Compute grand total ───────────────────────────────────────────────────
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
        content: The note text (max 500 characters).
        author:  Who wrote it — 'me' or 'wife'.
        tag:     Optional label, e.g. 'reminder', 'budget', 'grocery' (case-insensitive).

    Returns:
        Confirmation dict with ok, id, and message (or error if validation fails).

    Raises:
        ValueError: If content is empty, exceeds 500 chars, or author is invalid.
    """
    # ── Validate and normalize author ─────────────────────────────────────────
    valid_authors = {"me", "wife"}
    normalized_author = author.lower().strip() if author else "me"
    if normalized_author not in valid_authors:
        return {
            "ok": False,
            "error": f"Invalid author '{author}'. Must be 'me' or 'wife'."
        }

    # ── Validate content ─────────────────────────────────────────────────────
    content_stripped = content.strip() if content else ""
    if not content_stripped:
        return {
            "ok": False,
            "error": "Note content cannot be empty. Please provide a note."
        }

    # ── Limit content length ──────────────────────────────────────────────────
    if len(content_stripped) > 500:
        return {
            "ok": False,
            "error": f"Note content exceeds 500 characters. Current length: {len(content_stripped)}."
        }

    # ── Normalize and limit tag ───────────────────────────────────────────────
    tag_normalized = tag.strip().lower() if tag else ""
    tag_val = tag_normalized[:50] if tag_normalized else None  # Limit tag length

    # ── Insert into database ──────────────────────────────────────────────────
    row_id = insert_note(content_stripped, normalized_author, tag_val)

    return {
        "ok": True,
        "id": row_id,
        "content_preview": content_stripped[:50] + "..." if len(content_stripped) > 50 else content_stripped,
        "message": f"Note '{content_stripped[:30]}...' saved by {normalized_author}."
    }


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
        limit:  Max number of notes to return (default 10, max 100).
        author: Filter by author — 'me' or 'wife' (leave blank for all).
        tag:    Filter by tag label (case-insensitive, leave blank for all).

    Returns:
        Dict with ok flag, count, and notes list. Each note includes id, content,
        author, tag, created_at timestamp.

    Raises:
        ValueError: If limit is outside [1, 100] or author/tag are invalid.
    """
    # ── Validate limit ────────────────────────────────────────────────────────
    try:
        limit_int = int(limit)
    except (ValueError, TypeError):
        return {
            "ok": False,
            "error": f"Invalid limit '{limit}'. Must be an integer between 1 and 100."
        }

    if limit_int < 1 or limit_int > 100:
        return {
            "ok": False,
            "error": f"Limit must be between 1 and 100. Current value: {limit_int}."
        }

    # ── Validate author ───────────────────────────────────────────────────────
    valid_authors = {"me", "wife"}
    normalized_author = author.lower().strip() if author else ""
    if normalized_author and normalized_author not in valid_authors:
        return {
            "ok": False,
            "error": f"Invalid author '{author}'. Must be empty, 'me', or 'wife'."
        }

    # ── Validate tag ──────────────────────────────────────────────────────────
    normalized_tag = tag.strip().lower() if tag else ""
    if not normalized_tag and tag:
        return {
            "ok": False,
            "error": f"Empty tag is not allowed when provided. Please provide a valid tag or leave blank."
        }

    # ── Fetch notes ───────────────────────────────────────────────────────────
    notes = fetch_notes(
        limit=limit_int,
        author=normalized_author if normalized_author else None,
        tag=normalized_tag if normalized_tag else None,
    )

    return {
        "ok": True,
        "count": len(notes),
        "limit_used": min(limit_int, 100),
        "author_filter": normalized_author if normalized_author else None,
        "tag_filter": normalized_tag if normalized_tag else None,
        "notes": notes
    }


# ── Tool 5: delete_note ──────────────────────────────────────────────────────

@mcp.tool()
def delete_note(note_id: int) -> dict:
    """
    Delete a note by its ID.

    Args:
        note_id: The ID of the note to remove (get IDs via get_notes).
                 Must be a positive integer.

    Returns:
        Success or not-found message.

    Raises:
        ValueError: If note_id is not a valid positive integer.
    """
    # ── Validate note_id ──────────────────────────────────────────────────────
    if not isinstance(note_id, int):
        return {
            "ok": False,
            "error": f"Invalid note_id type '{type(note_id).__name__}'. Must be an integer."
        }

    if note_id <= 0:
        return {
            "ok": False,
            "error": f"Invalid note_id {note_id}. ID must be a positive integer."
        }

    # ── Attempt deletion ──────────────────────────────────────────────────────
    deleted = remove_note(note_id)

    if deleted:
        return {
            "ok": True,
            "message": f"Note {note_id} deleted successfully.",
            "deleted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    else:
        return {
            "ok": False,
            "message": f"No note found with ID {note_id}."
        }


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


# ── Tool 8: send_notes_summary ───────────────────────────────────────────────

@mcp.tool()
def send_notes_summary(
    limit: int = 20,
    tag: str = "",
    to_me: bool = True,
    to_wife: bool = True,
) -> dict:
    """
    Email a summary of shared notes, with reminders highlighted at the top.

    Args:
        limit:    Max number of notes to include (default 20, max 100).
        tag:      Filter by tag — e.g. 'reminder', 'budget' (case-insensitive, blank for all).
        to_me:    Send to your email address (luis.cazares@gmail.com)
        to_wife:  Send to your wife's email address (victoria.vela99@gmail.com)

    Returns:
        Dict with ok flag, sent_to list, count of notes sent, or error message.
    """
    # ── Validate limit ────────────────────────────────────────────────────────
    try:
        limit_int = int(limit)
    except (ValueError, TypeError):
        return {
            "ok": False,
            "error": f"Invalid limit '{limit}'. Must be an integer between 1 and 100."
        }

    if limit_int < 1 or limit_int > 100:
        return {
            "ok": False,
            "error": f"Limit must be between 1 and 100. Current value: {limit_int}."
        }

    # ── Validate tag ──────────────────────────────────────────────────────────
    normalized_tag = tag.strip().lower() if tag else ""
    if not normalized_tag and tag:
        return {
            "ok": False,
            "error": f"Empty tag is not allowed when provided. Please provide a valid tag or leave blank."
        }

    # ── Fetch notes with filters ───────────────────────────────────────────────
    notes_result = get_notes(limit=limit_int, author="", tag=normalized_tag)
    if not notes_result["ok"]:
        return notes_result

    notes = notes_result["notes"]

    if not notes:
        return {
            "ok": False,
            "error": f"No notes found matching filters (limit={limit_int}, tag='{normalized_tag or 'all'}')."
        }

    # ── Get recipients ────────────────────────────────────────────────────────
    recipients = _all_recipients(to_me, to_wife)
    if not recipients:
        return {
            "ok": False,
            "error": "No recipients configured. Set MY_EMAIL and WIFE_EMAIL in .env"
        }

    # ── Send email ────────────────────────────────────────────────────────────
    result = email_notes_summary(
        notes=notes,
        recipients=recipients,
    )

    if result.get("ok"):
        return {
            "ok": True,
            "sent_to": result.get("sent_to", []),
            "count": len(notes),
            "limit_used": min(limit_int, 100),
            "tag_filter": normalized_tag if normalized_tag else None,
            "message": f"Notes summary sent to {len(recipients)} recipient(s)."
        }
    else:
        return result


# ── Start server when invoked via MCP stdio transport ──────────────────────────

mcp.run(transport="stdio")
