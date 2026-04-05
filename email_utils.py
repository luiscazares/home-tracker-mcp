"""
Email Utility Module for Home Tracker
=====================================
Handles SMTP email sending for:
- Weekly digest emails
- Alert notifications
- Notes summary emails
"""

import dotenv
import smtplib
import ssl
import os
import logging
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Configure logging for debugging and production monitoring
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("email_utils")


TEMPLATES_DIR = Path(__file__).parent / "templates"

# Load dotenv at module load time to ensure environment variables are available
load_dotenv()


def _get_smtp_config():
    """Get SMTP configuration from environment variables.
    
    Returns:
        Tuple of (host, port, password) or None if credentials missing.
    """
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    password = os.getenv("EMAIL_PASSWORD")
    
    sender_email = os.getenv("EMAIL_SENDER")
    if not sender_email or not password:
        return None
    
    return (smtp_host, smtp_port, password)


def _load_template(name: str) -> str:
    """Load a template file from the templates directory.
    
    Args:
        name: The template filename (e.g., 'weekly_digest.txt').
        
    Returns:
        Template content as a string.
        
    Raises:
        FileNotFoundError: If templates directory doesn't exist.
        ValueError: If template file is missing or has encoding issues.
    """
    template_path = TEMPLATES_DIR / name
    
    if not (TEMPLATES_DIR.exists() and TEMPLATES_DIR.is_dir()):
        raise FileNotFoundError(f"Templates directory does not exist: {TEMPLATES_DIR}")
    
    try:
        content = template_path.read_text(encoding="utf-8")
        
        if len(content) > 100_000:
            logger.warning(f"Template '{name}' is unusually large ({len(content)} chars)")
        
        return content.strip()
    except FileNotFoundError:
        logger.error(f"Template file not found: {template_path}")
        raise ValueError(f"Template file missing: {name}") from None
    except UnicodeDecodeError as e:
        logger.error(f"Template file encoding error for {name}: {e}")
        raise ValueError(f"Could not read template {name} (encoding issue).") from None


def _validate_recipients(recipients: list[str], max_recipients: int = 10) -> tuple[list[str], str | None]:
    """Validate recipient email addresses.
    
    Args:
        recipients: List of recipient email addresses.
        max_recipients: Maximum allowed recipients (default 10).
        
    Returns:
        Tuple of (validated_recipients, error_message).
    """
    if not recipients:
        return [], "No recipients provided."
    
    if len(recipients) > max_recipients:
        return [], f"Too many recipients ({len(recipients)}). Max allowed: {max_recipients}."
    
    validated = []
    for email in recipients:
        email = email.strip().lower()
        # Check basic format
        if "@" not in email:
            return [], f"Invalid email format (missing @): '{email}'"
        
        # Split at @ and check both parts
        parts = email.split("@")
        if len(parts) != 2:
            return [], f"Invalid email format (multiple @ signs): '{email}'"
        
        local_part, domain_part = parts
        
        # Check local part is not empty
        if not local_part:
            return [], f"Invalid email format (empty local part): '{email}'"
        
        # Check domain has at least one dot and some content after @
        if "." not in domain_part or not domain_part:
            return [], f"Invalid email format (invalid domain): '{email}'"
        
        validated.append(email)
    
    return validated, None


