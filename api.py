from fastapi import FastAPI, HTTPException, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
import os
from dotenv import load_dotenv
load_dotenv()

from server import (
    log_expense, get_summary, add_note,
    get_notes, delete_note, send_weekly_digest,
    send_alert, send_notes_summary
)

app = FastAPI(title="Home Tracker API")

# --- API Key Auth ---
API_KEY = os.getenv("HOME_TRACKER_API_KEY")
api_key_header = APIKeyHeader(name="X-API-Key")

def verify_key(key: str = Security(api_key_header)):
    if key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return key

# --- Models ---
class ExpenseRequest(BaseModel):
    amount: float
    category: str
    description: str = ""
    date: str = ""
    added_by: str = "me"

class NoteRequest(BaseModel):
    content: str
    author: str = "me"
    tag: str = ""

class AlertRequest(BaseModel):
    title: str
    message: str
    amount: float = 0.0
    to_me: bool = True
    to_wife: bool = True

# --- Endpoints ---
@app.post("/expenses")
def api_log_expense(req: ExpenseRequest, _: str = Security(verify_key)):
    return log_expense(**req.model_dump())

@app.get("/summary")
def api_get_summary(period: str = "month", _: str = Security(verify_key)):
    return get_summary(period)

@app.post("/notes")
def api_add_note(req: NoteRequest, _: str = Security(verify_key)):
    return add_note(**req.model_dump())

@app.get("/notes")
def api_get_notes(limit: int = 20, author: str = "", tag: str = "", _: str = Security(verify_key)):
    return get_notes(limit=limit, author=author, tag=tag)

@app.delete("/notes/{note_id}")
def api_delete_note(note_id: int, _: str = Security(verify_key)):
    return delete_note(note_id)

@app.post("/email/digest")
def api_weekly_digest(period: str = "week", to_me: bool = True, to_wife: bool = True, _: str = Security(verify_key)):
    return send_weekly_digest(period, to_me, to_wife)

@app.post("/email/alert")
def api_send_alert(req: AlertRequest, _: str = Security(verify_key)):
    return send_alert(**req.model_dump())

@app.post("/email/notes")
def api_notes_summary(limit: int = 20, tag: str = "", to_me: bool = True, to_wife: bool = True, _: str = Security(verify_key)):
    return send_notes_summary(limit, tag, to_me, to_wife)