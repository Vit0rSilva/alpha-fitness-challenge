# main.py
import os
import time
import threading
from typing import List, Dict, Any
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from utils.sheet_reader import fetch_and_clean_sheet
from dotenv import load_dotenv

load_dotenv()

SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "1OO7gDKXv4YJiDfpfrIHaXIa_XUgDhl3rG2FQImQ-ixY")
GID = os.getenv("GOOGLE_SHEET_GID", os.getenv("GID", "0"))
POLL_SECONDS = int(os.getenv("POLL_SECONDS", "8"))

CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"

app = FastAPI(title="Alpha Fitness - Sheet Viewer")

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

_cache = {
    "rows": [],
    "last_hash": None,
    "last_updated": None
}

def sheet_poller():
    """Background thread: polls Google Sheets CSV URL and updates cache when changed."""
    while True:
        try:
            rows, hh = fetch_and_clean_sheet(CSV_URL)
            if hh != _cache.get("last_hash"):
                _cache["rows"] = rows
                _cache["last_hash"] = hh
                _cache["last_updated"] = time.time()
                print(f"[sheet_poller] dados atualizados ({len(rows)} linhas) - hash {hh}")
        except Exception as e:
            print("[sheet_poller] erro ao buscar/parsear planilha:", e)
        time.sleep(POLL_SECONDS)

@app.on_event("startup")
def startup_event():
    t = threading.Thread(target=sheet_poller, daemon=True)
    t.start()
    print("[startup] Iniciado sheet_poller em background")

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/data")
def get_data():
    """Retorna os registros limpos como JSON"""
    return JSONResponse({
        "rows": _cache["rows"],
        "last_updated": _cache["last_updated"]
    })
