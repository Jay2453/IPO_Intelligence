import io
import re
from typing import List, Dict, Any, Optional, Tuple
import pdfplumber

from app.pipeline.interfaces import IStructuredExtractor


class PdfExtractionError(Exception):
    """Raised when PDF structure cannot be parsed or is corrupted."""
    pass


def parse_numeric_cell(cell_value: Optional[str]) -> Optional[float]:
    """
    Parses a raw table cell string into a numeric float.
    Handles commas ('1,204.92'), parentheses for negatives ('(24.66)'),
    percentages ('65.73%'), and dashes/empty values.
    Returns None for missing values (never 0.0).
    """
    if not cell_value or not isinstance(cell_value, str):
        return None

    cleaned = cell_value.strip().replace("\n", " ")
    if cleaned in ("-", "", "N/A", "null", "None", "[*]", "[+]"):
        return None

    is_negative = False
    paren_match = re.match(r"^\((.+)\)$", cleaned)
    if paren_match:
        is_negative = True
        cleaned = paren_match.group(1).strip()

    # Remove Rs, spaces, %, keep digits and .
    cleaned = re.sub(r"[Rs\s%]", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace(",", "")

    num_match = re.search(r"^-?\d+(?:\.\d+)?", cleaned)
    if not num_match:
        return None

    try:
        val = float(num_match.group(0))
        return -val if is_negative else val
    except ValueError:
        return None


def normalize_to_crores(value: Optional[float], unit_str: str) -> Optional[float]:
    """
    Normalizes monetary values from various source units to Crores.
    1 Crore = 100 Lakhs = 10 Million = 10,000,000 INR.
    """
    if value is None:
        return None

    unit_lower = unit_str.lower()
    if "million" in unit_lower:
        return round(value * 0.1, 4)
    elif "lakh" in unit_lower:
        return round(value * 0.01, 4)
    elif "crore" in unit_lower:
        return round(value, 4)
    elif "thousand" in unit_lower:
        return round(value * 0.0001, 4)
    elif "inr" in unit_lower or "rupee" in unit_lower or "rs" in unit_lower:
        return round(value / 1e7, 4)

    if abs(value) > 1000000:
        return round(value / 1e7, 4)
    return round(value, 4)


def extract_fiscal_period(header_str: str) -> Optional[str]:
    """
    Standardizes column header strings to fiscal periods like 'FY26', 'FY25', 'H1FY25'.
    """
    if not header_str:
        return None

    cleaned = header_str.replace("\n", " ").strip()

    match_fiscal = re.search(r"(?:Fiscal(?:\s+Year)?|FY)\s*(20\d{2}|\d{2})", cleaned, re.IGNORECASE)
    if match_fiscal:
        yr = match_fiscal.group(1)
        return f"FY{yr[2:]}" if len(yr) == 4 else f"FY{yr}"

    match_march = re.search(r"March\s*(?:31,?\s*)?(20\d{2})", cleaned, re.IGNORECASE)
    if match_march:
        return f"FY{match_march.group(1)[2:]}"

    match_sep = re.search(r"September\s*(?:30,?\s*)?(20\d{2})", cleaned, re.IGNORECASE)
    if match_sep:
        yr = int(match_sep.group(1)) + 1
        return f"H1FY{str(yr)[2:]}"

    return None


# Regex: trailing numeric tokens at end of a text line
_TRAILING_NUM_RE = re.compile(
    r"[\s\t]+(\(\s*[\d,]+(?:\.\d+)?%?\s*\)|[\d,]+(?:\.\d+)?%?|-|N/A)\s*$"
)


def _strip_trailing_numbers(line: str) -> Tuple[str, List[str]]:
    """
    Strips numeric tokens from the right end of a text line.
    Returns (label_portion, [token1, token2, ...]) left-to-right.
    """
    tokens: List[str] = []
    curr = line
    while True:
        m = _TRAILING_NUM_RE.search(curr)
        if not m:
            break
        tokens.insert(0, m.group(1).strip())
        curr = curr[: m.start()].rstrip()
    return curr, tokens


def _find_fiscal_periods_in_lines(lines: List[str], idx: int) -> Tuple[List[str], int]:
    """
    Scans line at idx (and optionally idx+1) for fiscal-period headers.
    Returns (periods_list, lines_consumed).
    """
    line = lines[idx]
    next_line = lines[idx + 1] if idx + 1 < len(lines) else ""

    for candidate, consume in [(line, 1), (f"{line} {next_line}", 2)]:
        periods: List[str] = []

        # Pattern 1: Explicit Fiscal/FY/March year patterns
        matches = re.findall(
            r"(?:(?:Fiscal(?:\s+Year)?|FY)\s*(20\d{2}|\d{2})|March\s*(?:31,?\s*)?(20\d{2}))",
            candidate,
            re.IGNORECASE,
        )
        for m in matches:
            yr = m[0] or m[1]
            fy = f"FY{yr[2:]}" if len(yr) == 4 else f"FY{yr}"
            if fy not in periods:
                periods.append(fy)

        if len(periods) >= 2:
            if consume == 2:
                years_in_next = re.findall(r"\b(20\d{2}|\d{2})\b", next_line)
                if not any(p[2:] in years_in_next for p in periods):
                    consume = 1
            return periods, consume

        # Pattern 2: plain 4-digit years in a context line
        if any(kw in candidate.lower() for kw in [
            "fiscal", "year", "particular", "ended", "as on", "as at", "kpi", "kpis",
        ]):
            year_matches = re.findall(r"\b(20\d{2})\b", candidate)
            seen: List[str] = []
            for yr in year_matches:
                fy = f"FY{yr[2:]}"
                if fy not in seen:
                    seen.append(fy)
            if len(seen) >= 2:
                if consume == 2:
                    years_in_next = re.findall(r"\b(20\d{2})\b", next_line)
                    if not any(p[2:] in years_in_next for p in seen):
                        consume = 1
                return seen, consume

    return [], 1


def _match_metric_label(raw_label: str) -> Tuple[Optional[str], bool]:
    """
    Maps raw text label to a FinancialObservation field.
    Returns (field_name, is_rate_or_per_share). Returns (None, False) if not matched.
    """
    label = raw_label.lower().strip()
    # Strip footnote markers (1), (2)(3) etc.
    label = re.sub(r"\(\d+\)(\(\d+\))*", " ", label)
    # Strip unit markers like (in rs.) but not negatives
    label = re.sub(r"\(in\s+[a-z \.]+\)", " ", label, flags=re.IGNORECASE)
    label = re.sub(r"\s+", " ", label).strip()

    # Revenue
    if any(t in label for t in ["revenue from operations", "total revenue", "total income"]):
        if any(t in label for t in ["%", "percent", "growth", "margin", "share of", "% of"]):
            return None, False
        return "revenue_crores", False
    # Bare 'revenue' label (common in abridged prospectuses)
    if re.search(r"\brevenue\b", label) and not any(
        t in label for t in ["%", "percent", "growth", "margin", "b2b", "d2c", "share of", "% of"]
    ):
        return "revenue_crores", False

    # EBITDA (not margin)
    if "ebitda" in label and "margin" not in label and "%" not in label:
        return "ebitda_crores", False

    # PAT
    pat_patterns = [
        "profit/(loss) after tax",
        "profit / (loss) after tax",
        "profit/(loss) for the",
        "restated profit for the year",
        "profit for the period/ year",
        "profit for the period",
        "profit for the year",
        "profit after tax",
        "net profit after tax",
        "net profit for",
        "restated pat",
    ]
    if any(t in label for t in pat_patterns) and "margin" not in label and "%" not in label:
        return "pat_crores", False

    # Net worth / Equity (not ratios or per-share)
    if any(t in label for t in ["net worth", "total equity"]):
        if not any(t in label for t in ["return", "%", "per share", "per equity"]):
            return "net_worth_crores", False

    # Total Assets
    if "total assets" in label:
        return "total_assets_crores", False

    # Total Liabilities
    if "total liabilities" in label:
        return "total_liabilities_crores", False

    # Borrowings / Debt
    if any(t in label for t in ["total borrowings", "total debt", "borrowings"]):
        return "total_debt_crores", False

    # Operating Cash Flow (not investing/financing)
    ocf_patterns = [
        "cash flow from operating activities",
        "cash generated from operating",
        "cash used in operating",
        "net cash from operating",
        "net cash used in operating",
        "operating activities",
    ]
    if any(t in label for t in ocf_patterns):
        if "investing" in label or "financing" in label:
            return None, False
        return "operating_cash_flow_crores", False

    # ROE / RONW
    if any(t in label for t in ["return on equity", "return on net worth", "ronw"]):
        return "roe_pct", True
    if re.search(r"\broe\b", label):
        return "roe_pct", True

    # ROCE
    if "return on capital employed" in label or re.search(r"\broce\b", label):
        return "roce_pct", True

    # EPS
    if any(t in label for t in ["basic eps", "diluted eps", "earnings per share"]):
        return "eps_inr", True

    # NAV per share
    if any(t in label for t in ["net asset value per", "nav per share"]):
        return "nav_per_share_inr", True

    return None, False


def _detect_unit(text: str) -> str:
    """Detects the monetary unit from a block of text."""
    lower = text.lower()
    if "million" in lower:
        return "MILLIONS"
    if "lakh" in lower:
        return "LAKHS"
    if "crore" in lower:
        return "CRORES"
    return "CRORES"


class PdfFinancialExtractor(IStructuredExtractor):
    """
    Extracts financial statement metrics from public IPO offer documents (DRHP, RHP, Abridged Prospectus).

    Uses two complementary strategies per page:
    1. pdfplumber structured table extraction (works for bordered/ruled tables)
    2. Text-line extraction (handles flowing-text tables common in abridged prospectuses)
    """

    FINANCIAL_KEYWORDS = [
        "restated summary statement",
        "financial information",
        "balance sheet",
        "profit and loss",
        "revenue from operations",
        "financial kpis",
        "operational kpis",
        "return on equity",
        "return on net worth",
        "net worth",
        "summary of restated",
        "key performance indicator",
        "profit/(loss) after tax",
        "profit after tax",
        "ebitda",
    ]

    METRIC_FIELDS = [
        "revenue_crores", "ebitda_crores", "pat_crores", "total_assets_crores",
        "net_worth_crores", "total_liabilities_crores", "total_debt_crores",
        "operating_cash_flow_crores", "roe_pct", "roce_pct", "eps_inr", "nav_per_share_inr",
    ]

    ISSUE_TERMS_KEYWORDS = [
        "objects of the offer",
        "capital structure",
        "shareholding pattern",
        "pre-offer shareholding",
        "the offer",
        "price band",
    ]

    def __init__(self, max_pages_to_scan: int = 150):
        self.max_pages_to_scan = max_pages_to_scan

    def extract_financials(self, document_bytes: bytes) -> List[Dict[str, Any]]:
        """
        Scans document pages for financial tables and extracts multi-year observations.
        Returns a list of dicts suitable for creating FinancialObservation records.
        """
        try:
            with pdfplumber.open(io.BytesIO(document_bytes)) as pdf:
                pages_to_check = min(len(pdf.pages), self.max_pages_to_scan)
                observations_by_fy: Dict[str, Dict[str, Any]] = {}

                for page_idx in range(pages_to_check):
                    page = pdf.pages[page_idx]
                    page_number = page_idx + 1
                    text = page.extract_text() or ""
                    text_lower = text.lower()

                    if not any(kw in text_lower for kw in self.FINANCIAL_KEYWORDS):
                        continue

                    is_standalone = "standalone" in text_lower and "consolidated" not in text_lower
                    statement_type = "STANDALONE" if is_standalone else "CONSOLIDATED"
                    is_restated = "restated" in text_lower
                    default_unit = _detect_unit(text)  # scan full page text for unit note

                    # Strategy 1: pdfplumber table extraction
                    tables = page.extract_tables()
                    for table in tables:
                        if not table or len(table) < 2:
                            continue
                        self._process_table(
                            table=table,
                            page_number=page_number,
                            statement_type=statement_type,
                            is_restated=is_restated,
                            page_text=text,
                            default_unit=default_unit,
                            observations_by_fy=observations_by_fy,
                        )

                    # Strategy 2: text-line extraction
                    self._process_page_text_lines(
                        text=text,
                        page_number=page_number,
                        statement_type=statement_type,
                        is_restated=is_restated,
                        default_unit=default_unit,
                        observations_by_fy=observations_by_fy,
                    )

                final_results: List[Dict[str, Any]] = []
                for fy, obs in sorted(observations_by_fy.items()):
                    validated = self._validate_observation(obs)
                    final_results.append(validated)

                return final_results

        except Exception as exc:
            raise PdfExtractionError(f"Failed to extract financial statements from PDF: {exc}") from exc

    # -------------------------------------------------------------------------
    # Text-line extraction strategy
    # -------------------------------------------------------------------------

    def _process_page_text_lines(
        self,
        text: str,
        page_number: int,
        statement_type: str,
        is_restated: bool,
        default_unit: str,
        observations_by_fy: Dict[str, Dict[str, Any]],
    ) -> None:
        """
        Parses plain text lines to extract financial metrics.
        Handles abridged prospectus layout where pdfplumber table detection fails.
        """
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        i = 0
        while i < len(lines):
            periods, consumed = _find_fiscal_periods_in_lines(lines, i)
            if not periods:
                i += 1
                continue

            i += consumed
            num_periods = len(periods)

            # Re-detect unit from a local window around the fiscal header.
            # Unit notes like '(in Rs. million)' typically appear 0-5 lines above the header.
            local_start = max(0, i - consumed - 6)
            local_window = " ".join(lines[local_start:i])
            active_unit = _detect_unit(local_window) if local_window else default_unit
            # Also check a few lines below the header (some docs put it after)
            if active_unit == "CRORES":
                post_window = " ".join(lines[i : min(len(lines), i + 4)])
                maybe_unit = _detect_unit(post_window) if post_window else "CRORES"
                if maybe_unit != "CRORES":
                    active_unit = maybe_unit

            for fy in periods:
                if fy not in observations_by_fy:
                    observations_by_fy[fy] = self._blank_observation(
                        fy, page_number, statement_type, is_restated
                    )

            while i < len(lines):
                line = lines[i]
                line_lower = line.lower()

                if line_lower.startswith("notes:") or line_lower.startswith("note:"):
                    break

                # Stop if we hit a new distinct fiscal header section
                new_periods, _ = _find_fiscal_periods_in_lines(lines, i)
                if new_periods and len(new_periods) >= 2 and set(new_periods) != set(periods):
                    break

                label_part, tokens = _strip_trailing_numbers(line)

                # Trim excess tokens (take rightmost N)
                if len(tokens) > num_periods:
                    tokens = tokens[len(tokens) - num_periods:]

                if len(tokens) != num_periods:
                    i += 1
                    continue

                metric_key, is_rate = _match_metric_label(label_part)
                if not metric_key:
                    i += 1
                    continue

                for period_idx, fy in enumerate(periods):
                    val_str = tokens[period_idx]
                    parsed = parse_numeric_cell(val_str)
                    if parsed is None:
                        continue

                    if is_rate or metric_key in ("eps_inr", "nav_per_share_inr"):
                        final_val = round(parsed, 4)
                    else:
                        final_val = normalize_to_crores(parsed, active_unit)

                    obs = observations_by_fy[fy]
                    if obs.get(metric_key) is None:
                        obs[metric_key] = final_val
                        if obs.get("source_page") is None:
                            obs["source_page"] = page_number
                            obs["raw_data_provenance"]["source_page"] = page_number
                        obs["raw_data_provenance"]["line_items_extracted"][metric_key] = {
                            "raw_label": label_part.strip(),
                            "raw_cell": val_str,
                            "normalized_value": final_val,
                            "source_page": page_number,
                            "extraction_method": "TEXT_LINE",
                        }
                i += 1

    # -------------------------------------------------------------------------
    # pdfplumber table extraction strategy
    # -------------------------------------------------------------------------

    def _process_table(
        self,
        table: List[List[Optional[str]]],
        page_number: int,
        statement_type: str,
        is_restated: bool,
        page_text: str,
        default_unit: str,
        observations_by_fy: Dict[str, Dict[str, Any]],
    ):
        """Processes a single pdfplumber table, extracting periods and metrics."""
        table_text = " ".join([" ".join([c for c in row if c]) for row in table[:3]])
        unit = _detect_unit(f"{page_text[:400]} {table_text}") or default_unit

        period_cols: List[Tuple[int, str]] = []
        last_header_row_idx = 0

        for r_idx in range(min(4, len(table))):
            row = table[r_idx]
            for c_idx, cell in enumerate(row):
                if cell:
                    fy = extract_fiscal_period(cell)
                    if fy and not any(p[1] == fy for p in period_cols):
                        period_cols.append((c_idx, fy))
                        last_header_row_idx = max(last_header_row_idx, r_idx)

        if not period_cols:
            return

        period_cols.sort(key=lambda x: x[0])

        for _, fy in period_cols:
            if fy not in observations_by_fy:
                observations_by_fy[fy] = self._blank_observation(
                    fy, page_number, statement_type, is_restated
                )

        for row in table[last_header_row_idx + 1:]:
            if not row or not any(row):
                continue

            label_col = -1
            label = ""
            for idx, c in enumerate(row):
                if c and len(c.strip()) > 1:
                    label = c.replace("\n", " ").strip()
                    label_col = idx
                    break

            if not label or label_col < 0:
                continue

            metric_key, is_rate = _match_metric_label(label)
            if not metric_key:
                continue

            data_cells = [
                (idx, c) for idx, c in enumerate(row)
                if idx > label_col and c and c.strip()
            ]
            if not data_cells:
                continue

            if len(data_cells) == len(period_cols):
                for d_idx, (_, cell_val) in enumerate(data_cells):
                    _, fy = period_cols[d_idx]
                    self._assign_metric(
                        observations_by_fy, fy, metric_key, cell_val,
                        is_rate, unit, label, page_number, "PDFPLUMBER_TABLE",
                    )
            else:
                for cell_idx, cell_val in data_cells:
                    closest_fy = min(period_cols, key=lambda p: abs(p[0] - cell_idx))[1]
                    self._assign_metric(
                        observations_by_fy, closest_fy, metric_key, cell_val,
                        is_rate, unit, label, page_number, "PDFPLUMBER_TABLE",
                    )

    def _assign_metric(
        self,
        observations_by_fy: Dict[str, Dict[str, Any]],
        fy: str,
        metric_key: str,
        cell_val: str,
        is_rate: bool,
        default_unit: str,
        label: str,
        page_number: int,
        method: str = "PDFPLUMBER_TABLE",
    ):
        parsed_num = parse_numeric_cell(cell_val)
        if parsed_num is None:
            return

        if is_rate or metric_key in ("eps_inr", "nav_per_share_inr"):
            final_val = round(parsed_num, 4)
        else:
            final_val = normalize_to_crores(parsed_num, default_unit)

        obs = observations_by_fy[fy]
        if obs.get(metric_key) is None:
            obs[metric_key] = final_val
            if obs.get("source_page") is None:
                obs["source_page"] = page_number
                obs["raw_data_provenance"]["source_page"] = page_number
            obs["raw_data_provenance"]["line_items_extracted"][metric_key] = {
                "raw_label": label,
                "raw_cell": cell_val,
                "normalized_value": final_val,
                "source_page": page_number,
                "extraction_method": method,
            }

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _blank_observation(
        self, fy: str, page_number: int, statement_type: str, is_restated: bool
    ) -> Dict[str, Any]:
        return {
            "fiscal_year": fy,
            "period_months": 12 if not fy.startswith("H1") else 6,
            "statement_type": statement_type,
            "is_restated": is_restated,
            "currency": "INR",
            "unit": "CRORES",
            "source_page": page_number,
            "extraction_method": "PDFPLUMBER_TABLE",
            "verification_status": "EXTRACTED",
            "revenue_crores": None,
            "ebitda_crores": None,
            "pat_crores": None,
            "total_assets_crores": None,
            "net_worth_crores": None,
            "total_liabilities_crores": None,
            "total_debt_crores": None,
            "operating_cash_flow_crores": None,
            "roe_pct": None,
            "roce_pct": None,
            "eps_inr": None,
            "nav_per_share_inr": None,
            "raw_data_provenance": {
                "source_page": page_number,
                "line_items_extracted": {},
                "validation_checks": [],
            },
        }

    def _validate_observation(self, obs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Runs financial consistency checks. Sets verification_status:
          EXTRACTED: some metrics present, no conflicts
          CONFLICT:  logical inconsistency detected
          FAILED:    no usable metrics whatsoever
        """
        checks = []
        status = "EXTRACTED"

        rev = obs.get("revenue_crores")
        pat = obs.get("pat_crores")
        ebitda = obs.get("ebitda_crores")
        assets = obs.get("total_assets_crores")

        if rev is not None and pat is not None and rev > 0:
            if pat > rev:
                checks.append("WARNING: PAT exceeds Total Revenue")
                status = "CONFLICT"
            else:
                checks.append("PASS: PAT <= Revenue consistency")

        if assets is not None:
            if assets < 0:
                checks.append("ERROR: Negative Total Assets")
                status = "CONFLICT"
            else:
                checks.append("PASS: Non-negative Total Assets")

        if rev is not None and ebitda is not None and rev > 0:
            if ebitda > rev * 1.2:
                checks.append("WARNING: EBITDA significantly exceeds Total Revenue")
                status = "CONFLICT"
            else:
                checks.append("PASS: EBITDA in plausible bounds")

        if rev is not None and rev >= 0:
            checks.append("PASS: Revenue is non-negative")

        usable_fields = [
            "revenue_crores", "ebitda_crores", "pat_crores", "total_assets_crores",
            "net_worth_crores", "total_liabilities_crores", "total_debt_crores",
            "operating_cash_flow_crores", "roe_pct", "roce_pct", "eps_inr", "nav_per_share_inr",
        ]
        if not any(obs.get(f) is not None for f in usable_fields):
            checks.append("FAIL: No usable financial metrics extracted")
            status = "FAILED"

        obs["verification_status"] = status
        obs["raw_data_provenance"]["validation_checks"] = checks

        # Determine accurate observation-level extraction_method and primary source_page
        line_items = obs.get("raw_data_provenance", {}).get("line_items_extracted", {})
        if line_items:
            methods = {
                item.get("extraction_method")
                for item in line_items.values()
                if item.get("extraction_method")
            }
            if len(methods) == 1:
                obs["extraction_method"] = next(iter(methods))
            elif len(methods) > 1:
                obs["extraction_method"] = "HYBRID"

            # Determine primary statement source page from core statement metrics
            core_priority = [
                "revenue_crores", "pat_crores", "net_worth_crores", "ebitda_crores",
                "total_debt_crores", "operating_cash_flow_crores"
            ]
            primary_page = None
            for cp in core_priority:
                if cp in line_items and line_items[cp].get("source_page"):
                    primary_page = line_items[cp]["source_page"]
                    break
            if primary_page is None:
                item_pages = [item["source_page"] for item in line_items.values() if "source_page" in item]
                primary_page = min(item_pages) if item_pages else obs.get("source_page")

            if primary_page is not None:
                obs["source_page"] = primary_page
                obs["raw_data_provenance"]["source_page"] = primary_page
                obs["raw_data_provenance"]["source_pages"] = sorted(
                    list({item["source_page"] for item in line_items.values() if "source_page" in item})
                )
        return obs

    def extract_issue_terms(self, document_bytes: bytes) -> Dict[str, Any]:
        """
        Extracts issue-level terms such as promoter holding, use of proceeds, risk factors.
        """
        terms: Dict[str, Any] = {
            "promoter_holding_pct": None,
            "fresh_issue_crores": None,
            "ofs_crores": None,
            "price_band_min": None,
            "price_band_max": None,
            "use_of_proceeds": [],
            "risk_factors_count": None,
            "material_risks_sample": [],
        }

        try:
            with pdfplumber.open(io.BytesIO(document_bytes)) as pdf:
                pages_to_check = min(len(pdf.pages), self.max_pages_to_scan)

                for page_idx in range(pages_to_check):
                    page = pdf.pages[page_idx]
                    text = page.extract_text() or ""
                    text_lower = text.lower()

                    if "promoter" in text_lower and terms["promoter_holding_pct"] is None:
                        for table in page.extract_tables():
                            for row in table:
                                row_str = " ".join([str(c) for c in row if c])
                                if "total (a)" in row_str.lower() or "promoters" in row_str.lower():
                                    pct_match = re.search(r"(\d+(?:\.\d+)?)\s*%", row_str)
                                    if pct_match:
                                        val = float(pct_match.group(1))
                                        if 10.0 <= val <= 100.0:
                                            terms["promoter_holding_pct"] = val
                                            break

                    if "objects of the offer" in text_lower or "use of proceeds" in text_lower:
                        for table in page.extract_tables():
                            for row in table:
                                if len(row) >= 2:
                                    part = str(row[1] or row[0]).replace("\n", " ").strip()
                                    if len(part) > 10 and not part.lower().startswith("particulars"):
                                        if part not in terms["use_of_proceeds"] and len(terms["use_of_proceeds"]) < 5:
                                            terms["use_of_proceeds"].append(part)

                    if "risk factors" in text_lower and not terms["material_risks_sample"]:
                        for line in text.split("\n"):
                            line_s = line.strip()
                            if len(line_s) > 25 and (
                                line_s.startswith("*") or line_s.startswith("-")
                                or re.match(r"^\d+\.", line_s)
                            ):
                                if len(terms["material_risks_sample"]) < 4:
                                    terms["material_risks_sample"].append(line_s)

        except Exception:
            pass

        return terms
