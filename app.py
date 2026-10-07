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


def replace_shared_dataset(new_df, filename, file_date, updated_by):
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
        conn.commit()
    finally:
        conn.close()


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
    pattern = str(pattern).strip()
    if "*" not in pattern:
        return pattern, ""
    domain, basis = pattern.strip("*").split("*", 1)
    return domain.strip(), basis.strip("*").strip()


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
        "pending_admin_repairs",
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
                with st.spinner("Replacing shared dataset..."):
                    replace_shared_dataset(
                        pending_df, pending_filename,
                        date_validation["date_found"] if date_validation else None,
                        st.session_state.get("authenticated_username", "Unknown"),
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
        for row in search_results.itertuples(index=False):
            domain, basis = split_domain_basis(row.url_pattern)
            split_results.append({
                "domain": domain, "basis": basis, "url_pattern_id": row.url_pattern_id,
                "priority": row.priority, "language_code": row.language_code,
                "admin_name": row.admin_name,
                "updated_admin_id": row.updated_admin_id,
            })
        split_df = pd.DataFrame(split_results)
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
    ],
    position="top",
)
navigation.run()
