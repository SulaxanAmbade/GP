import os
import re
import sqlite3
import hmac
import json
from datetime import datetime

import pandas as pd
import streamlit as st
from urllib.parse import unquote, urlsplit


# =============================================================
# PAGE CONFIGURATION
# =============================================================

st.set_page_config(
    page_title="Global Patterns",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Global Pattern Database")


# =============================================================
# DATABASE CONFIGURATION
# =============================================================

DB_FILE = "url_patterns.db"


# =============================================================
# DATABASE FUNCTIONS
# =============================================================

def get_connection():
    return sqlite3.connect(
        DB_FILE,
        check_same_thread=False
    )


def initialize_database():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS dataset_metadata (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            filename TEXT,
            file_date TEXT,
            updated_at TEXT,
            total_rows INTEGER,
            updated_by TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS url_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url_pattern TEXT,
            url_pattern_id TEXT,
            priority TEXT,
            language_code TEXT
        )
        """
    )

    # ---------------------------------------------------------
    # Migration safety
    # ---------------------------------------------------------

    cursor.execute(
        "PRAGMA table_info(dataset_metadata)"
    )

    existing_columns = [
        row[1]
        for row in cursor.fetchall()
    ]

    if "file_date" not in existing_columns:
        cursor.execute(
            """
            ALTER TABLE dataset_metadata
            ADD COLUMN file_date TEXT
            """
        )

    if "updated_by" not in existing_columns:
        cursor.execute(
            """
            ALTER TABLE dataset_metadata
            ADD COLUMN updated_by TEXT
            """
        )

    cursor.execute(
        "PRAGMA table_info(url_patterns)"
    )

    pattern_columns = [
        row[1]
        for row in cursor.fetchall()
    ]

    if "language_code" not in pattern_columns:
        cursor.execute(
            """
            ALTER TABLE url_patterns
            ADD COLUMN language_code TEXT
            """
        )

    conn.commit()
    conn.close()


def get_dataset_metadata():

    conn = get_connection()

    try:

        metadata = pd.read_sql_query(
            """
            SELECT
                filename,
                file_date,
                updated_at,
                total_rows,
                updated_by
            FROM dataset_metadata
            WHERE id = 1
            """,
            conn
        )

        if metadata.empty:
            return None

        return metadata.iloc[0].to_dict()

    finally:

        conn.close()


def load_shared_dataset():

    conn = get_connection()

    try:

        df = pd.read_sql_query(
            """
            SELECT
                url_pattern,
                url_pattern_id,
                priority,
                language_code
            FROM url_patterns
            """,
            conn
        )

        if not df.empty:

            df["_url_pattern_length"] = (
                df["url_pattern"]
                .fillna("")
                .astype(str)
                .str.len()
            )

            df.sort_values(
                by="_url_pattern_length",
                ascending=False,
                inplace=True
            )

            df.drop(
                columns=["_url_pattern_length"],
                inplace=True
            )

            df.reset_index(
                drop=True,
                inplace=True
            )

        return df

    finally:

        conn.close()


def replace_shared_dataset(
    new_df,
    filename,
    file_date,
    updated_by
):

    conn = get_connection()

    try:

        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM url_patterns"
        )

        records = []

        for _, row in new_df.iterrows():

            url_pattern = row["url_pattern"]
            url_pattern_id = row["url_pattern_id"]
            priority = row["priority"]
            language_code = row["language_code"]

            records.append(
                (
                    None if pd.isna(url_pattern)
                    else str(url_pattern),

                    None if pd.isna(url_pattern_id)
                    else str(url_pattern_id),

                    None if pd.isna(priority)
                    else str(priority),

                    None if pd.isna(language_code)
                    else str(language_code)
                )
            )

        cursor.executemany(
            """
            INSERT INTO url_patterns (
                url_pattern,
                url_pattern_id,
                priority,
                language_code
            )
            VALUES (?, ?, ?, ?)
            """,
            records
        )

        updated_at = datetime.now().strftime(
            "%d-%m-%Y %I:%M:%S %p"
        )

        file_date_string = ""

        if file_date is not None:

            file_date_string = file_date.strftime(
                "%d-%m-%Y"
            )

        cursor.execute(
            """
            INSERT INTO dataset_metadata (
                id,
                filename,
                file_date,
                updated_at,
                total_rows,
                updated_by
            )
            VALUES (
                1,
                ?,
                ?,
                ?,
                ?,
                ?
            )
            ON CONFLICT(id)
            DO UPDATE SET
                filename = excluded.filename,
                file_date = excluded.file_date,
                updated_at = excluded.updated_at,
                total_rows = excluded.total_rows,
                updated_by = excluded.updated_by
            """,
            (
                filename,
                file_date_string,
                updated_at,
                len(new_df),
                str(updated_by).strip()
                if updated_by
                else "Unknown"
            )
        )

        conn.commit()

    finally:

        conn.close()


# =============================================================
# INITIALIZE DATABASE
# =============================================================

initialize_database()


# =============================================================
# USER AUTHENTICATION
# =============================================================

def get_app_users():

    users = {}

    for secrets_key in [
        "users",
        "USERS"
    ]:

        try:

            configured_users = st.secrets[
                secrets_key
            ]

            users.update(
                {
                    str(username).strip().lower(): str(password)
                    for username, password
                    in configured_users.items()
                    if str(username).strip()
                }
            )

        except Exception:
            pass

    environment_users = os.environ.get(
        "APP_USERS_JSON",
        ""
    )

    if environment_users:

        try:

            parsed_users = json.loads(
                environment_users
            )

            if isinstance(parsed_users, dict):

                users.update(
                    {
                        str(username).strip().lower(): str(password)
                        for username, password
                        in parsed_users.items()
                        if str(username).strip()
                    }
                )

        except (TypeError, ValueError):
            pass

    try:

        legacy_password = st.secrets[
            "ADMIN_PASSWORD"
        ]

    except Exception:

        legacy_password = os.environ.get(
            "ADMIN_PASSWORD",
            ""
        )

    if legacy_password and "admin" not in users:
        users["admin"] = str(legacy_password)

    return users


def admin_login():

    if st.session_state.get(
        "admin_authenticated",
        False
    ):
        return True

    st.subheader("🔐 User Login")

    configured_users = get_app_users()

    if not configured_users:

        st.error(
            "No user accounts are configured. Add a [users] "
            "section to .streamlit/secrets.toml."
        )

        return False

    with st.form(
        "user_login_form",
        clear_on_submit=False
    ):

        username = st.text_input(
            "Username",
            key="login_username"
        )

        password = st.text_input(
            "Password",
            type="password",
            key="login_password"
        )

        login_submitted = st.form_submit_button(
            "Login",
            use_container_width=True
        )

    if login_submitted:

        normalized_username = (
            username.strip().lower()
        )

        correct_password = configured_users.get(
            normalized_username
        )

        if (
            correct_password is not None
            and hmac.compare_digest(
                str(password).encode("utf-8"),
                str(correct_password).encode("utf-8")
            )
        ):

            st.session_state[
                "admin_authenticated"
            ] = True

            st.session_state[
                "authenticated_username"
            ] = normalized_username

            st.success(
                "✅ Login successful."
            )

            st.rerun()

        else:

            st.error(
                "❌ Incorrect username or password."
            )

    return False


# =============================================================
# LOGOUT / USER HEADER
# =============================================================

def render_user_header():

    if not st.session_state.get(
        "admin_authenticated",
        False
    ):
        return

    user_col, logout_col = st.columns(
        [8, 1]
    )

    with user_col:

        st.caption(
            "🟢 Signed in as "
            f"{st.session_state.get('authenticated_username', 'admin').title()}"
        )

    with logout_col:

        if st.button(
            "Logout",
            use_container_width=True
        ):

            st.session_state[
                "admin_authenticated"
            ] = False

            for login_key in [
                "authenticated_username",
                "login_username",
                "login_password"
            ]:

                st.session_state.pop(
                    login_key,
                    None
                )

            st.rerun()


# =============================================================
# FILE DATE FUNCTIONS
# =============================================================

def extract_file_date(filename):

    match = re.search(
        r"(\d{2}-\d{2}-\d{4})",
        filename
    )

    if not match:
        return None

    date_string = match.group(1)

    try:

        return datetime.strptime(
            date_string,
            "%d-%m-%Y"
        )

    except ValueError:

        return None


def validate_file_date(filename):

    file_date = extract_file_date(
        filename
    )

    current_date = datetime.now().date()

    if file_date is None:

        return {
            "date_found": None,
            "current_date": current_date,
            "is_match": False,
            "difference_days": None,
            "date_missing": True
        }

    file_date_only = file_date.date()

    difference_days = (
        current_date
        - file_date_only
    ).days

    return {
        "date_found": file_date_only,
        "current_date": current_date,
        "is_match": (
            file_date_only == current_date
        ),
        "difference_days": difference_days,
        "date_missing": False
    }


# =============================================================
# FILE PARSER
# =============================================================

def parse_uploaded_file(uploaded_file):

    df = None
    last_error_msg = ""

    # =========================================================
    # STRATEGY 1: BINARY XLS
    # =========================================================

    try:

        uploaded_file.seek(0)

        df = pd.read_excel(
            uploaded_file,
            engine="xlrd",
            header=None
        )

    except Exception as excel_err:

        last_error_msg = str(
            excel_err
        )

        # =====================================================
        # STRATEGY 2: TSV
        # =====================================================

        if (
            "Expected BOF record" in last_error_msg
            or "b'\\xff\\xfe'" in last_error_msg
            or "tsv" in last_error_msg.lower()
        ):

            try:

                uploaded_file.seek(0)

                raw_content = (
                    uploaded_file
                    .read()
                    .decode("utf-16")
                )

                lines = raw_content.splitlines()

                raw_rows = [
                    line.split("\t")
                    for line in lines
                    if line.strip()
                ]

                row_lengths = [
                    len(row)
                    for row in raw_rows
                ]

                if row_lengths:

                    standard_cols = max(
                        set(row_lengths),
                        key=row_lengths.count
                    )

                else:

                    standard_cols = 0

                aligned_rows = []

                for row_list in raw_rows:

                    while (
                        row_list
                        and row_list[-1] == ""
                    ):

                        row_list.pop()

                    if len(row_list) > standard_cols:

                        row_list = row_list[
                            :standard_cols
                        ]

                    while len(row_list) < standard_cols:

                        row_list.append("")

                    aligned_rows.append(
                        row_list
                    )

                if aligned_rows:

                    df = pd.DataFrame(
                        aligned_rows
                    )

            except Exception as tsv_err:

                last_error_msg = (
                    "TSV Flow Realignment Error: "
                    f"{tsv_err}"
                )

        # =====================================================
        # STRATEGY 3: HTML
        # =====================================================

        if df is None:

            try:

                uploaded_file.seek(0)

                html_tables = pd.read_html(
                    uploaded_file,
                    header=None
                )

                if html_tables:

                    df = html_tables[0]

            except Exception as html_err:

                last_error_msg = (
                    "HTML Parse Error: "
                    f"{html_err}"
                )

    # =========================================================
    # COMPLETE FAILURE
    # =========================================================

    if df is None:

        raise ValueError(
            "Failed to parse file.\n\n"
            f"Diagnostic Details: "
            f"{last_error_msg}"
        )

    # =========================================================
    # HEADER DETECTION
    # =========================================================

    header_row_idx = None

    for idx, row in df.iterrows():

        row_str_values = [
            str(value).strip().lower()
            for value in row.values
        ]

        if "url_pattern" in row_str_values:

            header_row_idx = idx
            break

    # =========================================================
    # APPLY HEADER
    # =========================================================

    if header_row_idx is not None:

        df.columns = [
            str(col).strip()
            for col in df.iloc[
                header_row_idx
            ]
        ]

        df = df.iloc[
            header_row_idx + 1:
        ].reset_index(drop=True)

    else:

        df.columns = [
            str(col).strip()
            for col in df.iloc[0]
        ]

        df = df.iloc[
            1:
        ].reset_index(drop=True)

    # =========================================================
    # REQUIRED COLUMNS
    # =========================================================

    required_targets = [
        "url_pattern",
        "url_pattern_id",
        "priority",
        "total_count",
        "language_code",
        "url_pattern_order"
    ]

    for col in required_targets:

        if col not in df.columns:
            df[col] = None

    # =========================================================
    # CLEAN NULL VALUES
    # =========================================================

    df = (
        df
        .replace(
            r"^\s*$",
            None,
            regex=True
        )
        .replace(
            ["None", "nan", "NaN"],
            None
        )
    )

    # =========================================================
    # TARGETED ALIGNMENT SHIFT
    # =========================================================

    shifted_mask = (
        df["url_pattern_id"].isna()
        & df["total_count"].notna()
    )

    fixed_count = shifted_mask.sum()

    if fixed_count > 0:

        df.loc[
            shifted_mask,
            "url_pattern_id"
        ] = df.loc[
            shifted_mask,
            "total_count"
        ]

    shifted_language_mask = (
        pd.to_datetime(
            df["language_code"],
            errors="coerce"
        ).notna()
        & df["url_pattern_order"].notna()
    )

    fixed_language_count = (
        shifted_language_mask.sum()
    )

    if fixed_language_count > 0:

        df.loc[
            shifted_language_mask,
            "language_code"
        ] = df.loc[
            shifted_language_mask,
            "url_pattern_order"
        ]

    fixed_count += fixed_language_count

    # =========================================================
    # SELECT REQUIRED COLUMNS
    # =========================================================

    final_df = df[
        [
            "url_pattern",
            "url_pattern_id",
            "priority",
            "language_code"
        ]
    ].copy()

    # =========================================================
    # REMOVE DUPLICATES
    # =========================================================

    initial_len = len(final_df)

    final_df.drop_duplicates(
        inplace=True
    )

    duplicates_removed = (
        initial_len - len(final_df)
    )

    # =========================================================
    # SORT LONGEST → SHORTEST
    # =========================================================

    final_df[
        "_url_pattern_length"
    ] = (
        final_df[
            "url_pattern"
        ]
        .fillna("")
        .astype(str)
        .str.len()
    )

    final_df.sort_values(
        by="_url_pattern_length",
        ascending=False,
        inplace=True
    )

    final_df.drop(
        columns=["_url_pattern_length"],
        inplace=True
    )

    final_df.reset_index(
        drop=True,
        inplace=True
    )

    return (
        final_df,
        fixed_count,
        duplicates_removed
    )


# =============================================================
# SEARCH NORMALIZATION
# =============================================================

def normalize_search_text(text):

    text = str(text)

    text = unquote(text)

    text = text.replace(
        "+",
        " "
    )

    text = re.sub(
        r"[-_/\\*]+",
        " ",
        text
    )

    text = re.sub(
        r"[^a-zA-Z0-9\s]",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip().lower()


# =============================================================
# DOMAIN - BASIS SPLIT
# =============================================================

def split_domain_basis(pattern):

    pattern = str(
        pattern
    ).strip()

    if "*" not in pattern:
        return pattern, ""

    unwrapped_pattern = pattern.strip("*")

    domain, basis = unwrapped_pattern.split(
        "*",
        1
    )

    return (
        domain.strip(),
        basis.strip("*").strip()
    )


# =============================================================
# COVERAGE REPORT FUNCTIONS
# =============================================================

def normalize_domain(value):

    value = unquote(
        str(value)
    ).strip().lower()

    value = re.sub(
        r"^[~*.]+",
        "",
        value
    )

    parsed = urlsplit(
        value
        if "://" in value
        else f"//{value}",
        scheme="https"
    )

    hostname = (
        parsed.hostname
        or value.split("/")[0]
    )

    hostname = hostname.split(":")[0].strip(".")

    if hostname.startswith("www."):
        hostname = hostname[4:]

    return hostname


def get_url_parts(url):

    raw_url = str(url).strip()

    parsed = urlsplit(
        raw_url
        if "://" in raw_url
        else f"https://{raw_url}"
    )

    hostname = normalize_domain(
        parsed.hostname or ""
    )

    searchable_content = " ".join(
        [
            parsed.path,
            parsed.query,
            parsed.fragment
        ]
    )

    return (
        hostname,
        normalize_search_text(
            searchable_content
        )
    )


def domains_match(
    url_domain,
    pattern_domain
):

    if not url_domain or not pattern_domain:
        return False

    return (
        url_domain == pattern_domain
        or url_domain.endswith(
            f".{pattern_domain}"
        )
    )


def make_basis_catalog(pattern_df):

    catalog_rows = []

    for _, row in pattern_df.iterrows():

        domain, basis = split_domain_basis(
            row["url_pattern"]
        )

        normalized_domain = normalize_domain(
            domain
        )

        normalized_basis = normalize_search_text(
            basis
        )

        language_code = str(
            row.get(
                "language_code",
                ""
            )
        ).strip().lower()

        if (
            not normalized_domain
            or not normalized_basis
            or not language_code
            or language_code in {"none", "nan"}
        ):
            continue

        catalog_rows.append(
            {
                "domain": domain,
                "normalized_domain": normalized_domain,
                "basis": basis,
                "normalized_basis": normalized_basis,
                "language_code": language_code,
                "url_pattern_id": row["url_pattern_id"],
                "priority": row["priority"]
            }
        )

    if not catalog_rows:

        return pd.DataFrame(
            columns=[
                "domain",
                "normalized_domain",
                "basis",
                "normalized_basis",
                "language_code",
                "url_pattern_id",
                "priority"
            ]
        )

    catalog = pd.DataFrame(
        catalog_rows
    )

    catalog = (
        catalog
        .groupby(
            [
                "language_code",
                "normalized_basis"
            ],
            dropna=False,
            as_index=False
        )
        .agg(
            {
                "basis": "first",

                "domain": lambda values: ", ".join(
                    sorted(
                        {
                            str(value)
                            for value in values
                            if pd.notna(value)
                            and str(value).strip()
                        }
                    )
                ),

                "normalized_domain": "first",

                "url_pattern_id": lambda values: ", ".join(
                    sorted(
                        {
                            str(value)
                            for value in values
                            if pd.notna(value)
                            and str(value).strip()
                        }
                    )
                ),

                "priority": lambda values: ", ".join(
                    sorted(
                        {
                            str(value)
                            for value in values
                            if pd.notna(value)
                            and str(value).strip()
                        }
                    )
                )
            }
        )
    )

    catalog.sort_values(
        by="normalized_basis",
        key=lambda series: series.str.len(),
        ascending=False,
        inplace=True
    )

    return catalog.reset_index(
        drop=True
    )


def word_forms_match(
    first_word,
    second_word
):

    def word_forms(word):

        forms = {word}

        if len(word) > 3 and word.endswith("ies"):
            forms.add(
                f"{word[:-3]}y"
            )

        if len(word) > 3 and word.endswith("es"):

            forms.add(
                word[:-2]
            )

            forms.add(
                word[:-1]
            )

        if (
            len(word) > 3
            and word.endswith("s")
            and not word.endswith("ss")
        ):

            forms.add(
                word[:-1]
            )

        return forms

    return bool(
        word_forms(first_word)
        & word_forms(second_word)
    )


def basis_matches_url(
    normalized_basis,
    searchable_url
):

    basis_words = normalized_basis.split()
    url_words = searchable_url.split()

    if (
        not basis_words
        or len(basis_words) > len(url_words)
    ):
        return False

    window_length = len(basis_words)

    for start in range(
        len(url_words) - window_length + 1
    ):

        url_window = url_words[
            start:start + window_length
        ]

        if all(
            word_forms_match(
                basis_word,
                url_word
            )
            for basis_word, url_word
            in zip(
                basis_words,
                url_window
            )
        ):

            return True

    return False


def coerce_metric(series):

    cleaned = (
        series
        .fillna(0)
        .astype(str)
        .str.strip()
        .str.replace(
            ",",
            "",
            regex=False
        )
        .str.replace(
            r"[^0-9.\-()]",
            "",
            regex=True
        )
        .str.replace(
            r"^\((.*)\)$",
            r"-\1",
            regex=True
        )
    )

    return pd.to_numeric(
        cleaned,
        errors="coerce"
    ).fillna(0)


def read_coverage_csv(uploaded_file):

    last_error = None

    for encoding in [
        "utf-8-sig",
        "utf-16",
        "latin-1"
    ]:

        try:

            uploaded_file.seek(0)

            return pd.read_csv(
                uploaded_file,
                encoding=encoding,
                sep=None,
                engine="python"
            )

        except Exception as err:

            last_error = err

    raise ValueError(
        f"Unable to read the CSV file: {last_error}"
    )


def find_suggested_column(
    columns,
    candidates
):

    normalized_columns = {
        re.sub(
            r"[^a-z0-9]",
            "",
            str(column).lower()
        ): column
        for column in columns
    }

    for candidate in candidates:

        normalized_candidate = re.sub(
            r"[^a-z0-9]",
            "",
            candidate.lower()
        )

        if normalized_candidate in normalized_columns:

            return normalized_columns[
                normalized_candidate
            ]

    for (
        normalized_column,
        original_column
    ) in normalized_columns.items():

        if any(
            re.sub(
                r"[^a-z0-9]",
                "",
                candidate.lower()
            ) in normalized_column
            for candidate in candidates
        ):

            return original_column

    return None


def remove_report_total_rows(
    input_df
):

    if (
        input_df is None
        or "URL" not in input_df.columns
    ):

        return input_df, 0

    excluded_values = {
        "grand total",
        "report total",
        "stripped url (others)",
        "report total<br>stripped url (others)",
        "report total<br/>stripped url (others)",
        "report total<br />stripped url (others)"
    }

    excluded_mask = (
        input_df["URL"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
        .isin(excluded_values)
    )

    return (
        input_df.loc[
            ~excluded_mask
        ].copy(),
        int(
            excluded_mask.sum()
        )
    )


def create_coverage_report(
    input_df,
    basis_catalog
):

    detail_rows = []
    url_rows = []

    selected_language = str(
        basis_catalog[
            "language_code"
        ].iloc[0]
    )

    input_df, _ = remove_report_total_rows(
        input_df
    )

    input_df = input_df.copy()

    input_df["URL"] = (
        input_df["URL"]
        .astype(str)
        .str.strip()
    )

    input_df = (
        input_df
        .groupby(
            "URL",
            as_index=False,
            sort=False
        )
        .agg(
            {
                "Keyword Impressions": "sum",
                "Revenue": "sum"
            }
        )
    )

    for _, input_row in input_df.iterrows():

        url = str(
            input_row["URL"]
        ).strip()

        impressions = input_row[
            "Keyword Impressions"
        ]

        revenue = input_row[
            "Revenue"
        ]

        url_domain, searchable_url = get_url_parts(
            url
        )

        matches = basis_catalog[
            basis_catalog[
                "normalized_basis"
            ].apply(
                lambda basis:
                    basis_matches_url(
                        basis,
                        searchable_url
                    )
            )
        ]

        if matches.empty:

            detail_rows.append(
                {
                    "URL": url,
                    "URL Domain": url_domain,
                    "Language Code": selected_language,
                    "Coverage Status": "No Matching Basis",
                    "Matching Basis": "No Matching Basis",
                    "Source Pattern Domain(s)": "",
                    "URL Pattern ID": "",
                    "Priority": "",
                    "Keyword Impressions": impressions,
                    "Revenue": revenue
                }
            )

            url_rows.append(
                {
                    "URL": url,
                    "URL Domain": url_domain,
                    "Language Code": selected_language,
                    "Coverage Status": "No Matching Basis",
                    "Matched Basis Count": 0,
                    "Matching Bases": "No Matching Basis",
                    "Keyword Impressions": impressions,
                    "Revenue": revenue
                }
            )

            continue

        matched_bases = []

        for _, match in matches.iterrows():

            matched_bases.append(
                str(match["basis"])
            )

            detail_rows.append(
                {
                    "URL": url,
                    "URL Domain": url_domain,
                    "Language Code": match["language_code"],
                    "Coverage Status": "Covered",
                    "Matching Basis": match["basis"],
                    "Source Pattern Domain(s)": match["domain"],
                    "URL Pattern ID": match["url_pattern_id"],
                    "Priority": match["priority"],
                    "Keyword Impressions": impressions,
                    "Revenue": revenue
                }
            )

        url_rows.append(
            {
                "URL": url,
                "URL Domain": url_domain,
                "Language Code": selected_language,
                "Coverage Status": "Covered",
                "Matched Basis Count": len(matches),
                "Matching Bases": " | ".join(
                    matched_bases
                ),
                "Keyword Impressions": impressions,
                "Revenue": revenue
            }
        )

    detail_df = pd.DataFrame(
        detail_rows
    )

    url_summary_df = pd.DataFrame(
        url_rows
    )

    coverage_pivot = (
        url_summary_df
        .groupby(
            [
                "Language Code",
                "Coverage Status"
            ],
            as_index=False,
            dropna=False
        )
        .agg(
            URLs=("URL", "count"),
            Keyword_Impressions=(
                "Keyword Impressions",
                "sum"
            ),
            Revenue=(
                "Revenue",
                "sum"
            )
        )
        .rename(
            columns={
                "Keyword_Impressions":
                    "Keyword Impressions"
            }
        )
    )

    covered_detail = detail_df[
        detail_df[
            "Coverage Status"
        ] == "Covered"
    ]

    if covered_detail.empty:

        basis_pivot = pd.DataFrame(
            columns=[
                "Language Code",
                "URL Domain",
                "Matching Basis",
                "URLs",
                "Keyword Impressions",
                "Revenue"
            ]
        )

    else:

        basis_pivot = (
            covered_detail
            .groupby(
                [
                    "Language Code",
                    "URL Domain",
                    "Matching Basis"
                ],
                as_index=False,
                dropna=False
            )
            .agg(
                URLs=("URL", "nunique"),
                Keyword_Impressions=(
                    "Keyword Impressions",
                    "sum"
                ),
                Revenue=(
                    "Revenue",
                    "sum"
                )
            )
            .rename(
                columns={
                    "Keyword_Impressions":
                        "Keyword Impressions"
                }
            )
            .sort_values(
                by=[
                    "Revenue",
                    "Keyword Impressions",
                    "URLs"
                ],
                ascending=False
            )
        )

    return (
        url_summary_df,
        detail_df,
        coverage_pivot,
        basis_pivot
    )


def render_coverage_report(
    final_df
):

    st.subheader(
        "🧭 URL Coverage Report"
    )

    st.write(
        "Check URLs against bases from the active global pattern "
        "dataset. Matching is global and does not compare domains. "
        "A basis matches when its normalized words appear together "
        "in the URL path, including common singular/plural variations."
    )

    if final_df.empty:

        st.warning(
            "⚠️ Upload a shared global pattern dataset before "
            "creating a coverage report."
        )

        return

    complete_basis_catalog = make_basis_catalog(
        final_df
    )

    if complete_basis_catalog.empty:

        st.warning(
            "⚠️ The active dataset has no usable language-basis rows."
        )

        return

    available_languages = sorted(
        complete_basis_catalog[
            "language_code"
        ]
        .dropna()
        .astype(str)
        .str.strip()
        .loc[
            lambda values:
                values.ne("")
        ]
        .unique()
        .tolist()
    )

    if not available_languages:

        st.warning(
            "⚠️ No language codes are available "
            "in the active dataset."
        )

        return

    selected_language = st.selectbox(
        "Language code",
        available_languages,
        format_func=lambda value:
            value.upper(),
        key="coverage_language_code",
        help=(
            "Only bases with this language code will be "
            "checked against the submitted URLs."
        )
    )

    basis_catalog = complete_basis_catalog[
        complete_basis_catalog[
            "language_code"
        ] == selected_language
    ].copy()

    st.caption(
        f"{len(basis_catalog):,} unique bases are "
        f"available for language "
        f"{selected_language.upper()}."
    )

    input_type = st.radio(
        "Input type",
        [
            "Paste URLs",
            "Upload CSV With Performance"
        ],
        horizontal=True,
        key="coverage_input_type"
    )

    prepared_input = None

    if input_type == "Paste URLs":

        pasted_urls = st.text_area(
            "URLs",
            placeholder=(
                "https://example.com/topic-one\n"
                "https://example.com/topic-two"
            ),
            height=180,
            key="coverage_urls"
        )

        urls = [
            value.strip()
            for value in re.split(
                r"[\n,]+",
                pasted_urls
            )
            if value.strip()
        ]

        urls = list(
            dict.fromkeys(urls)
        )

        if urls:

            prepared_input = pd.DataFrame(
                {
                    "URL": urls,
                    "Keyword Impressions": 0,
                    "Revenue": 0.0
                }
            )

    else:

        performance_file = st.file_uploader(
            "Upload CSV",
            type=["csv"],
            accept_multiple_files=False,
            key="coverage_csv"
        )

        if performance_file is not None:

            try:

                source_df = read_coverage_csv(
                    performance_file
                )

                if source_df.empty:

                    st.warning(
                        "The uploaded CSV has no data rows."
                    )

                else:

                    columns = list(
                        source_df.columns
                    )

                    suggested_url = find_suggested_column(
                        columns,
                        [
                            "url",
                            "urls",
                            "page url",
                            "page"
                        ]
                    )

                    suggested_impressions = find_suggested_column(
                        columns,
                        [
                            "keyword impressions",
                            "impressions",
                            "keyword_impressions"
                        ]
                    )

                    suggested_revenue = find_suggested_column(
                        columns,
                        [
                            "revenue",
                            "keyword revenue",
                            "earnings"
                        ]
                    )

                    mapping1, mapping2, mapping3 = (
                        st.columns(3)
                    )

                    with mapping1:

                        url_column = st.selectbox(
                            "URL column",
                            columns,
                            index=(
                                columns.index(
                                    suggested_url
                                )
                                if suggested_url in columns
                                else 0
                            ),
                            key="coverage_url_column"
                        )

                    optional_columns = [
                        "None"
                    ] + columns

                    with mapping2:

                        impressions_column = st.selectbox(
                            "Keyword impressions column",
                            optional_columns,
                            index=(
                                optional_columns.index(
                                    suggested_impressions
                                )
                                if suggested_impressions
                                in columns
                                else 0
                            ),
                            key="coverage_impressions_column"
                        )

                    with mapping3:

                        revenue_column = st.selectbox(
                            "Revenue column",
                            optional_columns,
                            index=(
                                optional_columns.index(
                                    suggested_revenue
                                )
                                if suggested_revenue
                                in columns
                                else 0
                            ),
                            key="coverage_revenue_column"
                        )

                    prepared_input = pd.DataFrame(
                        {
                            "URL":
                                source_df[
                                    url_column
                                ]
                        }
                    )

                    prepared_input[
                        "Keyword Impressions"
                    ] = (
                        coerce_metric(
                            source_df[
                                impressions_column
                            ]
                        )
                        if impressions_column != "None"
                        else 0
                    )

                    prepared_input[
                        "Revenue"
                    ] = (
                        coerce_metric(
                            source_df[
                                revenue_column
                            ]
                        )
                        if revenue_column != "None"
                        else 0.0
                    )

                    prepared_input = (
                        prepared_input[
                            prepared_input["URL"].notna()
                            & prepared_input["URL"]
                            .astype(str)
                            .str.strip()
                            .ne("")
                        ]
                        .copy()
                    )

            except Exception as err:

                st.error(
                    f"❌ Could not read the CSV: {err}"
                )

    removed_total_rows = 0

    if prepared_input is not None:

        prepared_input, removed_total_rows = (
            remove_report_total_rows(
                prepared_input
            )
        )

    if removed_total_rows:

        st.info(
            f"Removed {removed_total_rows:,} summary row(s): "
            "Grand Total, Report Total, or Stripped URL (Others)."
        )

    if st.button(
        "Create Coverage Report",
        type="primary",
        use_container_width=True,
        disabled=(
            prepared_input is None
            or prepared_input.empty
        )
    ):

        with st.spinner(
            "Checking URL coverage..."
        ):

            st.session_state[
                "coverage_report"
            ] = create_coverage_report(
                prepared_input,
                basis_catalog
            )

            st.session_state[
                "coverage_report_language"
            ] = selected_language

    report = st.session_state.get(
        "coverage_report"
    )

    if (
        st.session_state.get(
            "coverage_report_language"
        ) != selected_language
    ):

        report = None

    if report is None:
        return

    (
        url_summary_df,
        detail_df,
        coverage_pivot,
        basis_pivot
    ) = report

    total_urls = len(
        url_summary_df
    )

    covered_urls = int(
        (
            url_summary_df[
                "Coverage Status"
            ] == "Covered"
        ).sum()
    )

    uncovered_urls = (
        total_urls - covered_urls
    )

    coverage_rate = (
        covered_urls
        / total_urls
        * 100
        if total_urls
        else 0
    )

    metric1, metric2, metric3, metric4 = (
        st.columns(4)
    )

    metric1.metric(
        "URLs Checked",
        f"{total_urls:,}"
    )

    metric2.metric(
        "Covered URLs",
        f"{covered_urls:,}"
    )

    metric3.metric(
        "No Matching Basis",
        f"{uncovered_urls:,}"
    )

    metric4.metric(
        "Coverage Rate",
        f"{coverage_rate:.1f}%"
    )

    summary_tab, basis_tab, url_tab, detail_tab = (
        st.tabs(
            [
                "Coverage Summary",
                "Basis Performance",
                "URL Summary",
                "Match Details"
            ]
        )
    )

    with summary_tab:

        st.dataframe(
            coverage_pivot,
            use_container_width=True,
            hide_index=True
        )

    with basis_tab:

        st.dataframe(
            basis_pivot,
            use_container_width=True,
            hide_index=True
        )

        st.caption(
            "When one URL matches multiple bases, its performance "
            "is attributed to each matching basis. Use URL Summary "
            "for non-duplicated totals."
        )

    with url_tab:

        st.dataframe(
            url_summary_df,
            use_container_width=True,
            hide_index=True
        )

    with detail_tab:

        st.dataframe(
            detail_df,
            use_container_width=True,
            hide_index=True
        )

    download1, download2, download3 = (
        st.columns(3)
    )

    download1.download_button(
        "Download URL Summary",
        data=url_summary_df.to_csv(
            index=False
        ),
        file_name="coverage_url_summary.csv",
        mime="text/csv",
        use_container_width=True
    )

    download2.download_button(
        "Download Basis Report",
        data=basis_pivot.to_csv(
            index=False
        ),
        file_name="coverage_basis_report.csv",
        mime="text/csv",
        use_container_width=True
    )

    download3.download_button(
        "Download Match Details",
        data=detail_df.to_csv(
            index=False
        ),
        file_name="coverage_match_details.csv",
        mime="text/csv",
        use_container_width=True
    )


# =============================================================
# CONCATENATE / PATTERN GENERATOR PAGE
# =============================================================

def concatenate_sheet_page():

    st.header(
        "🔗 Pattern Generator"
    )

    st.write(
        "Enter multiple domains and multiple bases. "
        "Every domain will be combined with every basis."
    )

    col1, col2 = st.columns(2)

    with col1:

        domains_input = st.text_area(
            "Domains",
            placeholder=(
                "domain1.com\n"
                "domain2.com\n"
                "domain3.com"
            ),
            height=200,
            key="generator_domains"
        )

    with col2:

        basis_input = st.text_area(
            "Basis",
            placeholder=(
                "labor day\n"
                "hair shampoo\n"
                "italian restaurants"
            ),
            height=200,
            key="generator_basis"
        )

    if st.button(
        "Generate Patterns",
        type="primary",
        use_container_width=True
    ):

        domains = [
            x.strip()
            for x in domains_input.splitlines()
            if x.strip()
        ]

        basis = [
            x.strip()
            for x in basis_input.splitlines()
            if x.strip()
        ]

        if not domains:

            st.warning(
                "Please enter at least one domain."
            )

        elif not basis:

            st.warning(
                "Please enter at least one basis."
            )

        else:

            results = []

            # =================================================
            # EVERY DOMAIN × EVERY BASIS
            # =================================================
            for domain, b in zip(domains, basis):
                results.append(f"*{domain}*{b}*")
                    

            result_text = "\n".join(
                results
            )

            st.success(
                f"Generated {len(results):,} pattern(s)."
            )

            st.text_area(
                "Generated Patterns",
                value=result_text,
                height=300,
                key="generated_patterns"
            )

            st.download_button(
                "📥 Download Generated Patterns",
                data=result_text,
                file_name="generated_patterns.txt",
                mime="text/plain",
                use_container_width=True
            )


# =============================================================
# COVERAGE REPORT PAGE
# =============================================================

def coverage_report_page():

    st.header(
        "🧭 Coverage Report"
    )

    final_df = load_shared_dataset()

    render_coverage_report(
        final_df
    )

    st.write("---")

    st.caption(
        "📊 Shared URL Pattern Database • "
        "Coverage uses the current active dataset."
    )


# =============================================================
# GLOBAL PATTERN DASHBOARD PAGE
# =============================================================

def global_pattern_dashboard_page():

    # =========================================================
    # CURRENT DATASET
    # =========================================================

    metadata = get_dataset_metadata()

    final_df = load_shared_dataset()

    st.subheader(
        "📌 Current Shared Dataset"
    )

    if metadata is None:

        st.warning(
            "⚠️ No dataset has been uploaded yet."
        )

    else:

        info1, info2, info3, info4, info5 = (
            st.columns(5)
        )

        with info1:

            st.metric(
                "Total Patterns",
                f"{metadata['total_rows']:,}"
            )

        with info2:

            st.metric(
                "Dataset Date",
                metadata["file_date"]
                if metadata["file_date"]
                else "Unknown"
            )

        with info3:

            st.metric(
                "Last Updated",
                metadata["updated_at"]
            )

        with info4:

            st.metric(
                "Updated By",
                metadata["updated_by"].title()
                if metadata.get("updated_by")
                else "Unknown"
            )

        with info5:

            st.metric(
                "Source File",
                metadata["filename"]
            )

    # =========================================================
    # ADMIN DATASET UPDATE
    # =========================================================

    if st.session_state.get(
        "admin_authenticated",
        False
    ):

        with st.expander(
            "⚙️ Update Shared Dataset",
            expanded=False
        ):

            new_file = st.file_uploader(
                "Upload new .xls file",
                type=["xls"],
                accept_multiple_files=False,
                key="admin_file_uploader"
            )

            if new_file is not None:

                # =================================================
                # DATE VALIDATION
                # =================================================

                date_validation = (
                    validate_file_date(
                        new_file.name
                    )
                )

                st.write(
                    f"**Selected file:** "
                    f"`{new_file.name}`"
                )

                if date_validation[
                    "date_missing"
                ]:

                    st.error(
                        "🚨 No valid date was found "
                        "in the filename."
                    )

                    st.info(
                        "Expected a date in "
                        "`DD-MM-YYYY` format.\n\n"
                        "Example:\n"
                        "`Global_Pattern_All_27-08-2026_xxxxx.xls`"
                    )

                    date_confirmed = st.checkbox(
                        "I have manually verified the file date.",
                        key="manual_date_confirmation"
                    )

                elif date_validation[
                    "is_match"
                ]:

                    file_date = (
                        date_validation[
                            "date_found"
                        ]
                    )

                    current_date = (
                        date_validation[
                            "current_date"
                        ]
                    )

                    st.success(
                        "✅ File date matches today's date."
                    )

                    date_col1, date_col2 = (
                        st.columns(2)
                    )

                    with date_col1:

                        st.write(
                            "**File Date**"
                        )

                        st.write(
                            file_date.strftime(
                                "%d-%m-%Y"
                            )
                        )

                    with date_col2:

                        st.write(
                            "**Current Date**"
                        )

                        st.write(
                            current_date.strftime(
                                "%d-%m-%Y"
                            )
                        )

                    date_confirmed = True

                else:

                    file_date = (
                        date_validation[
                            "date_found"
                        ]
                    )

                    current_date = (
                        date_validation[
                            "current_date"
                        ]
                    )

                    difference_days = (
                        date_validation[
                            "difference_days"
                        ]
                    )

                    st.error(
                        "🚨 DATE MISMATCH DETECTED!"
                    )

                    date_col1, date_col2, date_col3 = (
                        st.columns(3)
                    )

                    with date_col1:

                        st.metric(
                            "File Date",
                            file_date.strftime(
                                "%d-%m-%Y"
                            )
                        )

                    with date_col2:

                        st.metric(
                            "Current Date",
                            current_date.strftime(
                                "%d-%m-%Y"
                            )
                        )

                    with date_col3:

                        if difference_days > 0:

                            st.metric(
                                "File Age",
                                f"{difference_days} day(s)"
                            )

                        else:

                            st.metric(
                                "Difference",
                                f"{abs(difference_days)} day(s)"
                            )

                    if difference_days > 0:

                        st.warning(
                            f"⚠️ The uploaded dataset is "
                            f"{difference_days} day(s) older "
                            f"than today's date."
                        )

                    elif difference_days < 0:

                        st.warning(
                            f"⚠️ The uploaded dataset is "
                            f"{abs(difference_days)} day(s) "
                            f"in the future."
                        )

                    st.write(
                        "Please verify that this is the "
                        "correct dataset before continuing."
                    )

                    date_confirmed = st.checkbox(
                        "I have verified the date mismatch "
                        "and want to continue.",
                        key="date_mismatch_confirmation"
                    )

                # =================================================
                # PROCESS NEW FILE
                # =================================================

                if date_confirmed:

                    if st.button(
                        "🔍 Process & Preview New Dataset",
                        use_container_width=True
                    ):

                        try:

                            with st.spinner(
                                "⏳ Processing new dataset..."
                            ):

                                (
                                    preview_df,
                                    fixed_count,
                                    duplicates_removed
                                ) = parse_uploaded_file(
                                    new_file
                                )

                            st.session_state[
                                "pending_dataset"
                            ] = preview_df

                            st.session_state[
                                "pending_filename"
                            ] = new_file.name

                            st.session_state[
                                "pending_fixed_count"
                            ] = fixed_count

                            st.session_state[
                                "pending_duplicates"
                            ] = duplicates_removed

                            st.session_state[
                                "pending_date_validation"
                            ] = date_validation

                            st.success(
                                "✅ New dataset processed successfully."
                            )

                        except Exception as err:

                            st.error(
                                "❌ Failed to process file."
                            )

                            st.info(
                                f"Details: {err}"
                            )

                else:

                    st.info(
                        "🔒 Date verification is required "
                        "before the file can be processed."
                    )

    # =========================================================
    # PENDING DATASET PREVIEW
    # =========================================================

    if "pending_dataset" in st.session_state:

        st.write("---")

        st.subheader(
            "👀 New Dataset Preview"
        )

        pending_df = st.session_state[
            "pending_dataset"
        ]

        pending_filename = st.session_state[
            "pending_filename"
        ]

        pending_fixed_count = st.session_state[
            "pending_fixed_count"
        ]

        pending_duplicates = st.session_state[
            "pending_duplicates"
        ]

        pending_date_validation = (
            st.session_state.get(
                "pending_date_validation"
            )
        )

        preview1, preview2, preview3, preview4 = (
            st.columns(4)
        )

        with preview1:

            st.metric(
                "New Rows",
                f"{len(pending_df):,}"
            )

        with preview2:

            st.metric(
                "Duplicates Removed",
                f"{pending_duplicates:,}"
            )

        with preview3:

            st.metric(
                "Alignment Fixes",
                f"{pending_fixed_count:,}"
            )

        with preview4:

            if pending_date_validation:

                if pending_date_validation[
                    "date_found"
                ]:

                    st.metric(
                        "File Date",
                        pending_date_validation[
                            "date_found"
                        ].strftime(
                            "%d-%m-%Y"
                        )
                    )

                else:

                    st.metric(
                        "File Date",
                        "Not Found"
                    )

        st.write(
            f"**File:** `{pending_filename}`"
        )

        # =====================================================
        # DATE STATUS
        # =====================================================

        if pending_date_validation:

            if pending_date_validation[
                "date_missing"
            ]:

                st.error(
                    "🚨 No valid date was detected "
                    "in the filename. "
                    "The date was manually verified."
                )

            elif pending_date_validation[
                "is_match"
            ]:

                st.success(
                    "✅ Dataset date verified — "
                    "matches today's date."
                )

            else:

                file_date = (
                    pending_date_validation[
                        "date_found"
                    ]
                )

                current_date = (
                    pending_date_validation[
                        "current_date"
                    ]
                )

                difference_days = (
                    pending_date_validation[
                        "difference_days"
                    ]
                )

                st.warning(
                    f"⚠️ Date mismatch acknowledged. "
                    f"File date: "
                    f"{file_date.strftime('%d-%m-%Y')} | "
                    f"Current date: "
                    f"{current_date.strftime('%d-%m-%Y')} | "
                    f"Difference: "
                    f"{abs(difference_days)} day(s)"
                )

        # =====================================================
        # DATA PREVIEW
        # =====================================================

        st.write(
            "**First 100 rows:**"
        )

        st.dataframe(
            pending_df
            .head(100)
            .fillna(""),
            use_container_width=True,
            hide_index=True
        )

        st.warning(
            "⚠️ Confirming below will replace the "
            "current dataset for ALL users."
        )

        confirm = st.checkbox(
            "I understand that this will replace the current shared dataset.",
            key="confirm_dataset_replacement"
        )

        confirm_col1, confirm_col2 = (
            st.columns(2)
        )

        # =====================================================
        # REPLACE DATASET
        # =====================================================

        with confirm_col1:

            if st.button(
                "🚨 Replace Shared Dataset",
                disabled=not confirm,
                use_container_width=True
            ):

                try:

                    pending_file_date = None

                    if pending_date_validation:

                        pending_file_date = (
                            pending_date_validation[
                                "date_found"
                            ]
                        )

                    with st.spinner(
                        "⏳ Replacing shared dataset..."
                    ):

                        replace_shared_dataset(
                            pending_df,
                            pending_filename,
                            pending_file_date,
                            st.session_state.get(
                                "authenticated_username",
                                "Unknown"
                            )
                        )

                    keys_to_remove = [
                        "pending_dataset",
                        "pending_filename",
                        "pending_fixed_count",
                        "pending_duplicates",
                        "pending_date_validation",
                        "confirm_dataset_replacement",
                        "admin_file_uploader",
                        "manual_date_confirmation",
                        "date_mismatch_confirmation"
                    ]

                    for key in keys_to_remove:

                        st.session_state.pop(
                            key,
                            None
                        )

                    st.success(
                        "🎉 Shared dataset replaced successfully!"
                    )

                    st.rerun()

                except Exception as err:

                    st.error(
                        "❌ Failed to replace shared dataset."
                    )

                    st.info(
                        f"Details: {err}"
                    )

        # =====================================================
        # CANCEL UPDATE
        # =====================================================

        with confirm_col2:

            if st.button(
                "❌ Cancel Update",
                use_container_width=True
            ):

                keys_to_remove = [
                    "pending_dataset",
                    "pending_filename",
                    "pending_fixed_count",
                    "pending_duplicates",
                    "pending_date_validation",
                    "confirm_dataset_replacement",
                    "admin_file_uploader",
                    "manual_date_confirmation",
                    "date_mismatch_confirmation"
                ]

                for key in keys_to_remove:

                    st.session_state.pop(
                        key,
                        None
                    )

                st.rerun()

    # =========================================================
    # SEARCH
    # =========================================================

        # =========================================================
    # SEARCH
    # =========================================================

    st.write("---")

    st.subheader(
        "🔎 Search URL Patterns / IDs"
    )

    st.write(
        "Search one or multiple URL patterns or URL pattern IDs. "
        "Choose Exact Match for complete-value matching, "
        "or Normalized Search for flexible separator-independent matching."
    )

    # =========================================================
    # SEARCH MODE
    # =========================================================

    search_mode = st.radio(
        "Search Mode",
        [
            "Exact Match",
            "Normalized Search"
        ],
        horizontal=True,
        key="database_search_mode",
        help=(
            "Exact Match requires the complete URL pattern or URL pattern ID. "
            "Normalized Search ignores separators such as *, -, _, and /."
        )
    )

    # =========================================================
    # SEARCH INPUT
    # =========================================================

    search_string = st.text_area(
        "Search",
        placeholder=(
            "Examples:\n"
            "*example.com*bug*bite*\n"
            "1341291255\n"
            "bug bite"
        ),
        key="main_search"
    )

    # =========================================================
    # PROCESS SEARCH
    # =========================================================

    if search_string.strip():

        if final_df.empty:

            st.warning(
                "⚠️ There is currently no shared dataset."
            )

        else:

            # =================================================
            # SPLIT MULTIPLE SEARCH TERMS
            # =================================================

            search_terms = [
                term.strip()
                for term in re.split(
                    r"[,\n]+",
                    search_string
                )
                if term.strip()
            ]

            # Remove duplicate searches while preserving order
            search_terms = list(
                dict.fromkeys(
                    search_terms
                )
            )

            # =================================================
            # PREPARE DATABASE VALUES
            # =================================================

            raw_patterns = (
                final_df[
                    "url_pattern"
                ]
                .fillna("")
                .astype(str)
                .str.strip()
                .str.lower()
            )

            raw_ids = (
                final_df[
                    "url_pattern_id"
                ]
                .fillna("")
                .astype(str)
                .str.strip()
                .str.lower()
            )

            normalized_patterns = (
                final_df[
                    "url_pattern"
                ]
                .fillna("")
                .astype(str)
                .apply(
                    normalize_search_text
                )
            )

            # =================================================
            # INITIAL SEARCH MASK
            # =================================================

            combined_search_mask = pd.Series(
                False,
                index=final_df.index
            )

            matched_terms = {
                index: []
                for index in final_df.index
            }

            # =================================================
            # SEARCH EACH TERM
            # =================================================

            for search_term in search_terms:

                raw_search = (
                    str(search_term)
                    .strip()
                    .lower()
                )

                # =============================================
                # EXACT MATCH
                # =============================================

                if search_mode == "Exact Match":

                    pattern_mask = (
                        raw_patterns
                        == raw_search
                    )

                    id_mask = (
                        raw_ids
                        == raw_search
                    )

                # =============================================
                # NORMALIZED SEARCH
                # =============================================

                else:

                    normalized_search = (
                        normalize_search_text(
                            search_term
                        )
                    )

                    if normalized_search:

                        pattern_mask = (
                            normalized_patterns
                            .str.contains(
                                normalized_search,
                                case=False,
                                na=False,
                                regex=False
                            )
                        )

                    else:

                        pattern_mask = pd.Series(
                            False,
                            index=final_df.index
                        )

                    # ID search stays partial in normalized mode
                    id_mask = (
                        raw_ids
                        .str.contains(
                            raw_search,
                            case=False,
                            na=False,
                            regex=False
                        )
                    )

                # =============================================
                # COMBINE PATTERN + ID MATCH
                # =============================================

                term_mask = (
                    pattern_mask
                    | id_mask
                )

                combined_search_mask = (
                    combined_search_mask
                    | term_mask
                )

                # Track which search term matched each row
                for index in final_df.index[
                    term_mask
                ]:

                    matched_terms[
                        index
                    ].append(
                        search_term
                    )

            # =================================================
            # BUILD RESULTS
            # =================================================

            search_results = (
                final_df[
                    combined_search_mask
                ]
                .copy()
            )

            # =================================================
            # RESULTS FOUND
            # =================================================

            if not search_results.empty:

                st.success(
                    f"🔍 Found "
                    f"{len(search_results):,} "
                    f"matching result(s) for "
                    f"{len(search_terms)} search term(s) "
                    f"using {search_mode}."
                )

                # =============================================
                # RESULT VIEW
                # =============================================

                result_type = st.radio(
                    "Search Result View",
                    [
                        "Original",
                        "Domain - Basis Split"
                    ],
                    horizontal=True,
                    key="result_view"
                )

                # =============================================
                # ORIGINAL VIEW
                # =============================================

                if result_type == "Original":

                    st.dataframe(
                        search_results.fillna(""),
                        use_container_width=True,
                        hide_index=True
                    )

                    search_csv = (
                        search_results
                        .to_csv(
                            index=False,
                            encoding="utf-8"
                        )
                    )

                    filename_search = re.sub(
                        r"[^a-zA-Z0-9]+",
                        "_",
                        search_string
                    ).strip("_")

                    if not filename_search:

                        filename_search = (
                            "search_results"
                        )

                    # Keep filename manageable
                    filename_search = (
                        filename_search[:50]
                    )

                    st.download_button(
                        label=(
                            "📥 Download "
                            "Original Results"
                        ),
                        data=search_csv,
                        file_name=(
                            f"{filename_search}"
                            "_original.csv"
                        ),
                        mime="text/csv",
                        use_container_width=True
                    )

                # =============================================
                # DOMAIN - BASIS SPLIT VIEW
                # =============================================

                else:

                    split_results = []

                    for _, row in (
                        search_results
                        .iterrows()
                    ):

                        domain, basis = (
                            split_domain_basis(
                                row[
                                    "url_pattern"
                                ]
                            )
                        )

                        split_results.append(
                            {
                                "domain":
                                    domain,

                                "basis":
                                    basis,

                                "url_pattern_id":
                                    row[
                                        "url_pattern_id"
                                    ],

                                "priority":
                                    row[
                                        "priority"
                                    ],

                                "language_code":
                                    row[
                                        "language_code"
                                    ]
                            }
                        )

                    split_df = pd.DataFrame(
                        split_results
                    )

                    st.dataframe(
                        split_df.fillna(""),
                        use_container_width=True,
                        hide_index=True
                    )

                    split_csv = (
                        split_df
                        .to_csv(
                            index=False,
                            encoding="utf-8"
                        )
                    )

                    filename_search = re.sub(
                        r"[^a-zA-Z0-9]+",
                        "_",
                        search_string
                    ).strip("_")

                    if not filename_search:

                        filename_search = (
                            "search_results"
                        )

                    filename_search = (
                        filename_search[:50]
                    )

                    st.download_button(
                        label=(
                            "📥 Download "
                            "Domain - Basis Results"
                        ),
                        data=split_csv,
                        file_name=(
                            f"{filename_search}"
                            "_domain_basis.csv"
                        ),
                        mime="text/csv",
                        use_container_width=True
                    )

            # =================================================
            # NO RESULTS
            # =================================================

            else:

                if search_mode == "Exact Match":

                    st.warning(
                        "❌ No exact URL pattern or URL pattern ID "
                        "was found for the entered search term(s). "
                        "Try Normalized Search for broader matching."
                    )

                else:

                    st.warning(
                        "❌ No URL patterns or URL pattern IDs "
                        "were found for the entered search term(s)."
                    )

        if final_df.empty:

            st.warning(
                "⚠️ There is currently no shared dataset."
            )

        else:

            search_terms = [
                term.strip()
                for term in re.split(
                    r"[,\n]+",
                    search_string
                )
                if term.strip()
            ]

            search_terms = list(
                dict.fromkeys(
                    search_terms
                )
            )

            combined_search_mask = pd.Series(
                False,
                index=final_df.index
            )

            matched_terms = {
                index: []
                for index in final_df.index
            }

            normalized_patterns = (
                final_df[
                    "url_pattern"
                ]
                .fillna("")
                .astype(str)
                .apply(
                    normalize_search_text
                )
            )

            normalized_ids = (
                final_df[
                    "url_pattern_id"
                ]
                .fillna("")
                .astype(str)
                .str.strip()
                .str.lower()
            )

            for search_term in search_terms:

                normalized_search = (
                    normalize_search_text(
                        search_term
                    )
                )

                pattern_mask = (
                    normalized_patterns
                    .str.contains(
                        normalized_search,
                        case=False,
                        na=False,
                        regex=False
                    )
                )

                normalized_id_search = (
                    str(search_term)
                    .strip()
                    .lower()
                )

                id_mask = (
                    normalized_ids
                    .str.contains(
                        normalized_id_search,
                        case=False,
                        na=False,
                        regex=False
                    )
                )

                term_mask = (
                    pattern_mask
                    | id_mask
                )

                combined_search_mask = (
                    combined_search_mask
                    | term_mask
                )

                for index in final_df.index[
                    term_mask
                ]:

                    matched_terms[
                        index
                    ].append(
                        search_term
                    )

            search_results = (
                final_df[
                    combined_search_mask
                ]
                .copy()
            )

            if not search_results.empty:

                st.success(
                    f"🔍 Found "
                    f"{len(search_results):,} "
                    f"matching result(s) for "
                    f"{len(search_terms)} search term(s)."
                )

                result_type = st.radio(
                    "Search Result View",
                    [
                        "Original",
                        "Domain - Basis Split"
                    ],
                    horizontal=True,
                    key="result_view"
                )

                if result_type == "Original":

                    st.dataframe(
                        search_results.fillna(""),
                        use_container_width=True,
                        hide_index=True
                    )

                    search_csv = (
                        search_results
                        .to_csv(
                            index=False,
                            encoding="utf-8"
                        )
                    )

                    filename_search = re.sub(
                        r"[^a-zA-Z0-9]+",
                        "_",
                        search_string
                    ).strip("_")

                    if not filename_search:
                        filename_search = "search_results"

                    st.download_button(
                        label=(
                            "📥 Download "
                            "Original Results"
                        ),
                        data=search_csv,
                        file_name=(
                            f"{filename_search}"
                            "_original.csv"
                        ),
                        mime="text/csv",
                        use_container_width=True
                    )

                else:

                    split_results = []

                    for _, row in (
                        search_results
                        .iterrows()
                    ):

                        domain, basis = (
                            split_domain_basis(
                                row["url_pattern"]
                            )
                        )

                        split_results.append(
                            {
                                "domain": domain,
                                "basis": basis,
                                "url_pattern_id":
                                    row[
                                        "url_pattern_id"
                                    ],
                                "priority":
                                    row[
                                        "priority"
                                    ]
                            }
                        )

                    split_df = pd.DataFrame(
                        split_results
                    )

                    st.dataframe(
                        split_df.fillna(""),
                        use_container_width=True,
                        hide_index=True
                    )

                    split_csv = (
                        split_df
                        .to_csv(
                            index=False,
                            encoding="utf-8"
                        )
                    )

                    filename_search = re.sub(
                        r"[^a-zA-Z0-9]+",
                        "_",
                        search_string
                    ).strip("_")

                    if not filename_search:
                        filename_search = "search_results"

                    st.download_button(
                        label=(
                            "📥 Download "
                            "Domain - Basis Results"
                        ),
                        data=split_csv,
                        file_name=(
                            f"{filename_search[:9]}"
                            "_domain_basis.csv"
                        ),
                        mime="text/csv",
                        use_container_width=True
                    )

            else:

                st.warning(
                    "❌ No URL patterns or URL pattern IDs "
                    "found for the entered search terms."
                )

    # =========================================================
    # FULL DATASET
    # =========================================================

    st.write("---")

    st.subheader(
        "📋 Complete Shared Dataset"
    )

    if final_df.empty:

        st.info(
            "No dataset is currently available."
        )

    else:

        stat1, stat2, stat3 = (
            st.columns(3)
        )

        with stat1:

            st.metric(
                "Total Unique Rows",
                f"{len(final_df):,}"
            )

        with stat2:

            max_length = (
                final_df[
                    "url_pattern"
                ]
                .fillna("")
                .astype(str)
                .str.len()
                .max()
            )

            st.metric(
                "Longest URL Pattern",
                f"{max_length} characters"
            )

        with stat3:

            min_length = (
                final_df[
                    "url_pattern"
                ]
                .fillna("")
                .astype(str)
                .str.len()
                .min()
            )

            st.metric(
                "Shortest URL Pattern",
                f"{min_length} characters"
            )

        if metadata:

            filename_base = (
                metadata[
                    "filename"
                ]
                .rsplit(
                    ".",
                    1
                )[0]
            )

        else:

            filename_base = "shared_dataset"

        csv_data = (
            final_df
            .to_csv(
                index=False,
                encoding="utf-8"
            )
        )

        st.download_button(
            label="📥 Download Complete Shared Dataset",
            data=csv_data,
            file_name=(
                f"{filename_base}_cleaned.csv"
            ),
            mime="text/csv",
            use_container_width=True
        )

        st.dataframe(
            final_df.fillna(""),
            use_container_width=True,
            hide_index=True
        )

    # =========================================================
    # FOOTER
    # =========================================================

    st.write("---")

    st.caption(
        "📊 Shared URL Pattern Database • "
        "All users access the same active dataset."
    )


# =============================================================
# APPLICATION ACCESS GATE
# =============================================================

if not st.session_state.get(
    "admin_authenticated",
    False
):

    st.write(
        "Sign in with your username and password to access "
        "the dashboard, coverage reports, dataset search, "
        "downloads, and updates."
    )

    admin_login()

    st.stop()


# =============================================================
# TOP USER / LOGOUT AREA
# =============================================================

render_user_header()


# =============================================================
# TOP NAVIGATION
# =============================================================

navigation = st.navigation(
    [
        st.Page(
            global_pattern_dashboard_page,
            title="Global Pattern Dashboard",
            icon="📊"
        ),
        st.Page(
            coverage_report_page,
            title="Coverage Report",
            icon="🧭"
        ),
        st.Page(
            concatenate_sheet_page,
            title="Concatenate Sheet",
            icon="🔗"
        )
    ],
    position="top"
)


# =============================================================
# RUN SELECTED PAGE
# =============================================================

navigation.run()