def _send(
    subject: str, 
    body: str, 
    recipients: list[str],
    sender_email: str,
    sender_name: str | None = None,
) -> dict:
    """Sends the email using SMTP with STARTTLS encryption.
    
    Args:
        subject: Email subject line.
        body: Plain text email body.
        recipients: List of recipient email addresses.
        sender_email: SMTP sender email address (with password).
        sender_name: Optional sender display name.
        
    Returns:
        Dict with ok flag and either sent_to list or error message.
    """
    # Validate inputs first
    if not subject or len(subject) > 200:
        return {"ok": False, "error": f"Subject must be between 1-200 chars (got {len(subject) if subject else 0} chars)."}
    
    if not body or len(body) > 50_000:
        return {"ok": False, "error": f"Body must be between 1-50000 chars (got {len(body)} chars)."}
    
    # Validate recipients
    validated_recipients, err = _validate_recipients(recipients)
    if err:
        return {"ok": False, "error": err}
    
    # Get SMTP configuration from environment variables
    config = _get_smtp_config()
    
    if not config:
        logger.warning("Credentials missing. EMAIL_SENDER and EMAIL_PASSWORD must be set in .env")
        return {"ok": False, "error": "EMAIL_SENDER and EMAIL_PASSWORD must be set in .env"}
    
    smtp_host, smtp_port, password = config
    
    # Construct from address (with optional name)
    from_header = f"{sender_name or ''} <{sender_email}>" if sender_name else sender_email
    
    # Create MIME message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject.strip()
    msg["From"] = from_header
    msg["To"] = ", ".join(validated_recipients)
    msg.attach(MIMEText(body, "plain"))
    
    logger.info(f"Sending email to {len(validated_recipients)} recipient(s): {', '.join(validated_recipients)}")
    
    try:
        # Connect to SMTP server using STARTTLS style (port 465 uses SSL instead)
        if smtp_port == 465:
            logger.info(f"Connecting to SMTP server {smtp_host}:{smtp_port} with SSL/TLS")
            with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
                server.ehlo()
                server.login(sender_email, password)
                message_ids = server.sendmail(from_header, validated_recipients, msg.as_string())
        else:
            logger.info(f"Connecting to SMTP server {smtp_host}:{smtp_port} with STARTTLS")
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.ehlo()
                # Upgrade connection to TLS using STARTTLS
                server.starttls()
                server.ehlo()  # Re-send EHLO after TLS upgrade
                server.login(sender_email, password)
                message_ids = server.sendmail(from_header, validated_recipients, msg.as_string())
        
        return {"ok": True, "sent_to": validated_recipients}
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP Authentication failed. Check credentials or 2FA settings.")
        return {"ok": False, "error": "SMTP Authentication failed. Use App Password at https://myaccount.google.com/apppasswords"}
    except smtplib.SMTPConnectError as e:
        logger.error(f"Failed to connect to SMTP server {smtp_host}:{smtp_port}: {e}")
        return {"ok": False, "error": f"Cannot connect to SMTP server: {str(e)}"}
    except smtplib.SMTPException as e:
        logger.error(f"SMTP Error: {e}")
        return {"ok": False, "error": f"SMTP Server Error: {str(e)}"}
    except Exception as e:
        logger.exception("Unexpected error during email send")
        return {"ok": False, "error": f"Email sending failed: {str(e)}"}


def _generate_digest_body(
    period_label: str, 
    total: float, 
    breakdown: list[dict],
) -> tuple[str, dict]:
    """Generate the weekly digest email body.
    
    Args:
        period_label: Time period (e.g., "Week of 2024-01-01 – 2024-01-07")
        total: Grand total amount
        breakdown: List of category breakdown dicts with category, total, count
        
    Returns:
        Tuple of (email_body, metadata_dict).
    """
    if not breakdown:
        body = "──────────────────────────────────────\n"
        body += "   NO EXPENSES IN THIS PERIOD\n"
        body += "──────────────────────────────────────\n"
    else:
        sorted_breakdown = sorted(
            breakdown, 
            key=lambda x: (-x["total"], x["category"])
        )
        
        categorized = {}
        for item in sorted_breakdown:
            cat = item["category"].strip().capitalize()
            if cat not in categorized:
                categorized[cat] = {"label": cat, "total": 0.0, "count": 0}
            categorized[cat]["total"] += item["total"]
            categorized[cat]["count"] += item["count"]
        
        rows = []
        for cat in sorted(categorized.values(), key=lambda x: (-x["total"], x["label"])):
            label = cat["label"]
            total_fmt = f"${cat['total']:>8.2f}"
            count = cat["count"]
            
            if count == 1:
                item_str = "item"
            else:
                item_str = "items"
            
            rows.append(f"  {label:<20} {total_fmt:>9} ({count} {item_str})")
        
        body = "\n".join(rows) if rows else "   (No expenses in this period)"
    
    return body, {"period": period_label, "categories_count": len(set(r["category"] for r in breakdown)) if breakdown else 0}


