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


@st.cache_resource(show_spinner=False)
def _processing_lru_registry():
    from threading import RLock
    return {},RLock()


def processing_lru_cache(maxsize):
    """Keep bounded LRU wrappers alive across Streamlit script reruns."""
    def decorate(function):
        import marshal
        token = (maxsize,hashlib.sha256(marshal.dumps(function.__code__)).hexdigest())
        registry,lock = _processing_lru_registry()
        with lock:
            previous = registry.get(function.__name__)
            if previous is None or previous[0]!=token:
                previous = (token,lru_cache(maxsize=maxsize)(function))
                registry[function.__name__] = previous
            return previous[1]
    return decorate


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


@processing_lru_cache(maxsize=2)
def _database_revision_monitor(path, device, inode):
    from threading import RLock
    # PRAGMA data_version must use the same connection between checks. It
    # detects commits from other users/processes, including WAL-mode commits.
    return sqlite3.connect(path,check_same_thread=False),RLock()


def database_revision():
    path = os.path.abspath(os.fspath(DB_FILE))
    info = os.stat(path)
    connection,lock = _database_revision_monitor(path,info.st_dev,info.st_ino)
    with lock:
        cursor = connection.execute("PRAGMA data_version")
        try:
            version = cursor.fetchone()[0]
        finally:
            cursor.close()
    return (path,info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,version)


@processing_lru_cache(maxsize=1)
def _cached_performance_snapshot(revision):
    if database_revision()!=revision:
        raise ValueError("The shared dataset changed. Run the check again.")
    conn = sqlite3.connect(revision[0])
    try:
        initialize_keyword_store(conn)
        conn.commit()
        conn.execute("BEGIN")
        patterns = pd.read_sql_query("SELECT url_pattern, language_code, admin_name, priority FROM url_patterns",conn)
        keywords = pd.read_sql_query("SELECT source_pattern, keyword, language, source_admin_name FROM internal_pattern_keyword_training",conn)
        return patterns,keywords
    finally:
        conn.close()


def load_performance_snapshot():
    for attempt in range(3):
        revision = database_revision()
        try:
            patterns,keywords = _cached_performance_snapshot(revision)
        except ValueError:
            if database_revision()!=revision:
                continue
            raise
        if database_revision()==revision:
            # Internal callers treat these cached frames as read-only.
            return revision,patterns,keywords
    raise ValueError("The shared dataset is being updated. Run the check again when the update finishes.")


@processing_lru_cache(maxsize=1)
def _cached_performance_index(revision):
    patterns,keywords = _cached_performance_snapshot(revision)
    return performance_live_index(patterns,keywords)


@processing_lru_cache(maxsize=1)
def _cached_existing_basis_keywords(revision):
    return performance_existing_basis_keywords(_cached_performance_snapshot(revision)[1])


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
    for attempt in range(3):
        revision = database_revision()
        frame = _cached_shared_dataset(revision)
        if database_revision()==revision:
            return frame.copy(deep=True)
    raise ValueError("The shared dataset is being updated. Please retry.")


@processing_lru_cache(maxsize=1)
def _cached_shared_dataset(revision):
    conn = sqlite3.connect(revision[0])
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
        store_pattern_keyword_rows(conn, pattern_keyword_rows, filename)
        conn.commit()
        _cached_performance_snapshot.cache_clear()
        _cached_performance_index.cache_clear()
        _cached_existing_basis_keywords.cache_clear()
        _cached_shared_dataset.cache_clear()
    except Exception:
        conn.rollback()
        raise
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
    final_df.attrs["_internal_pattern_keyword_rows"] = extract_pattern_keyword_rows(df)
    final_df.attrs["_pattern_keyword_skipped_rows"] = df.attrs.get("_pattern_keyword_skipped_rows", [])
    return final_df, fixed_count, duplicates_removed


# =============================================================
# NORMALIZATION AND MATCHING
# =============================================================
def normalize_search_text(text):
    return _cached_normalize_search_text(str(text))


@processing_lru_cache(maxsize=32768)
def _cached_normalize_search_text(text):
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
    return _cached_split_domain_basis(str(pattern))


@processing_lru_cache(maxsize=32768)
def _cached_split_domain_basis(pattern):
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
    return _cached_normalize_domain(str(value))


@processing_lru_cache(maxsize=32768)
def _cached_normalize_domain(value):
    value = re.sub(r"^[~*.]+", "", unquote(str(value)).strip().lower())
    parsed = urlsplit(value if "://" in value else f"//{value}", scheme="https")
    hostname = (parsed.hostname or value.split("/")[0]).split(":")[0].strip(".")
    return hostname[4:] if hostname.startswith("www.") else hostname


def get_url_parts(url):
    return _cached_get_url_parts(str(url))


@processing_lru_cache(maxsize=16384)
def _cached_get_url_parts(url):
    raw_url = str(url).strip()
    parsed = urlsplit(raw_url if "://" in raw_url else f"https://{raw_url}")
    searchable_content = " ".join([parsed.path, parsed.query, parsed.fragment])
    return normalize_domain(parsed.hostname or ""), normalize_search_text(searchable_content)


def domains_match(url_domain, pattern_domain):
    return bool(url_domain and pattern_domain) and (
        url_domain == pattern_domain or url_domain.endswith(f".{pattern_domain}")
    )


def normalize_coverage_basis(basis):
    return _cached_normalize_coverage_basis(str(basis))


@processing_lru_cache(maxsize=32768)
def _cached_normalize_coverage_basis(basis):
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
def coverage_priority_value(value):
    """Lower numeric priorities catch first; missing/invalid values catch last."""
    try:
        number = Decimal(str(value).strip().replace(",", ""))
        return number if number.is_finite() and number >= 0 else Decimal("Infinity")
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("Infinity")


def coverage_first_priority(values):
    usable = [value for value in values if coverage_priority_value(value).is_finite()]
    return str(min(usable, key=coverage_priority_value)).strip() if usable else ""


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
        "url_pattern_id": join_unique, "priority": coverage_first_priority,
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
    return _cached_coverage_csv(uploaded_file.getvalue()).copy(deep=True)


@processing_lru_cache(maxsize=2)
def _cached_coverage_csv(raw):
    from io import BytesIO
    last_error = None
    for encoding in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            return pd.read_csv(BytesIO(raw), encoding=encoding, sep=None, engine="python")
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
@processing_lru_cache(maxsize=50000)
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


@processing_lru_cache(maxsize=4)
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


