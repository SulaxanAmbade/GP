"""Standalone coverage report for a URL CSV and user-supplied bases.

Install: python -m pip install pandas streamlit
UI:      streamlit run manual_basis_coverage_fast.py
CLI:     python manual_basis_coverage_fast.py --csv urls.csv --basis 'thanks*giving' --output coverage.csv

Output: stripped url, imp, rev, matching basis.
Wildcard-separated fragments retain the original coverage matcher (including
reordered fragments, common URL plurals and exact ~word~ locks). Additionally,
a wildcard may consume zero characters: thanks*giving matches thanksgiving.
The lowest numeric priority wins; ties prefer the longer normalized basis.
Language codes filter user-supplied bases; labels retain the entered spelling.
This file needs no shared database or other application files.
"""
import argparse
import csv
import hashlib
import re
import sys
from collections import Counter, deque
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from html import unescape
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pandas as pd

OUTPUT_COLUMNS = ["stripped url", "imp", "rev", "matching basis"]
NO_MATCH = "No Matching Basis"

def normalize_search_text(text):
    return _cached_normalize_search_text(str(text))

@lru_cache(maxsize=8192)
def _cached_normalize_search_text(text):
    text = unquote(str(text)).replace("+", " ")
    text = re.sub(r"[-_/\\*]+", " ", text)
    text = re.sub(r"[^a-zA-Z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip().lower()

def split_domain_basis(pattern):
    return _cached_split_domain_basis(str(pattern))

@lru_cache(maxsize=8192)
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

def normalize_coverage_basis(basis):
    return _cached_normalize_coverage_basis(str(basis))

@lru_cache(maxsize=8192)
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

def coverage_priority_value(value):
    """Lower numeric priorities catch first; missing/invalid values catch last."""
    try:
        number = Decimal(str(value).strip().replace(",", ""))
        return number if number.is_finite() and number >= 0 else Decimal("Infinity")
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("Infinity")

def coerce_metric(series):
    cleaned = (
        series.fillna(0).astype(str).str.strip()
        .str.replace(",", "", regex=False)
        .str.replace(r"[^0-9.\-()]", "", regex=True)
        .str.replace(r"^\((.*)\)$", r"-\1", regex=True)
    )
    return pd.to_numeric(cleaned, errors="coerce").fillna(0)

@lru_cache(maxsize=16384)
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

@lru_cache(maxsize=1)
def _coverage_basis_index(bases):
    """Compact trie: one edge table per branching node; no tables on leaves."""
    children = [None]
    terminals = {}
    fragment_ids = {}
    requirements = []
    frequency = Counter()
    for basis_id, basis in enumerate(bases):
        fragments = [tuple(part.split()) for part in basis.split("*") if part.strip()]
        required = Counter(fragments)
        basis_requirements = []
        for fragment, occurrences in required.items():
            fragment_id = fragment_ids.get(fragment)
            if fragment_id is None:
                fragment_id = len(fragment_ids)
                fragment_ids[fragment] = fragment_id
                node = 0
                for word in fragment:
                    edges = children[node]
                    if edges is None:
                        edges = children[node] = {}
                    child = edges.get(word)
                    if child is None:
                        child = len(children)
                        edges[word] = child
                        children.append(None)
                    node = child
                terminals.setdefault(node, []).append(fragment_id)
            basis_requirements.append((fragment_id, occurrences))
            frequency[fragment_id] += 1
        requirements.append(tuple(basis_requirements))
    # A common word such as "health" must not touch every basis for every URL.
    # Only the rarest required fragment nominates a basis for verification.
    anchors = {}
    for basis_id, required in enumerate(requirements):
        if required:
            fragment_id, count = min(required, key=lambda item: frequency[item[0]])
            anchors.setdefault(fragment_id, {}).setdefault(count, []).append(basis_id)
    return children, terminals, anchors, requirements

def _coverage_match_ids(searchable_url, index, order_rank=None):
    children, terminals, anchors, requirements = index
    active = set()
    occurrences = Counter()
    for word in searchable_url.split():
        forms = _coverage_word_forms(word)
        locked_word = f"~{word}~"
        next_active = set()
        for node in active | {0}:
            # Tilde locks match the original token, not its singular forms.
            edges = children[node]
            if edges is None:
                continue
            child = edges.get(locked_word)
            if child is not None:
                next_active.add(child)
            for form in forms:
                child = edges.get(form)
                if child is not None:
                    next_active.add(child)
        found_fragments = {
            fragment_id for node in next_active for fragment_id in terminals.get(node, ())
        }
        for fragment_id in found_fragments:
            occurrences[fragment_id] += 1
        active = next_active
    matches = []
    best = None
    for fragment_id, count in occurrences.items():
        for required_count, candidates in anchors.get(fragment_id, {}).items():
            if count < required_count:
                continue
            for basis_id in candidates:
                if order_rank is not None and best is not None and order_rank[basis_id] >= order_rank[best]:
                    continue
                if all(occurrences.get(fragment, 0) >= needed for fragment, needed in requirements[basis_id]):
                    if order_rank is None:
                        matches.append(basis_id)
                    else:
                        best = basis_id
                        if order_rank[best] == 0:
                            return (best,)
    return tuple(sorted(matches)) if order_rank is None else (() if best is None else (best,))


def text_value(value):
    return "" if value is None or pd.isna(value) else str(value).strip()


def header_key(value):
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def suggested_column(columns, aliases):
    for alias in aliases:
        matches = [column for column in columns if header_key(column) == header_key(alias)]
        if matches:
            return matches[0]
    return None


def read_csv_bytes(raw, nrows=None, usecols=None):
    last_error = None
    for encoding in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            try:
                delimiter = csv.Sniffer().sniff(raw[:65536].decode(encoding, errors="replace"), delimiters=",;\t|").delimiter
            except csv.Error:
                delimiter = ","
            return pd.read_csv(BytesIO(raw), encoding=encoding, sep=delimiter,
                engine="c" if delimiter else "python", nrows=nrows, usecols=usecols)
        except (ValueError, UnicodeError, pd.errors.ParserError) as error:
            last_error = error
    raise ValueError(f"Could not read CSV: {last_error}")


def prepare_urls(frame, url_column, impressions_column=None, revenue_column=None):
    if url_column not in frame:
        raise ValueError("Choose a valid URL column.")
    data = pd.DataFrame({"stripped url": frame[url_column].map(text_value)})
    data["imp"] = coerce_metric(frame[impressions_column]) if impressions_column else 0
    data["rev"] = coerce_metric(frame[revenue_column]) if revenue_column else 0.0
    if data[["imp", "rev"]].isin([float("inf"), float("-inf")]).any().any():
        raise ValueError("Impressions and revenue cannot contain infinite values.")
    labels = data["stripped url"].map(lambda value: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", unescape(value))).strip().casefold())
    totals = labels.isin({"grand total", "report total", "stripped url (others)",
        "report total stripped url (others)", "grand total stripped url (others)"})
    removed = int(totals.sum())
    data = data.loc[~totals & data["stripped url"].ne("")]
    data = data.groupby("stripped url", as_index=False, sort=False)[["imp", "rev"]].sum()
    return data, removed


def prepare_bases(frame, default_language="EN", default_format="Basis"):
    basis_column = suggested_column(frame.columns, ["basis", "basis name", "url_pattern", "pattern"])
    if basis_column is None:
        raise ValueError("The basis table needs a Basis or url_pattern column.")
    language_column = suggested_column(frame.columns, ["language code", "languagecode", "language"])
    priority_column = suggested_column(frame.columns, ["priority"])
    format_column = suggested_column(frame.columns, ["input type", "format", "type"])
    implicit_format = "Full url_pattern" if header_key(basis_column) == "urlpattern" else default_format
    rows = []
    for position, source in enumerate(frame.to_dict("records"), 1):
        basis = text_value(source[basis_column])
        if not basis:
            continue
        input_format = (text_value(source.get(format_column)) if format_column else "") or implicit_format
        if input_format.casefold() in {"full url_pattern", "url_pattern", "pattern", "full pattern"}:
            _, basis = split_domain_basis(basis)
        elif input_format.casefold() != "basis":
            raise ValueError(f"Basis row {position}: choose Basis or Full url_pattern as the input type.")
        if not basis:
            raise ValueError(f"Basis row {position}: a domain-only pattern has no basis to match.")
        language = ((text_value(source.get(language_column)) if language_column else "") or default_language).upper()
        if not re.fullmatch(r"[A-Z]{2,3}(?:-[A-Z0-9]{2,8})*", language):
            raise ValueError(f"Basis row {position}: enter a language code such as EN, FR or PT-BR.")
        priority = text_value(source.get(priority_column)) if priority_column else ""
        if priority:
            value = coverage_priority_value(priority)
            if not value.is_finite() or value != value.to_integral_value():
                raise ValueError(f"Basis row {position}: priority must be a nonnegative whole number or blank.")
        normalized = normalize_coverage_basis(basis)
        if not normalized:
            raise ValueError(f"Basis row {position}: enter searchable words, not only wildcards.")
        rows.append(dict(basis=basis, language=language, priority=priority, normalized=normalized))
    result = pd.DataFrame(rows, columns=["basis", "language", "priority", "normalized"])
    if result.empty:
        raise ValueError("Enter at least one basis.")
    return result.drop_duplicates(["basis", "language", "priority"]).reset_index(drop=True)


def searchable_url(url):
    try:
        parsed = urlsplit(url if "://" in url else f"https://{url}")
        return normalize_search_text(" ".join([parsed.hostname or "", parsed.path, parsed.query, parsed.fragment]))
    except ValueError as error:
        raise ValueError(f"Invalid URL: {url[:150]}") from error


def joined_wildcard_patterns(normalized):
    """Supplement whole-word matching with zero-length/within-word wildcard gaps.

    Outer word boundaries prevent matching inside an unrelated larger word.
    Tilde locks retain their own word boundaries even next to a wildcard.
    """
    if "*" not in normalized:
        return None
    fragments = [fragment.strip() for fragment in normalized.split("*") if fragment.strip()]
    if len(fragments) < 2:
        return None
    patterns = []
    for position, fragment in enumerate(fragments):
        words = []
        for word in fragment.split():
            locked = word.startswith("~") and word.endswith("~")
            literal = re.escape(word[1:-1] if locked else word)
            words.append(r"\b" + literal + r"\b" if locked else literal)
        expression = r"\s+".join(words)
        if position == 0:
            expression = r"(?<![a-z0-9])" + expression
        if position == len(fragments) - 1:
            expression += r"(?![a-z0-9])"
        patterns.append(re.compile(expression))
    return tuple(patterns)


def joined_wildcard_matches(searchable, patterns):
    # Search fixed fragments from left to right instead of compiling repeated
    # greedy .* expressions, which can backtrack excessively on long URLs.
    position = 0
    for pattern in patterns:
        match = pattern.search(searchable, position)
        if match is None:
            return False
        position = match.end()
    return True


@lru_cache(maxsize=1)
def _joined_candidate_index(normalized_bases):
    """Index one mandatory literal per wildcard basis in a shared automaton.

    The index only nominates candidates. The unchanged fragment matcher below
    still verifies word boundaries, locks, order and the complete wildcard rule.
    """
    patterns, literals = {}, {}
    frequency = Counter()
    for basis_id, normalized in enumerate(normalized_bases):
        compiled = joined_wildcard_patterns(normalized)
        if compiled is None:
            continue
        patterns[basis_id] = compiled
        fragments = tuple(dict.fromkeys(part.replace("~", "").strip()
            for part in normalized.split("*") if part.strip()))
        literals[basis_id] = fragments
        frequency.update(fragments)
    children = [{}]
    failure = [0]
    output_links = [0]
    terminals = {}
    for basis_id, fragments in literals.items():
        # Rare fragments avoid nominating thousands of unrelated bases sharing
        # a word such as health. Longer literals reduce incidental substring hits.
        anchor = min(fragments, key=lambda part: (frequency[part], -len(part), part))
        node = 0
        for character in anchor:
            child = children[node].get(character)
            if child is None:
                child = len(children)
                children[node][character] = child
                children.append({})
                failure.append(0)
                output_links.append(0)
            node = child
        terminals.setdefault(node, []).append(basis_id)
    queue = deque(children[0].values())
    while queue:
        node = queue.popleft()
        for character, child in children[node].items():
            queue.append(child)
            fallback = failure[node]
            while fallback and character not in children[fallback]:
                fallback = failure[fallback]
            failure[child] = children[fallback].get(character, 0)
            target = failure[child]
            output_links[child] = target if target in terminals else output_links[target]
    return children, failure, output_links, terminals, patterns


def _joined_candidates(searchable, index, ranks, best_rank):
    children, failure, output_links, terminals, _ = index
    node = 0
    candidates = set()
    for character in searchable:
        while node and character not in children[node]:
            node = failure[node]
        node = children[node].get(character, 0)
        output = node
        while output:
            for basis_id in terminals.get(output, ()):
                if ranks[basis_id] < best_rank:
                    candidates.add(basis_id)
            output = output_links[output]
    return candidates


def create_report(prepared_urls, bases, selected_languages=None, excluded_bases=()):
    """Return the requested four columns, with exactly one winning basis per URL."""
    catalog = bases
    if selected_languages is not None:
        selected = {str(value).upper() for value in selected_languages}
        catalog = catalog.loc[catalog.language.isin(selected)]
    excluded = set(excluded_bases)
    if excluded:
        catalog = catalog.loc[~catalog.basis.isin(excluded)]
    records = list(catalog.itertuples(index=False))
    order = sorted(range(len(records)), key=lambda i: (
        coverage_priority_value(records[i].priority), -len(records[i].normalized),
        records[i].normalized.casefold(), records[i].language,
        records[i].basis.casefold(), records[i].basis, i))
    ranks = {basis_id: rank for rank, basis_id in enumerate(order)}
    normalized_bases = tuple(record.normalized for record in records)
    index = _coverage_basis_index(normalized_bases)
    joined_index = _joined_candidate_index(normalized_bases)
    joined_patterns = joined_index[4]
    rows = []
    for url, impressions, revenue in prepared_urls[["stripped url", "imp", "rev"]].itertuples(index=False, name=None):
        searchable = searchable_url(url)
        if len(records) == 1 and 0 in joined_patterns and joined_wildcard_matches(searchable, joined_patterns[0]):
            rows.append((url, impressions, revenue, records[0].basis))
            continue
        matches = _coverage_match_ids(searchable, index, ranks)
        winner = matches[0] if matches else None
        # Scan the URL once for mandatory literals, then verify only candidates
        # that could beat the current winner. No URLs × all-bases fallback loop.
        best_rank = ranks[winner] if winner is not None else len(records)
        if not best_rank or not joined_patterns:
            candidates = ()
        elif len(joined_patterns) <= 8:
            # A short direct list is cheaper than scanning every character.
            candidates = (basis_id for basis_id in joined_patterns if ranks[basis_id] < best_rank)
        else:
            candidates = _joined_candidates(searchable, joined_index, ranks, best_rank)
        for candidate in sorted(candidates, key=ranks.__getitem__):
            if joined_wildcard_matches(searchable, joined_patterns[candidate]):
                winner = candidate
                break
        rows.append((url, impressions, revenue, records[winner].basis if winner is not None else NO_MATCH))
    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS)


def run_ui():
    import streamlit as st
    st.set_page_config(page_title="Manual Basis Coverage", layout="wide")
    st.title("Manual Basis Coverage")
    st.caption("Upload a URL CSV and enter your own bases. The lowest priority wins (1000 before 2000); ties prefer the longer basis. Blank priorities catch last. Wildcard fragments can be separated or joined: thanks*giving catches thanksgiving and thanks-giving. ~word~ locks an exact word. URL matching ignores capitalization; output preserves your basis labels.")
    upload = st.file_uploader("URL performance CSV", type=["csv"])
    if upload is None:
        st.info("Choose a CSV containing URLs and optional impressions/revenue columns.")
        return
    try:
        raw = upload.getvalue()
        digest = hashlib.sha256(raw).hexdigest()
        old_headers = st.session_state.get("manual_headers")
        if old_headers is None or old_headers[0] != digest:
            old_headers = (digest, list(read_csv_bytes(raw, nrows=0).columns))
            st.session_state["manual_headers"] = old_headers
        columns = old_headers[1]
        if not columns:
            raise ValueError("The uploaded CSV has no columns.")
        mapping = st.columns(3)
        suggested_url = suggested_column(columns, ["stripped url", "url", "urls", "page url", "page"])
        with mapping[0]:
            url_column = st.selectbox("URL column", columns, index=columns.index(suggested_url) if suggested_url else 0, key=f"url_{digest}")
        optionals = [None] + columns
        selected_metrics = []
        for container, label, aliases in [(mapping[1], "Impressions column", ["imp", "keyword impressions", "impressions"]),
            (mapping[2], "Revenue column", ["rev", "revenue", "keyword revenue", "earnings"])]:
            with container:
                suggested = suggested_column(columns, aliases)
                selected_metrics.append(st.selectbox(label, optionals, index=optionals.index(suggested),
                    format_func=lambda value: "Not supplied (use 0)" if value is None else value, key=f"{label}_{digest}"))
        input_key = (digest, url_column, *selected_metrics)
        saved_input = st.session_state.get("manual_prepared_input")
        if saved_input is None or saved_input[0] != input_key:
            wanted = list(dict.fromkeys([url_column] + [column for column in selected_metrics if column]))
            prepared, removed = prepare_urls(read_csv_bytes(raw, usecols=wanted), url_column, *selected_metrics)
            saved_input = (input_key, prepared, removed)
            st.session_state["manual_prepared_input"] = saved_input
        _, prepared, removed = saved_input
        if removed:
            st.caption(f"Removed {removed:,} report-total rows.")
        st.subheader("Your Bases")
        st.caption("Enter one basis per row. Use Basis for facty.com*health. Choose Full url_pattern only for a complete pattern such as patternkeywords.global*facty.com*health; its basis becomes facty.com*health. For a phrase such as heart health, use heart*health when words may be separated.")
        source_type = st.radio("Basis input", ["Data editor", "Paste bases", "Upload bases CSV"], horizontal=True)
        default_language = st.text_input("Default language code", value="EN").strip().upper()
        if source_type == "Data editor":
            entered = st.data_editor(pd.DataFrame([{"Basis": "", "Language Code": "EN", "Priority": "", "Input Type": "Basis"}]),
                num_rows="dynamic", hide_index=True, use_container_width=True, key="manual_basis_editor",
                column_config={"Basis": st.column_config.TextColumn("Basis"),
                    "Language Code": st.column_config.TextColumn("Language Code"),
                    "Priority": st.column_config.TextColumn("Priority"),
                    "Input Type": st.column_config.SelectboxColumn("Input Type", options=["Basis", "Full url_pattern"])})
        elif source_type == "Paste bases":
            pasted = st.text_area("One basis per line", placeholder="thanks*giving\nheart*health\nfacty.com*health", height=160)
            input_type = st.radio("Pasted values are", ["Basis", "Full url_pattern"], horizontal=True)
            entered = pd.DataFrame({"Basis": [line.strip() for line in pasted.splitlines() if line.strip()], "Input Type": input_type})
        else:
            bases_upload = st.file_uploader("Bases CSV (Basis, Language Code, Priority; optional Input Type)", type=["csv"], key="manual_bases_csv")
            if bases_upload is None:
                return
            entered = read_csv_bytes(bases_upload.getvalue())
        basis_column = suggested_column(entered.columns, ["basis", "basis name", "url_pattern", "pattern"])
        if entered.empty or (basis_column is not None and not entered[basis_column].map(text_value).ne("").any()):
            st.info("Enter at least one basis to check coverage.")
            return
        bases = prepare_bases(entered, default_language)
        languages = sorted(bases.language.unique())
        selected_languages = st.multiselect("Basis languages to include", languages, default=languages)
        excluded = st.multiselect("Exclude bases (optional)", list(dict.fromkeys(bases.basis)), default=[])
        signature = hashlib.sha256((repr(input_key) + bases.to_json() + repr(selected_languages) + repr(excluded)).encode()).hexdigest()
        if st.button("Check Coverage", type="primary", disabled=prepared.empty or not selected_languages):
            st.session_state.pop("manual_result", None)
            st.session_state.pop("manual_download", None)
            with st.spinner(f"Checking {len(prepared):,} URLs..."):
                st.session_state["manual_result"] = (signature, create_report(prepared, bases, selected_languages, excluded))
        caught = st.session_state.get("manual_result")
        if caught is None:
            return
        if caught[0] != signature:
            st.info("Inputs changed. Check Coverage again to refresh the result.")
            return
        report = caught[1]
        covered = report["matching basis"].ne(NO_MATCH)
        first, second, third = st.columns(3)
        first.metric("URLs", f"{len(report):,}")
        second.metric("Covered URLs", f"{int(covered.sum()):,}")
        total_impressions = report.imp.sum()
        third.metric("Impressions Covered", f"{100 * report.loc[covered, 'imp'].sum() / total_impressions:.1f}%" if total_impressions else "0.0%")
        st.dataframe(report.head(1000), hide_index=True, use_container_width=True)
        if len(report) > 1000:
            st.caption("Showing the first 1,000 rows. The CSV includes all rows.")
        if st.button("Prepare CSV Download"):
            st.session_state["manual_download"] = (signature, report.to_csv(index=False).encode("utf-8-sig"))
        download = st.session_state.get("manual_download")
        if download and download[0] == signature:
            st.download_button("Download Coverage CSV", download[1], "manual_basis_coverage.csv", "text/csv")
    except (ValueError, KeyError, pd.errors.ParserError) as error:
        st.error(str(error))


def run_cli():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--csv", required=True, type=Path, help="URL performance CSV")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--basis", action="append", help="Basis; repeat this option for multiple bases")
    group.add_argument("--bases-csv", type=Path, help="CSV with Basis and optional Language Code, Priority and Input Type")
    parser.add_argument("--url-column")
    parser.add_argument("--imp-column")
    parser.add_argument("--rev-column")
    parser.add_argument("--default-language", default="EN")
    parser.add_argument("--language", action="append", help="Included basis language; repeat for multiple languages")
    parser.add_argument("--full-patterns", action="store_true", help="Values are full domain*basis url_patterns")
    parser.add_argument("--exclude", action="append", default=[], help="Exclude this exact basis label")
    parser.add_argument("--output", type=Path, default=Path("manual_basis_coverage.csv"))
    args = parser.parse_args()
    try:
        raw = args.csv.read_bytes()
        columns = list(read_csv_bytes(raw, nrows=0).columns)
        url_column = args.url_column or suggested_column(columns, ["stripped url", "url", "urls", "page url"])
        imp_column = args.imp_column or suggested_column(columns, ["imp", "keyword impressions", "impressions"])
        rev_column = args.rev_column or suggested_column(columns, ["rev", "revenue", "keyword revenue"])
        if url_column is None:
            raise ValueError("Could not detect the URL column; specify --url-column.")
        wanted = list(dict.fromkeys([url_column] + [value for value in (imp_column, rev_column) if value]))
        prepared, removed = prepare_urls(read_csv_bytes(raw, usecols=wanted), url_column, imp_column, rev_column)
        entered = read_csv_bytes(args.bases_csv.read_bytes()) if args.bases_csv else pd.DataFrame({"Basis": args.basis})
        bases = prepare_bases(entered, args.default_language, "Full url_pattern" if args.full_patterns else "Basis")
        if args.language and not {value.upper() for value in args.language}.issubset(set(bases.language)):
            raise ValueError("A requested language is absent from the supplied bases.")
        report = create_report(prepared, bases, args.language, args.exclude)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        report.to_csv(args.output, index=False, encoding="utf-8-sig")
        print(f"Saved {len(report):,} URLs to {args.output}. Removed {removed:,} total rows.")
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"Error: {error}\n")


if __name__ == "__main__":
    if any(arg in ("--csv", "--help", "-h") or arg.startswith("--csv=") for arg in sys.argv[1:]):
        run_cli()
    else:
        try:
            run_ui()
        except ModuleNotFoundError as error:
            if error.name != "streamlit":
                raise
            raise SystemExit("Install Streamlit with: python -m pip install pandas streamlit\nThen run: streamlit run manual_basis_coverage_fast.py\nOr use CLI mode: python manual_basis_coverage_fast.py --help")

