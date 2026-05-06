import os
import gspread
import gspread.utils
import pandas as pd
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
SPREADSHEET_ID = os.environ.get("APPLE_SPREADSHEET_ID", "<YOUR_SHEET_ID>")
APPLE_SHEET = os.environ.get("APPLE_SHEET_NAME", "apples")
ENRICHMENT_COLS = ["Image", "Prof. Tasting Notes", "AR Score", "AR Notes"]
AUTO_TAG_COLS = ["Type", "Origin", "Country"]

WISHLIST_SHEET = "Apple Wishlist"
WISHLIST_COLS = ["Name", "Tasting Notes", "Price", "Where to Find It", "Link", "Image"]


def _client() -> gspread.Client:
    path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not path:
        raise EnvironmentError("GOOGLE_SERVICE_ACCOUNT_JSON is not set")
    creds = Credentials.from_service_account_file(path, scopes=SCOPES)
    return gspread.authorize(creds)


def _find_header(rows: list[list[str]]) -> int:
    for i, row in enumerate(rows):
        if row and row[0].strip().lower() in ("apple variety", "apple type"):
            return i
    raise ValueError("Could not find 'Apple Type' or 'Apple Variety' header row in the sheet")


def _open_apple_worksheet() -> gspread.Worksheet:
    sh = _client().open_by_key(SPREADSHEET_ID)
    try:
        return sh.worksheet(APPLE_SHEET)
    except gspread.WorksheetNotFound:
        pass
    for ws in sh.worksheets():
        try:
            rows = ws.get_all_values()
            _find_header(rows)
            return ws
        except Exception:
            continue
    raise ValueError(
        "Could not find a worksheet with an 'Apple Variety' header. "
        "Set APPLE_SHEET_NAME in .env to your exact tab name."
    )


def load_apple_data() -> pd.DataFrame:
    ws = _open_apple_worksheet()
    rows = ws.get_all_values()
    header_idx = _find_header(rows)
    headers = [h.strip() for h in rows[header_idx]]
    data = [r for r in rows[header_idx + 1:] if any(c.strip() for c in r)]

    padded = [r + [""] * (len(headers) - len(r)) for r in data]
    df = pd.DataFrame(padded, columns=headers)
    if "Apple Type" in df.columns and "Apple Variety" not in df.columns:
        df = df.rename(columns={"Apple Type": "Apple Variety"})
    df = df[df["Apple Variety"].str.strip() != ""].copy()
    df["Score"] = pd.to_numeric(df["Score"], errors="coerce")
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"].str.strip(), format="%B %Y", errors="coerce")
    return df.reset_index(drop=True)


def update_enrichment(df_enriched: pd.DataFrame) -> None:
    ws = _open_apple_worksheet()
    rows = ws.get_all_values()
    header_idx = _find_header(rows)
    headers = [h.strip() for h in rows[header_idx]]

    batch: list[dict] = []

    for col_name in ENRICHMENT_COLS:
        if col_name not in headers:
            col_num = len(headers) + 1
            headers.append(col_name)
            cell = gspread.utils.rowcol_to_a1(header_idx + 1, col_num)
            batch.append({"range": cell, "values": [[col_name]]})

    img_col      = headers.index("Image") + 1
    notes_col    = headers.index("Prof. Tasting Notes") + 1
    ar_score_col = headers.index("AR Score") + 1
    ar_notes_col = headers.index("AR Notes") + 1
    name_col     = next(
        headers.index(h) for h in ("Apple Variety", "Apple Type") if h in headers
    )

    for row_idx in range(header_idx + 1, len(rows)):
        row = rows[row_idx]
        if not row or not (len(row) > name_col and row[name_col].strip()):
            continue
        apple_name = row[name_col].strip()
        match = df_enriched[df_enriched["Apple Variety"].str.strip() == apple_name]
        if match.empty:
            continue
        m = match.iloc[0]
        sheet_row = row_idx + 1

        def _val(key: str) -> str:
            v = m.get(key, "")
            return str(v).strip() if pd.notna(v) else ""

        img_url     = _val("Image URL")
        img_formula = f'=IMAGE("{img_url}", 1)' if img_url else ""

        for col_num, value in [
            (img_col,       img_formula),
            (notes_col,     _val("Prof. Tasting Notes")),
            (ar_score_col,  _val("AR Score")),
            (ar_notes_col,  _val("AR Notes")),
        ]:
            if value:
                batch.append({"range": gspread.utils.rowcol_to_a1(sheet_row, col_num), "values": [[value]]})

    if batch:
        for i in range(0, len(batch), 100):
            ws.batch_update(batch[i: i + 100], value_input_option="USER_ENTERED")