def create_coverage_report(input_df, basis_catalog, selected_languages=None):
    """Attribute each URL to its first matching basis in numeric priority order."""
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
    if basis_catalog.empty and not selected_languages:
        raise ValueError("Select at least one language with usable bases.")
    selected_languages = sorted(selected_languages or basis_catalog["language_code"].astype(str).unique().tolist())
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
    # Priority wins over specificity. Equal priorities prefer the longer basis,
    # then stable text/language/ID order, so exactly one winner is reproducible.
    match_order = sorted(range(len(records)), key=lambda i: (
        coverage_priority_value(records[i][5]), -len(str(records[i][0])),
        str(records[i][0]).casefold(), str(records[i][2]).casefold(),
        str(records[i][1]).casefold(), str(records[i][4]),
    ))
    order_rank = {basis_id:rank for rank,basis_id in enumerate(match_order)}
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
            matches = _coverage_match_ids(searchable_url, index)
            ids = [min(matches,key=order_rank.__getitem__)] if matches else []
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
    """Assign new bases their row's language and optional numeric priority."""
    if isinstance(selected_languages, str):
        selected_languages = [selected_languages]
    selected_languages = sorted(set(selected_languages))
    if (not selected_languages or basis_catalog.empty
            or not basis_catalog["language_code"].isin(selected_languages).all()):
        raise ValueError("Use the basis catalog for the report's selected languages.")
    if "Language Code" not in edited_rows.columns:
        raise ValueError("The new-basis table must include a Language Code column.")
    existing = set(zip(basis_catalog["language_code"], basis_catalog["normalized_basis"]))
    edited_rows = edited_rows.copy()
    if "Priority" not in edited_rows.columns:
        edited_rows["Priority"] = None
    added_rows = []
    added_positions = {}
    invalid = []
    for row_number, (value, language_value, priority_value) in enumerate(
        edited_rows[["New Basis", "Language Code", "Priority"]].itertuples(index=False, name=None), 1,
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
        priority = ""
        if pd.notna(priority_value) and str(priority_value).strip():
            numeric_priority = coverage_priority_value(priority_value)
            if not numeric_priority.is_finite() or numeric_priority != numeric_priority.to_integral_value():
                invalid.append(f"Row {row_number}: priority must be a nonnegative whole number, or left blank.")
                continue
            priority = str(int(numeric_priority))
        # Multiple bases in a cell all use the language and priority of that row.
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
            identity = (language, normalized)
            if identity in added_positions:
                previous = added_rows[added_positions[identity]]
                if coverage_priority_value(priority) < coverage_priority_value(previous["priority"]):
                    previous["priority"] = priority
                continue
            added_positions[identity] = len(added_rows)
            added_rows.append({
                "domain": "User Added", "normalized_domain": "",
                "basis": basis, "normalized_basis": normalized,
                "language_code": language,
                "url_pattern_id": f"user-added-{len(added_rows) + 1}",
                "priority": priority,
            })
    additions = pd.DataFrame(added_rows, columns=basis_catalog.columns)
    combined = pd.concat([basis_catalog, additions], ignore_index=True)
    combined = combined.sort_values(
        "normalized_basis", key=lambda values: values.str.len(), ascending=False,
        kind="stable",
    ).reset_index(drop=True)
    return combined, additions, invalid


def coverage_caught_basis_choices(report):
    """List winning basis/language pairs, without editing the shared catalog."""
    details = report[1]
    caught = details.loc[details["Coverage Status"].eq("Covered")].copy()
    columns = ["Exclude", "Basis", "Language Code", "Priority", "URLs Caught"]
    if caught.empty:
        return pd.DataFrame(columns=columns)
    result = caught.groupby(["Matching Basis", "Language Code"],as_index=False,sort=True).agg(
        **{"Priority":("Priority",coverage_first_priority), "URLs Caught":("URL","nunique")})
    result = result.rename(columns={"Matching Basis":"Basis"})
    result.insert(0,"Exclude",False)
    return result[columns]


def coverage_filter_caught_bases(choices, search):
    query = str(search or "").strip().casefold()
    if not query:
        return choices.copy()
    basis = choices["Basis"].fillna("").astype(str)
    mask = basis.str.casefold().str.contains(query,regex=False)
    terms = normalize_search_text(query).split()
    if terms:
        normalized = basis.map(normalize_search_text)
        words_match = pd.Series(True,index=choices.index)
        for term in terms:
            words_match &= normalized.str.contains(term,regex=False)
        mask |= words_match
    return choices.loc[mask].copy()


def coverage_merge_exclusion_choices(choices, edited_visible):
    result = choices.copy()
    key = lambda basis,language:(str(language).strip().lower(),normalize_coverage_basis(basis))
    updates = {key(row["Basis"],row["Language Code"]):bool(row["Exclude"])
               for row in edited_visible.to_dict("records")}
    result["Exclude"] = [updates.get(key(row["Basis"],row["Language Code"]),bool(row["Exclude"]))
                         for row in choices.to_dict("records")]
    return result


def coverage_exclude_bases(catalog, choices):
    excluded = {(str(language).strip().lower(), normalize_coverage_basis(basis))
                for exclude,basis,language in choices[["Exclude","Basis","Language Code"]].itertuples(index=False,name=None)
                if pd.notna(exclude) and bool(exclude)}
    keep = [(str(language).strip().lower(),str(basis)) not in excluded
            for language,basis in catalog[["language_code","normalized_basis"]].itertuples(index=False,name=None)]
    return catalog.loc[keep].copy(), sorted(excluded)


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
        "Download Priority URL Summary", data=url_summary_df.to_csv(index=False),
        file_name=f"{key_prefix}_priority_url_summary.csv", mime="text/csv",
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
                "Each URL's performance is attributed only to its selected basis. "
                "The lowest numeric priority wins; equal priorities prefer the longer basis."
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
    for key in list(st.session_state):
        if key.startswith(("coverage_excluded_basis_keys_", "coverage_exclusion_search_", "coverage_exclude_caught_editor_")):
            st.session_state.pop(key,None)
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
        "Each URL is counted once and assigned to one matching basis: lowest numeric priority first "
        "(1000 before 2000). Equal priorities prefer the longer basis, then stable alphabetical order. "
        "Blank or invalid priorities catch last. The summary shows the winning basis's language."
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
        ("priority-single-basis-v1\n" + basis_catalog.to_csv(index=False)).encode("utf-8")
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

    render_coverage_results(report, "Priority URL Summary — Existing Bases", "coverage_original")
    url_summary_df = report[0]
    uncovered = url_summary_df.loc[
        url_summary_df["Coverage Status"].eq("No Matching Basis"), ["URL"]
    ].reset_index(drop=True)
    st.write("---")
    st.subheader("Second Coverage Check")
    st.caption("Exclude caught bases to see which remaining basis catches next by priority. Exclusions apply only to this second report and to the listed language; the shared database and first report remain unchanged.")
    revision = st.session_state.get("coverage_report_revision", 0)
    caught_choices = coverage_caught_basis_choices(report)
    if not caught_choices.empty:
        selection_key = f"coverage_excluded_basis_keys_{revision}"
        selected = set(tuple(pair) for pair in st.session_state.get(selection_key,[]))
        caught_choices["Exclude"] = [(str(row["Language Code"]).lower(),normalize_coverage_basis(row["Basis"])) in selected
                                     for row in caught_choices.to_dict("records")]
        search = st.text_input("Search Caught Bases",placeholder="Example: heart health or blood*sugar",key=f"coverage_exclusion_search_{revision}")
        visible = coverage_filter_caught_bases(caught_choices,search)
        query_key = hashlib.sha256(str(search).encode()).hexdigest()[:12]
        excluded_choices = caught_choices
        if visible.empty:
            st.info("No caught bases match this search. Clear the search to show all bases.")
        else:
            edited_visible = st.data_editor(
                visible,hide_index=True,use_container_width=True,num_rows="fixed",
                disabled=["Basis","Language Code","Priority","URLs Caught"],
                key=f"coverage_exclude_caught_editor_{revision}_{query_key}",
                column_config={"Exclude":st.column_config.CheckboxColumn("Exclude",help="Skip this basis and language in the second coverage check.")},
            )
            excluded_choices = coverage_merge_exclusion_choices(caught_choices,edited_visible)
        st.session_state[selection_key] = [(str(row["Language Code"]).lower(),normalize_coverage_basis(row["Basis"]))
                                          for row in excluded_choices.to_dict("records") if row["Exclude"]]
        st.caption(f"Showing {len(visible):,} of {len(caught_choices):,} caught basis/language pairs. {int(excluded_choices['Exclude'].sum()):,} excluded in total, including selections outside this search.")
    else:
        excluded_choices = caught_choices
        st.caption("No caught bases to exclude in the first report.")
    if uncovered.empty:
        st.success("All submitted URLs have a matching basis. You can still exclude caught bases and run a second check.")
    else:
        st.subheader("Add Bases for URLs With No Matching Basis")
        st.write("Enter a new basis beside each URL, for example bug*bite. Separate multiple bases with semicolons. Choose its Language Code and Priority. The second report checks all original URLs against remaining existing bases and new bases using the same priority order: 1000 before 2000. Blank priorities catch last. Multiple bases in one row share its priority.")
        st.caption("New bases are used for this coverage check and do not update the shared dataset.")
    editor_input = uncovered.assign(**{
        "New Basis": "",
        "Language Code": selected_languages[0] if len(selected_languages) == 1 else "",
        "Priority": pd.Series(pd.NA,index=uncovered.index,dtype="Int64"),
    })
    if editor_input.empty:
        edited_rows = editor_input
    else:
        edited_rows = st.data_editor(
            editor_input, hide_index=True, use_container_width=True,
            num_rows="fixed", disabled=["URL"],
            key=f"coverage_new_basis_priority_editor_{revision}",
            column_config={
                "URL": st.column_config.TextColumn("No Matching Basis URL", width="large"),
                "New Basis": st.column_config.TextColumn("New Basis",width="large",help="Example: bug*bite; heart*health"),
                "Priority": st.column_config.NumberColumn("Priority",min_value=0,step=1,help="Optional. Lower numbers catch first, e.g. 1000 before 2000. Blank catches last."),
                "Language Code": st.column_config.SelectboxColumn(
                    "Language Code",options=[""]+list(selected_languages),width="small",
                    help="Choose one of the language codes selected at the top.",
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
    remaining_catalog, excluded_keys = coverage_exclude_bases(combined_catalog,excluded_choices)
    st.caption(f"{len(excluded_keys):,} caught basis/language pair(s) excluded from the second check.")
    additions_signature = (edited_rows[["URL", "New Basis", "Language Code", "Priority"]].to_csv(index=False)
                           + json.dumps(excluded_keys,ensure_ascii=False))
    if st.button(
        "Run Second Coverage Check", type="primary",
        use_container_width=True, disabled=(additions.empty and not excluded_keys) or bool(invalid),
        key="coverage_recheck_button",
    ):
        with st.spinner("Checking coverage with exclusions and new bases..."):
            st.session_state["coverage_recheck_report"] = create_coverage_report(
                st.session_state["coverage_report_input"], remaining_catalog, selected_languages=selected_languages,
            )
            st.session_state["coverage_recheck_signature"] = additions_signature
    revised_report = st.session_state.get("coverage_recheck_report")
    if revised_report is None:
        return
    if invalid or st.session_state.get("coverage_recheck_signature") != additions_signature:
        st.info("Exclusions, new bases, priorities or language entries changed. Run Second Coverage Check again to refresh the report.")
        return
    st.write("---")
    original_covered = int(url_summary_df["Coverage Status"].eq("Covered").sum())
    revised_covered = int(revised_report[0]["Coverage Status"].eq("Covered").sum())
    st.info(f"Covered URLs: {original_covered:,} in the first report; {revised_covered:,} in the second report. Excluded bases are skipped.")
    render_coverage_results(
        revised_report, "Priority URL Summary — Second Coverage Check", "coverage_rechecked",
    )
    st.download_button(
        "Download New Bases", data=additions[["basis", "language_code", "priority"]].to_csv(index=False),
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
            f"{len(skipped_keyword_rows):,} keyword cell(s) could not be stored for keyword matching "
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
                with st.spinner("Replacing shared dataset..."):
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
# KEYWORD STORAGE AND PERFORMANCE UTILITIES
# =============================================================
def keyword_text(value):
    return "" if pd.isna(value) else str(value).strip()


def keyword_header(value):
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def keyword_words(value):
    # Keep accented and non-Latin letters; URL-decode and ignore separators.
    import unicodedata
    value = unicodedata.normalize("NFKC", unquote(keyword_text(value))).casefold()
    return re.findall(r"[^\W_]+", value, flags=re.UNICODE)


def keyword_basis_key(value):
    # Preserve wildcard order and exact-token locks for DATABASE identity.
    value = unquote(keyword_text(value)).replace("\\", "").casefold().strip()
    return re.sub(r"\s+", " ", value)


def keyword_domain_key(value):
    value = clean_generator_domain(keyword_text(value)).strip("*")
    return normalize_domain(value) if value else ""


def read_keyword_csv(uploaded):
    return _cached_keyword_csv(uploaded.getvalue()).copy(deep=True)


@processing_lru_cache(maxsize=2)
def _cached_keyword_csv(raw):
    from io import BytesIO
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


@processing_lru_cache(maxsize=2)
def _cached_performance_csv(raw):
    return remove_pair_report_total_rows(_cached_keyword_csv(raw))


@processing_lru_cache(maxsize=2)
def _cached_upload_digest(raw):
    return hashlib.sha256(raw).hexdigest()[:16]


def keyword_priority_lookup(database):
    lookup = {}
    for row in database.to_dict("records"):
        pattern = keyword_text(row.get("url_pattern"))
        if "*" in pattern.strip("*"):
            domain, basis = split_domain_basis(pattern)
        else:
            # Basis-only stored patterns have no domain.
            domain, basis = "", pattern.strip("*")
        key = (keyword_domain_key(domain), keyword_basis_key(basis), keyword_text(row.get("language_code")).lower())
        lookup.setdefault(key, set()).add(keyword_text(row.get("priority")))
    return lookup


def keyword_default_priority(domain, basis):
    if "promote" in domain.casefold():
        return 1000
    # One topic (including exact locks) is broad; a multi-term restriction is niche.
    return 10000 if len(set(keyword_words(basis))) <= 1 else 8000


def initialize_keyword_store(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS internal_pattern_keyword_training (
        pair_key TEXT PRIMARY KEY, domain TEXT NOT NULL, basis TEXT NOT NULL,
        keyword TEXT NOT NULL, language TEXT NOT NULL, source_pattern TEXT NOT NULL,
        source_filename TEXT NOT NULL, captured_at TEXT NOT NULL,
        source_admin_name TEXT
    )""")
    columns = {row[1] for row in conn.execute("PRAGMA table_info(internal_pattern_keyword_training)")}
    if "source_admin_name" not in columns:
        conn.execute("ALTER TABLE internal_pattern_keyword_training ADD COLUMN source_admin_name TEXT")


def unpack_pattern_keywords(value):
    import csv
    from html import unescape
    if isinstance(value, (list, tuple)):
        values = [keyword for part in value for keyword in unpack_pattern_keywords(part)]
    elif isinstance(value, dict):
        headers = {keyword_header(key): key for key in value}
        key = next((headers[name] for name in ("keyword", "keywordterm", "keywords", "patternkeywords") if name in headers), None)
        if key is None:
            raise ValueError("Unsupported pattern_keywords JSON object. Use keyword/Keyword Term/keywords fields or a JSON list of strings.")
        values = unpack_pattern_keywords(value[key])
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
                            raise ValueError("Malformed structured keyword list; skipped for keyword matching.")
                        text = inner
                    elif text.startswith("[") and "]" in text:
                        pass  # A literal keyword such as '[2026] Laptop Deals'.
                    else:
                        raise ValueError("Malformed structured keyword value; skipped for keyword matching.")
                else:
                    return unpack_pattern_keywords(parsed)
            else:
                return unpack_pattern_keywords(parsed)
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        values = []
        for segment in re.split(r"[\n\r;|\t]+", text):
            # CSV quoting preserves commas inside a keyword.
            values.extend(next(csv.reader([segment], skipinitialspace=True)))
    return list(dict.fromkeys(keyword_text(keyword) for keyword in values if keyword_text(keyword)))


def extract_pattern_keyword_rows(df):
    if "pattern_keywords" not in df.columns:
        return None  # No new keyword snapshot supplied; retain the previous store.
    if list(df.columns).count("pattern_keywords") > 1:
        raise ValueError("Duplicate pattern_keywords columns in the workbook.")
    rows, issues = {}, []
    for position, row in enumerate(df.to_dict("records"), 1):
        try:
            keywords = unpack_pattern_keywords(row.get("pattern_keywords"))
        except (ValueError, TypeError, RecursionError):
            issues.append(position)
            continue
        if not keywords:
            continue
        pattern = keyword_text(row.get("url_pattern"))
        language = keyword_text(row.get("language_code")).lower()
        if not pattern or not language:
            issues.append(position)
            continue
        if "*" in pattern.strip("*"):
            domain, basis = split_domain_basis(pattern)
        else:
            domain, basis = "", pattern.strip("*")
        if not keyword_words(basis):
            continue  # Domain-only patterns do not establish a basis–keyword mapping.
        for keyword in keywords:
            source_admin = keyword_text(row.get("admin_name"))
            identity = [pattern.replace("\\*", "*").strip().casefold(),language,keyword.casefold(),source_admin.casefold()]
            key = hashlib.sha256(json.dumps(identity,ensure_ascii=False).encode("utf-8")).hexdigest()
            rows[key] = {"pair_key": key, "domain": domain, "basis": basis,
                         "keyword": keyword, "language": language, "source_pattern": pattern,
                         "source_admin_name": source_admin}
    df.attrs["_pattern_keyword_skipped_rows"] = issues
    return list(rows.values())


def store_pattern_keyword_rows(conn, rows, filename):
    initialize_keyword_store(conn)
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



# =============================================================
# EXISTING PAIR PERFORMANCE CHECK
# =============================================================
def export_promote_domain(domain, admin_name):
    if not re.search(r"\.promote(?:\.|$)", keyword_text(domain), flags=re.IGNORECASE):
        return domain, ""
    ids = list(dict.fromkeys(re.findall(
        r"\bset[\s_-]*id\s*[:=]\s*(\d+)\b", keyword_text(admin_name), flags=re.IGNORECASE,
    )))
    if len(ids) == 1:
        prefix = re.split(r"(?<=\.promote)\.", domain, maxsplit=1, flags=re.IGNORECASE)[0]
        return f"{prefix}.{ids[0]}.setid", ""
    reason = "Missing setid in admin_name" if not ids else "Conflicting setid values in admin_name"
    return domain, reason


def audit_text_key(value):
    return _cached_audit_text_key(keyword_text(value))


@processing_lru_cache(maxsize=32768)
def _cached_audit_text_key(value):
    return re.sub(r"\s+", " ", keyword_text(value)).casefold()


def audit_pattern_key(value):
    return audit_text_key(value).replace("\\*", "*")


def audit_count_values(series, name):
    cleaned = series.map(keyword_text).str.replace(",", "", regex=False).str.replace(r"\s+", "", regex=True)
    counts = pd.to_numeric(cleaned, errors="coerce")
    invalid = counts.isna() | counts.isin([float("inf"),float("-inf")]) | counts.lt(0) | counts.mod(1).ne(0)
    if invalid.any():
        rows = ", ".join(str(i+2) for i in range(len(series)) if invalid.iloc[i])
        raise ValueError(f"{name} must contain nonnegative whole numbers. Check CSV line(s): {rows[:300]}.")
    return counts


def remove_pair_report_total_rows(frame, basis_column=None, keyword_column=None):
    from html import unescape
    def report_label(value):
        text = unescape(keyword_text(value)).casefold()
        text = re.sub(r"<br\s*/?>", " ", text)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return re.sub(r"url\s*\(", "url (", text)
    excluded = {"grand total", "report total", "stripped url (others)",
                "report total stripped url (others)", "grand total stripped url (others)"}
    # Upload cleanup also recognizes summary labels in otherwise unnamed report columns.
    checked = [column for column in (basis_column, keyword_column) if column in frame.columns]
    checked.extend(frame.columns)
    mask = pd.Series(False,index=frame.index)
    for column in dict.fromkeys(checked):
        mask |= frame[column].map(report_label).isin(excluded)
    cleaned = frame.loc[~mask].copy()
    count = int(mask.sum())
    cleaned.attrs["excluded_report_rows"] = frame.attrs.get("excluded_report_rows", 0) + count
    return cleaned, count


PERFORMANCE_ALIASES = {
    "basis": ["basis", "basis name", "url pattern"],
    "keyword": ["kwds", "kwd", "keyword", "keywords", "keyword term"],
    "impressions": ["kimpressions", "keyword impressions", "kwd impressions", "impressions"],
    "revenue": ["revenue", "keyword revenue", "kwd revenue", "earnings"],
    "rpm": ["krpm", "rpm", "kwdrpm", "keyword rpm", "KWD RPM (audited)"],
    "l2r": ["kl2r", "l2r", "kwdl2r", "keyword l2r"],
    "rpc": ["rpc", "keyword rpc", "kwd rpc"],
    "clicks": ["kwd clicks", "keyword clicks", "kclicks"],
    "ad_clicks": ["ad clicks", "adclicks"],
    "language": ["languagecode", "language code", "language", "KBB Selected Language"],
    "domain": ["domain"],
}


def performance_number(series, label):
    text = series.map(keyword_text).str.replace(",", "", regex=False)
    text = text.str.replace(r"[$€£%\s]", "", regex=True).str.replace(r"^\((.*)\)$", r"-\1", regex=True)
    values = pd.to_numeric(text, errors="coerce")
    invalid = values.isna() | values.isin([float("inf"), -float("inf")]) | values.lt(0)
    if invalid.any():
        raise ValueError(f"{label}: missing, negative or invalid numbers on data row(s) " +
                         ", ".join(str(i + 1) for i in range(len(values)) if invalid.iloc[i])[:300])
    return values


def performance_live_index(patterns, keyword_rows):
    """Build the exact live lookup, resolving shared source metadata once."""
    live,index,resolved = {},{},{}
    for source in patterns.to_dict("records"):
        key = (audit_pattern_key(source.get("url_pattern")),keyword_text(source.get("language_code")).lower())
        live.setdefault(key,[]).append(source)
    fields = ["source_pattern","keyword","language","source_admin_name"]
    for pattern_value,keyword_value,language_value,admin in keyword_rows.reindex(columns=fields).itertuples(index=False,name=None):
        pattern,language = keyword_text(pattern_value),keyword_text(language_value).lower()
        source_admin = None if admin is None or pd.isna(admin) else audit_text_key(admin)
        source_key = (pattern,language,source_admin)
        if source_key not in resolved:
            sources = live.get((audit_pattern_key(pattern),language),[])
            if source_admin is not None:
                sources = [source for source in sources if audit_text_key(source.get("admin_name"))==source_admin]
            elif ".promote" in pattern.casefold() and len({audit_text_key(source.get("admin_name")) for source in sources})>1:
                sources = [dict(sources[0],admin_name="")]
            domain,basis = split_domain_basis(pattern)
            aliases = {audit_pattern_key(alias) for alias in (basis,pattern,domain+"*"+basis)}
            templates = []
            for source in sources:
                decorated,issue = export_promote_domain(domain,source.get("admin_name"))
                templates.append(dict(domain=decorated,basis=basis,languagecode=language,
                                      priority=keyword_text(source.get("priority")),issue=issue))
            resolved[source_key] = aliases,templates
        aliases,templates = resolved[source_key]
        keyword = keyword_text(keyword_value)
        identity = audit_text_key(keyword)
        for template in templates:
            mapping = dict(template,keywords=keyword)
            for alias in aliases:
                index.setdefault((alias,identity),[]).append(mapping)
    return index


PERFORMANCE_RULE_METRICS = {
    "RPM":"rpm", "Keyword Impressions":"impressions", "Revenue":"revenue",
    "Keyword Clicks":"clicks", "Ad Clicks":"ad_clicks", "L2R":"l2r", "RPC":"rpc",
}


def performance_check_conditions(minimum_impressions=1000, mode="All conditions", rules=None):
    minimum = coverage_priority_value(minimum_impressions)
    if not minimum.is_finite() or minimum!=minimum.to_integral_value():
        raise ValueError("Minimum impressions must be a nonnegative whole number.")
    if mode not in {"All conditions","Any condition"}:
        raise ValueError("Choose All conditions or Any condition.")
    if rules is None:
        rules = [{"Metric":"RPM","Operator":"<","Compare To":"Basis Average","Value":100.0}]
    checked = []
    for position,rule in enumerate(rules,1):
        metric,operator,target = (keyword_text(rule.get(field)) for field in ("Metric","Operator","Compare To"))
        if not any((metric,operator,target)):
            continue
        if metric not in PERFORMANCE_RULE_METRICS or operator not in {"<","<=",">",">=","=","!="} or target not in {"Fixed Value","Basis Average","Basis Average %"}:
            raise ValueError(f"Condition {position}: choose a metric, operator and comparison type.")
        value = None
        if target!="Basis Average":
            number = coverage_priority_value(rule.get("Value"))
            if not number.is_finite():
                raise ValueError(f"Condition {position}: enter a finite, nonnegative value.")
            value = float(number)
            if value in {float("inf"),float("-inf")}:
                raise ValueError(f"Condition {position}: the value is too large.")
        checked.append(dict(metric=PERFORMANCE_RULE_METRICS[metric],label=metric,operator=operator,target=target,value=value))
    return dict(minimum_impressions=int(minimum),mode=mode,rules=checked)


def performance_conditions_mask(pairs, conditions):
    result = pd.Series(conditions["mode"]=="All conditions",index=pairs.index,dtype=bool)
    if not conditions["rules"]:
        return pd.Series(True,index=pairs.index,dtype=bool)
    for rule in conditions["rules"]:
        values = pairs[rule["metric"]]
        target = rule["value"] if rule["target"]=="Fixed Value" else pairs["basis_average_"+rule["metric"]]
        if rule["target"]=="Basis Average %":
            target = target*rule["value"]/100.
        matches = {"<":values.lt,"<=":values.le,">":values.gt,">=":values.ge,"=":values.eq,"!=":values.ne}[rule["operator"]](target)
        result = result & matches if conditions["mode"]=="All conditions" else result | matches
    return result


def prepare_performance_review(frame, columns, patterns, keyword_rows, conditions=None, live_index=None):
    conditions = conditions or performance_check_conditions()
    for field in ("basis", "keyword", "impressions", "rpm"):
        if not columns.get(field):
            raise ValueError(f"Choose the {field} column.")
    mapped = [c for c in columns.values() if c]
    if len(mapped) != len(set(mapped)):
        raise ValueError("Each source column can be mapped to only one field.")
    source, removed = remove_pair_report_total_rows(frame, columns["basis"], columns["keyword"])
    removed += frame.attrs.get("excluded_report_rows", 0)
    source = source.loc[~source.apply(lambda column: column.map(keyword_text).eq("")).all(axis=1)].reset_index(drop=True)
    if source.empty:
        return pd.DataFrame(),{},dict(pairs=0,eligible=0,underperforming=0,removed=removed)
    data = pd.DataFrame(index=source.index)
    for field in ("basis", "keyword", "language", "domain"):
        data[field] = source[columns[field]].map(keyword_text) if columns.get(field) else ""
    if data["basis"].eq("").any() or data["keyword"].eq("").any():
        raise ValueError("Every data row requires a basis and keyword.")
    data["impressions"] = audit_count_values(source[columns["impressions"]], "Keyword impressions")
    data["rpm"] = performance_number(source[columns["rpm"]], "Pair RPM")
    used_metrics = {rule["metric"] for rule in conditions["rules"]} | {"rpm","impressions"}
    if "rpc" in used_metrics and columns.get("clicks"):
        used_metrics.add("clicks")
    for field in used_metrics - {"rpm","impressions"}:
        if not columns.get(field):
            raise ValueError(f"Choose the {field} CSV column to use it in a condition.")
        data[field] = (audit_count_values(source[columns[field]],field) if field in {"clicks","ad_clicks"}
                       else performance_number(source[columns[field]],field))
    data["basis_key"] = data["basis"].map(audit_pattern_key)
    data["keyword_key"] = data["keyword"].map(audit_text_key)
    data["language"] = data["language"].str.lower()
    data["domain"] = data["domain"].map(keyword_domain_key)
    data["weighted_rpm"] = data["impressions"] * data["rpm"]
    data["source_row"] = source.index
    keys = ["basis_key", "keyword_key", "language", "domain"]
    aggregation = dict(impressions=("impressions","sum"),weighted_rpm=("weighted_rpm","sum"),
                       reported_rpm=("rpm","mean"),source_rows=("source_row",list))
    for field in used_metrics - {"rpm","impressions"}:
        if field in {"revenue","clicks","ad_clicks"}:
            aggregation[field] = (field,"sum")
        else:
            data["weighted_"+field] = data[field]*data["impressions"]
            aggregation["weighted_"+field] = ("weighted_"+field,"sum")
            aggregation["reported_"+field] = (field,"mean")
    if "rpc" in used_metrics and "clicks" in used_metrics:
        data["click_weighted_rpc"] = data["rpc"]*data["clicks"]
        aggregation["click_weighted_rpc"] = ("click_weighted_rpc","sum")
    totals = data.groupby(keys, as_index=False, sort=False).agg(**aggregation)
    index = performance_live_index(patterns,keyword_rows) if live_index is None else live_index
    eligible = []
    for pair in totals.to_dict("records"):
        if pair["impressions"] < conditions["minimum_impressions"]:
            continue
        matches = index.get((pair["basis_key"], pair["keyword_key"]), [])
        matches = [m for m in matches if (not pair["language"] or m["languagecode"] == pair["language"])
                   and (not pair["domain"] or keyword_domain_key(m["domain"]) == pair["domain"])]
        if pair["impressions"] >= conditions["minimum_impressions"] and matches:
            pair["rpm"] = pair["weighted_rpm"] / pair["impressions"] if pair["impressions"] else pair["reported_rpm"]
            for field in used_metrics & {"l2r","rpc"}:
                pair[field] = pair["weighted_"+field]/pair["impressions"] if pair["impressions"] else pair["reported_"+field]
            if "rpc" in used_metrics and pair.get("clicks",0)>0:
                pair["rpc"] = pair["click_weighted_rpc"]/pair["clicks"]
            pair["matches"] = matches
            eligible.append(pair)
    pairs = pd.DataFrame(eligible)
    review_rows, exports = [], {}
    source_records = source.to_dict("records") if not pairs.empty else []
    if not pairs.empty:
        for field in used_metrics:
            pairs["basis_average_"+field] = pairs.groupby(["basis_key","language","domain"])[field].transform("mean")
        pairs["average"] = pairs["basis_average_rpm"]
        for pair_id, pair in enumerate(pairs.loc[performance_conditions_mask(pairs,conditions)].to_dict("records")):
            exports[pair_id] = pair["matches"]
            for row_id in pair["source_rows"]:
                review_rows.append({"Select for deletion": False, **source_records[row_id],
                                    "Review: Pair impressions": pair["impressions"],
                                    "Review: Pair RPM": pair["rpm"], "Review: Basis average RPM": pair["average"],
                                    "Review: Pair ID": pair_id,
                                    **{"Review: Pair "+label:pair[field] for label,field in PERFORMANCE_RULE_METRICS.items() if field in used_metrics and field not in {"rpm","impressions"}},
                                    **{"Review: Basis average "+label:pair["basis_average_"+field] for label,field in PERFORMANCE_RULE_METRICS.items() if field in used_metrics and field not in {"rpm"}}})
    reserved = {"Select for deletion", "Review: Pair impressions", "Review: Pair RPM", "Review: Basis average RPM", "Review: Pair ID"}
    reserved.update("Review: Pair "+label for label in PERFORMANCE_RULE_METRICS)
    reserved.update("Review: Basis average "+label for label in PERFORMANCE_RULE_METRICS)
    if reserved.intersection(source.columns):
        raise ValueError("Rename CSV columns that conflict with reserved review column names.")
    review = pd.DataFrame(review_rows)
    if not review.empty:
        review = review.sort_values(
            [columns["basis"], columns["keyword"]],
            key=lambda values: values.map(audit_text_key), kind="stable",
        ).reset_index(drop=True)
        display_columns = ["Select for deletion", columns["basis"], columns["keyword"],
                           "Review: Basis average RPM", "Review: Pair RPM"]
        review = review[display_columns + [c for c in review.columns if c not in display_columns]]
    return review, exports, {"pairs": len(totals), "eligible": len(pairs), "underperforming": len(exports), "removed": removed}


def performance_deletion_sheet(selected_ids, exports):
    rows, issues = [], []
    for pair_id in sorted(set(selected_ids)):
        for mapping in exports[int(pair_id)]:
            if mapping["issue"]:
                issues.append({k: mapping[k] for k in ("domain", "basis", "languagecode", "issue")})
            else:
                rows.append({k: mapping[k] for k in ("domain", "basis", "keywords", "languagecode")})
    return pd.DataFrame(rows, columns=["domain", "basis", "keywords", "languagecode"]).drop_duplicates().reset_index(drop=True), issues


def performance_existing_basis_keywords(keyword_rows):
    """Stored keywords by basis/language, independent of the target domain."""
    lookup = {}
    for record in keyword_rows.to_dict("records"):
        pattern = keyword_text(record.get("source_pattern"))
        if "*" in pattern.strip("*").replace("\\*", "*"):
            _, basis = split_domain_basis(pattern)
        else:
            basis = keyword_text(record.get("basis")) or pattern.strip("*")
        identity = (audit_pattern_key(basis), keyword_text(record.get("language")).lower())
        keyword = audit_text_key(record.get("keyword"))
        if identity[0] and keyword:
            lookup.setdefault(identity, set()).add(keyword)
    return lookup


def performance_replacement_entries(deletion, patterns):
    """Prepare blank manual rows; no keyword model or generation is used."""
    rows = []
    priorities = keyword_priority_lookup(patterns)
    for (domain,basis,language),group in deletion.groupby(["domain","basis","languagecode"],sort=False):
        saved = priorities.get((keyword_domain_key(domain),keyword_basis_key(basis),language),set())
        priority = keyword_default_priority(domain,basis)
        if len(saved)==1:
            try:
                value = Decimal(next(iter(saved)))
                if value.is_finite() and value==value.to_integral_value() and value>=0:
                    priority = int(value)
            except InvalidOperation:
                pass
        for slot in range(len(group)):
            rows.append({"Select":False,"domain":domain,"basis":basis,"keywords":"",
                         "languagecode":language,"priority":priority})
    return pd.DataFrame(rows,columns=["Select","domain","basis","keywords","languagecode","priority"])


def performance_upload_sheet(edited, deletion, allowed_domains, patterns, keyword_rows, existing_keywords=None):
    selected = edited.loc[edited["Select"].fillna(False)].copy()
    if selected.empty:
        raise ValueError("Select at least one keyword to generate an upload sheet.")
    existing = performance_existing_basis_keywords(keyword_rows) if existing_keywords is None else existing_keywords
    seen, rows = set(), []
    for position, row in enumerate(selected.to_dict("records"), 1):
        domain, basis, keyword, language = [keyword_text(row[k]) for k in ("domain", "basis", "keywords", "languagecode")]
        language = language.lower()
        if not keyword or not basis or not re.fullmatch(r"[a-z]{2,3}(?:-[a-z0-9]{2,8})*", language):
            raise ValueError(f"Replacement row {position}: keyword, basis and valid language code are required.")
        if domain not in allowed_domains:
            raise ValueError(f"Replacement row {position}: choose an available domain.")
        prefix = "patternkeywords.global."
        if domain.startswith(prefix) and not domain.startswith(prefix + "promote.") and domain != prefix + language:
            raise ValueError(f"Replacement row {position}: language-specific domain must match languagecode.")
        try:
            priority = Decimal(keyword_text(row["priority"]))
            if not priority.is_finite() or priority != priority.to_integral_value() or priority < 0:
                raise InvalidOperation
        except InvalidOperation:
            raise ValueError(f"Replacement row {position}: priority must be a nonnegative whole number.")
        key = (audit_pattern_key(basis), language, audit_text_key(keyword))
        if key in seen or key[2] in existing.get(key[:2], set()):
            raise ValueError(f"Replacement row {position}: this keyword is already present under the same basis/language, or repeats another selected replacement, regardless of domain.")
        seen.add(key)
        rows.append(dict(domain=domain, basis=basis, keywords=keyword, languagecode=language, rank=1, priority=int(priority)))
    return pd.DataFrame(rows)


def underperforming_pairs_page():
    st.header("Keyword Performance Check")
    st.write("Select existing underperforming pairs, generate a deletion sheet, then enter replacement keywords manually and generate an upload sheet.")
    st.caption("Set your base threshold and metric rules below. Only existing shared-database pairs qualify. Basis averages use existing pairs meeting the minimum impressions, within the CSV language/domain when supplied, before metric rules are applied.")
    file = st.file_uploader("Performance CSV", type=["csv"], key="performance_workflow_file")
    if file is None:
        return
    try:
        frame, removed_on_upload = _cached_performance_csv(file.getvalue())
        if removed_on_upload:
            st.info(f"Removed {removed_on_upload:,} summary row(s): Grand Total, Report Total or Stripped URL (Others).")
        if frame.empty:
            st.warning("The uploaded CSV contains no performance data after removing summary rows.")
            return
        digest = _cached_upload_digest(file.getvalue())
        columns = {}
        with st.expander("CSV column mapping", expanded=True):
            st.caption("Basis, keyword, impressions and RPM are required. Other columns are preserved exactly in the review table.")
            for field, aliases in PERFORMANCE_ALIASES.items():
                detected = [c for c in frame.columns if keyword_header(c) in {keyword_header(a) for a in aliases}]
                options = [None] + list(frame.columns)
                columns[field] = st.selectbox(field, options, index=options.index(detected[0]) if len(detected) == 1 else 0,
                    format_func=lambda value: "Not mapped" if value is None else value,
                    key=f"perf_map_{digest}_{field}")
        with st.expander("Performance Check Conditions",expanded=True):
            minimum_impressions = st.number_input("Minimum Pair Impressions",min_value=0,value=1000,step=100,key="perf_minimum_impressions")
            mode = st.radio("Match Rules",["All conditions","Any condition"],horizontal=True,key="perf_conditions_mode")
            rule_rows = st.data_editor(pd.DataFrame([{"Metric":"RPM","Operator":"<","Compare To":"Basis Average","Value":100.0}]),
                num_rows="dynamic",hide_index=True,use_container_width=True,key="perf_conditions_editor",
                column_config={"Metric":st.column_config.SelectboxColumn("Metric",options=list(PERFORMANCE_RULE_METRICS),required=True),
                    "Operator":st.column_config.SelectboxColumn("Operator",options=["<","<=",">",">=","=","!="],required=True),
                    "Compare To":st.column_config.SelectboxColumn("Compare To",options=["Fixed Value","Basis Average","Basis Average %"],required=True),
                    "Value":st.column_config.NumberColumn("Value",min_value=0.0,help="Fixed threshold, or percentage of basis average. Ignored for Basis Average.")})
            st.caption("Examples: Keyword Clicks < Fixed Value 5; RPM < Basis Average; RPM < Basis Average % 80 (below 80% of the average). Add/remove rows to customize. Removing all rules lists all existing pairs meeting the impression threshold.")
            st.caption("Duplicates: counts and revenue are summed; RPM/L2R use impression weights. RPC uses keyword-click weights when that column is mapped, otherwise impression weights. Zero-weight groups use the mean reported rate. Percentages use the numeric scale in your CSV, e.g. enter 5 for values written as 5%.")
            conditions = performance_check_conditions(minimum_impressions,mode,rule_rows.to_dict("records"))
        revision_key,patterns,keyword_rows = load_performance_snapshot()
        signature = hashlib.sha256((digest+json.dumps(columns,sort_keys=True)+json.dumps(conditions,sort_keys=True)+repr(revision_key)).encode()).hexdigest()
        if st.button("Check Keyword Performance", type="primary", key="perf_check"):
            if keyword_rows.empty:
                raise ValueError("Upload and confirm a shared workbook containing pattern_keywords first.")
            review, exports, stats = prepare_performance_review(frame,columns,patterns,keyword_rows,conditions,live_index=_cached_performance_index(revision_key))
            st.session_state["perf_manual_workflow"] = dict(signature=signature, review=review, exports=exports, stats=stats,
                                                    revision=st.session_state.get("perf_revision", 0) + 1)
            st.session_state["perf_revision"] = st.session_state["perf_manual_workflow"]["revision"]
        state = st.session_state.get("perf_manual_workflow")
        if not state or state["signature"] != signature:
            st.info("Run the check for the current CSV, column mapping, conditions and shared dataset.")
            return
        revision = state["revision"]
        stats = state["stats"]
        st.success(f"Pairs: {stats['pairs']:,} | Existing pairs with ≥{conditions['minimum_impressions']:,} impressions: {stats['eligible']:,} | Matching your conditions: {stats['underperforming']:,}")
        if stats["removed"]:
            st.caption(f"Removed {stats['removed']:,} report total rows.")
        if state["review"].empty:
            return
        st.caption("Select any source row to select its entire aggregated pair. All original CSV columns are retained.")
        reviewed = st.data_editor(state["review"], hide_index=True, use_container_width=True,
            disabled=[c for c in state["review"].columns if c != "Select for deletion"],
            column_config={"Review: Pair ID": None,
                           "Review: Basis average RPM": st.column_config.NumberColumn("Basis Average RPM", format="%.4f"),
                           "Review: Pair RPM": st.column_config.NumberColumn("Pair RPM", format="%.4f")},
            key=f"perf_review_{revision}")
        selected_ids = sorted(set(reviewed.loc[reviewed["Select for deletion"], "Review: Pair ID"].tolist()))
        if st.button("Generate Deletion Sheet", type="primary", disabled=not selected_ids, key="perf_delete"):
            deletion, issues = performance_deletion_sheet(selected_ids, state["exports"])
            state.update(deletion=deletion, issues=issues, selected_ids=selected_ids)
            for key in ("replacement_entries", "upload", "replacement_latest", "editor_baseline", "editor_sig"):
                state.pop(key, None)
            state["replacement_revision"] = state.get("replacement_revision", 0) + 1
        if "deletion" not in state or state["selected_ids"] != selected_ids:
            return
        if state["issues"]:
            st.error("Some selected mappings have an unresolved promote set ID. Correct the shared data before generating a complete deletion sheet.")
            st.dataframe(pd.DataFrame(state["issues"]), hide_index=True)
            return
        deletion = state["deletion"]
        st.subheader("Deletion Sheet")
        st.dataframe(deletion, hide_index=True, use_container_width=True)
        st.download_button("Download Deletion Sheet", deletion.to_csv(index=False).encode("utf-8-sig"), "keyword_deletion.csv", "text/csv")
        st.caption(f"{len(deletion):,} keyword mappings selected for deletion. Enter replacement keywords manually below and select the rows to upload. Sheets do not modify the shared database.")
        if "replacement_entries" not in state:
            state["replacement_entries"] = performance_replacement_entries(deletion, patterns)
        st.subheader("Replacement Keywords — Manual Entry")
        st.caption("Add your own keywords, then choose their domain, language and priority. You may add or remove rows as needed.")
        language_input = st.text_input("Additional language codes (comma separated)", key="perf_add_languages")
        set_id = st.text_input("Promote set ID (required to offer a promote domain)", key="perf_set_id").strip()
        partner = st.selectbox("Partner ID", ["8PRVCXX19", "7PRFT79UO"], key="perf_partner")
        languages = sorted(set(deletion["languagecode"]) | {v.strip().lower() for v in language_input.split(",") if v.strip()})
        languages = [v for v in languages if re.fullmatch(r"[a-z]{2,3}(?:-[a-z0-9]{2,8})*", v)]
        domains = ["patternkeywords.global"] + [f"patternkeywords.global.{v}" for v in languages] + [f"{partner}.partner"]
        if set_id:
            if re.fullmatch(r"[0-9]+", set_id):
                domains.append(f"patternkeywords.global.promote.{set_id}.setid")
            else:
                st.warning("Set ID must contain digits only.")
        editor_sig = hashlib.sha256(json.dumps(domains).encode()).hexdigest()[:12]
        if state.get("editor_sig") != editor_sig:
            entries = state.get("replacement_latest", state["replacement_entries"]).copy()
            entries.loc[~entries["domain"].isin(domains), "domain"] = "patternkeywords.global"
            state["editor_baseline"] = entries
            state["editor_sig"] = editor_sig
        entries = state["editor_baseline"]
        edited = st.data_editor(entries, hide_index=True, use_container_width=True, num_rows="dynamic",
            column_config={"Select": st.column_config.CheckboxColumn("Select"),
                           "domain": st.column_config.SelectboxColumn("domain", options=domains, required=True),
                           "languagecode": st.column_config.SelectboxColumn("languagecode", options=languages, required=True),
                           "priority": st.column_config.NumberColumn("priority", min_value=0, step=1, required=True)},
            key=f"perf_replacements_{revision}_{state['replacement_revision']}_{editor_sig}")
        state["replacement_latest"] = edited.copy()
        # Preserve edits across domain-option changes without reusing a changed editor baseline.
        st.caption("Select any number of keywords; add or remove rows as needed. Choose a domain and priority for each replacement. Language-specific domains must match languagecode. Promote domains use the set ID entered above.")
        upload_signature = hashlib.sha256((edited.to_json() + json.dumps(domains)).encode()).hexdigest()
        if st.button("Generate Upload Sheet", type="primary", key="perf_upload"):
            state.pop("upload", None)
            state["upload"] = performance_upload_sheet(edited,deletion,domains,patterns,keyword_rows,existing_keywords=_cached_existing_basis_keywords(revision_key))
            state["upload_signature"] = upload_signature
        if state.get("upload_signature") == upload_signature and "upload" in state:
            st.subheader("Upload Sheet")
            st.dataframe(state["upload"], hide_index=True, use_container_width=True)
            st.download_button("Download Upload Sheet", state["upload"].to_csv(index=False).encode("utf-8-sig"), "keyword_upload.csv", "text/csv")
    except (ValueError, KeyError, pd.errors.ParserError) as exc:
        st.error(str(exc))


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
        st.Page(underperforming_pairs_page, title="Keyword Performance Check", icon=":material/fact_check:"),
    ],
    position="top",
)
navigation.run()
