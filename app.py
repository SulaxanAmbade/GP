import os
import re
import sqlite3
from datetime import datetime

import pandas as pd
import streamlit as st
from urllib.parse import unquote


# =============================================================
# GOOGLE AUTHENTICATION
# =============================================================

if not st.user.is_logged_in:
    st.button(
        "🔵 Sign in with Google",
        on_click=st.login
    )
    st.stop()


# =============================================================
# USER ACCESS CONTROL
# =============================================================

user_email = (
    st.user.email
    .lower()
    .strip()
)


allowed_users = [
    email.lower().strip()
    for email in st.secrets["ALLOWED_USERS"]
]


if user_email not in allowed_users:

    st.error(
        "🚫 Access denied."
    )

    st.write(
        f"The Google account `{user_email}` "
        "is not authorized to use this application."
    )

    st.stop()


# =============================================================
# AUTHORIZED USER
# =============================================================

st.sidebar.success(
    f"Signed in as {user_email}"
)

if st.button(
    "Sign out",
    key="logout_button"
):

    st.logout()
# =============================================================
# PAGE CONFIGURATION
# =============================================================

st.set_page_config(
    page_title="Shared URL Pattern Database",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Shared URL Pattern Database")

st.write(
    "Upload, search, clean, and manage a shared URL pattern dataset."
)


# =============================================================
# DATABASE CONFIGURATION
# =============================================================

DB_FILE = "url_patterns.db"


# =============================================================
# DATABASE FUNCTIONS
# =============================================================

def get_connection():
    """
    Create a connection to the SQLite database.
    """

    return sqlite3.connect(
        DB_FILE,
        check_same_thread=False
    )


def initialize_database():
    """
    Create database tables if they do not exist.
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS dataset_metadata (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            filename TEXT,
            file_date TEXT,
            updated_at TEXT,
            total_rows INTEGER
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS url_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url_pattern TEXT,
            url_pattern_id TEXT,
            priority TEXT
        )
        """
    )

    # ---------------------------------------------------------
    # Migration safety
    # ---------------------------------------------------------
    # If the database was created by an older version
    # without file_date, add the column.
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

    conn.commit()
    conn.close()