def append_apple(
    name: str,
    date: str,
    from_where: str,
    score: float,
    tasting_notes: str,
    extra_fields: dict[str, str] | None = None,
) -> None:
    ws = _open_apple_worksheet()
    rows = ws.get_all_values()
    header_idx = _find_header(rows)
    headers = [h.strip() for h in rows[header_idx]]

    if extra_fields:
        new_col_batch: list[dict] = []
        for col_name in extra_fields:
            if col_name not in headers:
                col_num = len(headers) + 1
                headers.append(col_name)
                cell = gspread.utils.rowcol_to_a1(header_idx + 1, col_num)
                new_col_batch.append({"range": cell, "values": [[col_name]]})
        if new_col_batch:
            ws.batch_update(new_col_batch, value_input_option="USER_ENTERED")

    col_map = {h: i for i, h in enumerate(headers)}
    row_data = [""] * len(headers)
    apple_col = "Apple Type" if "Apple Type" in col_map else "Apple Variety"
    for col_name, val in [
        (apple_col,       name),
        ("Date",          date),
        ("Score",         str(score)),
        ("Tasting Notes", tasting_notes),
    ]:
        if col_name in col_map:
            row_data[col_map[col_name]] = val

    if extra_fields:
        for col_name, val in extra_fields.items():
            if col_name in col_map:
                row_data[col_map[col_name]] = val

    ws.append_row(row_data, value_input_option="USER_ENTERED")


# ── Wishlist ───────────────────────────────────────────────────────────────────

def _ensure_wishlist_sheet(sh: gspread.Spreadsheet) -> gspread.Worksheet:
    try:
        ws = sh.worksheet(WISHLIST_SHEET)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=WISHLIST_SHEET, rows=200, cols=len(WISHLIST_COLS))
        ws.append_row(WISHLIST_COLS, value_input_option="USER_ENTERED")
        return ws

    existing_headers = ws.row_values(1)
    batch = []
    for col_name in WISHLIST_COLS:
        if col_name not in existing_headers:
            col_num = len(existing_headers) + 1
            existing_headers.append(col_name)
            batch.append({"range": gspread.utils.rowcol_to_a1(1, col_num), "values": [[col_name]]})
    if batch:
        ws.batch_update(batch, value_input_option="USER_ENTERED")
    return ws


def load_pinned_apples() -> list[str]:
    try:
        sh = _client().open_by_key(SPREADSHEET_ID)
        ws = _ensure_wishlist_sheet(sh)
        rows = ws.get_all_values()
        return [r[0].strip() for r in rows[1:] if r and r[0].strip()]
    except Exception:
        return []


def load_wishlist() -> list[dict]:
    try:
        sh = _client().open_by_key(SPREADSHEET_ID)
        ws = _ensure_wishlist_sheet(sh)
        rows = ws.get_all_values()
        if len(rows) < 2:
            return []
        headers = [h.strip() for h in rows[0]]
        result = []
        for row in rows[1:]:
            if not row or not row[0].strip():
                continue
            padded = row + [""] * (len(headers) - len(row))
            result.append(dict(zip(headers, padded)))
        return result
    except Exception:
        return []


def remove_from_wishlist(name: str) -> None:
    sh = _client().open_by_key(SPREADSHEET_ID)
    ws = _ensure_wishlist_sheet(sh)
    rows = ws.get_all_values()
    target = name.strip().lower()
    for i, row in enumerate(rows[1:], start=2):
        if row and row[0].strip().lower() == target:
            ws.delete_rows(i)
            return


def pin_to_wishlist(rec: dict) -> None:
    sh = _client().open_by_key(SPREADSHEET_ID)
    ws = _ensure_wishlist_sheet(sh)

    existing_names = {r[0].strip().lower() for r in ws.get_all_values()[1:] if r}
    if rec.get("name", "").strip().lower() in existing_names:
        return

    tasting_notes = ", ".join(rec.get("tasting_notes", [])) or rec.get("flavor_profile", "")
    img_url = rec.get("picture_url", "")
    img_formula = f'=IMAGE("{img_url}", 1)' if img_url else ""

    stores = rec.get("stores", [])
    where_parts = []
    for store in stores:
        sname = store.get("name", "").strip()
        loc   = store.get("location", "").strip()
        if sname and loc:
            where_parts.append(f"{sname} — {loc}")
        elif sname:
            where_parts.append(sname)
    where_to_find = "\n".join(where_parts)

    link = rec.get("link", "")

    ws.append_row(
        [
            rec.get("name", ""),
            tasting_notes,
            rec.get("price_range", ""),
            where_to_find,
            link,
            img_formula,
        ],
        value_input_option="USER_ENTERED",
    )
