# main.py
import os
import time
import threading
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from utils.sheet_reader import fetch_and_clean_sheet
from dotenv import load_dotenv
import pandas as pd

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

def rows_to_df(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    return df

@app.get("/api/data")
def get_data(search: Optional[str] = Query(None), column: Optional[str] = Query(None), limit: Optional[int] = Query(1000)):
    rows = _cache.get("rows", [])
    if not rows:
        return JSONResponse({"rows": [], "last_updated": _cache.get("last_updated")})

    df = rows_to_df(rows)

    if search:
        q = str(search).lower()
        if column and column in df.columns:
            df = df[df[column].astype(str).str.lower().str.contains(q, na=False)]
        else:
            mask = None
            for c in df.columns:
                s = df[c].astype(str).str.lower().fillna("")
                m = s.str.contains(q, na=False)
                mask = m if mask is None else (mask | m)
            if mask is not None:
                df = df[mask]

    if limit is not None and len(df) > limit:
        df = df.head(limit)

    out = df.where(pd.notnull(df), None).to_dict(orient="records")
    return JSONResponse({"rows": out, "last_updated": _cache.get("last_updated")})

def detect_date_column(df: pd.DataFrame) -> Optional[str]:
    for c in df.columns:
        try:
            parsed = pd.to_datetime(df[c], errors='coerce', dayfirst=True)
            if parsed.notna().sum() >= max(1, int(len(parsed)*0.2)):
                return c
        except Exception:
            continue
    return None

@app.get("/api/stats")
def get_stats():
    rows = _cache.get("rows", [])
    if not rows:
        return JSONResponse({"stats": {}, "last_updated": _cache.get("last_updated")})

    df = rows_to_df(rows)
    n_total = len(df)

    numeric = df.select_dtypes(include=['number']).columns.tolist()
    numeric_stats = {}

    id_keywords = ["cpf", "telefone", "tel", "phone", "numero", "rg", "documento", "id"]

    for c in numeric:
        series = pd.to_numeric(df[c], errors='coerce')
        count = int(series.count())
        unique = int(series.nunique(dropna=True))
        missing = int(series.isna().sum())

        name_lower = str(c).lower()
        has_keyword = any(k in name_lower for k in id_keywords)

        integer_frac = 0.0
        max_abs = 0.0
        if count > 0:
            non_na = series.dropna()
            integer_frac = float((non_na % 1 == 0).sum()) / float(len(non_na)) if len(non_na) > 0 else 0.0
            max_abs = float(non_na.abs().max()) if len(non_na) > 0 else 0.0

        unique_ratio = (unique / count) if count > 0 else 0.0

        is_identifier = False
        if has_keyword:
            is_identifier = True
        else:
            if count > 0 and integer_frac > 0.85 and unique_ratio > 0.6 and max_abs > 1e5:
                is_identifier = True

        if is_identifier:
            samples = df[c].dropna().astype(str).astype(object)
            examples = []
            seen = set()
            for v in samples:
                if v not in seen:
                    seen.add(v)
                    examples.append(v)
                if len(examples) >= 5:
                    break
            numeric_stats[c] = {
                "type": "identifier",
                "count": int(count),
                "unique": int(unique),
                "missing": int(missing),
                "examples": examples
            }
        else:
            s_sum = float(series.sum(skipna=True)) if count > 0 else None
            s_mean = float(series.mean(skipna=True)) if count > 0 else None
            s_min = float(series.min(skipna=True)) if count > 0 else None
            s_max = float(series.max(skipna=True)) if count > 0 else None
            numeric_stats[c] = {
                "type": "numeric",
                "count": int(count),
                "missing": int(missing),
                "sum": s_sum,
                "mean": s_mean,
                "min": s_min,
                "max": s_max
            }

    date_col = detect_date_column(df)
    timeseries = None
    if date_col:
        parsed = pd.to_datetime(df[date_col], errors='coerce', dayfirst=True)
        series_counts = parsed.dt.to_period("M").value_counts().sort_index()
        timeseries = [{"period": str(idx), "count": int(v)} for idx, v in series_counts.items()]

    categorical = []
    for c in df.columns:
        if c in numeric:
            continue
        unique_count = int(df[c].nunique(dropna=True))
        if unique_count <= 50:
            top = df[c].dropna().astype(str).value_counts().head(5).to_dict()
            categorical.append({"column": c, "unique": unique_count, "top": top})

    missing = {c: int(df[c].isna().sum()) for c in df.columns}

    stats = {
        "total_rows": int(n_total),
        "numeric_stats": numeric_stats,
        "date_column": date_col,
        "timeseries_monthly": timeseries,
        "categorical_summary": categorical,
        "missing_per_column": missing
    }

    return JSONResponse({"stats": stats, "last_updated": _cache.get("last_updated")})
