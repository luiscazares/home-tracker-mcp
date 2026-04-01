# 🏠 Home Tracker MCP

A personal MCP server for tracking household expenses and shared notes,
with pre-built email templates to keep you and your wife in sync.

---

## Features

| Tool                  | What it does                                      |
|-----------------------|---------------------------------------------------|
| `log_expense`         | Add an expense with category, amount, date        |
| `get_summary`         | Weekly or monthly breakdown by category           |
| `add_note`            | Save a shared note with optional tag              |
| `get_notes`           | Retrieve notes, filter by author or tag           |
| `delete_note`         | Remove a note by ID                               |
| `send_weekly_digest`  | Email a formatted spending report                 |
| `send_alert`          | Email a one-off alert (big purchase, budget warn) |

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure credentials

```bash
cp .env.example .env
# Edit .env with your Gmail address and App Password
```

> **Gmail App Password**: Go to https://myaccount.google.com/apppasswords
> and generate a password for "Mail". Use that instead of your real password.

### 3. Run locally to test

```bash
python server.py
```

---

## Add to Claude Desktop

Edit your Claude Desktop config file:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

Add this block inside `"mcpServers"`:

```json
{
  "mcpServers": {
    "home-tracker": {
      "command": "python",
      "args": ["/absolute/path/to/home-tracker-mcp/server.py"],
      "env": {
        "PYTHONPATH": "/absolute/path/to/home-tracker-mcp"
      }
    }
  }
}
```

Restart Claude Desktop. The tools will appear automatically.

---

## Example usage with Claude

- *"Log a $67 grocery run at HEB today"*
- *"Give me a summary of our spending this month"*
- *"Add a note reminding us to cancel the gym membership"*
- *"Send the weekly digest to both of us"*
- *"Alert my wife that I just spent $800 on car repair"*

---

## Categories to get started

`groceries` · `utilities` · `dining` · `rent` · `transport` · `health` · `subscriptions` · `entertainment` · `clothing` · `misc`
