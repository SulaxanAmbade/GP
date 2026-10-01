import os
import re
import sqlite3
import hmac
import json
from datetime import datetime
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
                url_pattern_id TEXT, priority TEXT, language_code TEXT
            )
        """)
        cursor.execute("PRAGMA table_info(dataset_metadata)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        for column in ("file_date", "updated_by"):
            if column not in existing_columns:
                cursor.execute(f"ALTER TABLE dataset_metadata ADD COLUMN {column} TEXT")
        cursor.execute("PRAGMA table_info(url_patterns)")
        if "language_code" not in {row[1] for row in cursor.fetchall()}:
            cursor.execute("ALTER TABLE url_patterns ADD COLUMN language_code TEXT")
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
            SELECT url_pattern, url_pattern_id, priority, language_code FROM url_patterns
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
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM url_patterns")
        records = [
            tuple(None if pd.isna(value) else str(value) for value in row)
            for row in new_df[["url_pattern", "url_pattern_id", "priority", "language_code"]]
            .itertuples(index=False, name=None)
        ]
        cursor.executemany("""
            INSERT INTO url_patterns (url_pattern, url_pattern_id, priority, language_code)
            VALUES (?, ?, ?, ?)
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
            datetime.now().strftime("%d-%m-%Y %I:%M:%S %p"), len(new_df),
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
        username = st.session_state.get("authenticated_username", "admin").title()
        st.markdown(
            f'<span class="gp-user-pill"><span class="gp-dot"></span>Signed in as {username}</span>',
            unsafe_allow_html=True,
        )
    with logout_col:
        if st.button("Logout", width="content"):
            st.session_state["admin_authenticated"] = False
            for key in ("authenticated_username", "login_username", "login_password"):
                st.session_state.pop(key, None)
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