def _generate_alert_body(
    title: str, 
    message: str, 
    amount: float | None = None,
) -> tuple[str, dict]:
    """Generate the alert email body.
    
    Args:
        title: Alert title/subject
        message: Alert body text
        amount: Optional dollar amount to include
        
    Returns:
        Tuple of (email_body, metadata_dict).
    """
    amount_line = f"Amount: ${amount:>10.2f}\n" if amount and amount > 0 else ""
    body = f"{title}\n\n{message}{amount_line}"
    
    return body, {"title": title}


def _generate_notes_body(
    notes: list[dict],
) -> tuple[str, dict]:
    """Generate the notes summary email body.
    
    Args:
        notes: List of note dicts with content, author, tag, created_at
        
    Returns:
        Tuple of (email_body, metadata_dict).
    """
    if not notes:
        return "No notes found.", {"count": 0}
    
    reminders = [n for n in notes if n.get("tag") and str(n["tag"]).lower() == "reminder"]
    others = [n for n in notes if not n.get("tag") or str(n["tag"]).lower() != "reminder"]
    
    def format_note(n):
        tag_display = f"[{str(n['tag'])}] " if n.get("tag") else ""
        author = str(n.get("author", "me")).capitalize()
        created_at = n.get("created_at", "")
        date_display = created_at[:10] if created_at else "(no date)"
        
        content = n.get("content", "")
        if len(content) > 300:
            content = str(content)[:300] + "\n..."
        else:
            content = str(content)
        
        return f"  • {tag_display}{content}\n      (by {author} on {date_display})"
    
    sections = []
    
    if reminders:
        reminder_lines = "\n".join(format_note(n) for n in reminders)
        sections.append("⚠️  REMINDERS\n" + reminder_lines)
    
    if others:
        other_lines = "\n".join(format_note(n) for n in others)
        sections.append("📝  NOTES\n" + other_lines)
    
    body = "Home Tracker — Notes Summary\n"
    body += "=============================\n\n"
    
    if sections:
        body += "\n\n".join(sections)
    else:
        body += "No notes to display."
    
    body += f"\n\n—\nTotal: {len(notes)} note(s)"
    
    return body, {"total_count": len(notes), "reminder_count": len(reminders), "other_count": len(others)}


def send_weekly_digest(
    period_label: str,          
    total: float,
    breakdown: list[dict],      
    recipients: list[str],
    sender_email: str | None = None,
) -> dict:
    """Send a weekly/monthly expense digest email.
    
    Args:
        period_label: Time period (e.g., 'Week of 2024-01-01 – 2024-01-07')
        total: Grand total spending amount
        breakdown: List of dicts with {category, count, total} for each category
        recipients: List of recipient email addresses
        sender_email: Override default sender (from .env)
        
    Returns:
        Dict with ok flag, sent_to list, and message.
    """
    if not period_label:
        return {"ok": False, "error": "period_label cannot be empty"}
    
    if not isinstance(total, (int, float)) or total < 0:
        return {"ok": False, "error": f"Invalid total: {total}. Must be a non-negative number."}
    
    if not recipients:
        return {"ok": False, "error": "No recipients provided"}
    
    try:
        template = _load_template("weekly_digest.txt")
    except ValueError as e:
        logger.error(f"Template load error in send_weekly_digest: {e}")
        return {"ok": False, "error": f"Template error: {str(e)}"}
    
    try:
        body, metadata = _generate_digest_body(period_label, total, breakdown)
    except Exception as e:
        logger.exception(f"Error generating digest body: {e}")
        return {"ok": False, "error": f"Body generation failed: {str(e)}"}
    
    from_env = os.getenv("EMAIL_SENDER", "")
    
    try:
        result = _send(
            subject=f"🏠 Home Expense Digest – {period_label}",
            body=body,
            recipients=recipients,
            sender_email=from_env if not sender_email else sender_email,
            sender_name=None,
        )
        
        return result
    except Exception as e:
        logger.exception(f"Failed to send weekly digest: {e}")
        return {"ok": False, "error": str(e)}


