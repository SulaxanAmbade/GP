import os
import re
import sqlite3
import hmac
import json
import hashlib
from html import escape
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from urllib.parse import unquote, urlsplit

import pandas as pd
import streamlit as st


# =============================================================
# PAGE CONFIGURATION AND THEME
# =============================================================
st.set_page_config(
    page_title="Global Patterns",
    page_icon="🔴",
    layout="centered",
    initial_sidebar_state="collapsed",
)
st.set_option("client.toolbarMode", "minimal")


def apply_red_theme():
    st.markdown(
        r"""
        <style>
        :root {
            color-scheme: light !important;
            --gp-red: #b7202e;
            --gp-red-dark: #991b1b;
            --gp-red-soft: #fff1f2;
            --gp-red-border: #fecdd3;
            --gp-bg: #fafafa;
            --gp-surface: #ffffff;
            --gp-text: #991b1b;
            --gp-muted: #71717a;
            --gp-border: #e4e4e7;
            --gp-shadow: 0 8px 24px rgba(24, 24, 27, 0.06);
        }
        .stApp {
            background: radial-gradient(circle at top right, rgba(200,30,30,0.06), transparent 28rem), var(--gp-bg);
            color: var(--gp-text);
        }
        .block-container { max-width: 1450px; padding-top: 1.4rem; padding-bottom: 3rem; }
        h1, h2, h3 { color: var(--gp-text); letter-spacing: -0.02em; }
        h1 { font-weight: 760; }
        h2, h3 { font-weight: 700; }
        label, .stCaption { color: var(--gp-muted); }
        [data-testid="stHeader"] { background: rgba(250,250,250,0.86); backdrop-filter: blur(10px); }
        [data-testid="stToolbar"] { right: 1rem; }
        div[data-testid="stMetric"] {
            background: var(--gp-surface); border: 1px solid var(--gp-border);
            border-radius: 14px; padding: 1rem 1.1rem; box-shadow: var(--gp-shadow);
        }
        div[data-testid="stMetric"] label { color: var(--gp-muted) !important; font-weight: 600; }
        div[data-testid="stMetricValue"] { color: var(--gp-muted); font-weight: 750; }
        .stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button {
            min-height: 2.65rem; border-radius: 10px; transition: all 0.16s ease; box-shadow: none;
        }
        .stButton > button[kind="primary"], [data-testid="stFormSubmitButton"] > button {
            background: var(--gp-red); border-color: var(--gp-red); color: #fff;
        }
        .stButton > button[kind="primary"]:hover, [data-testid="stFormSubmitButton"] > button:hover {
            background: var(--gp-red-dark); border-color: var(--gp-red-dark);
        }
        .stButton > button:not([kind="primary"]), .stDownloadButton > button {
            background: var(--gp-surface); border: 1px solid var(--gp-border); color: var(--gp-text);
        }
        .stButton > button:not([kind="primary"]):hover, .stDownloadButton > button:hover {
            border-color: var(--gp-red); color: var(--gp-red-dark); background: var(--gp-red-soft);
        }
        div[data-baseweb="input"] > div, div[data-baseweb="textarea"] > div, div[data-baseweb="select"] > div {
            border-radius: 10px !important; border-color: var(--gp-border) !important;
            background: var(--gp-surface) !important;
        }
        div[data-baseweb="input"] > div:focus-within, div[data-baseweb="textarea"] > div:focus-within,
        div[data-baseweb="select"] > div:focus-within {
            border-color: var(--gp-red) !important; box-shadow: 0 0 0 1px var(--gp-red) !important;
        }
        [data-testid="stFileUploader"] {
            background: var(--gp-surface); border: 1px dashed #d4d4d8;
            border-radius: 14px; padding: 0.35rem 0.65rem;
        }
        [data-testid="stExpander"] {
            background: var(--gp-surface); border: 1px solid var(--gp-border);
            border-radius: 14px; box-shadow: var(--gp-shadow); overflow: hidden;
        }
        [data-baseweb="tab-list"] { gap: 0.35rem; border-bottom: 1px solid var(--gp-border); }
        button[data-baseweb="tab"] { border-radius: 9px 9px 0 0; padding-left: 1rem; padding-right: 1rem; }
        button[data-baseweb="tab"][aria-selected="true"] { color: var(--gp-red-dark); font-weight: 700; }
        [data-testid="stDataFrame"] {
            border: 1px solid var(--gp-border); border-radius: 12px;
            overflow: hidden; background: var(--gp-surface);
        }
        [data-testid="stAlert"] { border-radius: 12px; border-width: 1px; }
        hr { border: 0; border-top: 1px solid var(--gp-border); margin: 1.6rem 0; }
        .gp-hero {
            display: flex; align-items: center; justify-content: space-between; gap: 1rem;
            padding: 1.1rem 1.25rem; margin-bottom: 1.2rem;
            background: linear-gradient(135deg, #ffffff 0%, #fff7f7 100%);
            border: 1px solid var(--gp-red-border); border-left: 5px solid var(--gp-red);
            border-radius: 16px; box-shadow: var(--gp-shadow);
        }
        .gp-title {
            margin: 0; color: var(--gp-text); font-size: clamp(1.55rem, 2vw, 2.15rem);
            font-weight: 780; line-height: 1.15;
        }
        .gp-subtitle { margin: 0.35rem 0 0; color: var(--gp-muted); font-size: 0.96rem; }
        .gp-user-pill {
            display: inline-flex; align-items: center; gap: 0.45rem; padding: 0.4rem 0.7rem;
            border-radius: 999px; background: var(--gp-red-soft); color: var(--gp-red-dark);
            border: 1px solid var(--gp-red-border); font-weight: 650; font-size: 0.86rem;
        }
        .gp-dot { width: 0.48rem; height: 0.48rem; border-radius: 999px; background: var(--gp-red); display: inline-block; }
        [data-testid="stSidebar"] { border-right: 1px solid var(--gp-border); }
        [data-testid="stNavigation"] {
            background: var(--gp-surface); border: 1px solid var(--gp-border);
            border-radius: 12px; padding: 0.25rem; box-shadow: var(--gp-shadow); margin-bottom: 1rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


apply_red_theme()
st.markdown(
    """
    <div class="gp-hero"><div>
        <div class="gp-title">Global Pattern Database</div>
        <div class="gp-subtitle">Search, validate, generate, and review shared URL patterns from one workspace.</div>
    </div></div>
    """,
    unsafe_allow_html=True,
)


# =============================================================
# DATABASE
# =============================================================
DB_FILE = "url_patterns.db"
ADMIN_LOOKUP_FLAG = "(Lookup)"
PATTERN_COLUMNS = [
    "url_pattern", "url_pattern_id", "priority", "language_code",
    "admin_name", "updated_admin_id",
]


def get_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)


def initialize_database():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dataset_metadata (
                id INTEGER PRIMARY KEY CHECK (id = 1), filename TEXT,
                file_date TEXT, updated_at TEXT, total_rows INTEGER, updated_by TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS url_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT, url_pattern TEXT,
                url_pattern_id TEXT, priority TEXT, language_code TEXT,
                admin_name TEXT, updated_admin_id TEXT
            )
        """)
        cursor.execute("PRAGMA table_info(dataset_metadata)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        for column in ("file_date", "updated_by"):
            if column not in existing_columns:
                cursor.execute(f"ALTER TABLE dataset_metadata ADD COLUMN {column} TEXT")
        cursor.execute("PRAGMA table_info(url_patterns)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        for column in ("language_code", "admin_name", "updated_admin_id"):
            if column not in existing_columns:
                cursor.execute(f"ALTER TABLE url_patterns ADD COLUMN {column} TEXT")
        conn.commit()
    finally:
        conn.close()


def get_dataset_metadata():
    conn = get_connection()
    try:
        metadata = pd.read_sql_query("""
            SELECT filename, file_date, updated_at, total_rows, updated_by
            FROM dataset_metadata WHERE id = 1
        """, conn)
        return None if metadata.empty else metadata.iloc[0].to_dict()
    finally:
        conn.close()


def load_shared_dataset():
    conn = get_connection()
    try:
        df = pd.read_sql_query("""
            SELECT url_pattern, url_pattern_id, priority, language_code,
                   admin_name, updated_admin_id
            FROM url_patterns
        """, conn)
        if not df.empty:
            df["_url_pattern_length"] = df["url_pattern"].fillna("").astype(str).str.len()
            df.sort_values("_url_pattern_length", ascending=False, inplace=True)
            df.drop(columns=["_url_pattern_length"], inplace=True)
            df.reset_index(drop=True, inplace=True)
        return df
    finally:
        conn.close()


def replace_shared_dataset(new_df, filename, file_date, updated_by, pattern_keyword_rows=None):
    # Allow older DataFrames to be stored with a blank admin_name.
    prepared = new_df.copy()
    for column in ("admin_name", "updated_admin_id"):
        if column not in prepared.columns:
            prepared[column] = None
    prepared["updated_admin_id"] = prepared["updated_admin_id"].map(normalize_admin_id)
    prepared["admin_name"] = prepared["admin_name"].map(
        lambda value: None if pd.isna(value) or not str(value).strip() else str(value).strip()
    )
    records = [
        tuple(None if pd.isna(value) else str(value) for value in row)
        for row in prepared[PATTERN_COLUMNS].itertuples(index=False, name=None)
    ]
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM url_patterns")
        cursor.executemany("""
            INSERT INTO url_patterns
                (url_pattern, url_pattern_id, priority, language_code, admin_name, updated_admin_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, records)
        cursor.execute("""
            INSERT INTO dataset_metadata
                (id, filename, file_date, updated_at, total_rows, updated_by)
            VALUES (1, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                filename = excluded.filename, file_date = excluded.file_date,
                updated_at = excluded.updated_at, total_rows = excluded.total_rows,
                updated_by = excluded.updated_by
        """, (
            filename, file_date.strftime("%d-%m-%Y") if file_date is not None else "",
            datetime.now().strftime("%d-%m-%Y %I:%M:%S %p"), len(prepared),
            str(updated_by).strip() if updated_by else "Unknown",
        ))
        mapper_store_global_keyword_rows(conn, pattern_keyword_rows, filename)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    if pattern_keyword_rows is not None:
        # Model failures do not roll back an already accepted pattern workbook.
        try:
            mapper_ensure_auto_model()
        except Exception as exc:
            with get_connection() as model_conn:
                mapper_model_schema(model_conn)
                model_conn.execute("UPDATE automatic_keyword_model SET status='error',error=? WHERE id=1",
                                   (f"Automatic training failed: {type(exc).__name__}: {str(exc)[:250]}",))


initialize_database()


# =============================================================
# USER AUTHENTICATION
# =============================================================
def get_app_users():
    users = {}
    for secrets_key in ("users", "USERS"):
        try:
            configured_users = st.secrets[secrets_key]
            users.update({
                str(username).strip().lower(): str(password)
                for username, password in configured_users.items()
                if str(username).strip()
            })
        except Exception:
            pass
    environment_users = os.environ.get("APP_USERS_JSON", "")
    if environment_users:
        try:
            parsed_users = json.loads(environment_users)
            if isinstance(parsed_users, dict):
                users.update({
                    str(username).strip().lower(): str(password)
                    for username, password in parsed_users.items()
                    if str(username).strip()
                })
        except (TypeError, ValueError):
            pass
    try:
        legacy_password = st.secrets["ADMIN_PASSWORD"]
    except Exception:
        legacy_password = os.environ.get("ADMIN_PASSWORD", "")
    if legacy_password and "admin" not in users:
        users["admin"] = str(legacy_password)
    return users


def admin_login():
    if st.session_state.get("admin_authenticated", False):
        return True
    st.subheader("User Login")
    configured_users = get_app_users()
    if not configured_users:
        st.error("No user accounts are configured. Add a [users] section to .streamlit/secrets.toml.")
        return False
    with st.form("user_login_form", clear_on_submit=False):
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        submitted = st.form_submit_button("Sign In", width="content", type="primary")
    if submitted:
        normalized_username = username.strip().lower()
        correct_password = configured_users.get(normalized_username)
        if correct_password is not None and hmac.compare_digest(
            str(password).encode("utf-8"), str(correct_password).encode("utf-8")
        ):
            st.session_state["admin_authenticated"] = True
            st.session_state["authenticated_username"] = normalized_username
            st.success("Login successful.")
            st.rerun()
        else:
            st.error("Incorrect username or password.")
    return False


def render_user_header():
    if not st.session_state.get("admin_authenticated", False):
        return
    user_col, logout_col = st.columns([8, 1])
    with user_col:
        username = escape(st.session_state.get("authenticated_username", "admin").title())
        st.markdown(
            f'<span class="gp-user-pill"><span class="gp-dot"></span>Signed in as {username}</span>',
            unsafe_allow_html=True,
        )
    with logout_col:
        if st.button("Logout", width="content"):
            st.session_state.clear()
            st.rerun()


# =============================================================
# FILE DATE VALIDATION AND PARSING
# =============================================================
def extract_file_date(filename):
    match = re.search(r"(\d{2}-\d{2}-\d{4})", filename)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%d-%m-%Y")
    except ValueError:
        return None


def validate_file_date(filename):
    file_date = extract_file_date(filename)
    current_date = datetime.now().date()
    if file_date is None:
        return {
            "date_found": None, "current_date": current_date, "is_match": False,
            "difference_days": None, "date_missing": True,
        }
    file_date = file_date.date()
    return {
        "date_found": file_date, "current_date": current_date,
        "is_match": file_date == current_date,
        "difference_days": (current_date - file_date).days, "date_missing": False,
    }


def clean_admin_value(value):
    if pd.isna(value):
        return None
    value = re.sub(r"[\u200b-\u200d\ufeff]", "", str(value))
    value = " ".join(value.split())
    return None if value.casefold() in {"", "none", "nan", "null", "<na>", "n/a", "-"} else value


def normalize_admin_id(value):
    """Normalize integer IDs read by Excel as floats, without float rounding."""
    value = clean_admin_value(value)
    if value is not None:
        numeric_value = value
        if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.0+)?", value):
            numeric_value = value.replace(",", "")
        try:
            number = Decimal(numeric_value)
            if number.is_finite() and number >= 0 and number == number.to_integral_value():
                return str(int(number))
        except InvalidOperation:
            pass
    return value


def admin_lookup_base_name(value):
    """Ignore trailing set-ID labels and repair flags only for lookup matching."""
    name = clean_admin_value(value)
    if not name:
        return None
    # Already repaired names may return as reference rows on the next upload.
    name = re.sub(
        rf"(?:\s*{re.escape(ADMIN_LOOKUP_FLAG)})+\s*$", "", name,
        flags=re.IGNORECASE,
    ).strip()
    name = re.sub(
        r"\s+(?:[\[(]\s*)?set[\s_-]*id\s*(?:=|:)\s*[\w.-]+(?:\s*[\])])?\s*$",
        "", name, flags=re.IGNORECASE,
    ).strip()
    return name or None


def get_database_admin_reference():
    """Read saved ID/name pairs before the uploaded dataset replaces them."""
    conn = get_connection()
    try:
        return pd.read_sql_query("""
            SELECT DISTINCT updated_admin_id, admin_name
            FROM url_patterns
            WHERE updated_admin_id IS NOT NULL AND admin_name IS NOT NULL
        """, conn)
    finally:
        conn.close()


def repair_admin_alignment(df, database_reference=None):
    """Move misplaced IDs on the same row, then fill names from the database.

    Use valid workbook pairs only when the database has no pair for that ID.
    Set-ID variants share a base name; filled names receive a lookup flag.
    Different base names for one ID remain unresolved.
    """
    repaired = df.copy()
    for column in ("admin_name", "updated_admin_id"):
        if column not in repaired.columns:
            repaired[column] = None
    # Pandas can convert returned None values back into float NaN. Keep the
    # working columns as strings with an empty-string missing-value sentinel.
    ids = repaired["updated_admin_id"].map(normalize_admin_id).fillna("").astype(str)
    names = repaired["admin_name"].map(clean_admin_value).fillna("").astype(str)
    if database_reference is None:
        database_reference = pd.DataFrame(columns=["updated_admin_id", "admin_name"])
    database_ids = database_reference["updated_admin_id"].map(normalize_admin_id).fillna("").astype(str)
    database_names = database_reference["admin_name"].map(clean_admin_value).fillna("").astype(str)
    known_ids = set(ids.loc[ids.ne("")]) | set(database_ids.loc[database_ids.ne("")])
    # Numeric values in admin_name are treated as misplaced administrator IDs.
    def is_misplaced_id(value):
        value = clean_admin_value(value)
        return bool(value) and (
            re.fullmatch(r"\d+", normalize_admin_id(value) or "") is not None
            or normalize_admin_id(value) in known_ids
        )
    misplaced = names.map(is_misplaced_id).astype(bool)
    candidate_ids = names.map(normalize_admin_id).fillna("").astype(str)
    recovered = misplaced & ids.eq("")
    overwritten = misplaced & ids.ne("") & candidate_ids.ne(ids)
    # The user-specified repair moves the ID even when the destination contains
    # a different value; admin_name is cleared on that same row.
    ids.loc[misplaced] = candidate_ids.loc[misplaced]
    names.loc[misplaced] = ""

    def make_lookup(pair_ids, pair_names):
        candidates = {}
        for admin_id, name in zip(pair_ids, pair_names):
            base_name = admin_lookup_base_name(name)
            if admin_id and base_name and not is_misplaced_id(base_name):
                key = base_name.casefold()
                candidates.setdefault(admin_id, {}).setdefault(key, base_name)
        lookup = {
            admin_id: next(iter(values.values()))
            for admin_id, values in candidates.items() if len(values) == 1
        }
        conflicts = {admin_id for admin_id, values in candidates.items() if len(values) > 1}
        return lookup, conflicts

    database_lookup, database_conflicts = make_lookup(database_ids, database_names)
    workbook_lookup, workbook_conflicts = make_lookup(ids, names)
    # Prefer database names for blanks. Never overwrite an existing valid name.
    database_matches = ids.map(database_lookup).fillna("").astype(str)
    database_filled = names.eq("") & database_matches.ne("")
    names.loc[database_filled] = database_matches.loc[database_filled] + " " + ADMIN_LOOKUP_FLAG
    workbook_matches = ids.map(workbook_lookup).fillna("").astype(str)
    # A conflicting historical DB pair must not block a unique valid pair in
    # the current workbook (for example, missing names for admin ID 19153).
    workbook_filled = names.eq("") & workbook_matches.ne("")
    names.loc[workbook_filled] = workbook_matches.loc[workbook_filled] + " " + ADMIN_LOOKUP_FLAG
    filled = database_filled | workbook_filled
    repaired["updated_admin_id"] = ids.astype(object).where(ids.ne(""), None)
    repaired["admin_name"] = names.astype(object).where(names.ne(""), None)
    stats = {
        "repaired_rows": int((misplaced | filled).sum()),
        "misplaced_ids": int(misplaced.sum()),
        "recovered_ids": int(recovered.sum()),
        "filled_names": int(filled.sum()),
        "overwritten_ids": int(overwritten.sum()),
        "database_names_filled": int(database_filled.sum()),
        "workbook_names_filled": int(workbook_filled.sum()),
        "unresolved_rows": int(names.eq("").sum()),
        "conflicting_ids": sorted(database_conflicts | workbook_conflicts),
    }
    return repaired, stats


def parse_uploaded_file(uploaded_file):
    df = None
    last_error_msg = ""
    try:
        uploaded_file.seek(0)
        engine = "openpyxl" if str(getattr(uploaded_file, "name", "")).lower().endswith(".xlsx") else "xlrd"
        df = pd.read_excel(uploaded_file, engine=engine, header=None)
    except Exception as excel_err:
        last_error_msg = str(excel_err)
        if (
            "Expected BOF record" in last_error_msg
            or "b'\\xff\\xfe'" in last_error_msg
            or "tsv" in last_error_msg.lower()
        ):
            try:
                uploaded_file.seek(0)
                raw_content = uploaded_file.read().decode("utf-16")
                raw_rows = [line.split("\t") for line in raw_content.splitlines() if line.strip()]
                row_lengths = [len(row) for row in raw_rows]
                # The header width takes precedence so admin_name is not truncated.
                header = next((
                    row for row in raw_rows
                    if "url_pattern" in [str(value).strip().lower() for value in row]
                ), None)
                standard_cols = len(header) if header is not None else (
                    max(set(row_lengths), key=row_lengths.count) if row_lengths else 0
                )
                aligned_rows = []
                for row_list in raw_rows:
                    while row_list and row_list[-1] == "":
                        row_list.pop()
                    row_list = row_list[:standard_cols]
                    row_list.extend([""] * (standard_cols - len(row_list)))
                    aligned_rows.append(row_list)
                if aligned_rows:
                    df = pd.DataFrame(aligned_rows)
            except Exception as tsv_err:
                last_error_msg = f"TSV Flow Realignment Error: {tsv_err}"
        if df is None:
            try:
                uploaded_file.seek(0)
                html_tables = pd.read_html(uploaded_file, header=None)
                if html_tables:
                    df = html_tables[0]
            except Exception as html_err:
                last_error_msg = f"HTML Parse Error: {html_err}"
    if df is None:
        raise ValueError(f"Failed to parse file.\n\nDiagnostic Details: {last_error_msg}")
    if df.empty:
        raise ValueError("The uploaded file contains no rows.")
    header_row_idx = None
    for idx, row in df.iterrows():
        if "url_pattern" in [str(value).strip().lower() for value in row.values]:
            header_row_idx = idx
            break
    header_row_idx = 0 if header_row_idx is None else header_row_idx
    df.columns = [str(col).strip().lower() for col in df.iloc[header_row_idx]]
    df = df.iloc[header_row_idx + 1:].reset_index(drop=True)
    for col in (
        "url_pattern", "url_pattern_id", "priority", "total_count",
        "language_code", "url_pattern_order", "admin_name", "updated_admin_id",
    ):
        if col not in df.columns:
            df[col] = None
    df = df.replace(r"^\s*$", None, regex=True).replace(["None", "nan", "NaN"], None)
    shifted_mask = df["url_pattern_id"].isna() & df["total_count"].notna()
    fixed_count = int(shifted_mask.sum())
    if fixed_count:
        df.loc[shifted_mask, "url_pattern_id"] = df.loc[shifted_mask, "total_count"]
    shifted_language_mask = (
        pd.to_datetime(df["language_code"], errors="coerce").notna()
        & df["url_pattern_order"].notna()
    )
    if shifted_language_mask.any():
        df.loc[shifted_language_mask, "language_code"] = df.loc[shifted_language_mask, "url_pattern_order"]
    fixed_count += int(shifted_language_mask.sum())
    database_reference = get_database_admin_reference()
    df, admin_repairs = repair_admin_alignment(df, database_reference)
    fixed_count += admin_repairs["repaired_rows"]
    final_df = df[PATTERN_COLUMNS].copy()
    final_df["admin_name"] = final_df["admin_name"].map(
        lambda value: None if pd.isna(value) or not str(value).strip() else str(value).strip()
    )
    initial_len = len(final_df)
    final_df.drop_duplicates(inplace=True)
    duplicates_removed = initial_len - len(final_df)
    final_df["_url_pattern_length"] = final_df["url_pattern"].fillna("").astype(str).str.len()
    final_df.sort_values("_url_pattern_length", ascending=False, inplace=True)
    final_df.drop(columns=["_url_pattern_length"], inplace=True)
    final_df.reset_index(drop=True, inplace=True)
    final_df.attrs["admin_repairs"] = admin_repairs
    final_df.attrs["_internal_pattern_keyword_rows"] = mapper_extract_global_keyword_rows(df)
    final_df.attrs["_pattern_keyword_skipped_rows"] = df.attrs.get("_pattern_keyword_skipped_rows", [])
    return final_df, fixed_count, duplicates_removed


# =============================================================
# NORMALIZATION AND MATCHING
# =============================================================
def normalize_search_text(text):
    text = unquote(str(text)).replace("+", " ")
    text = re.sub(r"[-_/\\*]+", " ", text)
    text = re.sub(r"[^a-zA-Z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def word_forms_match(first_word, second_word):
    def word_forms(word):
        forms = {word}
        if len(word) > 3 and word.endswith("ies"):
            forms.add(word[:-3] + "y")
        if len(word) > 3 and word.endswith("s"):
            forms.add(word[:-1])
        if len(word) > 3 and word.endswith("es"):
            forms.update((word[:-2], word[:-1]))
        if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
            forms.add(word[:-1])
        return forms
    return bool(word_forms(first_word) & word_forms(second_word))


def normalized_word_match(search_word, pattern_word):
    search_word = str(search_word).strip().lower()
    pattern_word = str(pattern_word).strip().lower()
    if not search_word or not pattern_word:
        return False
    if search_word == pattern_word or word_forms_match(search_word, pattern_word):
        return True
    if min(len(search_word), len(pattern_word)) >= 5:
        return search_word + "y" == pattern_word or pattern_word + "y" == search_word
    return False


def normalized_pattern_match(normalized_search, normalized_pattern):
    search_words = str(normalized_search).split()
    pattern_words = str(normalized_pattern).split()
    if not search_words or not pattern_words or len(search_words) > len(pattern_words):
        return False
    size = len(search_words)
    return any(
        all(normalized_word_match(a, b) for a, b in zip(search_words, pattern_words[start:start + size]))
        for start in range(len(pattern_words) - size + 1)
    )


def split_domain_basis(pattern):
    # Remove exactly one outer wrapper, retaining extra basis wildcards.
    pattern = str(pattern).strip().replace("\\*", "*")
    if "*" not in pattern:
        return pattern, ""
    inner = pattern[1:] if pattern.startswith("*") else pattern
    if "*" not in inner:
        return inner[:-1] if inner.endswith("*") else inner, ""
    domain,basis = inner.split("*",1)
    if basis.endswith("*"):
        basis = basis[:-1]
    return domain.strip(),basis.strip()


def normalize_domain(value):
    value = re.sub(r"^[~*.]+", "", unquote(str(value)).strip().lower())
    parsed = urlsplit(value if "://" in value else f"//{value}", scheme="https")
    hostname = (parsed.hostname or value.split("/")[0]).split(":")[0].strip(".")
    return hostname[4:] if hostname.startswith("www.") else hostname


def get_url_parts(url):
    raw_url = str(url).strip()
    parsed = urlsplit(raw_url if "://" in raw_url else f"https://{raw_url}")
    searchable_content = " ".join([parsed.path, parsed.query, parsed.fragment])
    return normalize_domain(parsed.hostname or ""), normalize_search_text(searchable_content)


def domains_match(url_domain, pattern_domain):
    return bool(url_domain and pattern_domain) and (
        url_domain == pattern_domain or url_domain.endswith(f".{pattern_domain}")
    )


def normalize_coverage_basis(basis):
    """Preserve wildcard gaps and exact ~word~ locks; ignore backslashes."""
    raw_basis = unquote(str(basis)).replace("\\", "")
    tokens = []
    for part in re.split(r"(~[^~]*~|\*)", raw_basis):
        if part == "*":
            if tokens and tokens[-1] != "*":
                tokens.append("*")
        elif part.startswith("~") and part.endswith("~") and len(part) >= 2:
            # Lock each word of a phrase; the phrase's words stay adjacent.
            tokens.extend(f"~{word}~" for word in normalize_search_text(part[1:-1]).split())
        else:
            tokens.extend(normalize_search_text(part).split())
    if tokens and tokens[-1] == "*":
        tokens.pop()
    return " ".join(tokens)


def basis_matches_url(normalized_basis, searchable_url):
    return bool(_coverage_match_ids(
        searchable_url, _coverage_basis_index((normalized_basis,)),
    ))


# =============================================================
# COVERAGE CATALOG AND INPUT UTILITIES
# =============================================================
@st.cache_data(show_spinner=False, max_entries=4)
def make_basis_catalog(pattern_df):
    columns = [
        "domain", "normalized_domain", "basis", "normalized_basis",
        "language_code", "url_pattern_id", "priority",
    ]
    catalog_rows = []
    for pattern, pattern_id, priority, language in pattern_df[[
        "url_pattern", "url_pattern_id", "priority", "language_code",
    ]].itertuples(index=False, name=None):
        domain, basis = split_domain_basis(pattern)
        normalized_domain = normalize_domain(domain)
        normalized_basis = normalize_coverage_basis(basis)
        language_code = str(language).strip().lower()
        if (
            not normalized_domain or not normalized_basis or not language_code
            or language_code in {"none", "nan"}
        ):
            continue
        catalog_rows.append({
            "domain": domain, "normalized_domain": normalized_domain,
            "basis": basis, "normalized_basis": normalized_basis,
            "language_code": language_code, "url_pattern_id": pattern_id,
            "priority": priority,
        })
    if not catalog_rows:
        return pd.DataFrame(columns=columns)

    def join_unique(values):
        return ", ".join(sorted({
            str(value) for value in values if pd.notna(value) and str(value).strip()
        }))

    catalog = pd.DataFrame(catalog_rows).groupby(
        ["language_code", "normalized_basis"], dropna=False, as_index=False,
    ).agg({
        "basis": "first", "domain": join_unique, "normalized_domain": "first",
        "url_pattern_id": join_unique, "priority": join_unique,
    })
    catalog.sort_values(
        "normalized_basis", key=lambda series: series.str.len(),
        ascending=False, inplace=True,
    )
    return catalog.reset_index(drop=True)


def coerce_metric(series):
    cleaned = (
        series.fillna(0).astype(str).str.strip()
        .str.replace(",", "", regex=False)
        .str.replace(r"[^0-9.\-()]", "", regex=True)
        .str.replace(r"^\((.*)\)$", r"-\1", regex=True)
    )
    return pd.to_numeric(cleaned, errors="coerce").fillna(0)


def read_coverage_csv(uploaded_file):
    last_error = None
    for encoding in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            uploaded_file.seek(0)
            return pd.read_csv(uploaded_file, encoding=encoding, sep=None, engine="python")
        except Exception as err:
            last_error = err
    raise ValueError(f"Unable to read the CSV file: {last_error}")


def find_suggested_column(columns, candidates):
    normalized_columns = {
        re.sub(r"[^a-z0-9]", "", str(column).lower()): column for column in columns
    }
    for candidate in candidates:
        candidate = re.sub(r"[^a-z0-9]", "", candidate.lower())
        if candidate in normalized_columns:
            return normalized_columns[candidate]
    for normalized_column, original_column in normalized_columns.items():
        if any(re.sub(r"[^a-z0-9]", "", c.lower()) in normalized_column for c in candidates):
            return original_column
    return None


def remove_report_total_rows(input_df):
    if input_df is None or "URL" not in input_df.columns:
        return input_df, 0
    excluded_values = {
        "grand total", "report total", "stripped url (others)",
        "report total<br>stripped url (others)",
        "report total<br/>stripped url (others)",
        "report total<br />stripped url (others)",
    }
    excluded_mask = input_df["URL"].fillna("").astype(str).str.strip().str.lower().isin(excluded_values)
    return input_df.loc[~excluded_mask].copy(), int(excluded_mask.sum())


# =============================================================
# FAST COVERAGE MATCHER
# =============================================================
@lru_cache(maxsize=50000)
def _coverage_word_forms(word):
    """URL-side forms only: exact token plus common singular spellings."""
    forms = {word}
    if len(word) > 3:
        if word.endswith("ies"):
            forms.add(word[:-3] + "y")
            forms.add(word[:-1])
        elif word.endswith(("sses", "shes", "ches", "xes", "zes")):
            forms.add(word[:-2])
        elif word in {"buses", "statuses"}:
            forms.add(word[:-2])
        elif word.endswith("s") and not word.endswith(("ss", "us", "is")):
            forms.add(word[:-1])
    return frozenset(forms)


@lru_cache(maxsize=4)
def _coverage_basis_index(bases):
    """Index contiguous fragments; wildcard-separated fragments may reorder."""
    children = [{}]
    form_edges = [{}]
    exact_edges = [{}]
    terminals = [[]]
    fragment_ids = {}
    watchers = []
    condition_counts = []
    for basis_id, basis in enumerate(bases):
        fragments = [tuple(part.split()) for part in basis.split("*") if part.strip()]
        required = Counter(fragments)
        condition_counts.append(len(required))
        for fragment, occurrences in required.items():
            fragment_id = fragment_ids.get(fragment)
            if fragment_id is None:
                fragment_id = len(fragment_ids)
                fragment_ids[fragment] = fragment_id
                watchers.append({})
                node = 0
                for word in fragment:
                    child = children[node].get(word)
                    if child is None:
                        child = len(children)
                        children[node][word] = child
                        children.append({})
                        form_edges.append({})
                        exact_edges.append({})
                        terminals.append([])
                        if word.startswith("~") and word.endswith("~"):
                            exact_edges[node].setdefault(word[1:-1], set()).add(child)
                        else:
                            form_edges[node].setdefault(word, set()).add(child)
                    node = child
                terminals[node].append(fragment_id)
            watchers[fragment_id].setdefault(occurrences, []).append(basis_id)
    return form_edges, exact_edges, terminals, watchers, condition_counts


def _coverage_match_ids(searchable_url, index):
    form_edges, exact_edges, terminals, watchers, condition_counts = index
    active = set()
    occurrences = Counter()
    satisfied = Counter()
    matches = set()
    for word in searchable_url.split():
        forms = _coverage_word_forms(word)
        next_active = set()
        for node in active | {0}:
            # Tilde locks match the original token, not its singular forms.
            next_active.update(exact_edges[node].get(word, ()))
            for form in forms:
                next_active.update(form_edges[node].get(form, ()))
        found_fragments = {
            fragment_id for node in next_active for fragment_id in terminals[node]
        }
        for fragment_id in found_fragments:
            occurrences[fragment_id] += 1
            for basis_id in watchers[fragment_id].get(occurrences[fragment_id], ()):
                satisfied[basis_id] += 1
                if satisfied[basis_id] == condition_counts[basis_id]:
                    matches.add(basis_id)
        active = next_active
    return tuple(sorted(matches))


def create_coverage_report(input_df, basis_catalog):
    """Return URL summary, match details, coverage pivot, and basis pivot."""
    summary_columns = [
        "URL", "URL Domain", "Language Code", "Coverage Status",
        "Matched Basis Count", "Matching Bases", "Keyword Impressions", "Revenue",
    ]
    detail_columns = [
        "URL", "URL Domain", "Language Code", "Coverage Status", "Matching Basis",
        "Source Pattern Domain(s)", "URL Pattern ID", "Priority",
        "Keyword Impressions", "Revenue",
    ]
    coverage_columns = [
        "Language Code", "Coverage Status", "URLs", "Keyword Impressions", "Revenue",
    ]
    basis_columns = [
        "Language Code", "URL Domain", "Matching Basis", "URLs",
        "Keyword Impressions", "Revenue",
    ]
    if basis_catalog.empty:
        raise ValueError("Select at least one language with usable bases.")
    selected_languages = sorted(basis_catalog["language_code"].astype(str).unique())
    language_label = ", ".join(selected_languages)
    prepared, _ = remove_report_total_rows(input_df)
    prepared = prepared.copy()
    prepared["URL"] = prepared["URL"].astype(str).str.strip()
    prepared = prepared.groupby("URL", as_index=False, sort=False).agg({
        "Keyword Impressions": "sum", "Revenue": "sum",
    })
    if prepared.empty:
        return (
            pd.DataFrame(columns=summary_columns),
            pd.DataFrame(columns=detail_columns),
            pd.DataFrame(columns=coverage_columns),
            pd.DataFrame(columns=basis_columns),
        )
    records = list(basis_catalog[[
        "normalized_basis", "basis", "language_code", "domain",
        "url_pattern_id", "priority",
    ]].itertuples(index=False, name=None))
    index = _coverage_basis_index(tuple(str(row[0]) for row in records))
    path_matches = {}
    summary_rows = []
    detail_rows = []
    for url, impressions, revenue in prepared[[
        "URL", "Keyword Impressions", "Revenue",
    ]].itertuples(index=False, name=None):
        domain, searchable_url = get_url_parts(url)
        ids = path_matches.get(searchable_url)
        if ids is None:
            ids = _coverage_match_ids(searchable_url, index)
            path_matches[searchable_url] = ids
        if not ids:
            summary_rows.append((
                url, domain, language_label, "No Matching Basis", 0,
                "No Matching Basis", impressions, revenue,
            ))
            detail_rows.append((
                url, domain, language_label, "No Matching Basis",
                "No Matching Basis", "", "", "", impressions, revenue,
            ))
            continue
        matched_bases = []
        matched_languages = set()
        for basis_id in ids:
            _, basis, language, source_domain, pattern_id, priority = records[basis_id]
            matched_bases.append(str(basis))
            matched_languages.add(str(language))
            detail_rows.append((
                url, domain, language, "Covered", basis, source_domain,
                pattern_id, priority, impressions, revenue,
            ))
        matched_bases = list(dict.fromkeys(matched_bases))
        summary_rows.append((
            url, domain, ", ".join(sorted(matched_languages)), "Covered", len(matched_bases),
            " | ".join(matched_bases), impressions, revenue,
        ))
    url_summary_df = pd.DataFrame(summary_rows, columns=summary_columns)
    detail_df = pd.DataFrame(detail_rows, columns=detail_columns)
    coverage_pivot = url_summary_df.groupby(
        ["Language Code", "Coverage Status"], as_index=False, dropna=False,
    ).agg(**{
        "URLs": ("URL", "count"),
        "Keyword Impressions": ("Keyword Impressions", "sum"),
        "Revenue": ("Revenue", "sum"),
    })
    covered_detail = detail_df.loc[detail_df["Coverage Status"].eq("Covered")]
    if covered_detail.empty:
        basis_pivot = pd.DataFrame(columns=basis_columns)
    else:
        basis_pivot = covered_detail.groupby(
            ["Language Code", "URL Domain", "Matching Basis"],
            as_index=False, dropna=False,
        ).agg(**{
            "URLs": ("URL", "nunique"),
            "Keyword Impressions": ("Keyword Impressions", "sum"),
            "Revenue": ("Revenue", "sum"),
        }).sort_values(
            ["Revenue", "Keyword Impressions", "URLs"], ascending=False,
        )
    return url_summary_df, detail_df, coverage_pivot, basis_pivot


def add_user_coverage_bases(basis_catalog, edited_rows, selected_languages):
    """Assign each new basis only to the language chosen on its editor row."""
    if isinstance(selected_languages, str):
        selected_languages = [selected_languages]
    selected_languages = sorted(set(selected_languages))
    if (not selected_languages or basis_catalog.empty
            or not basis_catalog["language_code"].isin(selected_languages).all()):
        raise ValueError("Use the basis catalog for the report's selected languages.")
    if "Language Code" not in edited_rows.columns:
        raise ValueError("The new-basis table must include a Language Code column.")
    existing = set(zip(basis_catalog["language_code"], basis_catalog["normalized_basis"]))
    added_rows = []
    invalid = []
    for row_number, (value, language_value) in enumerate(
        edited_rows[["New Basis", "Language Code"]].itertuples(index=False, name=None), 1,
    ):
        if pd.isna(value) or not str(value).strip():
            continue
        language = "" if pd.isna(language_value) else str(language_value).strip().lower()
        if not language:
            invalid.append(f"Row {row_number}: choose a language code for the new basis.")
            continue
        if language not in selected_languages:
            invalid.append(
                f"Row {row_number}: language '{language}' is not selected at the top of the report."
            )
            continue
        # Multiple bases in a cell all use the language on that same row.
        for raw_basis in re.split(r"[;\n]+", str(value)):
            basis = raw_basis.strip().strip("*").strip()
            if not basis:
                continue
            normalized = normalize_coverage_basis(basis)
            if not normalized:
                invalid.append(f"Row {row_number}: '{raw_basis.strip()}' contains no searchable words.")
                continue
            if (language, normalized) in existing:
                continue
            existing.add((language, normalized))
            added_rows.append({
                "domain": "User Added", "normalized_domain": "",
                "basis": basis, "normalized_basis": normalized,
                "language_code": language,
                "url_pattern_id": f"user-added-{len(added_rows) + 1}",
                "priority": "",
            })
    additions = pd.DataFrame(added_rows, columns=basis_catalog.columns)
    combined = pd.concat([basis_catalog, additions], ignore_index=True)
    combined = combined.sort_values(
        "normalized_basis", key=lambda values: values.str.len(), ascending=False,
        kind="stable",
    ).reset_index(drop=True)
    return combined, additions, invalid


def render_coverage_results(report, title, key_prefix):
    """Show url_summary_df directly, with optional aggregate and match details."""
    url_summary_df, detail_df, coverage_pivot, basis_pivot = report
    st.subheader(title)
    total_urls = len(url_summary_df)
    covered_urls = int(url_summary_df["Coverage Status"].eq("Covered").sum())
    metric1, metric2, metric3, metric4 = st.columns(4)
    metric1.metric("URLs Checked", f"{total_urls:,}")
    metric2.metric("Covered URLs", f"{covered_urls:,}")
    metric3.metric("No Matching Basis", f"{total_urls - covered_urls:,}")
    metric4.metric("Coverage Rate", f"{covered_urls / total_urls * 100 if total_urls else 0:.1f}%")
    st.dataframe(url_summary_df, use_container_width=True, hide_index=True)
    st.download_button(
        "Download URL Summary", data=url_summary_df.to_csv(index=False),
        file_name=f"{key_prefix}_url_summary.csv", mime="text/csv",
        use_container_width=True, key=f"{key_prefix}_download_summary",
    )
    with st.expander("Coverage Summary, Basis Performance, and Match Details", expanded=False):
        summary_tab, basis_tab, detail_tab = st.tabs([
            "Coverage Summary", "Basis Performance", "Match Details",
        ])
        with summary_tab:
            st.dataframe(coverage_pivot, use_container_width=True, hide_index=True)
        with basis_tab:
            st.dataframe(basis_pivot, use_container_width=True, hide_index=True)
            st.caption(
                "A URL's performance is attributed to each matching basis. "
                "Use URL Summary for non-duplicated totals."
            )
        with detail_tab:
            st.dataframe(detail_df, use_container_width=True, hide_index=True)
        download1, download2 = st.columns(2)
        download1.download_button(
            "Download Basis Report", data=basis_pivot.to_csv(index=False),
            file_name=f"{key_prefix}_basis_report.csv", mime="text/csv",
            use_container_width=True, key=f"{key_prefix}_download_basis",
        )
        download2.download_button(
            "Download Match Details", data=detail_df.to_csv(index=False),
            file_name=f"{key_prefix}_match_details.csv", mime="text/csv",
            use_container_width=True, key=f"{key_prefix}_download_details",
        )


def clear_coverage_reports():
    for key in (
        "coverage_report", "coverage_report_language", "coverage_report_languages", "coverage_report_input",
        "coverage_report_catalog_signature", "coverage_recheck_report",
        "coverage_recheck_signature",
    ):
        st.session_state.pop(key, None)


# =============================================================
# COVERAGE REPORT UI
# =============================================================
def render_coverage_report(final_df):
    if final_df.empty:
        st.warning("Upload a shared global pattern dataset before creating a coverage report.")
        return
    complete_basis_catalog = make_basis_catalog(final_df)
    if complete_basis_catalog.empty:
        st.warning("The active dataset has no usable language-basis rows.")
        return
    available_languages = sorted(
        complete_basis_catalog["language_code"].dropna().astype(str).str.strip()
        .loc[lambda values: values.ne("")].unique().tolist()
    )
    if not available_languages:
        st.warning("No language codes are available in the active dataset.")
        return
    language_key = "coverage_language_codes"
    if language_key in st.session_state:
        saved = st.session_state[language_key]
        valid = [language for language in saved if language in available_languages]
        if valid != saved:
            st.session_state[language_key] = valid
    selected_languages = st.multiselect(
        "Language codes", available_languages,
        default=(None if language_key in st.session_state else
                 (["en"] if "en" in available_languages else available_languages[:1])),
        format_func=lambda value: value.upper(), key=language_key,
        help="Choose one or more languages. A URL is covered if any selected language's basis matches.",
    )
    selected_languages = tuple(sorted(selected_languages))
    if not selected_languages:
        st.info("Select at least one language code before entering URLs.")
        return
    basis_catalog = complete_basis_catalog.loc[
        complete_basis_catalog["language_code"].isin(selected_languages)
    ].copy()
    st.caption(
        f"{len(basis_catalog):,} language/basis pairs are available for "
        f"{', '.join(language.upper() for language in selected_languages)}. "
        "Each URL is counted once. Covered summary rows show matching languages; "
        "Match Details shows each basis's language."
    )
    input_type = st.radio(
        "Input type", ["Paste URLs", "Upload CSV With Performance"],
        horizontal=True, key="coverage_input_type",
    )
    prepared_input = None
    if input_type == "Paste URLs":
        pasted_urls = st.text_area(
            "URLs", placeholder="https://example.com/topic-one\nhttps://example.com/topic-two",
            height=180, key="coverage_urls",
        )
        urls = list(dict.fromkeys(
            value.strip() for value in re.split(r"[\n,]+", pasted_urls) if value.strip()
        ))
        if urls:
            prepared_input = pd.DataFrame({"URL": urls, "Keyword Impressions": 0, "Revenue": 0.0})
    else:
        performance_file = st.file_uploader(
            "Upload CSV", type=["csv"], accept_multiple_files=False, key="coverage_csv",
        )
        if performance_file is not None:
            try:
                source_df = read_coverage_csv(performance_file)
                if source_df.empty:
                    st.warning("The uploaded CSV has no data rows.")
                else:
                    columns = list(source_df.columns)
                    suggested_url = find_suggested_column(columns, ["url", "urls", "page url", "page"])
                    suggested_impressions = find_suggested_column(
                        columns, ["keyword impressions", "impressions", "keyword_impressions"],
                    )
                    suggested_revenue = find_suggested_column(columns, ["revenue", "keyword revenue", "earnings"])
                    mapping1, mapping2, mapping3 = st.columns(3)
                    with mapping1:
                        url_column = st.selectbox(
                            "URL column", columns,
                            index=columns.index(suggested_url) if suggested_url in columns else 0,
                            key="coverage_url_column",
                        )
                    optional_columns = ["None"] + columns
                    with mapping2:
                        impressions_column = st.selectbox(
                            "Keyword impressions column", optional_columns,
                            index=optional_columns.index(suggested_impressions) if suggested_impressions in columns else 0,
                            key="coverage_impressions_column",
                        )
                    with mapping3:
                        revenue_column = st.selectbox(
                            "Revenue column", optional_columns,
                            index=optional_columns.index(suggested_revenue) if suggested_revenue in columns else 0,
                            key="coverage_revenue_column",
                        )
                    prepared_input = pd.DataFrame({"URL": source_df[url_column]})
                    prepared_input["Keyword Impressions"] = (
                        coerce_metric(source_df[impressions_column]) if impressions_column != "None" else 0
                    )
                    prepared_input["Revenue"] = (
                        coerce_metric(source_df[revenue_column]) if revenue_column != "None" else 0.0
                    )
                    prepared_input = prepared_input.loc[
                        prepared_input["URL"].notna()
                        & prepared_input["URL"].astype(str).str.strip().ne("")
                    ].copy()
            except Exception as err:
                st.error(f"Could not read the CSV: {err}")
    removed_total_rows = 0
    if prepared_input is not None:
        prepared_input, removed_total_rows = remove_report_total_rows(prepared_input)
    if removed_total_rows:
        st.info(
            f"Removed {removed_total_rows:,} summary row(s): "
            "Grand Total, Report Total, or Stripped URL (Others)."
        )
    catalog_signature = hashlib.sha256(
        basis_catalog.to_csv(index=False).encode("utf-8")
    ).hexdigest()
    if st.button(
        "Create Coverage Report", type="primary", use_container_width=True,
        disabled=prepared_input is None or prepared_input.empty,
    ):
        with st.spinner("Checking URL coverage..."):
            report = create_coverage_report(prepared_input, basis_catalog)
            clear_coverage_reports()
            st.session_state["coverage_report"] = report
            st.session_state["coverage_report_languages"] = selected_languages
            # Rechecks always use the same input, including performance metrics.
            st.session_state["coverage_report_input"] = prepared_input.copy()
            st.session_state["coverage_report_catalog_signature"] = catalog_signature
            st.session_state["coverage_report_revision"] = (
                st.session_state.get("coverage_report_revision", 0) + 1
            )
    report = st.session_state.get("coverage_report")
    if report is None:
        return
    if (
        st.session_state.get("coverage_report_languages") != selected_languages
        or st.session_state.get("coverage_report_catalog_signature") != catalog_signature
    ):
        st.info("Create a new coverage report for the selected languages and current dataset.")
        return

    render_coverage_results(report, "URL Summary — Existing Bases", "coverage_original")
    url_summary_df = report[0]
    uncovered = url_summary_df.loc[
        url_summary_df["Coverage Status"].eq("No Matching Basis"), ["URL"]
    ].reset_index(drop=True)
    if uncovered.empty:
        st.success("All submitted URLs have a matching basis.")
        return

    st.write("---")
    st.subheader("Add Bases for URLs With No Matching Basis")
    st.write(
        "Enter a new basis beside each URL, for example bug*bite. "
        "Separate multiple bases in one cell with semicolons. "
        "The next report checks every original URL against existing bases and "
        "all unique new bases for the selected languages. "
        "Choose a Language Code for each row; its new bases use only that language."
    )
    st.caption("New bases are used for this coverage check and do not update the shared dataset.")
    editor_input = uncovered.assign(**{
        "New Basis": "",
        "Language Code": selected_languages[0] if len(selected_languages) == 1 else "",
    })
    revision = st.session_state.get("coverage_report_revision", 0)
    edited_rows = st.data_editor(
        editor_input, hide_index=True, use_container_width=True,
        num_rows="fixed", disabled=["URL"],
        key=f"coverage_new_basis_language_editor_{revision}",
        column_config={
            "URL": st.column_config.TextColumn("No Matching Basis URL", width="large"),
            "New Basis": st.column_config.TextColumn(
                "New Basis", width="large", help="Example: bug*bite; heart*health",
            ),
            "Language Code": st.column_config.SelectboxColumn(
                "Language Code", options=[""] + list(selected_languages), width="small",
                help="Choose one of the language codes selected at the top. Applies to this row's new bases.",
            ),
        },
    )
    combined_catalog, additions, invalid = add_user_coverage_bases(
        basis_catalog, edited_rows, selected_languages,
    )
    if invalid:
        st.warning("Please fix the following entries before rechecking:\n\n" + "\n".join(f"- {message}" for message in invalid))
    st.caption(
        f"{additions['normalized_basis'].nunique():,} unique new basis/bases "
        f"across {len(additions):,} language/basis pairs ready to check."
    )
    additions_signature = edited_rows[["URL", "New Basis", "Language Code"]].to_csv(index=False)
    if st.button(
        "Check Coverage With Existing and New Bases", type="primary",
        use_container_width=True, disabled=additions.empty or bool(invalid),
        key="coverage_recheck_button",
    ):
        with st.spinner("Checking coverage with existing and new bases..."):
            st.session_state["coverage_recheck_report"] = create_coverage_report(
                st.session_state["coverage_report_input"], combined_catalog,
            )
            st.session_state["coverage_recheck_signature"] = additions_signature
    revised_report = st.session_state.get("coverage_recheck_report")
    if revised_report is None:
        return
    if invalid or st.session_state.get("coverage_recheck_signature") != additions_signature:
        st.info("New basis or language entries changed. Fix any flagged rows and run the coverage check again to refresh the second report.")
        return
    st.write("---")
    original_covered = int(url_summary_df["Coverage Status"].eq("Covered").sum())
    revised_covered = int(revised_report[0]["Coverage Status"].eq("Covered").sum())
    st.info(f"{revised_covered - original_covered:,} additional URL(s) now have a matching basis.")
    render_coverage_results(
        revised_report, "URL Summary — Existing and New Bases", "coverage_rechecked",
    )
    st.download_button(
        "Download New Bases", data=additions[["basis", "language_code"]].to_csv(index=False),
        file_name="coverage_new_bases.csv", mime="text/csv", use_container_width=True,
        key="coverage_download_new_bases",
    )


# =============================================================
# CONCATENATE / PATTERN GENERATOR PAGE
# =============================================================
def clean_generator_domain(value):
    """Convert pasted HTTP links into plain domains without changing bases."""
    if pd.isna(value):
        return ""
    value = str(value).strip()
    markdown_link = re.fullmatch(r"\[[^\]]*\]\((https?://[^\s)]+)\)", value, re.IGNORECASE)
    if markdown_link:
        value = markdown_link.group(1)
    value = value.strip("<>").strip()
    if re.match(r"^(?:https?:)?//", value, flags=re.IGNORECASE):
        parsed = urlsplit(value)
        return (parsed.hostname or "").strip()
    return value


def concatenate_sheet_page():
    st.header("Concatenate Sheet")
    st.write("Enter Domain and Basis values in the table below. Each row will generate one pattern.")
    if "pattern_generator_data" not in st.session_state:
        st.session_state["pattern_generator_data"] = pd.DataFrame({"Domain": [""], "Basis": [""]})
    default_df = st.session_state["pattern_generator_data"]
    revision = st.session_state.get("pattern_generator_revision", 0)
    input_df = st.data_editor(
        default_df, num_rows="dynamic", use_container_width=True,
        key=f"pattern_generator_plain_domain_table_{revision}",
        column_config={
            "Domain": st.column_config.TextColumn(
                "Domain", help="Plain domain, for example example.com. Pasted HTTP links are cleaned automatically.",
                width="large",
            ),
            "Basis": st.column_config.TextColumn("Basis", help="Example: labor day", width="large"),
        },
    )
    cleaned_domains = input_df["Domain"].map(clean_generator_domain)
    original_domains = input_df["Domain"].fillna("").astype(str)
    if not cleaned_domains.equals(original_domains):
        refreshed = input_df.copy()
        refreshed["Domain"] = cleaned_domains
        st.session_state["pattern_generator_data"] = refreshed.reset_index(drop=True)
        st.session_state["pattern_generator_revision"] = revision + 1
        st.rerun()
    if st.button("Generate Patterns", type="primary", use_container_width=True):
        df = input_df.copy()
        for column in ("Domain", "Basis"):
            df[column] = df[column].fillna("").astype(str).str.strip()
        df["Domain"] = df["Domain"].map(clean_generator_domain)
        df = df.loc[df["Domain"].ne("") & df["Basis"].ne("")].copy()
        if df.empty:
            st.warning("Please enter at least one Domain and Basis.")
        else:
            def generate_pattern(row):
                domain, basis = row["Domain"], row["Basis"]
                if domain.startswith("patternkeywords.global.promote"):
                    return f"*patternkeywords.global.promote*{basis}*"
                return f"*{domain}*{basis}*"
            df["Pattern"] = df.apply(generate_pattern, axis=1)
            st.success(f"Generated {len(df):,} pattern(s).")
            st.dataframe(
                df, use_container_width=True, hide_index=True,
                column_config={
                    "Domain": st.column_config.TextColumn("Domain"),
                    "Pattern": st.column_config.TextColumn("Pattern"),
                },
            )
            st.download_button(
                "Download Patterns As TXT", data="\n".join(df["Pattern"].tolist()),
                file_name="generated_patterns.txt", mime="text/plain", use_container_width=True,
            )
            st.download_button(
                "Download As CSV", data=df.to_csv(index=False).encode("utf-8"),
                file_name="generated_patterns.csv", mime="text/csv", use_container_width=True,
            )


def coverage_report_page():
    st.header("Coverage Report")
    render_coverage_report(load_shared_dataset())
    st.write("---")
    st.caption("Shared URL Pattern Database • Coverage uses the current active dataset.")


# =============================================================
# DATASET UPDATE UI
# =============================================================
def render_dataset_update():
    with st.expander("Update Shared Dataset", expanded=False):
        new_file = st.file_uploader(
            "Upload new workbook (.xls or .xlsx)", type=["xls", "xlsx"], accept_multiple_files=False,
            key="admin_file_uploader",
        )
        if new_file is None:
            return
        date_validation = validate_file_date(new_file.name)
        st.write(f"**Selected file:** `{new_file.name}`")
        if date_validation["date_missing"]:
            st.error("No valid date was found in the filename.")
            st.info(
                "Expected a date in `DD-MM-YYYY` format.\n\n"
                "Example:\n`Global_Pattern_All_27-08-2026_xxxxx.xls`"
            )
            date_confirmed = st.checkbox(
                "I have manually verified the file date.", key="manual_date_confirmation",
            )
        elif date_validation["is_match"]:
            st.success("File date matches today's date.")
            date_col1, date_col2 = st.columns(2)
            with date_col1:
                st.write("**File Date**")
                st.write(date_validation["date_found"].strftime("%d-%m-%Y"))
            with date_col2:
                st.write("**Current Date**")
                st.write(date_validation["current_date"].strftime("%d-%m-%Y"))
            date_confirmed = True
        else:
            st.error("Date mismatch detected")
            difference_days = date_validation["difference_days"]
            date_col1, date_col2, date_col3 = st.columns(3)
            date_col1.metric("File Date", date_validation["date_found"].strftime("%d-%m-%Y"))
            date_col2.metric("Current Date", date_validation["current_date"].strftime("%d-%m-%Y"))
            date_col3.metric("File Age" if difference_days > 0 else "Difference", f"{abs(difference_days)} day(s)")
            if difference_days > 0:
                st.warning(f"The uploaded dataset is {difference_days} day(s) older than today's date.")
            elif difference_days < 0:
                st.warning(f"The uploaded dataset is {abs(difference_days)} day(s) in the future.")
            st.write("Please verify that this is the correct dataset before continuing.")
            date_confirmed = st.checkbox(
                "I have verified the date mismatch and want to continue.",
                key="date_mismatch_confirmation",
            )
        if date_confirmed:
            if st.button("Process & Preview Dataset", type="primary", use_container_width=True):
                try:
                    with st.spinner("Processing new dataset..."):
                        preview_df, fixed_count, duplicates_removed = parse_uploaded_file(new_file)
                    private_rows = preview_df.attrs.pop("_internal_pattern_keyword_rows", None)
                    skipped_keyword_rows = preview_df.attrs.pop("_pattern_keyword_skipped_rows", [])
                    st.session_state["pending_pattern_keyword_rows"] = private_rows
                    st.session_state["pending_keyword_skipped_rows"] = skipped_keyword_rows
                    st.session_state.update({
                        "pending_dataset": preview_df, "pending_filename": new_file.name,
                        "pending_fixed_count": fixed_count, "pending_duplicates": duplicates_removed,
                        "pending_date_validation": date_validation,
                        "pending_admin_repairs": preview_df.attrs.get("admin_repairs", {}),
                    })
                    st.success("New dataset processed successfully.")
                    if preview_df["admin_name"].fillna("").astype(str).str.strip().eq("").all():
                        st.warning("No admin_name values were found. Include an admin_name column in the workbook to populate the search dropdown.")
                except Exception as err:
                    st.error("Failed to process file.")
                    st.info(f"Details: {err}")
        else:
            st.info("Date verification is required before the file can be processed.")


def clear_pending_dataset():
    for key in (
        "pending_dataset", "pending_filename", "pending_fixed_count", "pending_duplicates",
        "pending_date_validation", "confirm_dataset_replacement", "admin_file_uploader",
        "manual_date_confirmation", "date_mismatch_confirmation",
        "pending_admin_repairs", "pending_pattern_keyword_rows", "pending_keyword_skipped_rows",
    ):
        st.session_state.pop(key, None)


def render_pending_dataset():
    if "pending_dataset" not in st.session_state:
        return
    st.write("---")
    st.subheader("New Dataset Preview")
    pending_df = st.session_state["pending_dataset"]
    pending_filename = st.session_state["pending_filename"]
    date_validation = st.session_state.get("pending_date_validation")
    preview1, preview2, preview3, preview4 = st.columns(4)
    preview1.metric("New Rows", f"{len(pending_df):,}")
    preview2.metric("Duplicates Removed", f"{st.session_state['pending_duplicates']:,}")
    preview3.metric("Alignment Fixes", f"{st.session_state['pending_fixed_count']:,}")
    if date_validation:
        preview4.metric(
            "File Date",
            date_validation["date_found"].strftime("%d-%m-%Y") if date_validation["date_found"] else "Not Found",
        )
    st.write(f"**File:** `{pending_filename}`")
    if date_validation:
        if date_validation["date_missing"]:
            st.error("No valid date was detected in the filename. The date was manually verified.")
        elif date_validation["is_match"]:
            st.success("Dataset date verified — matches today's date.")
        else:
            st.warning(
                f"Date mismatch acknowledged. File date: {date_validation['date_found'].strftime('%d-%m-%Y')} | "
                f"Current date: {date_validation['current_date'].strftime('%d-%m-%Y')} | "
                f"Difference: {abs(date_validation['difference_days'])} day(s)"
            )
    skipped_keyword_rows = st.session_state.get("pending_keyword_skipped_rows", [])
    if skipped_keyword_rows:
        row_labels = ", ".join(map(str, skipped_keyword_rows[:20]))
        st.warning(
            f"{len(skipped_keyword_rows):,} keyword cell(s) could not be used for training "
            f"(data rows {row_labels}{', ...' if len(skipped_keyword_rows) > 20 else ''}). "
            "Their URL pattern rows are still included in the shared dataset."
        )
    st.write("**First 100 rows:**")
    st.dataframe(pending_df.head(100).fillna(""), use_container_width=True, hide_index=True)
    admin_repairs = st.session_state.get("pending_admin_repairs", {})
    if admin_repairs:
        st.info(
            f"Admin repairs: {admin_repairs['misplaced_ids']:,} ID value(s) removed from admin_name; "
            f"{admin_repairs['recovered_ids']:,} missing ID(s) recovered; "
            f"{admin_repairs['database_names_filled']:,} name(s) filled from the database; "
            f"{admin_repairs['workbook_names_filled']:,} name(s) filled from workbook pairs. "
            f"Filled names are marked {ADMIN_LOOKUP_FLAG}."
        )
        if admin_repairs["conflicting_ids"]:
            st.warning(
                "These admin IDs have conflicting names in a lookup source. "
                "Ambiguous pairs were not used from that source: " + ", ".join(admin_repairs["conflicting_ids"])
            )
        if admin_repairs["overwritten_ids"]:
            st.info(
                f"{admin_repairs['overwritten_ids']:,} existing updated_admin_id value(s) "
                "were replaced with the ID found in admin_name on the same row."
            )
        if admin_repairs["unresolved_rows"]:
            st.warning(
                f"{admin_repairs['unresolved_rows']:,} input row(s) still have no resolved admin name. "
                "Names cannot be inferred without a unique valid ID/name pair."
            )
            unresolved = pending_df.loc[pending_df["admin_name"].isna()]
            with st.expander("Review Rows With Unresolved Admin Names", expanded=False):
                st.dataframe(unresolved.fillna(""), use_container_width=True, hide_index=True)
                st.download_button(
                    "Download Unresolved Admin Rows", data=unresolved.to_csv(index=False),
                    file_name="unresolved_admin_rows.csv", mime="text/csv",
                    use_container_width=True,
                )
    st.warning("Confirming below will replace the current dataset for ALL users.")
    confirm = st.checkbox(
        "I understand that this will replace the current shared dataset.",
        key="confirm_dataset_replacement",
    )
    confirm_col1, confirm_col2 = st.columns(2)
    with confirm_col1:
        if st.button("Replace Shared Dataset", type="primary", disabled=not confirm, use_container_width=True):
            try:
                with st.spinner("Replacing shared dataset and training the keyword model..."):
                    replace_shared_dataset(
                        pending_df, pending_filename,
                        date_validation["date_found"] if date_validation else None,
                        st.session_state.get("authenticated_username", "Unknown"),
                        pattern_keyword_rows=st.session_state.get("pending_pattern_keyword_rows"),
                    )
                clear_pending_dataset()
                clear_coverage_reports()
                # The replacement workbook may have a different set of admins.
                st.session_state.pop("database_admin_name", None)
                make_basis_catalog.clear()
                _coverage_basis_index.cache_clear()
                st.success("Shared dataset replaced successfully.")
                st.rerun()
            except Exception as err:
                st.error("Failed to replace shared dataset.")
                st.info(f"Details: {err}")
    with confirm_col2:
        if st.button("Cancel Update", use_container_width=True):
            clear_pending_dataset()
            st.rerun()


# =============================================================
# ADMIN FILTER AND DATASET SEARCH
# =============================================================
def get_admin_options(final_df):
    """None = all admins; empty string = rows without an admin_name."""
    names = final_df["admin_name"].fillna("").astype(str).str.strip()
    available = sorted(names.loc[names.ne("")].unique().tolist(), key=lambda value: (value.casefold(), value))
    return [None] + ([""] if names.eq("").any() else []) + available


def search_dataset(final_df, search_string, search_mode, selected_admin=None):
    """Apply the admin filter AND the selected search; multiple terms use OR."""
    filtered_df = final_df.copy()
    if selected_admin is not None:
        admin_values = filtered_df["admin_name"].fillna("").astype(str).str.strip()
        filtered_df = filtered_df.loc[admin_values.eq(selected_admin)].copy()
    search_terms = list(dict.fromkeys(
        term.strip() for term in re.split(r"[,\n]+", search_string) if term.strip()
    ))
    if filtered_df.empty or not search_terms:
        return filtered_df, search_terms
    raw_patterns = filtered_df["url_pattern"].fillna("").astype(str).str.strip().str.lower()
    raw_ids = filtered_df["url_pattern_id"].fillna("").astype(str).str.strip().str.lower()
    basis_values = filtered_df["url_pattern"].fillna("").astype(str).map(
        lambda value: split_domain_basis(value)[1]
    ).str.strip().str.lower()
    search_values = raw_patterns
    normalized_values = search_values.apply(normalize_search_text) if search_mode == "Normalized Search" else None
    combined_search_mask = pd.Series(False, index=filtered_df.index)
    for search_term in search_terms:
        raw_search = search_term.strip().lower()
        if search_mode == "Exact Match":
            pattern_mask = search_values.eq(raw_search) | basis_values.eq(raw_search)
            id_mask = raw_ids.eq(raw_search)
        else:
            normalized_search = normalize_search_text(search_term)
            pattern_mask = (
                normalized_values.apply(lambda value: normalized_pattern_match(normalized_search, value))
                if normalized_search else pd.Series(False, index=filtered_df.index)
            )
            id_mask = raw_ids.str.contains(raw_search, case=False, na=False, regex=False)
        combined_search_mask |= pattern_mask | id_mask
    return filtered_df.loc[combined_search_mask].copy(), search_terms


def render_dataset_search(final_df):
    st.write("---")
    st.subheader("Search URL Patterns / IDs / Bases")
    st.write(
        "Select an admin to search their rows, or choose All Admins. "
        "Search URL patterns, pattern IDs, or bases in the same search box. "
        "Leave Search empty to list all rows for the selected admin."
    )
    if final_df.empty:
        st.warning("There is currently no shared dataset.")
        return
    options = get_admin_options(final_df)
    # Also handle another user's dataset replacement during this session.
    if st.session_state.get("database_admin_name") not in options:
        st.session_state.pop("database_admin_name", None)
    selected_admin = st.selectbox(
        "Admin name", options=options,
        format_func=lambda value: "All Admins" if value is None else ("No Admin Name" if value == "" else value),
        key="database_admin_name",
        help="Values come from the admin_name column in the active shared dataset.",
    )
    if not any(value not in (None, "") for value in options):
        st.info("Upload a workbook containing admin_name values to populate this dropdown.")
    search_mode = st.radio(
        "Search Mode", ["Exact Match", "Normalized Search"], horizontal=True,
        key="database_search_mode",
        help=("Exact Match accepts a complete URL pattern, pattern ID, or basis. "
              "Normalized Search ignores separators such as *, -, _, and /."),
    )
    search_string = st.text_area(
        "Search",
        placeholder="Examples:\n*example.com*bug*bite*\n1341291255\nbug*bite\nbug bite",
        key="main_search",
    )
    if not search_string.strip() and selected_admin is None:
        st.caption("Enter a search term or select an admin to view matching rows.")
        return
    search_results, search_terms = search_dataset(
        final_df, search_string, search_mode, selected_admin,
    )
    if search_results.empty:
        st.warning("No matching rows were found for the selected admin and search criteria.")
        return
    admin_label = "All Admins" if selected_admin is None else (selected_admin or "No Admin Name")
    st.success(
        f"Found {len(search_results):,} matching result(s) for {admin_label}."
        + (f" Search: {len(search_terms)} term(s), {search_mode}." if search_terms else "")
    )
    result_type = st.radio(
        "Search Result View", ["Original", "Domain - Basis Split"], horizontal=True, key="result_view",
    )
    filename_seed = f"{admin_label}_{search_string}" if selected_admin is not None else search_string
    filename_search = re.sub(r"[^a-zA-Z0-9]+", "_", filename_seed).strip("_") or "search_results"
    filename_search = filename_search[:50]
    if result_type == "Original":
        st.dataframe(search_results.fillna(""), use_container_width=True, hide_index=True)
        st.download_button(
            "Download Original Results", data=search_results.to_csv(index=False, encoding="utf-8"),
            file_name=f"{filename_search}_original.csv", mime="text/csv", use_container_width=True,
        )
    else:
        split_results = []
        promote_issues = 0
        for row in search_results.itertuples(index=False):
            domain, basis = split_domain_basis(row.url_pattern)
            domain,promote_issue = export_promote_domain(domain,row.admin_name)
            promote_issues += bool(promote_issue)
            split_results.append({
                "domain": domain, "basis": basis, "url_pattern_id": row.url_pattern_id,
                "priority": row.priority, "language_code": row.language_code,
                "admin_name": row.admin_name,
                "updated_admin_id": row.updated_admin_id,
            })
        split_df = pd.DataFrame(split_results)
        if promote_issues:
            st.warning(f"{promote_issues:,} promote row(s) have no unique setid in admin_name. Their domain is shown without an inferred suffix.")
        st.dataframe(split_df.fillna(""), use_container_width=True, hide_index=True)
        st.download_button(
            "Download Domain - Basis Results", data=split_df.to_csv(index=False, encoding="utf-8"),
            file_name=f"{filename_search}_domain_basis.csv", mime="text/csv", use_container_width=True,
        )


# =============================================================
# GLOBAL PATTERN DASHBOARD PAGE
# =============================================================
def global_pattern_dashboard_page():
    metadata = get_dataset_metadata()
    final_df = load_shared_dataset()
    st.subheader("Current Shared Dataset")
    if metadata is None:
        st.warning("No dataset has been uploaded yet.")
    else:
        info1, info2, info3, info4, info5 = st.columns(5)
        info1.metric("Total Patterns", f"{metadata['total_rows']:,}")
        info2.metric("Dataset Date", metadata["file_date"] or "Unknown")
        info3.metric("Last Updated", metadata["updated_at"])
        info4.metric("Updated By", metadata["updated_by"].title() if metadata.get("updated_by") else "Unknown")
        info5.metric("Source File", metadata["filename"])
    if st.session_state.get("admin_authenticated", False):
        render_dataset_update()
    render_pending_dataset()
    render_dataset_search(final_df)
    st.write("---")
    st.subheader("Complete Shared Dataset")
    if final_df.empty:
        st.info("No dataset is currently available.")
    else:
        stat1, stat2, stat3 = st.columns(3)
        lengths = final_df["url_pattern"].fillna("").astype(str).str.len()
        stat1.metric("Total Unique Rows", f"{len(final_df):,}")
        stat2.metric("Longest URL Pattern", f"{lengths.max()} characters")
        stat3.metric("Shortest URL Pattern", f"{lengths.min()} characters")
        filename_base = metadata["filename"].rsplit(".", 1)[0] if metadata else "shared_dataset"
        st.download_button(
            "Download Complete Shared Dataset", data=final_df.to_csv(index=False, encoding="utf-8"),
            file_name=f"{filename_base}_cleaned.csv", mime="text/csv", use_container_width=True,
        )
        st.dataframe(final_df.fillna(""), use_container_width=True, hide_index=True)
    st.write("---")
    st.caption("Shared URL Pattern Database • All users access the same active dataset.")


# =============================================================
# KEYWORD PERFORMANCE MAPPER
# =============================================================
MAPPER_BASIS_COLUMNS = ["domain", "basis", "no. of keywords", "language", "keyword contains hint"]
MAPPER_OUTPUT_COLUMNS = ["domain", "basis", "keyword", "language", "rank", "priority", "database status", "mapping status"]


def mapper_text(value):
    return "" if pd.isna(value) else str(value).strip()


def mapper_header(value):
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def mapper_words(value):
    # Keep accented and non-Latin letters; URL-decode and ignore separators.
    import unicodedata
    value = unicodedata.normalize("NFKC", unquote(mapper_text(value))).casefold()
    return re.findall(r"[^\W_]+", value, flags=re.UNICODE)


def mapper_basis_key(value):
    # Preserve wildcard order and exact-token locks for DATABASE identity.
    value = unquote(mapper_text(value)).replace("\\", "").casefold().strip()
    return re.sub(r"\s+", " ", value)


def mapper_domain_key(value):
    value = clean_generator_domain(mapper_text(value)).strip("*")
    return normalize_domain(value) if value else ""


def mapper_read_csv(uploaded):
    from io import BytesIO
    raw = uploaded.getvalue()
    error = None
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            # Comma is the default; sniff only a clearly tab/semicolon header.
            text = raw.decode(encoding)
            header = text.splitlines()[0] if text.splitlines() else ""
            separator = "\t" if "\t" in header and "," not in header else ";" if ";" in header and "," not in header else ","
            df = pd.read_csv(BytesIO(raw), encoding=encoding, sep=separator, dtype=str, keep_default_na=False)
            return df
        except (UnicodeError, ValueError, pd.errors.ParserError) as exc:
            error = exc
    raise ValueError(f"Unable to read CSV: {error}")


def mapper_find_column(df, aliases, required=True):
    matches = [col for col in df.columns if mapper_header(col) in {mapper_header(a) for a in aliases}]
    if len(matches) > 1:
        raise ValueError(f"Ambiguous columns for {aliases[0]}: {', '.join(map(str, matches))}.")
    if not matches:
        if required:
            raise ValueError(f"Missing column: {aliases[0]}.")
        return None
    return matches[0]


def mapper_metric_columns(df, metric):
    canonical = {"kwdl2r":"l2r", "kwdrpm":"rpm", "revenue":"revenue", "rpc":"rpc"}.get(metric, mapper_header(metric))
    aliases = {mapper_header(metric), "keyword" + mapper_header(metric)}
    aliases.update(prefix + canonical for prefix in ("", "kwd", "kwds", "keyword", "keywords"))
    matches = []
    for column in df.columns:
        name = mapper_header(column)
        # Export qualifiers describe the metric, rather than changing its name.
        while re.search(r"(?:audited|percentage|percent|pct)$", name):
            name = re.sub(r"(?:audited|percentage|percent|pct)$", "", name)
        if name in aliases:
            matches.append(column)
    return matches


def mapper_keyword_language(value):
    language = mapper_text(value).casefold()
    if language in {"", "null", "none", "nan", "n/a", "na", "<na>", "undefined", "not categorized", "not categorised"}:
        return "Not categorized"
    return language


def mapper_prepare_keywords(df, metric, default_language, metric_column=None):
    keyword_col = mapper_find_column(df, ["Keyword Term", "keyword", "keywords"])
    if metric_column is not None:
        if metric_column not in df.columns:
            raise ValueError(f"Selected metric column not found: {metric_column}.")
        metric_col = metric_column
    else:
        matches = mapper_metric_columns(df, metric)
        if not matches:
            raise ValueError(f"No {metric} column detected. Choose the metric column from the CSV dropdown.")
        if len(matches) > 1:
            raise ValueError(f"Multiple {metric} columns found. Choose the metric column from the CSV dropdown.")
        metric_col = matches[0]
    language_col = mapper_find_column(df, ["KBB Selected Language", "language", "language code", "lang"], required=False)
    cleaned = df[metric_col].astype(str).str.strip().str.replace(",", "", regex=False)
    cleaned = cleaned.str.replace(r"[$€£%\s]", "", regex=True)
    cleaned = cleaned.str.replace(r"^\((.*)\)$", r"-\1", regex=True)
    numbers = pd.to_numeric(cleaned, errors="coerce")
    invalid = numbers.isna() | numbers.isin([float("inf"), float("-inf")])
    if invalid.any():
        rows = ", ".join(str(i + 2) for i in range(len(df)) if invalid.iloc[i])
        raise ValueError(f"Missing or invalid {metric} values on CSV line(s): {rows[:400]}.")
    prepared = pd.DataFrame({
        "keyword": df[keyword_col].map(mapper_text), "metric": numbers,
        "language": df[language_col].map(mapper_keyword_language) if language_col else mapper_keyword_language(default_language),
    })
    prepared = prepared.loc[prepared["keyword"].ne("")].copy()
    prepared["identity"] = prepared["keyword"].str.casefold()
    # Repeated performance rows use the highest supplied metric, not a sum of RPM/rates.
    return prepared.sort_values("metric", ascending=False, kind="stable").drop_duplicates(
        ["language", "identity"], keep="first",
    ).reset_index(drop=True)


def mapper_prepare_bases(df):
    aliases = {
        "domain": ["domain"], "basis": ["basis"],
        "no. of keywords": ["no. of keywords", "number of keywords", "keyword count", "no keywords"],
        "language": ["language", "language code", "lang"],
        "keyword contains hint": ["keyword contains hint", "keyword contains hint ()", "hint"],
    }
    normalized = pd.DataFrame(index=df.index)
    for name, choices in aliases.items():
        col = mapper_find_column(df, choices, required=name not in {"domain", "keyword contains hint"})
        normalized[name] = df[col] if col else ""
    records, errors = [], []
    for position, row in enumerate(normalized.to_dict("records"), 1):
        if all(not mapper_text(value) for value in row.values()):
            continue
        basis, language = mapper_text(row["basis"]), mapper_text(row["language"]).lower()
        try:
            count = Decimal(mapper_text(row["no. of keywords"]))
            if not count.is_finite() or count != count.to_integral_value() or not 1 <= count <= 1000:
                raise ValueError()
        except (InvalidOperation, ValueError):
            errors.append(f"Row {position}: no. of keywords must be a whole number from 1 to 1000.")
            continue
        if not mapper_words(basis) or not language:
            errors.append(f"Row {position}: basis and language are required.")
            continue
        records.append({
            "domain": clean_generator_domain(mapper_text(row["domain"])), "basis": basis,
            "no. of keywords": int(count), "language": language,
            "keyword contains hint": mapper_text(row["keyword contains hint"]),
        })
    if errors:
        raise ValueError("\n".join(errors))
    if not records:
        raise ValueError("Add at least one basis row.")
    result = pd.DataFrame(records)
    identities = result.apply(lambda row: (
        mapper_domain_key(row["domain"]), mapper_basis_key(row["basis"]), row["language"],
    ), axis=1)
    if identities.duplicated().any():
        raise ValueError("Duplicate domain/basis/language rows found. Combine their keyword counts into one row.")
    if result["no. of keywords"].sum() > 50000:
        raise ValueError("Request at most 50,000 output rows per run.")
    return result


def mapper_requirements(basis):
    # '*' separates URL fragments; order does not affect keyword relevance.
    requirements = []
    for part in re.split(r"(~[^~]+~)", mapper_text(basis)):
        locked = part.startswith("~") and part.endswith("~")
        requirements.extend((word, locked) for word in mapper_words(part))
    return list(dict.fromkeys(requirements))


def mapper_token_match(term, word, locked=False):
    if term == word:
        return True
    if locked:
        return False
    if _coverage_word_forms(term) & _coverage_word_forms(word):
        return True
    # Truncated URL roots such as diabet/constipat, without substring matches inside words.
    return len(term) >= 5 and word.startswith(term)


def mapper_priority_lookup(database):
    lookup = {}
    for row in database.to_dict("records"):
        pattern = mapper_text(row.get("url_pattern"))
        if "*" in pattern.strip("*"):
            domain, basis = split_domain_basis(pattern)
        else:
            # Basis-only stored patterns have no domain.
            domain, basis = "", pattern.strip("*")
        key = (mapper_domain_key(domain), mapper_basis_key(basis), mapper_text(row.get("language_code")).lower())
        lookup.setdefault(key, set()).add(mapper_text(row.get("priority")))
    return lookup


def mapper_default_priority(domain, basis):
    if "promote" in domain.casefold():
        return 1000
    # One topic (including exact locks) is broad; a multi-term restriction is niche.
    return 10000 if len(set(mapper_words(basis))) <= 1 else 8000


def mapper_initialize_global_keyword_store(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS internal_pattern_keyword_training (
        pair_key TEXT PRIMARY KEY, domain TEXT NOT NULL, basis TEXT NOT NULL,
        keyword TEXT NOT NULL, language TEXT NOT NULL, source_pattern TEXT NOT NULL,
        source_filename TEXT NOT NULL, captured_at TEXT NOT NULL,
        source_admin_name TEXT
    )""")
    columns = {row[1] for row in conn.execute("PRAGMA table_info(internal_pattern_keyword_training)")}
    if "source_admin_name" not in columns:
        conn.execute("ALTER TABLE internal_pattern_keyword_training ADD COLUMN source_admin_name TEXT")


def mapper_unpack_pattern_keywords(value):
    import csv
    from html import unescape
    if isinstance(value, (list, tuple)):
        values = [keyword for part in value for keyword in mapper_unpack_pattern_keywords(part)]
    elif isinstance(value, dict):
        headers = {mapper_header(key): key for key in value}
        key = next((headers[name] for name in ("keyword", "keywordterm", "keywords", "patternkeywords") if name in headers), None)
        if key is None:
            raise ValueError("Unsupported pattern_keywords JSON object. Use keyword/Keyword Term/keywords fields or a JSON list of strings.")
        values = mapper_unpack_pattern_keywords(value[key])
    elif value is None or pd.isna(value):
        values = []
    else:
        text = unescape(str(value)).strip()
        if not text or text.casefold() in {"null", "none", "nan"}:
            return []
        if text.startswith(("[", "{")):
            try:
                parsed = json.loads(text)
            except (ValueError, TypeError):
                # Exported workbooks often contain Python-style lists with single
                # quotes. literal_eval handles literals without executing code.
                import ast
                try:
                    parsed = ast.literal_eval(text)
                except (ValueError, SyntaxError, TypeError, RecursionError):
                    parsed = None
                if parsed is None:
                    if text.startswith("[") and text.endswith("]"):
                        inner = text[1:-1].strip()
                        # Accept plain bracket-wrapped lists, but do not turn
                        # broken structured objects/quoted arrays into keywords.
                        if not inner:
                            return []
                        if inner.startswith(("{", "[", "\"", "'")):
                            raise ValueError("Malformed structured keyword list; skipped for training.")
                        text = inner
                    elif text.startswith("[") and "]" in text:
                        pass  # A literal keyword such as '[2026] Laptop Deals'.
                    else:
                        raise ValueError("Malformed structured keyword value; skipped for training.")
                else:
                    return mapper_unpack_pattern_keywords(parsed)
            else:
                return mapper_unpack_pattern_keywords(parsed)
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        values = []
        for segment in re.split(r"[\n\r;|\t]+", text):
            # CSV quoting preserves commas inside a keyword.
            values.extend(next(csv.reader([segment], skipinitialspace=True)))
    return list(dict.fromkeys(mapper_text(keyword) for keyword in values if mapper_text(keyword)))


def mapper_extract_global_keyword_rows(df):
    if "pattern_keywords" not in df.columns:
        return None  # No new keyword snapshot supplied; retain the previous store.
    if list(df.columns).count("pattern_keywords") > 1:
        raise ValueError("Duplicate pattern_keywords columns in the workbook.")
    rows, issues = {}, []
    for position, row in enumerate(df.to_dict("records"), 1):
        try:
            keywords = mapper_unpack_pattern_keywords(row.get("pattern_keywords"))
        except (ValueError, TypeError, RecursionError):
            issues.append(position)
            continue
        if not keywords:
            continue
        pattern = mapper_text(row.get("url_pattern"))
        language = mapper_text(row.get("language_code")).lower()
        if not pattern or not language:
            issues.append(position)
            continue
        if "*" in pattern.strip("*"):
            domain, basis = split_domain_basis(pattern)
        else:
            domain, basis = "", pattern.strip("*")
        if not mapper_words(basis):
            continue  # Domain-only patterns do not establish a topic relationship.
        for keyword in keywords:
            source_admin = mapper_text(row.get("admin_name"))
            identity = [pattern.replace("\\*", "*").strip().casefold(),language,keyword.casefold(),source_admin.casefold()]
            key = hashlib.sha256(json.dumps(identity,ensure_ascii=False).encode("utf-8")).hexdigest()
            rows[key] = {"pair_key": key, "domain": domain, "basis": basis,
                         "keyword": keyword, "language": language, "source_pattern": pattern,
                         "source_admin_name": source_admin}
    df.attrs["_pattern_keyword_skipped_rows"] = issues
    return list(rows.values())


def mapper_store_global_keyword_rows(conn, rows, filename):
    mapper_initialize_global_keyword_store(conn)
    if rows is None:
        return
    # Update this private snapshot atomically with the accepted shared dataset.
    conn.execute("DELETE FROM internal_pattern_keyword_training")
    timestamp = datetime.now().isoformat(timespec="microseconds")
    conn.executemany("""INSERT INTO internal_pattern_keyword_training
        (pair_key, domain, basis, keyword, language, source_pattern, source_filename, captured_at, source_admin_name)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""", [
        (row["pair_key"], row["domain"], row["basis"], row["keyword"], row["language"],
         row["source_pattern"], filename, timestamp, row.get("source_admin_name")) for row in rows
    ])
    mapper_queue_model(conn, rows)


def mapper_pair_key(domain, basis, language, keyword):
    identity = [mapper_domain_key(domain), mapper_basis_key(basis),
                mapper_text(language).lower(), mapper_text(keyword).casefold()]
    return hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode("utf-8")).hexdigest()


# =============================================================
# AUTOMATIC SHARED-DATA MODEL
# =============================================================
MAPPER_MODEL_VERSION = "shared-topic-ngram-v2"


def mapper_model_schema(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS automatic_keyword_model (
        id INTEGER PRIMARY KEY CHECK(id=1), fingerprint TEXT NOT NULL,
        status TEXT NOT NULL, model_path TEXT NOT NULL DEFAULT '',
        trained_at TEXT NOT NULL DEFAULT '', error TEXT NOT NULL DEFAULT ''
    )""")


def mapper_model_fingerprint(rows):
    values = sorted((row["pair_key"], row["basis"], row["keyword"], row["language"]) for row in rows)
    payload = json.dumps([MAPPER_MODEL_VERSION, values], ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def mapper_queue_model(conn, rows):
    mapper_model_schema(conn)
    fingerprint = mapper_model_fingerprint(rows)
    status = "pending" if rows else "empty"
    conn.execute("""INSERT INTO automatic_keyword_model(id,fingerprint,status) VALUES (1,?,?)
        ON CONFLICT(id) DO UPDATE SET
        status=CASE WHEN automatic_keyword_model.fingerprint=excluded.fingerprint
                    AND automatic_keyword_model.status='ready' THEN 'ready' ELSE excluded.status END,
        model_path=CASE WHEN excluded.status='empty' THEN '' ELSE automatic_keyword_model.model_path END,
        fingerprint=excluded.fingerprint, error=''""", (fingerprint, status))


def mapper_model_status():
    with get_connection() as conn:
        mapper_model_schema(conn)
        row = conn.execute("SELECT fingerprint,status,model_path,trained_at,error FROM automatic_keyword_model WHERE id=1").fetchone()
    return dict(zip(["fingerprint","status","model_path","trained_at","error"], row)) if row else None


def mapper_encode(model, texts):
    from sklearn.preprocessing import normalize
    matrix = model["vectorizer"].transform(texts)
    if model["reducer"] is not None:
        matrix = model["reducer"].transform(matrix)
    return normalize(matrix)


def mapper_phrase_evidence(words, phrase):
    target = mapper_words(phrase)
    return bool(target) and any(
        all(bool(_coverage_word_forms(a) & _coverage_word_forms(b)) for a,b in zip(words[start:start+len(target)],target))
        for start in range(len(words)-len(target)+1)
    )


def mapper_topic_evidence(basis, keyword, language):
    """Independent topic constraints; a learned association alone is insufficient.

    Known topic aliases permit related wording. Unknown topics use conservative
    token evidence; the learned model cannot override this gate.
    """
    terms = mapper_words(basis)
    words = mapper_words(keyword)
    if not terms or not words:
        return False
    locks = [term for term, locked in mapper_requirements(basis) if locked]
    if not all(term in words for term in locks):
        return False
    # Longest family first prevents a narrow heart-attack basis from becoming
    # the broad cardiovascular topic. Generic disease labels are not aliases.
    families = [
        (["heart attack","myocardial infarction"], ["heart attack","myocardial infarction"]),
        (["heart failure","cardiac failure"], ["heart failure","cardiac failure"]),
        (["heart health","cardiovascular health","cardiac health","herzgesundheit","santé cardiaque","sante cardiaque","salud del corazón","saúde do coração"],
         ["heart health","heart healthy","cardiac","cardiovascular","coronary","cholesterol","blood pressure","hypertension",
          "herzgesundheit","kardiovaskulär","kardiovaskular","cholesterin","blutdruck",
          "cardiaque","cardiovasculaire","cholestérol","cholesterol","tension artérielle",
          "cardiovascular","colesterol","presión arterial","pressão arterial"]),
        (["blood pressure","hypertension","blutdruck","tension artérielle","presión arterial","pressão arterial"],
         ["blood pressure","hypertension","hypotension","blutdruck","tension artérielle","presión arterial","pressão arterial"]),
        (["myelodysplastic syndrome","myelodysplastic","myelodysplasia","mds"],
         ["myelodysplastic","myelodysplasia","mds"]),
        (["pulmonary fibrosis","idiopathic pulmonary fibrosis","ipf"],
         ["pulmonary fibrosis","lung fibrosis","ipf"]),
        (["personal loan","personal loans"], ["personal loan","personal loans","consumer loan"]),
        (["agricultural drone","agricultural drones","farm drones"],
         ["agricultural drone","agricultural drones","farm drone","farm drones","farming drone","crop drone","precision farming drone"]),
    ]
    basis_words = " ".join(terms)
    matches = []
    for canonical, aliases in families:
        for name in canonical:
            needle = mapper_words(name)
            # Canonical phrases may span wildcard separators in a basis.
            for start in range(len(terms)-len(needle)+1):
                if all(bool(_coverage_word_forms(a)&_coverage_word_forms(b)) for a,b in zip(terms[start:start+len(needle)],needle)):
                    matches.append((len(needle),start,needle,aliases,name))
    if matches:
        _,start,needle,aliases,name = max(matches,key=lambda item:item[0])
        topic_ok = any(mapper_phrase_evidence(words, alias) for alias in aliases)
        if not topic_ok and "health" in needle and any(term in needle for term in ("heart","cardiac","cardiovascular")):
            # "Heart" alone can refer to jewelry, romance, etc. Require an
            # additional clinical/context word rather than a substring match.
            health_words = {"screening","checkup","checkups","care","disease","diseases","treatment","treatments",
                            "symptom","symptoms","monitor","monitoring","surgery","clinic","doctor",
                            "condition","conditions","risk","risks","failure","attack","specialist","specialists"}
            topic_ok = "heart" in words and bool(set(words)&health_words)
        if not topic_ok:
            return False
        remaining = terms[:start]+terms[start+len(needle):]
    else:
        remaining = terms
    ignored = {"health","syndrome","disease","condition","the","a","an","and","of","for","to","in","on"}
    anchors = [term for term in remaining if term not in ignored]
    if not matches and not anchors:
        # A basis consisting solely of broad generic wording is not sufficient
        # evidence for transferring arbitrary learned keyword relationships.
        return all(any(mapper_token_match(term, word) for word in words) for term in terms)
    return all(any(mapper_token_match(term, word) for word in words) for term in anchors)


def mapper_fit_shared_model(rows):
    """Fit topic vectors and conditional trigram distributions to positive mappings.

    No fabricated negative labels or user annotations are required.
    """
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.decomposition import TruncatedSVD
    from sklearn.preprocessing import normalize
    groups = {}
    accepted_rows = 0
    for row in rows:
        if not mapper_topic_evidence(row["basis"],row["keyword"],row["language"]):
            continue
        accepted_rows += 1
        key = (row["language"], tuple(mapper_words(row["basis"])))
        group = groups.setdefault(key, {"basis": row["basis"], "language": row["language"], "keywords": {}})
        group["keywords"].setdefault(row["keyword"].casefold(), row["keyword"])
    topics = []
    for group in groups.values():
        keywords = list(group["keywords"].values())
        document = " ".join([" ".join(mapper_words(group["basis"]))] + keywords)
        transitions = {}
        for keyword in keywords:
            words = keyword.split()
            history = ("<START>", "<START>")
            for word in words + ["<END>"]:
                bucket = transitions.setdefault(history, {})
                bucket[word] = bucket.get(word, 0) + 1
                history = (history[1], word)
        topics.append({"basis": group["basis"], "language": group["language"],
                       "keywords": keywords, "document": document, "transitions": transitions})
    if not topics:
        raise ValueError("No usable basis-keyword relationships were found in pattern_keywords.")
    vectorizer = TfidfVectorizer(ngram_range=(1,2), sublinear_tf=True, max_features=60000,
                                 token_pattern=r"(?u)\b\w+\b", strip_accents="unicode")
    documents = [topic["document"] for topic in topics]
    matrix = vectorizer.fit_transform(documents)
    reducer = None
    # Small corpora work directly in sparse TF-IDF space; larger corpora learn
    # latent topic associations with SVD. Neither path needs label-based splits.
    if matrix.shape[0] >= 8 and matrix.shape[1] >= 8:
        reducer = TruncatedSVD(n_components=min(128, matrix.shape[0]-1, matrix.shape[1]-1), random_state=42)
        matrix = reducer.fit_transform(matrix)
    model = {"version": MAPPER_MODEL_VERSION, "vectorizer": vectorizer, "reducer": reducer,
             "topics": topics, "topic_vectors": normalize(matrix), "pair_count": accepted_rows}
    model["basis_vectors"] = mapper_encode(model, [" ".join(mapper_words(topic["basis"])) for topic in topics])
    all_keywords, offsets = [], []
    for topic in topics:
        start = len(all_keywords)
        all_keywords.extend(topic["keywords"])
        offsets.append((start, len(all_keywords)))
    model["keyword_vectors"] = mapper_encode(model, all_keywords)
    model["keyword_offsets"] = offsets
    return model


@st.cache_resource(show_spinner=False, max_entries=3)
def mapper_load_auto_model(path):
    import joblib
    # Only load model files created by this app, never uploaded model payloads.
    return joblib.load(path)


def mapper_auto_model_cache_root():
    """Generated models belong in the host cache, outside the source repository."""
    from pathlib import Path
    override = os.environ.get("GLOBAL_PATTERN_MODEL_CACHE", "").strip()
    if override:
        cache_base = Path(override).expanduser()
    elif os.name == "nt":
        cache_base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")) / "GlobalPatternDatabase" / "Cache"
    else:
        cache_base = Path(os.environ.get("XDG_CACHE_HOME") or (Path.home() / ".cache")) / "global_pattern_database"
    # Different databases must not share training locks or cached model files.
    database_key = hashlib.sha256(str(Path(DB_FILE).resolve()).encode("utf-8")).hexdigest()[:16]
    return (cache_base / database_key / "automatic").resolve()


def mapper_ensure_auto_model():
    """Train changed data automatically; reuse an unchanged saved model."""
    from pathlib import Path
    import tempfile
    state = mapper_model_status()
    if state is None:
        with get_connection() as conn:
            mapper_initialize_global_keyword_store(conn)
            rows = pd.read_sql_query("SELECT * FROM internal_pattern_keyword_training", conn).to_dict("records")
            mapper_queue_model(conn, rows)
        state = mapper_model_status()
    if state["status"] == "empty":
        return None, "Upload and confirm a shared workbook containing pattern_keywords to train the model."
    model_root = mapper_auto_model_cache_root()
    saved_path = Path(state["model_path"]).resolve() if state["model_path"] else None
    if state["status"] == "ready" and saved_path is not None and saved_path.parent == model_root and saved_path.is_file():
        try:
            cached = mapper_load_auto_model(state["model_path"])
            if cached.get("version") == MAPPER_MODEL_VERSION:
                return cached, "Model ready: trained automatically from the shared workbook."
        except Exception:
            pass  # Rebuild a missing/incompatible cache from the private source.
    try:
        import joblib
        import sklearn
    except ImportError:
        message = "Automatic training requires scikit-learn. Install: python -m pip install scikit-learn"
        with get_connection() as conn:
            conn.execute("UPDATE automatic_keyword_model SET status='error',error=? WHERE id=1", (message,))
        return None, message
    try:
        model_root.mkdir(parents=True, exist_ok=True)
        lock = model_root / "training.lock"
        handle = lock.open("a+b")
    except OSError as exc:
        return None, f"Cannot write the model cache: {exc}. Set GLOBAL_PATTERN_MODEL_CACHE to a writable directory outside your project. Literal mapping remains available."
    # OS locks release automatically if the app exits, so a restart cannot
    # leave a permanent stale lock that requires manual cleanup.
    try:
        if os.name == "nt":
            import msvcrt
            if handle.seek(0, 2) == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None, "Shared-data training is already running. Mapping can use literal matches meanwhile."
    temporary_path = None
    try:
        with get_connection() as conn:
            mapper_initialize_global_keyword_store(conn)
            rows = pd.read_sql_query("SELECT * FROM internal_pattern_keyword_training ORDER BY pair_key", conn).to_dict("records")
        fingerprint = mapper_model_fingerprint(rows)
        if fingerprint != state["fingerprint"]:
            with get_connection() as conn:
                mapper_queue_model(conn,rows)
            state = mapper_model_status()
        if not rows:
            with get_connection() as conn:
                mapper_queue_model(conn, rows)
            return None, "No usable pattern_keywords relationships are available for training."
        model = mapper_fit_shared_model(rows)
        path = model_root / (fingerprint + ".joblib")
        with tempfile.NamedTemporaryFile(dir=model_root, suffix=".joblib", delete=False) as temp:
            temporary_path = Path(temp.name)
        joblib.dump(model, temporary_path, compress=3)
        os.replace(temporary_path, path)
        timestamp = datetime.now().isoformat(timespec="seconds")
        with get_connection() as conn:
            mapper_model_schema(conn)
            # A concurrent upload must not be overwritten by an older training run.
            updated = conn.execute("""UPDATE automatic_keyword_model SET status='ready',
                model_path=?, trained_at=?, error='' WHERE id=1 AND fingerprint=?""",
                (str(path), timestamp, fingerprint)).rowcount
        if not updated:
            return None, "The shared workbook changed during training. Click Map Keywords again to use the latest data."
        return mapper_load_auto_model(str(path)), "Model ready: trained automatically from the shared workbook."
    except Exception as exc:
        message = f"Automatic training could not finish: {type(exc).__name__}: {str(exc)[:250]}"
        with get_connection() as conn:
            mapper_model_schema(conn)
            conn.execute("UPDATE automatic_keyword_model SET status='error',error=? WHERE id=1 AND fingerprint=?", (message, state["fingerprint"]))
        return None, message + " Literal mapping remains available."
    finally:
        if os.name == "nt":
            import msvcrt
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def mapper_topic_context(model, basis, language):
    import numpy as np
    from sklearn.metrics.pairwise import cosine_similarity
    query = mapper_encode(model, [" ".join(mapper_words(basis))])
    ids = [i for i, topic in enumerate(model["topics"]) if topic["language"] == language]
    exact = [i for i in ids if mapper_words(model["topics"][i]["basis"]) == mapper_words(basis)]
    if exact:
        return query, [(i, 1.0) for i in exact]
    if not ids:
        return query, []
    basis_scores = cosine_similarity(query, model["basis_vectors"][ids]).ravel()
    topic_scores = cosine_similarity(query, model["topic_vectors"][ids]).ravel()
    scores = np.maximum(basis_scores, topic_scores)
    ranked = sorted(zip(ids, scores), key=lambda pair: pair[1], reverse=True)
    return query, [(i, float(score)) for i, score in ranked[:3] if score >= .35]


def mapper_relationship_scores(model, basis, language, texts):
    import numpy as np
    from sklearn.metrics.pairwise import cosine_similarity
    if not texts:
        return []
    query, context = mapper_topic_context(model, basis, language)
    values = mapper_encode(model, texts)
    scores = cosine_similarity(values, query).ravel()
    # Compare to keywords learned for relevant topics, so "heart health" can
    # match cholesterol wording when that association appears in the workbook.
    for topic_id, relevance in context:
        start, end = model["keyword_offsets"][topic_id]
        for left in range(0, len(texts), 256):
            right = min(left+256, len(texts))
            maxima = np.zeros(right-left)
            for seed_start in range(start, end, 256):
                seed_end = min(seed_start+256, end)
                similarities = cosine_similarity(values[left:right], model["keyword_vectors"][seed_start:seed_end])
                maxima = np.maximum(maxima, similarities.max(axis=1))
            scores[left:right] = np.maximum(scores[left:right], maxima * relevance)
    return np.clip(scores, 0, 1).tolist()


def mapper_generate_suggestions(model, basis, language, count, excluded, threshold):
    import random
    if model is None or count <= 0:
        return []
    _, context = mapper_topic_context(model, basis, language)
    if not context:
        return []
    seed = int(hashlib.sha256((basis + language).encode()).hexdigest()[:16], 16)
    rng = random.Random(seed)
    candidates = {}
    # Learned phrases provide complete fallback suggestions, including when
    # generation reproduces an existing phrase from the private training data.
    for topic_id, relevance in context:
        for keyword in model["topics"][topic_id]["keywords"]:
            candidates.setdefault(keyword.casefold(), keyword)
    # Conditional trigrams can create new combinations of learned wording.
    for attempt in range(min(2000, max(100, count*30))):
        topic_id = rng.choices([pair[0] for pair in context], weights=[pair[1] for pair in context])[0]
        transitions = model["topics"][topic_id]["transitions"]
        history, words = ("<START>", "<START>"), []
        for step in range(15):
            bucket = transitions.get(history)
            if not bucket:
                break
            word = rng.choices(list(bucket), weights=list(bucket.values()))[0]
            if word == "<END>":
                keyword = " ".join(words)
                candidates.setdefault(keyword.casefold(), keyword)
                break
            words.append(word)
            history = (history[1], word)
    locks = [term for term, locked in mapper_requirements(basis) if locked]
    endings = {"for","of","to","with","and","or","at","on","in","the","a","an"}
    usable = [keyword for identity, keyword in candidates.items()
              if identity not in excluded and 3 <= len(mapper_words(keyword)) <= 12
              and len(keyword) <= 42 and mapper_words(keyword)[-1] not in endings
              and all(term in mapper_words(keyword) for term in locks)
              and mapper_topic_evidence(basis,keyword,language)]
    scores = mapper_relationship_scores(model, basis, language, usable)
    ranked = sorted(zip(usable, scores), key=lambda pair: (-pair[1], pair[0].casefold()))
    suggestions = []
    for keyword, score in ranked:
        if score < threshold:
            continue
        suggestions.append(keyword)
        if len(suggestions) >= count:
            break
    return suggestions


def mapper_generate(keywords, bases, database, model=None, threshold=.35):
    lookup = mapper_priority_lookup(database)
    output = []
    for row in bases.to_dict("records"):
        domain, basis, language = row["domain"], row["basis"], row["language"]
        existing = lookup.get((mapper_domain_key(domain), mapper_basis_key(basis), language))
        if existing is not None:
            if len(existing) != 1 or not next(iter(existing)):
                raise ValueError(f"Missing or conflicting database priority: {domain} | {basis} | {language}.")
            try:
                numeric = Decimal(next(iter(existing)))
                if not numeric.is_finite() or numeric != numeric.to_integral_value():
                    raise ValueError()
                priority = int(numeric)
            except (InvalidOperation, ValueError):
                raise ValueError(f"Invalid database priority: {domain} | {basis}.")
        else:
            priority = mapper_default_priority(domain, basis)
        # Uncategorized performance keywords are eligible for every requested
        # language, while explicit language codes remain isolated. If the same
        # term appears in both pools, keep its highest metric and map it once.
        eligible = keywords["language"].isin([language, "Not categorized"])
        pool = keywords.loc[eligible].sort_values("metric", ascending=False, kind="stable").drop_duplicates("identity", keep="first").to_dict("records")
        texts = [record["keyword"] for record in pool]
        scores = mapper_relationship_scores(model, basis, language, texts) if model is not None else [0.0]*len(pool)
        requirements = mapper_requirements(basis)
        locks = [term for term, locked in requirements if locked]
        candidates = []
        for record, score in zip(pool, scores):
            words = mapper_words(record["keyword"])
            literal = all(any(mapper_token_match(term, word, locked) for word in words) for term, locked in requirements)
            if (literal or score >= threshold) and all(term in words for term in locks) and mapper_topic_evidence(basis,record["keyword"],language):
                candidates.append((record["keyword"], ""))
        if not candidates and row["keyword contains hint"]:
            hints = [mapper_words(part) for part in re.split(r"[;\n]+", row["keyword contains hint"]) if mapper_words(part)]
            for record in pool:
                words = mapper_words(record["keyword"])
                if mapper_topic_evidence(basis,record["keyword"],language) and all(term in words for term in locks) and any(any(words[start:start+len(hint)] == hint for start in range(len(words)-len(hint)+1)) for hint in hints):
                    candidates.append((record["keyword"], "mapped using hint"))
        selected = candidates[:row["no. of keywords"]]
        excluded = {keyword.casefold() for keyword, status in selected}
        # Suggestions are distinct from ALL performing CSV terms. Their source
        # is the trained shared-data model, never a copied low-relevance CSV term.
        excluded.update(record["identity"] for record in pool)
        needed = row["no. of keywords"] - len(selected)
        selected.extend((keyword, "MODEL GENERATION") for keyword in mapper_generate_suggestions(model, basis, language, needed, excluded, threshold))
        for slot in range(row["no. of keywords"]):
            keyword, status = selected[slot] if slot < len(selected) else ("", "system couldnt map")
            output.append({"domain":domain,"basis":basis,"keyword":keyword,"language":language,
                           "rank":1,"priority":priority,
                           "database status":"already present" if existing is not None else "",
                           "mapping status":status})
    return pd.DataFrame(output, columns=MAPPER_OUTPUT_COLUMNS)


def mapper_highlight(row):
    styles = [""]*len(row)
    if row["database status"] == "already present":
        styles[row.index.get_loc("database status")] = "background-color: #dbeafe; color: #1e3a8a"
    if row["mapping status"] == "MODEL GENERATION":
        for column in ("keyword", "mapping status"):
            styles[row.index.get_loc(column)] = "background-color: #ede9fe; color: #5b21b6; font-weight: bold"
    elif row["mapping status"] == "system couldnt map":
        for column in ("keyword", "mapping status"):
            styles[row.index.get_loc(column)] = "background-color: #fee2e2; color: #991b1b"
    elif row["mapping status"] == "mapped using hint":
        styles[row.index.get_loc("mapping status")] = "background-color: #fef3c7; color: #92400e"
    return styles


def keyword_mapper_page():
    st.header("Keyword Performance Mapper")
    st.write("Map performing keywords using the shared-data model. Fill remaining slots with flagged model suggestions.")
    state = mapper_model_status()
    if state and state["status"] == "ready":
        st.success("Shared-data model ready. No manual training or activation needed.")
    else:
        st.info("The model trains automatically after a shared workbook is confirmed, or on your first mapping run using previously captured data.")
    metric = st.selectbox("Performance Metric", ["kwdl2r","kwdrpm","revenue","rpc"], key="simple_mapper_metric")
    uploaded = st.file_uploader("Performing Keywords CSV", type=["csv"], key="simple_mapper_csv")
    performance_input, metric_column = None, None
    if uploaded is not None:
        try:
            performance_input = mapper_read_csv(uploaded)
            detected = mapper_metric_columns(performance_input, metric)
            options = detected + [column for column in performance_input.columns if column not in detected]
            csv_signature = hashlib.sha256(uploaded.getvalue()).hexdigest()[:12]
            metric_column = st.selectbox(
                "Select Metric Column", options, index=0 if detected else None,
                placeholder="Choose the column containing your selected metric",
                key=f"mapper_metric_column_{metric}_{csv_signature}",
                help="Detected header variations appear first. You can also select another column manually.",
            )
            if len(detected) > 1:
                st.caption("Multiple matching metric columns detected. Select the one you want to rank by.")
            elif not detected:
                st.caption("No standard metric header detected. Select the correct CSV column manually.")
        except ValueError as exc:
            st.error(str(exc))
    language = st.text_input("CSV Language (if neither KBB Selected Language nor language is present)", value="en", key="simple_mapper_language")
    st.caption("CSV columns: Keyword Term and your selected metric (Revenue, KWD RPM (audited), KWDL2R or RPC). Language: KBB Selected Language, or language. Blank/null language values become Not categorized and are eligible for every requested language. An empty CSV with these headers is allowed when you only want model suggestions.")
    method = st.radio("Basis Input", ["Manual Table","Upload CSV"], horizontal=True, key="simple_mapper_basis_method")
    if method == "Manual Table":
        basis_file = None
        bases_input = st.data_editor(pd.DataFrame([{**{col:"" for col in MAPPER_BASIS_COLUMNS},"no. of keywords":None}]),
            num_rows="dynamic", hide_index=True, use_container_width=True, key="simple_mapper_basis_editor",
            column_config={"domain":st.column_config.TextColumn("domain",help="Optional plain domain."),
                           "no. of keywords":st.column_config.NumberColumn("no. of keywords",min_value=1,max_value=1000,step=1),
                           "keyword contains hint":st.column_config.TextColumn("keyword contains hint",help="Optional fallback phrase; semicolons separate alternatives.")})
    else:
        basis_file = st.file_uploader("Basis CSV", type=["csv"], key="simple_mapper_basis_csv")
        bases_input = None
        st.caption("domain | basis | no. of keywords | language | keyword contains hint")
    threshold = .35
    with st.expander("Mapping Settings"):
        threshold = st.slider("Minimum Learned Relevance",0.0,1.0,.35,.01,key="simple_mapper_threshold")
        st.caption("Every CSV match, hint match and model suggestion must pass a separate topic check. Known topic aliases allow related wording; unknown topics use stricter term evidence. Higher values are stricter. Relevance scores are not confidence probabilities. The model learns associations present in your workbook; unseen relationships may be missed.")
        st.write("Relevant CSV keywords rank by the selected metric, highest first. Hints are used only when no relevant CSV keywords match. Any remaining slots use MODEL GENERATION suggestions; if no suitable suggestion exists, the slot stays blank.")
        st.write("New priorities: broad single-term basis = 10000; more specific multi-term basis = 8000; domain containing promote = 1000. An exact domain/basis/language already in the database retains its saved priority.")
        st.caption("Model suggestions can reuse learned phrases or combine learned wording. Review them before use. CSV status columns preserve the flags; colors appear in the preview.")
    if st.button("Map Keywords",type="primary",use_container_width=True,key="simple_mapper_run"):
        st.session_state.pop("simple_mapper_result",None)
        if uploaded is None or (method=="Upload CSV" and basis_file is None):
            st.warning("Upload the performing CSV and provide the basis inputs.")
        else:
            try:
                if performance_input is None or metric_column is None:
                    raise ValueError("Choose a valid metric column from the performing CSV.")
                keywords = mapper_prepare_keywords(performance_input,metric,language,metric_column)
                bases = mapper_prepare_bases(mapper_read_csv(basis_file) if basis_file else bases_input)
                with st.spinner("Learning from shared data and mapping keywords..."):
                    model, message = mapper_ensure_auto_model()
                    result = mapper_generate(keywords,bases,load_shared_dataset(),model,threshold)
                st.session_state["simple_mapper_result"] = result
                st.session_state["simple_mapper_message"] = message
                st.session_state["simple_mapper_model_ready"] = model is not None
            except ValueError as exc:
                st.error(str(exc))
    if "simple_mapper_result" not in st.session_state:
        return
    result = st.session_state["simple_mapper_result"]
    if not st.session_state.get("simple_mapper_model_ready"):
        st.warning(st.session_state.get("simple_mapper_message","Model unavailable."))
    mapped = int((result["keyword"].ne("") & result["mapping status"].ne("MODEL GENERATION")).sum())
    generated = int(result["mapping status"].eq("MODEL GENERATION").sum())
    blank = int(result["keyword"].eq("").sum())
    st.success(f"CSV mapped: {mapped:,} | MODEL GENERATION: {generated:,} | Unfilled: {blank:,}")
    if generated:
        st.info("Purple MODEL GENERATION rows are suggestions from the learned workbook model. Review them before using the CSV.")
    st.caption("These are results from your last run. Click Map Keywords after changing inputs.")
    st.dataframe(result.style.apply(mapper_highlight,axis=1),hide_index=True,use_container_width=True)
    st.download_button("Download Mapped Keywords CSV",result.to_csv(index=False).encode("utf-8-sig"),
        "mapped_keywords.csv","text/csv",use_container_width=True,key="simple_mapper_download")


# =============================================================
# EXISTING PAIR PERFORMANCE CHECK
# =============================================================
def export_promote_domain(domain, admin_name):
    if not re.search(r"\.promote(?:\.|$)", mapper_text(domain), flags=re.IGNORECASE):
        return domain, ""
    ids = list(dict.fromkeys(re.findall(
        r"\bset[\s_-]*id\s*[:=]\s*(\d+)\b", mapper_text(admin_name), flags=re.IGNORECASE,
    )))
    if len(ids) == 1:
        prefix = re.split(r"(?<=\.promote)\.", domain, maxsplit=1, flags=re.IGNORECASE)[0]
        return f"{prefix}.{ids[0]}.setid", ""
    reason = "Missing setid in admin_name" if not ids else "Conflicting setid values in admin_name"
    return domain, reason


def audit_text_key(value):
    return re.sub(r"\s+", " ", mapper_text(value)).casefold()


def audit_pattern_key(value):
    return audit_text_key(value).replace("\\*", "*")


def audit_count_values(series, name):
    cleaned = series.map(mapper_text).str.replace(",", "", regex=False).str.replace(r"\s+", "", regex=True)
    counts = pd.to_numeric(cleaned, errors="coerce")
    invalid = counts.isna() | counts.isin([float("inf"),float("-inf")]) | counts.lt(0) | counts.mod(1).ne(0)
    if invalid.any():
        rows = ", ".join(str(i+2) for i in range(len(series)) if invalid.iloc[i])
        raise ValueError(f"{name} must contain nonnegative whole numbers. Check CSV line(s): {rows[:300]}.")
    return counts


def remove_pair_report_total_rows(frame, basis_column, keyword_column):
    from html import unescape
    def report_label(value):
        text = unescape(mapper_text(value)).casefold()
        text = re.sub(r"<br\s*/?>", " ", text)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return re.sub(r"url\s*\(", "url (", text)
    excluded = {"grand total", "report total", "stripped url (others)",
                "report total stripped url (others)", "grand total stripped url (others)"}
    checked = [basis_column, keyword_column]
    checked.extend(column for column in frame.columns if mapper_header(column) == "url")
    mask = pd.Series(False,index=frame.index)
    for column in dict.fromkeys(checked):
        mask |= frame[column].map(report_label).isin(excluded)
    return frame.loc[~mask].copy(), int(mask.sum())


def prepare_pair_performance_csv(frame):
    audited_columns = [col for col in frame.columns if mapper_header(col) == mapper_header("KWD RPM (audited)")]
    rpm_columns = audited_columns or mapper_metric_columns(frame,"kwdrpm")
    if len(rpm_columns) != 1:
        raise ValueError("Provide one KWD RPM (audited) column for the performance check.")
    columns = {
        "basis": mapper_find_column(frame,["Basis Name","basis"]),
        "keyword": mapper_find_column(frame,["Keyword Term","keyword"]),
        "impressions": mapper_find_column(frame,["Keyword Impressions"]),
        "clicks": mapper_find_column(frame,["Keyword Clicks","KWD Clicks"]),
        "rpm": rpm_columns[0],
    }
    frame, excluded_rows = remove_pair_report_total_rows(frame,columns["basis"],columns["keyword"])
    # Keep only the input fields used by this check; other report columns
    # cannot enter pair aggregation or the output CSV.
    result = pd.DataFrame({name: frame[col].map(mapper_text) for name,col in columns.items()})
    result = result.loc[~result.eq("").all(axis=1)].copy().reset_index(drop=True)
    if result["basis"].eq("").any() or result["keyword"].eq("").any():
        raise ValueError("Every performance row needs Basis Name and Keyword Term.")
    result["impressions"] = audit_count_values(result["impressions"],"Keyword Impressions")
    result["clicks"] = audit_count_values(result["clicks"],"Keyword Clicks")
    cleaned_rpm = result["rpm"].str.replace(",","",regex=False).str.replace(r"[$€£\s]","",regex=True)
    result["rpm"] = pd.to_numeric(cleaned_rpm,errors="coerce")
    invalid_rpm = result["rpm"].isna() | result["rpm"].isin([float("inf"),float("-inf")]) | result["rpm"].lt(0)
    if invalid_rpm.any():
        raise ValueError("KWD RPM (audited) must contain finite, nonnegative numeric values for every performance row.")
    result["basis_key"] = result["basis"].map(audit_pattern_key)
    result["keyword_key"] = result["keyword"].map(audit_text_key)
    result.attrs["excluded_report_rows"] = excluded_rows
    return result


def build_existing_pair_export(performance, patterns, keyword_rows):
    """Exact stored mappings only. No semantic matching or keyword generation."""
    output_columns = ["domain","basis","keyword","language"]
    if performance.empty:
        return pd.DataFrame(columns=output_columns), {"pairs":0,"base_qualified":0,"qualified":0,"matched":0}, []
    performance = performance.assign(rpm_weighted=performance["rpm"] * performance["impressions"])
    totals = performance.groupby(["basis_key","keyword_key"],as_index=False,sort=False).agg(
        impressions=("impressions","sum"), clicks=("clicks","sum"), basis=("basis","first"), keyword=("keyword","first"),
        rpm_weighted=("rpm_weighted","sum"),
    )
    eligible = totals.loc[totals["impressions"].ge(1000) & totals["clicks"].ge(5)].copy()
    # Consolidate repeated pair rates by impressions, then average distinct
    # eligible pairs equally within each basis before checking stored mappings.
    eligible["rpm"] = eligible["rpm_weighted"] / eligible["impressions"]
    eligible["basis_average_rpm"] = eligible.groupby("basis_key")["rpm"].transform("mean")
    qualifying = eligible.loc[eligible["rpm"].lt(eligible["basis_average_rpm"])]
    # The private keyword snapshot can outlive an upload without keyword data.
    # Only relationships whose exact source pattern/language are still live count.
    live = {}
    for row in patterns.to_dict("records"):
        pattern = mapper_text(row.get("url_pattern"))
        language = mapper_text(row.get("language_code")).lower()
        live.setdefault((audit_pattern_key(pattern),language),[]).append(row)
    index = {}
    for row in keyword_rows.to_dict("records"):
        pattern = mapper_text(row["source_pattern"])
        language = mapper_text(row["language"]).lower()
        source_matches = live.get((audit_pattern_key(pattern),language),[])
        source_admin = row.get("source_admin_name")
        if source_admin is not None and not pd.isna(source_admin):
            source_matches = [source for source in source_matches if audit_text_key(source.get("admin_name")) == audit_text_key(source_admin)]
        elif ".promote" in pattern.casefold() and len({audit_text_key(source.get("admin_name")) for source in source_matches}) > 1:
            # Older snapshots did not retain row-specific admin provenance.
            # Never attribute a keyword to an arbitrary set ID in that case.
            source_matches = [dict(source_matches[0],admin_name="")]
        if not source_matches:
            continue
        domain,basis = split_domain_basis(pattern)
        keys = {audit_pattern_key(basis),audit_pattern_key(pattern),audit_pattern_key(domain+"*"+basis)}
        for basis_key in keys:
            index.setdefault((basis_key,audit_text_key(row["keyword"])),[]).extend(
                (domain,basis,row["keyword"],language,source) for source in source_matches
            )
    rows,issues,seen,seen_issues = [],[],set(),set()
    matched = 0
    for row in qualifying.to_dict("records"):
        matches = index.get((row["basis_key"],row["keyword_key"]),[])
        if matches:
            matched += 1
        for domain,basis,keyword,language,source in matches:
            decorated,issue = export_promote_domain(domain,source.get("admin_name"))
            if issue:
                issue_key=(source["url_pattern"],language,issue)
                if issue_key not in seen_issues:
                    issues.append({"url_pattern":source["url_pattern"],"language":language,"reason":issue})
                    seen_issues.add(issue_key)
                continue  # Do not invent a promote set ID in the output.
            key = (decorated,basis,audit_text_key(keyword),language)
            if key not in seen:
                rows.append(dict(domain=decorated,basis=basis,keyword=keyword,language=mapper_text(source.get("language_code"))))
                seen.add(key)
    stats = {"pairs":len(totals),"base_qualified":len(eligible),"qualified":len(qualifying),"matched":matched}
    return pd.DataFrame(rows,columns=output_columns),stats,issues


def underperforming_pairs_page():
    st.header("Existing Keyword Performance Check")
    st.write("Find existing basis–keyword mappings with at least 1,000 keyword impressions and 5 keyword clicks whose audited RPM is below their basis average.")
    uploaded = st.file_uploader("Performance CSV Files",type=["csv"],accept_multiple_files=True,key="pair_check_files")
    st.caption("Supported columns: Basis Name, Keyword Term, Keyword Impressions, Revenue, KWD RPM (audited), RPC, Keyword Clicks, Ad Clicks. The check uses Basis Name, Keyword Term, Keyword Impressions, Keyword Clicks and KWD RPM (audited). Extra report columns are ignored. Grand Total, Report Total and Stripped URL (Others) rows are removed before checking.")
    st.caption("Basis Name may be the exact basis or full URL pattern. Duplicate pair rows across the uploaded files are summed before applying the thresholds. Keyword matching ignores case and repeated whitespace. Inner basis wildcards remain significant.")
    st.caption("Duplicate pair RPM is weighted by impressions. Each basis average is the simple mean RPM of its distinct pairs with at least 1,000 impressions and 5 clicks. Only pairs strictly below that average are checked against the shared database; equal RPM is excluded.")
    if st.button("Check Existing Pairs",type="primary",use_container_width=True,key="pair_check_run"):
        st.session_state.pop("pair_check_result",None)
        if not uploaded:
            st.warning("Upload at least one performance CSV.")
        else:
            try:
                with st.spinner("Reading CSV files and checking existing keyword pairs..."):
                    frames,seen_files = [],set()
                    excluded_rows = 0
                    for file in uploaded:
                        digest=hashlib.sha256(file.getvalue()).hexdigest()
                        if digest in seen_files:
                            continue
                        seen_files.add(digest)
                        try:
                            prepared = prepare_pair_performance_csv(mapper_read_csv(file))
                            excluded_rows += prepared.attrs.get("excluded_report_rows",0)
                            frames.append(prepared)
                        except ValueError as exc:
                            raise ValueError(f"{getattr(file,'name','CSV')}: {exc}") from exc
                    with get_connection() as conn:
                        mapper_initialize_global_keyword_store(conn)
                        keyword_rows=pd.read_sql_query("SELECT source_pattern,keyword,language,source_admin_name FROM internal_pattern_keyword_training",conn)
                        patterns=pd.read_sql_query("SELECT url_pattern,language_code,admin_name FROM url_patterns",conn)
                    if keyword_rows.empty:
                        raise ValueError("No stored pattern_keywords mappings are available. Re-upload and confirm the global workbook containing pattern_keywords first.")
                    result,stats,issues=build_existing_pair_export(pd.concat(frames,ignore_index=True),patterns,keyword_rows)
                    stats["excluded_rows"] = excluded_rows
                    st.session_state["pair_check_result"] = result
                    st.session_state["pair_check_stats"] = stats
                    st.session_state["pair_check_issues"] = issues
            except ValueError as exc:
                st.error(str(exc))
    if "pair_check_result" not in st.session_state:
        return
    result=st.session_state["pair_check_result"]
    stats=st.session_state["pair_check_stats"]
    st.success(f"Distinct CSV pairs: {stats['pairs']:,} | Minimums met: {stats.get('base_qualified',0):,} | Below basis average RPM: {stats['qualified']:,} | Existing qualified pairs: {stats['matched']:,} | Export rows: {len(result):,}")
    if stats.get("excluded_rows",0):
        st.caption(f"Removed {stats['excluded_rows']:,} report summary row(s): Grand Total, Report Total, or Stripped URL (Others).")
    issues=st.session_state.get("pair_check_issues",[])
    if issues:
        st.warning(f"{len(issues):,} promote pattern(s) could not be exported because admin_name has a missing or conflicting setid.")
        st.dataframe(pd.DataFrame(issues),hide_index=True,use_container_width=True)
    st.caption("Results reflect the last check. Click Check Existing Pairs again after changing files or the shared dataset.")
    st.dataframe(result,hide_index=True,use_container_width=True)
    st.download_button("Download Existing Below-Average RPM Pairs CSV",result.to_csv(index=False).encode("utf-8-sig"),
                       "existing_below_average_rpm_pairs.csv","text/csv",use_container_width=True,key="pair_check_download")


# =============================================================
# APPLICATION ACCESS GATE AND TOP NAVIGATION
# =============================================================
if not st.session_state.get("admin_authenticated", False):
    st.write(
        "Sign in with your username and password to access the dashboard, "
        "coverage reports, dataset search, downloads, and updates."
    )
    admin_login()
    st.stop()

render_user_header()
navigation = st.navigation(
    [
        st.Page(global_pattern_dashboard_page, title="Global Pattern Dashboard", icon=":material/dashboard:"),
        st.Page(coverage_report_page, title="Coverage Report", icon=":material/analytics:"),
        st.Page(concatenate_sheet_page, title="Concatenate Sheet", icon=":material/link:"),
        st.Page(keyword_mapper_page, title="Keyword Mapper", icon=":material/format_list_bulleted:"),
        st.Page(underperforming_pairs_page, title="Keyword Performance Check", icon=":material/fact_check:"),
    ],
    position="top",
)
navigation.run()
