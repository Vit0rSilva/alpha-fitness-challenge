# utils/sheet_reader.py
import requests
import io
import pandas as pd
import hashlib
from typing import Tuple, List, Dict, Any

def _hash_text(s: str) -> str:
    return hashlib.md5(s.encode('utf-8')).hexdigest()

def try_parse_column(series: pd.Series):
    """Tenta converter em data, se não, tenta number, senão string."""
    # tentativa data
    s_dt = pd.to_datetime(series, errors='coerce', dayfirst=True)
    if s_dt.notna().sum() >= max(1, int(len(series) * 0.2)):
        return s_dt.dt.strftime("%Y-%m-%dT%H:%M:%S").where(s_dt.notna(), None)

    # tentativa número
    s_num = pd.to_numeric(series.str.replace(r'[^\d\.\-\,]', '', regex=True).str.replace(',', '.'), errors='coerce')
    if s_num.notna().sum() >= max(1, int(len(series) * 0.2)):
        # retornar floats (None onde NaN)
        return s_num.where(s_num.notna(), None)

    # fallback: texto (strip, None empty)
    s_text = series.astype(str).replace({'nan': None, 'None': None})
    s_text = s_text.apply(lambda x: x.strip() if isinstance(x, str) and x.strip() != "" else None)
    return s_text

def fetch_and_clean_sheet(csv_url: str) -> Tuple[List[Dict[str, Any]], str]:
    """Busca CSV público da Google Sheets e retorna lista de dicionários limpos + hash do conteúdo."""
    resp = requests.get(csv_url, timeout=15)
    resp.raise_for_status()
    text = resp.text
    hh = _hash_text(text)

    df = pd.read_csv(io.StringIO(text))
    df.columns = [c.strip() if isinstance(c, str) else c for c in df.columns]

    clean = {}
    for col in df.columns:
        col_series = df[col].astype(str).replace({'nan': None})
        parsed = try_parse_column(col_series)
        clean[col] = parsed

    rows = []
    n = len(df)
    for i in range(n):
        row = {}
        for col in df.columns:
            val = clean[col].iloc[i]
            if pd.isna(val):
                row[col] = None
            else:
                if hasattr(val, "item"):
                    try:
                        val = val.item()
                    except:
                        pass
                row[col] = val
        rows.append(row)

    return rows, hh