def send_alert(
    title: str,
    message: str,
    amount: float | None = None,
    recipients: list[str] | None = None,
    sender_email: str | None = None,
) -> dict:
    """Send a one-off alert email (e.g., big purchase notification).
    
    Args:
        title: Alert subject/title (e.g., 'Big Purchase Logged')
        message: Alert body text
        amount: Optional dollar amount to display
        recipients: List of recipient email addresses
        sender_email: Override default sender (from .env)
        
    Returns:
        Dict with ok flag, sent_to list, and message.
    """
    if not title:
        return {"ok": False, "error": "Alert title cannot be empty"}
    
    if len(title) > 100:
        return {"ok": False, "error": f"Title too long ({len(title)} chars). Max: 100 chars."}
    
    message = message or ""
    if len(message) > 10_000:
        return {"ok": False, "error": f"Message must be 1-10000 chars (got {len(message)})."}
    
    recipients = recipients or []
    if not recipients:
        return {"ok": False, "error": "No recipients provided"}
    
    try:
        template = _load_template("alert.txt")
    except ValueError as e:
        logger.error(f"Template load error in send_alert: {e}")
        return {"ok": False, "error": f"Template error: {str(e)}"}
    
    try:
        body, metadata = _generate_alert_body(title, message, amount)
    except Exception as e:
        logger.exception(f"Error generating alert body: {e}")
        return {"ok": False, "error": f"Body generation failed: {str(e)}"}
    
    from_env = os.getenv("EMAIL_SENDER", "")
    
    try:
        result = _send(
            subject=f"🔔 Home Tracker Alert: {title}",
            body=body,
            recipients=recipients,
            sender_email=from_env if not sender_email else sender_email,
            sender_name=None,
        )
        
        return result
    except Exception as e:
        logger.exception(f"Failed to send alert: {e}")
        return {"ok": False, "error": str(e)}


def send_notes_summary(
    notes: list[dict],
    recipients: list[str] | None = None,
    sender_email: str | None = None,
) -> dict:
    """Send a notes summary email.
    
    Args:
        notes: List of note dicts with {content, author, tag, created_at}
        recipients: List of recipient email addresses
        sender_email: Override default sender (from .env)
        
    Returns:
        Dict with ok flag, sent_to list, and message.
    """
    if not notes:
        return {"ok": False, "error": "No notes to send"}
    
    notes = notes[:100]  # Limit to first 100 notes for email
    
    recipients = recipients or []
    if not recipients:
        return {"ok": False, "error": "No recipients provided"}
    
    try:
        body, metadata = _generate_notes_body(notes)
    except Exception as e:
        logger.exception(f"Error generating notes body: {e}")
        return {"ok": False, "error": f"Body generation failed: {str(e)}"}
    
    from_env = os.getenv("EMAIL_SENDER", "")
    
    try:
        result = _send(
            subject=f"📝 Home Tracker — Notes Summary ({len(notes)} notes)",
            body=body,
            recipients=recipients,
            sender_email=from_env if not sender_email else sender_email,
            sender_name=None,
        )
        
        return result
    except Exception as e:
        logger.exception(f"Failed to send notes summary: {e}")
        return {"ok": False, "error": str(e)}


def send_test_email(
    recipients: list[str],
    subject: str = "Test Email from Home Tracker",
    body: str = "This is a test email from the Home Tracker system.",
) -> dict:
    """Send a simple test email (useful for SMTP debugging).
    
    Args:
        recipients: List of recipient email addresses
        subject: Email subject
        body: Email body text
        
    Returns:
        Dict with send result.
    """
    from_env = os.getenv("EMAIL_SENDER", "")
    
    if not from_env:
        return {"ok": False, "error": "No EMAIL_SENDER configured"}
    
    validated, err = _validate_recipients(recipients)
    if err:
        return {"ok": False, "error": err}
    
    try:
        result = _send(
            subject=subject,
            body=body,
            recipients=validated,
            sender_email=from_env,
            sender_name=None,
        )
        
        return result
    except Exception as e:
        logger.exception(f"Failed to send test email: {e}")
        return {"ok": False, "error": str(e)}