def parse_uploaded_file(uploaded_file):
    df = None
    last_error_msg = ""
    try:
        uploaded_file.seek(0)
        df = pd.read_excel(uploaded_file, engine="xlrd", header=None)
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
                standard_cols = max(set(row_lengths), key=row_lengths.count) if row_lengths else 0
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
    df.columns = [str(col).strip() for col in df.iloc[header_row_idx]]
    df = df.iloc[header_row_idx + 1:].reset_index(drop=True)
    for col in (
        "url_pattern", "url_pattern_id", "priority", "total_count",
        "language_code", "url_pattern_order",
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
    final_df = df[["url_pattern", "url_pattern_id", "priority", "language_code"]].copy()
    initial_len = len(final_df)
    final_df.drop_duplicates(inplace=True)
    duplicates_removed = initial_len - len(final_df)
    final_df["_url_pattern_length"] = final_df["url_pattern"].fillna("").astype(str).str.len()
    final_df.sort_values("_url_pattern_length", ascending=False, inplace=True)
    final_df.drop(columns=["_url_pattern_length"], inplace=True)
    final_df.reset_index(drop=True, inplace=True)
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


def basis_matches_url(normalized_basis, searchable_url):
    basis_words = normalized_basis.split()
    url_words = searchable_url.split()
    if not basis_words or len(basis_words) > len(url_words):
        return False
    size = len(basis_words)
    return any(
        all(word_forms_match(a, b) for a, b in zip(basis_words, url_words[start:start + size]))
        for start in range(len(url_words) - size + 1)
    )


# =============================================================
# COVERAGE CATALOG AND INPUT UTILITIES
# =============================================================
@st.cache_data(show_spinner=False, max_entries=4)
def make_basis_catalog(pattern_df):
    # Cache catalog construction across reruns; dataset contents are part of the key.
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
        normalized_basis = normalize_search_text(basis)
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
    # Preserve the current word_forms_match rules exactly.
    forms = {word}
    if len(word) > 3:
        if word.endswith("ies"):
            forms.add(word[:-3] + "y")
        if word.endswith("s"):
            forms.add(word[:-1])
        if word.endswith("es"):
            forms.update((word[:-2], word[:-1]))
    return frozenset(forms)


@lru_cache(maxsize=4)
def _coverage_basis_index(bases):
    """Build a shared-prefix index; cache keys include the actual basis values.

    Each edge is indexed under all forms of its original word. Matching an
    edge requires intersecting word forms, just like word_forms_match.
    Cached dictionaries are only read after construction.
    """
    children = [{}]
    form_edges = [{}]
    terminals = [[]]
    for basis_id, basis in enumerate(bases):
        node = 0
        words = basis.split()
        if not words:
            continue
        for word in words:
            child = children[node].get(word)
            if child is None:
                child = len(children)
                children[node][word] = child
                children.append({})
                form_edges.append({})
                terminals.append([])
                for form in _coverage_word_forms(word):
                    form_edges[node].setdefault(form, set()).add(child)
            node = child
        terminals[node].append(basis_id)
    return form_edges, terminals


def _coverage_match_ids(searchable_url, index):
    form_edges, terminals = index
    active = set()
    matches = set()
    for word in searchable_url.split():
        forms = _coverage_word_forms(word)
        next_active = set()
        # Start a new match at this word as well as extending existing ones.
        for node in active | {0}:
            edges = form_edges[node]
            for form in forms:
                next_active.update(edges.get(form, ()))
        for node in next_active:
            matches.update(terminals[node])
        active = next_active
    # Preserve the catalog order used by the original report.
    return tuple(sorted(matches))


def create_coverage_report(input_df, basis_catalog):
    """Return URL summary, match details, coverage pivot, and basis pivot.

    Matches remain global, contiguous, ordered, and singular/plural aware.
    Select a single language before calling, as render_coverage_report does.
    """
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
        raise ValueError("Select a language with at least one usable basis.")
    if basis_catalog["language_code"].nunique(dropna=False) != 1:
        raise ValueError("Filter the basis catalog to one language first.")
    selected_language = str(basis_catalog["language_code"].iloc[0])

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

    # Convert the catalog once instead of filtering a DataFrame for every URL.
    records = list(basis_catalog[[
        "normalized_basis", "basis", "language_code", "domain",
        "url_pattern_id", "priority",
    ]].itertuples(index=False, name=None))
    index = _coverage_basis_index(tuple(str(row[0]) for row in records))
    # URLs with the same normalized path/query/fragment share their match work.
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
                url, domain, selected_language, "No Matching Basis", 0,
                "No Matching Basis", impressions, revenue,
            ))
            detail_rows.append((
                url, domain, selected_language, "No Matching Basis",
                "No Matching Basis", "", "", "", impressions, revenue,
            ))
            continue
        matched_bases = []
        for basis_id in ids:
            _, basis, language, source_domain, pattern_id, priority = records[basis_id]
            matched_bases.append(str(basis))
            detail_rows.append((
                url, domain, language, "Covered", basis, source_domain,
                pattern_id, priority, impressions, revenue,
            ))
        summary_rows.append((
            url, domain, selected_language, "Covered", len(ids),
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


# =============================================================
# COVERAGE REPORT UI
# =============================================================
def render_coverage_report(final_df):
    st.subheader("URL Coverage Report")
    st.write(
        "Check URLs against bases from the active global pattern dataset. "
        "Matching is global and does not compare domains. A basis matches when "
        "its normalized words appear together in the URL path, including common "
        "singular/plural variations."
    )
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
    selected_language = st.selectbox(
        "Language code", available_languages, format_func=lambda value: value.upper(),
        key="coverage_language_code",
        help="Only bases with this language code will be checked against the submitted URLs.",
    )
    basis_catalog = complete_basis_catalog.loc[
        complete_basis_catalog["language_code"].eq(selected_language)
    ].copy()
    st.caption(
        f"{len(basis_catalog):,} unique bases are available for language {selected_language.upper()}."
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
    if st.button(
        "Create Coverage Report", type="primary", use_container_width=True,
        disabled=prepared_input is None or prepared_input.empty,
    ):
        with st.spinner("Checking URL coverage..."):
            st.session_state["coverage_report"] = create_coverage_report(prepared_input, basis_catalog)
            st.session_state["coverage_report_language"] = selected_language
    report = st.session_state.get("coverage_report")
    if st.session_state.get("coverage_report_language") != selected_language:
        report = None
    if report is None:
        return
    url_summary_df, detail_df, coverage_pivot, basis_pivot = report
    total_urls = len(url_summary_df)
    covered_urls = int(url_summary_df["Coverage Status"].eq("Covered").sum())
    uncovered_urls = total_urls - covered_urls
    coverage_rate = covered_urls / total_urls * 100 if total_urls else 0
    metric1, metric2, metric3, metric4 = st.columns(4)
    metric1.metric("URLs Checked", f"{total_urls:,}")
    metric2.metric("Covered URLs", f"{covered_urls:,}")
    metric3.metric("No Matching Basis", f"{uncovered_urls:,}")
    metric4.metric("Coverage Rate", f"{coverage_rate:.1f}%")
    summary_tab, basis_tab, url_tab, detail_tab = st.tabs([
        "Coverage Summary", "Basis Performance", "URL Summary", "Match Details",
    ])
    with summary_tab:
        st.dataframe(coverage_pivot, use_container_width=True, hide_index=True)
    with basis_tab:
        st.dataframe(basis_pivot, use_container_width=True, hide_index=True)
        st.caption(
            "When one URL matches multiple bases, its performance is attributed "
            "to each matching basis. Use URL Summary for non-duplicated totals."
        )
    with url_tab:
        st.dataframe(url_summary_df, use_container_width=True, hide_index=True)
    with detail_tab:
        st.dataframe(detail_df, use_container_width=True, hide_index=True)
    download1, download2, download3 = st.columns(3)
    download1.download_button(
        "Download URL Summary", data=url_summary_df.to_csv(index=False),
        file_name="coverage_url_summary.csv", mime="text/csv", use_container_width=True,
    )
    download2.download_button(
        "Download Basis Report", data=basis_pivot.to_csv(index=False),
        file_name="coverage_basis_report.csv", mime="text/csv", use_container_width=True,
    )
    download3.download_button(
        "Download Match Details", data=detail_df.to_csv(index=False),
        file_name="coverage_match_details.csv", mime="text/csv", use_container_width=True,
    )


# =============================================================
# CONCATENATE / PATTERN GENERATOR PAGE
# =============================================================
def concatenate_sheet_page():
    st.header("Concatenate Sheet")
    st.write("Enter Domain and Basis values in the table below. Each row will generate one pattern.")
    default_df = pd.DataFrame({"Domain": [""], "Basis": [""]})
    input_df = st.data_editor(
        default_df, num_rows="dynamic", use_container_width=True, key="pattern_generator_table",
        column_config={
            "Domain": st.column_config.TextColumn("Domain", help="Example: example.com", width="large"),
            "Basis": st.column_config.TextColumn("Basis", help="Example: labor day", width="large"),
        },
    )
    if st.button("Generate Patterns", type="primary", use_container_width=True):
        df = input_df.copy()
        for column in ("Domain", "Basis"):
            df[column] = df[column].fillna("").astype(str).str.strip()
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
            st.dataframe(df, use_container_width=True, hide_index=True)
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
            "Upload new .xls file", type=["xls"], accept_multiple_files=False,
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
                    })
                    st.success("New dataset processed successfully.")
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
                # Clear this session's old report after the active dataset changes.
                st.session_state.pop("coverage_report", None)
                st.session_state.pop("coverage_report_language", None)
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
# DATASET SEARCH UI
# =============================================================
def render_dataset_search(final_df):
    st.write("---")
    st.subheader("Search URL Patterns / IDs")
    st.write(
        "Search one or multiple URL patterns or URL pattern IDs. Choose Exact Match "
        "for complete-value matching, or Normalized Search for flexible "
        "separator-independent matching."
    )
    search_mode = st.radio(
        "Search Mode", ["Exact Match", "Normalized Search"], horizontal=True,
        key="database_search_mode",
        help=("Exact Match requires the complete URL pattern or URL pattern ID. "
              "Normalized Search ignores separators such as *, -, _, and /."),
    )
    search_string = st.text_area(
        "Search", placeholder="Examples:\n*example.com*bug*bite*\n1341291255\nbug bite",
        key="main_search",
    )
    if not search_string.strip():
        return
    if final_df.empty:
        st.warning("There is currently no shared dataset.")
        return
    search_terms = list(dict.fromkeys(
        term.strip() for term in re.split(r"[,\n]+", search_string) if term.strip()
    ))
    raw_patterns = final_df["url_pattern"].fillna("").astype(str).str.strip().str.lower()
    raw_ids = final_df["url_pattern_id"].fillna("").astype(str).str.strip().str.lower()
    normalized_patterns = final_df["url_pattern"].fillna("").astype(str).apply(normalize_search_text)
    combined_search_mask = pd.Series(False, index=final_df.index)
    for search_term in search_terms:
        raw_search = str(search_term).strip().lower()
        if search_mode == "Exact Match":
            pattern_mask = raw_patterns.eq(raw_search)
            id_mask = raw_ids.eq(raw_search)
        else:
            normalized_search = normalize_search_text(search_term)
            pattern_mask = (
                normalized_patterns.apply(lambda pattern: normalized_pattern_match(normalized_search, pattern))
                if normalized_search else pd.Series(False, index=final_df.index)
            )
            id_mask = raw_ids.str.contains(raw_search, case=False, na=False, regex=False)
        combined_search_mask |= pattern_mask | id_mask
    search_results = final_df.loc[combined_search_mask].copy()
    if search_results.empty:
        if search_mode == "Exact Match":
            st.warning(
                "No exact URL pattern or URL pattern ID was found for the entered "
                "search term(s). Try Normalized Search for broader matching."
            )
        else:
            st.warning("No URL patterns or URL pattern IDs were found for the entered search term(s).")
        return
    st.success(
        f"Found {len(search_results):,} matching result(s) for {len(search_terms)} "
        f"search term(s) using {search_mode}."
    )
    result_type = st.radio(
        "Search Result View", ["Original", "Domain - Basis Split"], horizontal=True, key="result_view",
    )
    filename_search = re.sub(r"[^a-zA-Z0-9]+", "_", search_string).strip("_") or "search_results"
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
