
import pandas as pd
import streamlit as st
import re
from urllib.parse import unquote

# =============================================================
# PAGE CONFIGURATION
# =============================================================

st.set_page_config(
    page_title="Excel 97-2003 to CSV Converter",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Legacy Excel (.xls) to CSV Converter")

st.write(
    "Upload a Microsoft Excel 97-2003 Worksheet to clean it, "
    "re-align columns, search URL patterns, and download unique rows."
)

# =============================================================
# FILE UPLOADER
# =============================================================

uploaded_file = st.file_uploader(
    "Choose a legacy Excel file",
    type=["xls"],
    accept_multiple_files=False
)

if uploaded_file is not None:

    df = None
    last_error_msg = ""

    # =========================================================
    # FILE PROCESSING
    # =========================================================

    with st.spinner(
        "⏳ Analyzing, parsing, and re-aligning fields... Please wait."
    ):

        # -----------------------------------------------------
        # STRATEGY 1: GENUINE BINARY XLS PARSER
        # -----------------------------------------------------

        try:

            uploaded_file.seek(0)

            df = pd.read_excel(
                uploaded_file,
                engine="xlrd",
                header=None
            )

        except Exception as excel_err:

            last_error_msg = str(excel_err)

            # -------------------------------------------------
            # STRATEGY 2: TSV PARSER
            # -------------------------------------------------

            if (
                "Expected BOF record" in last_error_msg
                or "b'\\xff\\xfe'" in last_error_msg
                or "tsv" in last_error_msg.lower()
            ):

                try:

                    uploaded_file.seek(0)

                    raw_content = uploaded_file.read().decode(
                        "utf-16"
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

                        # Remove trailing empty items
                        while row_list and row_list[-1] == "":
                            row_list.pop()

                        # Truncate extra columns
                        if len(row_list) > standard_cols:

                            row_list = row_list[:standard_cols]

                        # Add missing columns
                        while len(row_list) < standard_cols:

                            row_list.append("")

                        aligned_rows.append(row_list)

                    if aligned_rows:

                        df = pd.DataFrame(aligned_rows)

                except Exception as csv_err:

                    last_error_msg = (
                        f"TSV Flow Realignment Error: {csv_err}"
                    )

            # -------------------------------------------------
            # STRATEGY 3: HTML TABLE PARSER
            # -------------------------------------------------

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

                    if "TSV" not in last_error_msg:

                        last_error_msg = (
                            f"HTML Parse Error: {html_err}"
                        )

    # =============================================================
    # PROCESS DATAFRAME
    # =============================================================

    if df is not None:

        try:

            # =====================================================
            # HEADER DETECTION
            # =====================================================

            header_row_idx = None

            for idx, row in df.iterrows():

                row_str_values = [
                    str(value).strip().lower()
                    for value in row.values
                ]

                if "url_pattern" in row_str_values:

                    header_row_idx = idx
                    break

            # -----------------------------------------------------
            # USE DETECTED HEADER
            # -----------------------------------------------------

            if header_row_idx is not None:

                df.columns = [
                    str(col).strip()
                    for col in df.iloc[header_row_idx]
                ]

                df = df.iloc[
                    header_row_idx + 1:
                ].reset_index(drop=True)

            # -----------------------------------------------------
            # FALLBACK TO FIRST ROW
            # -----------------------------------------------------

            else:

                df.columns = [
                    str(col).strip()
                    for col in df.iloc[0]
                ]

                df = df.iloc[
                    1:
                ].reset_index(drop=True)

            # =====================================================
            # ENSURE REQUIRED COLUMNS EXIST
            # =====================================================

            required_targets = [
                "url_pattern",
                "url_pattern_id",
                "priority",
                "total_count"
            ]

            for col in required_targets:

                if col not in df.columns:

                    df[col] = None

            # =====================================================
            # CLEAN NULL VALUES
            # =====================================================

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

            # =====================================================
            # TARGETED ALIGNMENT SHIFT
            # =====================================================

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

                st.warning(
                    f"⚠️ Re-aligned {fixed_count} row values "
                    "shifted into 'total_count' back into "
                    "'url_pattern_id'."
                )

            # =====================================================
            # SELECT REQUIRED FIELDS
            # =====================================================

            final_df = df[
                [
                    "url_pattern",
                    "url_pattern_id",
                    "priority"
                ]
            ].copy()

            # =====================================================
            # REMOVE DUPLICATES
            # =====================================================

            initial_len = len(final_df)

            final_df.drop_duplicates(
                inplace=True
            )

            duplicates_removed = (
                initial_len - len(final_df)
            )

            if duplicates_removed > 0:

                st.info(
                    f"✨ Removed {duplicates_removed} "
                    "duplicate row matches from the output data."
                )

            # =====================================================
            # SORT BY URL_PATTERN LENGTH
            # LONGEST → SHORTEST
            # =====================================================

            final_df["_url_pattern_length"] = (
                final_df["url_pattern"]
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

            st.success(
                "✅ File parsed, aligned, optimized, "
                "and sorted successfully!"
            )

            # =====================================================
            # SEARCH FEATURE
            # =====================================================

            st.write("---")

            st.subheader("🔎 Search URL Patterns")

            st.write(
                "Search for a word or phrase. "
                "Spaces, hyphens, underscores, slashes, "
                "and URL encoding are treated as equivalent."
            )

            search_string = st.text_input(
                "Search",
                placeholder=(
                    "Example: labor day, hair shampoo, "
                    "italian restaurants..."
                ),
                key="url_pattern_search"
            )

            # =====================================================
            # SEARCH NORMALIZATION FUNCTION
            # =====================================================

            def normalize_search_text(text):

                text = str(text)

                # Decode URL encoding
                text = unquote(text)

                # Convert + to spaces
                text = text.replace("+", " ")

                # Convert common URL separators to spaces
                text = re.sub(
                    r"[-_/\\]+",
                    " ",
                    text
                )

                # Remove remaining special characters
                text = re.sub(
                    r"[^a-zA-Z0-9\s]",
                    " ",
                    text
                )

                # Normalize multiple spaces
                text = re.sub(
                    r"\s+",
                    " ",
                    text
                )

                # Lowercase
                return text.strip().lower()

            # =====================================================
            # SEARCH
            # =====================================================

            if search_string.strip():

                # Normalize user's search
                normalized_search = normalize_search_text(
                    search_string
                )

                # Normalize URL patterns
                normalized_patterns = (
                    final_df["url_pattern"]
                    .fillna("")
                    .astype(str)
                    .apply(normalize_search_text)
                )

                # Case-insensitive phrase matching
                search_mask = normalized_patterns.str.contains(
                    normalized_search,
                    case=False,
                    na=False,
                    regex=False
                )

                search_results = final_df[
                    search_mask
                ].copy()

                # =================================================
                # SEARCH RESULTS
                # =================================================

                if not search_results.empty:

                    st.success(
                        f"🔍 Found {len(search_results)} "
                        f"matching URL pattern(s) for "
                        f"'{search_string}'."
                    )

                    # =================================================
                    # SEARCH RESULT VIEW
                    # =================================================

                    result_type = st.radio(
                        "Search Result View",
                        [
                            "Original",
                            "Domain - Basis Split"
                        ],
                        horizontal=True,
                        key="search_result_type"
                    )

                    # =================================================
                    # OPTION 1: ORIGINAL
                    # =================================================

                    if result_type == "Original":

                        st.dataframe(
                            search_results.fillna(""),
                            use_container_width=True,
                            hide_index=True
                        )

                        # ---------------------------------------------
                        # DOWNLOAD ORIGINAL RESULTS
                        # ---------------------------------------------

                        search_csv = search_results.to_csv(
                            index=False,
                            encoding="utf-8"
                        )

                        filename_search = re.sub(
                            r"[^a-zA-Z0-9]+",
                            "_",
                            normalized_search
                        ).strip("_")

                        if not filename_search:

                            filename_search = "search_results"

                        st.download_button(
                            label="📥 Download Search Results",
                            data=search_csv,
                            file_name=(
                                f"{filename_search}_results.csv"
                            ),
                            mime="text/csv",
                            use_container_width=True
                        )

                    # =================================================
                    # OPTION 2: DOMAIN - BASIS SPLIT
                    # =================================================

                    else:

                        split_results = []

                        for _, row in search_results.iterrows():

                            pattern = str(
                                row["url_pattern"]
                            ).strip()

                            # -------------------------------------------------
                            # DOMAIN - BASIS SPLIT RULE
                            # -------------------------------------------------
                            #
                            # Example:
                            #
                            # patternkeywords.global*labor*day
                            #
                            # First '*':
                            #     Separates Domain from Basis
                            #
                            # Result:
                            #     Domain = patternkeywords.global
                            #     Basis  = labor*day
                            #
                            # Another example:
                            #
                            # patternkeywords.global*best*labor*day
                            #
                            # Result:
                            #     Domain = patternkeywords.global
                            #     Basis  = best*labor*day
                            #
                            # Only the FIRST '*' is removed.
                            # Every '*' after it remains in Basis.
                            # -------------------------------------------------

                            if "*" in pattern:

                                parts = pattern.split(
                                    "*",
                                    2
                                )

                                domain = parts[1].strip()

                                basis = parts[2].strip()

                            else:

                                # If no '*' exists
                                domain = pattern
                                basis = ""

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

                        # =================================================
                        # DISPLAY DOMAIN - BASIS RESULTS
                        # =================================================

                        st.dataframe(
                            split_df.fillna(""),
                            use_container_width=True,
                            hide_index=True
                        )

                        # =================================================
                        # DOWNLOAD DOMAIN - BASIS RESULTS
                        # =================================================

                        split_csv = split_df.to_csv(
                            index=False,
                            encoding="utf-8"
                        )

                        filename_search = re.sub(
                            r"[^a-zA-Z0-9]+",
                            "_",
                            normalized_search
                        ).strip("_")

                        if not filename_search:

                            filename_search = "search_results"

                        st.download_button(
                            label="📥 Download Domain - Basis Results",
                            data=split_csv,
                            file_name=(
                                f"{filename_search}_domain_basis.csv"
                            ),
                            mime="text/csv",
                            use_container_width=True
                        )

                else:

                    st.warning(
                        f"❌ No URL patterns found for "
                        f"'{search_string}'."
                    )

            # =====================================================
            # FULL DATA DOWNLOAD
            # =====================================================

            st.write("---")

            col1, col2 = st.columns(2)

            with col1:

                st.subheader("📥 Download Full Data")

                filename_base = uploaded_file.name.rsplit(
                    ".",
                    1
                )[0]

                csv_data = final_df.to_csv(
                    index=False,
                    encoding="utf-8"
                )

                st.download_button(
                    label="Download Filtered CSV File",
                    data=csv_data,
                    file_name=(
                        f"{filename_base}_cleaned.csv"
                    ),
                    mime="text/csv",
                    use_container_width=True
                )

            with col2:

                st.subheader("📊 Dataset Information")

                st.metric(
                    "Total Unique Rows",
                    len(final_df)
                )

                if len(final_df) > 0:

                    max_length = (
                        final_df["url_pattern"]
                        .fillna("")
                        .astype(str)
                        .str.len()
                        .max()
                    )

                    min_length = (
                        final_df["url_pattern"]
                        .fillna("")
                        .astype(str)
                        .str.len()
                        .min()
                    )

                    st.write(
                        f"**Longest URL pattern:** "
                        f"{max_length} characters"
                    )

                    st.write(
                        f"**Shortest URL pattern:** "
                        f"{min_length} characters"
                    )

            # =====================================================
            # COMPLETE DATA PREVIEW
            # =====================================================

            st.write("---")

            st.subheader(
                "📋 Complete Filtered Spreadsheet"
            )

            display_df = final_df.fillna("")

            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True
            )

        # =========================================================
        # PROCESSING ERROR
        # =========================================================

        except Exception as processing_err:

            st.error(
                "❌ Error during column alignment or extraction."
            )

            st.info(
                f"Details: {processing_err}"
            )

    # =============================================================
    # FILE PARSING FAILURE
    # =============================================================

    else:

        st.error(
            "❌ Failed to parse file."
        )

        st.info(
            "The file format could not be verified automatically.\n\n"
            f"**Diagnostic Details:** {last_error_msg}"
        )

# =============================================================
# NO FILE UPLOADED
# =============================================================

else:

    st.info(
        "💡 Please drop or upload an `.xls` document above to begin."
    )