def get_dataset_metadata():
    """
    Get metadata for the currently active dataset.
    """

    conn = get_connection()

    try:

        metadata = pd.read_sql_query(
            """
            SELECT
                filename,
                file_date,
                updated_at,
                total_rows
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
    """
    Load the current shared dataset.
    """

    conn = get_connection()

    try:

        df = pd.read_sql_query(
            """
            SELECT
                url_pattern,
                url_pattern_id,
                priority
            FROM url_patterns
            """,
            conn
        )

        # -----------------------------------------------------
        # Keep the same longest → shortest ordering even after
        # loading from SQLite.
        # -----------------------------------------------------

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
                columns=[
                    "_url_pattern_length"
                ],
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
    file_date
):
    """
    Completely replace the shared dataset.
    """

    conn = get_connection()

    try:

        cursor = conn.cursor()

        # -----------------------------------------------------
        # Remove old data
        # -----------------------------------------------------

        cursor.execute(
            "DELETE FROM url_patterns"
        )

        # -----------------------------------------------------
        # Prepare new data
        # -----------------------------------------------------

        records = []

        for _, row in new_df.iterrows():

            url_pattern = row[
                "url_pattern"
            ]

            url_pattern_id = row[
                "url_pattern_id"
            ]

            priority = row[
                "priority"
            ]

            records.append(
                (
                    None
                    if pd.isna(url_pattern)
                    else str(url_pattern),

                    None
                    if pd.isna(url_pattern_id)
                    else str(url_pattern_id),

                    None
                    if pd.isna(priority)
                    else str(priority)
                )
            )

        # -----------------------------------------------------
        # Insert new data
        # -----------------------------------------------------

        cursor.executemany(
            """
            INSERT INTO url_patterns (
                url_pattern,
                url_pattern_id,
                priority
            )
            VALUES (?, ?, ?)
            """,
            records
        )

        # -----------------------------------------------------
        # Update metadata
        # -----------------------------------------------------

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
                total_rows
            )
            VALUES (
                1,
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
                total_rows = excluded.total_rows
            """,
            (
                filename,
                file_date_string,
                updated_at,
                len(new_df)
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
# ADMIN PASSWORD
# =============================================================

def get_admin_password():
    """
    Get admin password.

    Recommended:
    .streamlit/secrets.toml

    ADMIN_PASSWORD = "your-password"
    """

    try:

        return st.secrets[
            "ADMIN_PASSWORD"
        ]

    except Exception:

        return os.environ.get(
            "ADMIN_PASSWORD",
            ""
        )


def admin_login():
    """
    Admin authentication.
    """

    if st.session_state.get(
        "admin_authenticated",
        False
    ):

        return True

    st.subheader(
        "🔐 Admin Login"
    )

    password = st.text_input(
        "Admin password",
        type="password",
        key="admin_password"
    )

    if st.button(
        "Login as Admin",
        use_container_width=True
    ):

        correct_password = (
            get_admin_password()
        )

        if (
            correct_password
            and password == correct_password
        ):

            st.session_state[
                "admin_authenticated"
            ] = True

            st.success(
                "✅ Admin access granted."
            )

            st.rerun()

        else:

            st.error(
                "❌ Incorrect admin password."
            )

    return False


# =============================================================
# FILE DATE FUNCTIONS
# =============================================================

def extract_file_date(filename):
    """
    Extract DD-MM-YYYY from the filename.

    Example:

    Global_Pattern_All_27-08-2026_xxxxx.xls

    Returns a datetime object or None.
    """

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
    """
    Compare file date against today's date.
    """

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

    file_date_only = (
        file_date.date()
    )

    difference_days = (
        current_date
        - file_date_only
    ).days

    return {
        "date_found": file_date_only,
        "current_date": current_date,
        "is_match": (
            file_date_only
            == current_date
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
            "Expected BOF record"
            in last_error_msg
            or "b'\\xff\\xfe'"
            in last_error_msg
            or "tsv"
            in last_error_msg.lower()
        ):

            try:

                uploaded_file.seek(0)

                raw_content = (
                    uploaded_file
                    .read()
                    .decode("utf-16")
                )

                lines = (
                    raw_content
                    .splitlines()
                )

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

                    if (
                        len(row_list)
                        > standard_cols
                    ):

                        row_list = row_list[
                            :standard_cols
                        ]

                    while (
                        len(row_list)
                        < standard_cols
                    ):

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
            str(value)
            .strip()
            .lower()
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
        "total_count"
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

    fixed_count = (
        shifted_mask.sum()
    )

    if fixed_count > 0:

        df.loc[
            shifted_mask,
            "url_pattern_id"
        ] = df.loc[
            shifted_mask,
            "total_count"
        ]

    # =========================================================
    # SELECT REQUIRED COLUMNS
    # =========================================================

    final_df = df[
        [
            "url_pattern",
            "url_pattern_id",
            "priority"
        ]
    ].copy()

    # =========================================================
    # REMOVE DUPLICATES
    # =========================================================

    initial_len = len(
        final_df
    )

    final_df.drop_duplicates(
        inplace=True
    )

    duplicates_removed = (
        initial_len
        - len(final_df)
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
        columns=[
            "_url_pattern_length"
        ],
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
    """
    Make different URL separators searchable
    as equivalent characters.

    Example:

        labor day
        labor-day
        labor_day
        labor/day
        labor*day

    all become:

        labor day
    """

    text = str(text)

    # Decode URL encoding
    text = unquote(text)

    # Convert +
    text = text.replace(
        "+",
        " "
    )

    # Treat separators as spaces
    text = re.sub(
        r"[-_/\\*]+",
        " ",
        text
    )

    # Remove other special characters
    text = re.sub(
        r"[^a-zA-Z0-9\s]",
        " ",
        text
    )

    # Normalize spaces
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
    """
    Exact requested rule.

    Example:

    patternkeywords.global*labor*day

    becomes:

    domain = patternkeywords.global
    basis  = labor*day

    Only the FIRST '*' is used as
    the domain/basis separator.

    Every '*' after the first remains
    inside the basis.
    """

    pattern = str(
        pattern
    ).strip()

    if "*" not in pattern:

        return pattern, ""

    parts = pattern.split(
        "*",
        2
    )

    domain = parts[1].strip()
    basis = parts[2].strip()

    return domain, basis


# =============================================================
# SIDEBAR
# =============================================================

with st.sidebar:

    st.header(
        "⚙️ Administration"
    )

    if st.session_state.get(
        "admin_authenticated",
        False
    ):

        st.success(
            "🟢 Admin mode active"
        )

        if st.button(
            "Logout",
            use_container_width=True
        ):

            st.session_state[
                "admin_authenticated"
            ] = False

            st.rerun()

    else:

        st.info(
            "Only administrators can "
            "replace the shared dataset."
        )


# =============================================================
# CURRENT DATASET
# =============================================================

metadata = get_dataset_metadata()

final_df = load_shared_dataset()


# =============================================================
# CURRENT DATASET INFORMATION
# =============================================================

st.subheader(
    "📌 Current Shared Dataset"
)

if metadata is None:

    st.warning(
        "⚠️ No dataset has been uploaded yet."
    )

else:

    info1, info2, info3, info4 = (
        st.columns(4)
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
            "Source File",
            metadata["filename"]
        )


# =============================================================
# ADMIN LOGIN
# =============================================================

if not st.session_state.get(
    "admin_authenticated",
    False
):

    with st.expander(
        "🔐 Admin Login",
        expanded=False
    ):

        admin_login()


# =============================================================
# ADMIN DATASET UPDATE
# =============================================================

if st.session_state.get(
    "admin_authenticated",
    False
):

    with st.expander(
        "⚙️ Update Shared Dataset",
        expanded=False
    ):

        st.warning(
            "⚠️ Replacing the dataset will change "
            "the data visible to ALL users."
        )

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

            # =================================================
            # DATE NOT FOUND
            # =================================================

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

            # =================================================
            # DATE MATCH
            # =================================================

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

            # =================================================
            # DATE MISMATCH
            # =================================================

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
                    "I have verified the date mismatch and want to continue.",
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


# =============================================================
# PENDING DATASET PREVIEW
# =============================================================

if (
    "pending_dataset"
    in st.session_state
):

    st.write("---")

    st.subheader(
        "👀 New Dataset Preview"
    )

    pending_df = (
        st.session_state[
            "pending_dataset"
        ]
    )

    pending_filename = (
        st.session_state[
            "pending_filename"
        ]
    )

    pending_fixed_count = (
        st.session_state[
            "pending_fixed_count"
        ]
    )

    pending_duplicates = (
        st.session_state[
            "pending_duplicates"
        ]
    )

    pending_date_validation = (
        st.session_state.get(
            "pending_date_validation"
        )
    )

    # =========================================================
    # PREVIEW STATS
    # =========================================================

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

    # =========================================================
    # DATE STATUS
    # =========================================================

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

    # =========================================================
    # DATA PREVIEW
    # =========================================================

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

    # =========================================================
    # REPLACE DATASET
    # =========================================================

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
                        pending_file_date
                    )

                # -------------------------------------------------
                # Clear pending data
                # -------------------------------------------------

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

                    if key in st.session_state:

                        del st.session_state[
                            key
                        ]

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

    # =========================================================
    # CANCEL UPDATE
    # =========================================================

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

                if key in st.session_state:

                    del st.session_state[
                        key
                    ]

            st.rerun()


# =============================================================
# SEARCH
# =============================================================

st.write("---")

st.subheader(
    "🔎 Search URL Patterns"
)

st.write(
    "Search is separator-independent. "
    "For example, searching for `labor day` "
    "can find `labor*day`, `labor-day`, "
    "`labor_day`, `labor/day`, and similar patterns."
)

search_string = st.text_input(
    "Search",
    placeholder=(
        "Example: labor day"
    ),
    key="main_search"
)


# =============================================================
# SEARCH EXECUTION
# =============================================================

if search_string.strip():

    if final_df.empty:

        st.warning(
            "⚠️ There is currently no shared dataset."
        )

    else:

        normalized_search = (
            normalize_search_text(
                search_string
            )
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

        search_mask = (
            normalized_patterns
            .str.contains(
                normalized_search,
                case=False,
                na=False,
                regex=False
            )
        )

        search_results = (
            final_df[
                search_mask
            ]
            .copy()
        )

        # =====================================================
        # SEARCH RESULTS
        # =====================================================

        if not search_results.empty:

            st.success(
                f"🔍 Found "
                f"{len(search_results):,} "
                f"matching URL pattern(s) for "
                f"'{search_string}'."
            )

            # =================================================
            # RESULT TYPE
            # =================================================

            result_type = st.radio(
                "Search Result View",
                [
                    "Original",
                    "Domain - Basis Split"
                ],
                horizontal=True,
                key="result_view"
            )

            # =================================================
            # ORIGINAL RESULTS
            # =================================================

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
                    normalized_search
                ).strip("_")

                if not filename_search:

                    filename_search = (
                        "search_results"
                    )

                st.download_button(
                    label="📥 Download Original Results",
                    data=search_csv,
                    file_name=(
                        f"{filename_search}"
                        "_original.csv"
                    ),
                    mime="text/csv",
                    use_container_width=True
                )

            # =================================================
            # DOMAIN - BASIS RESULTS
            # =================================================

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
                            "domain": domain,
                            "basis": basis,
                            "url_pattern_id": row[
                                "url_pattern_id"
                            ],
                            "priority": row[
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
                    normalized_search
                ).strip("_")

                if not filename_search:

                    filename_search = (
                        "search_results"
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

        else:

            st.warning(
                f"❌ No URL patterns found for "
                f"'{search_string}'."
            )


# =============================================================
# FULL DATASET
# =============================================================

st.write("---")

st.subheader(
    "📋 Complete Shared Dataset"
)

if final_df.empty:

    st.info(
        "No dataset is currently available."
    )

else:

    # =========================================================
    # DATASET STATISTICS
    # =========================================================

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

    # =========================================================
    # DOWNLOAD COMPLETE DATASET
    # =========================================================

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

        filename_base = (
            "shared_dataset"
        )

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

    # =========================================================
    # DATA PREVIEW
    # =========================================================

    st.dataframe(
        final_df.fillna(""),
        use_container_width=True,
        hide_index=True
    )


# =============================================================
# FOOTER
# =============================================================

st.write("---")

st.caption(
    "📊 Shared URL Pattern Database • "
    "All users access the same active dataset."
)

