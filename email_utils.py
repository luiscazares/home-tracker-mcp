import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent / "templates"


def _load_template(name: str) -> str:
    return (TEMPLATES_DIR / name).read_text()


def _send(subject: str, body: str, recipients: list[str]) -> dict:
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    sender    = os.getenv("EMAIL_SENDER")
    password  = os.getenv("EMAIL_PASSWORD")

    if not sender or not password:
        return {"ok": False, "error": "EMAIL_SENDER or EMAIL_PASSWORD not set in .env"}

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = sender
    msg["To"]      = ", ".join(recipients)
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, recipients, msg.as_string())
        return {"ok": True, "sent_to": recipients}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def send_weekly_digest(
    period_label: str,          # e.g. "Week of Mar 24 – Mar 30"
    total: float,
    breakdown: list[dict],      # [{"category": ..., "count": ..., "total": ...}]
    recipients: list[str],
) -> dict:
    template = _load_template("weekly_digest.txt")

    rows = "\n".join(
        f"  {r['category'].capitalize():<20} ${r['total']:>8.2f}  ({r['count']} items)"
        for r in breakdown
    )

    body = template.format(
        period=period_label,
        total=f"{total:.2f}",
        breakdown_rows=rows,
    )

    return _send(
        subject=f"🏠 Home Expense Digest – {period_label}",
        body=body,
        recipients=recipients,
    )


def send_alert(
    title: str,
    message: str,
    amount: float | None,
    recipients: list[str],
) -> dict:
    template = _load_template("alert.txt")

    amount_line = f"Amount: ${amount:.2f}" if amount is not None else ""
    body = template.format(
        title=title,
        message=message,
        amount_line=amount_line,
    )

    return _send(
        subject=f"🔔 Home Tracker Alert: {title}",
        body=body,
        recipients=recipients,
    )
