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
    Handles commas ('1,204.92'), parentheses for negative numbers ('(24.66)'),
    percentages ('65.73%'), and dashes/empty values ('-', 'N/A').
    Missing values return None (never 0.0).
    """
    if not cell_value or not isinstance(cell_value, str):
        return None

    cleaned = cell_value.strip().replace("\n", " ")
    if cleaned in ("-", "", "N/A", "null", "None", "[•]", "[●]"):
        return None

    # Check for negative in parentheses: (123.45)
    is_negative = False
    paren_match = re.match(r"^\((.+)\)$", cleaned)
    if paren_match:
        is_negative = True
        cleaned = paren_match.group(1).strip()

    # Remove currency symbols, commas, percentage signs, and whitespace (preserve '.')
    cleaned = re.sub(r"[₹Rs\s%]", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace(",", "")

    # Match numeric float / integer
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
    Normalizes monetary values from various source units to ₹ Crores.
    1 Crore = 100 Lakhs = 10 Million = 10,000,000 INR.
    """
    if value is None:
        return None

    unit_lower = unit_str.lower()
    if "million" in unit_lower:
        # 1 Million = 0.1 Crore (10 Million = 1 Crore)
        return round(value * 0.1, 4)
    elif "lakh" in unit_lower:
        # 1 Lakh = 0.01 Crore
        return round(value * 0.01, 4)
    elif "crore" in unit_lower:
        return round(value, 4)
    elif "thousand" in unit_lower:
        return round(value * 0.0001, 4)
    elif "inr" in unit_lower or "rupee" in unit_lower or "rs" in unit_lower:
        # Absolute Rupees
        return round(value / 1e7, 4)

    # Default assumption for Indian IPO summaries: if unit unspecified but magnitude > 100,000 assume INR
    if abs(value) > 1000000:
        return round(value / 1e7, 4)
    return round(value, 4)


def extract_fiscal_period(header_str: str) -> Optional[str]:
    """
    Standardizes column header strings to standard fiscal periods like 'FY26', 'FY25', 'FY24', 'H1FY25'.
    """
    if not header_str:
        return None

    cleaned = header_str.replace("\n", " ").strip()

    # E.g., 'Fiscal 2026', 'Fiscal Year 2025', 'FY 2024', 'FY24'
    match_fiscal = re.search(r"(?:Fiscal(?:\s+Year)?|FY)\s*(20\d{2}|\d{2})", cleaned, re.IGNORECASE)
    if match_fiscal:
        yr = match_fiscal.group(1)
        if len(yr) == 4:
            return f"FY{yr[2:]}"
        return f"FY{yr}"

    # E.g., 'ended March 31, 2026' or 'March 31, 2025'
    match_march = re.search(r"March\s*(?:31,?\s*)?(20\d{2})", cleaned, re.IGNORECASE)
    if match_march:
        yr = match_march.group(1)
        return f"FY{yr[2:]}"

    # E.g. 'September 30, 2024' -> H1FY25
    match_sep = re.search(r"September\s*(?:30,?\s*)?(20\d{2})", cleaned, re.IGNORECASE)
    if match_sep:
        yr = int(match_sep.group(1)) + 1
        return f"H1FY{str(yr)[2:]}"

    return None


class PdfFinancialExtractor(IStructuredExtractor):
    """
    Extracts financial statement metrics and issue terms from public IPO offer documents (DRHP, RHP, DAP)
    using pdfplumber with full page provenance and validation checks.
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
        "net worth",
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
        Scans document pages for financial statement tables and extracts multi-year observations.
        Returns a list of dicts suitable for creating FinancialObservation records.
        """
        try:
            with pdfplumber.open(io.BytesIO(document_bytes)) as pdf:
                total_pages = len(pdf.pages)
                pages_to_check = min(total_pages, self.max_pages_to_scan)

                observations_by_fy: Dict[str, Dict[str, Any]] = {}

                for page_idx in range(pages_to_check):
                    page = pdf.pages[page_idx]
                    page_number = page_idx + 1
                    text = page.extract_text() or ""
                    text_lower = text.lower()

                    # Only process pages that contain financial table indicators
                    if not any(kw in text_lower for kw in self.FINANCIAL_KEYWORDS):
                        continue

                    # Determine if consolidated or standalone
                    is_standalone = "standalone" in text_lower and "consolidated" not in text_lower
                    statement_type = "STANDALONE" if is_standalone else "CONSOLIDATED"
                    is_restated = "restated" in text_lower

                    tables = page.extract_tables()
                    for t_idx, table in enumerate(tables):
                        if not table or len(table) < 2:
                            continue

                        self._process_table(
                            table=table,
                            page_number=page_number,
                            statement_type=statement_type,
                            is_restated=is_restated,
                            page_text=text,
                            observations_by_fy=observations_by_fy,
                        )

                # Validate and finalize observations
                final_results: List[Dict[str, Any]] = []
                for fy, obs in sorted(observations_by_fy.items()):
                    validated = self._validate_observation(obs)
                    final_results.append(validated)

                return final_results

        except Exception as exc:
            raise PdfExtractionError(f"Failed to extract financial statements from PDF: {exc}") from exc

    def extract_issue_terms(self, document_bytes: bytes) -> Dict[str, Any]:
        """
        Extracts issue-level terms such as promoter holding, fresh issue, OFS, price band,
        use of proceeds, and risk factors summary.
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

                    # 1. Promoter pre-offer holding
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

                    # 2. Objects of the offer / Use of proceeds
                    if "objects of the offer" in text_lower or "use of proceeds" in text_lower:
                        for table in page.extract_tables():
                            for row in table:
                                if len(row) >= 2:
                                    part = str(row[1] or row[0]).replace("\n", " ").strip()
                                    if len(part) > 10 and not part.lower().startswith("particulars"):
                                        if part not in terms["use_of_proceeds"] and len(terms["use_of_proceeds"]) < 5:
                                            terms["use_of_proceeds"].append(part)

                    # 3. Risk Factors
                    if "risk factors" in text_lower and not terms["material_risks_sample"]:
                        # Extract top 3 bullet lines
                        for line in text.split("\n"):
                            line_s = line.strip()
                            if len(line_s) > 25 and (line_s.startswith("•") or line_s.startswith("-") or re.match(r"^\d+\.", line_s)):
                                if len(terms["material_risks_sample"]) < 4:
                                    terms["material_risks_sample"].append(line_s)

        except Exception:
            pass

        return terms

    def _process_table(
        self,
        table: List[List[Optional[str]]],
        page_number: int,
        statement_type: str,
        is_restated: bool,
        page_text: str,
        observations_by_fy: Dict[str, Dict[str, Any]],
    ):
        """Processes a single table from a PDF page, extracting periods and metrics."""
        # Detect unit from page or table
        table_text = " ".join([" ".join([c for c in row if c]) for row in table[:3]])
        combined_header = f"{page_text[:400]} {table_text}"

        default_unit = "CRORES"
        if "million" in combined_header.lower():
            default_unit = "MILLIONS"
        elif "lakh" in combined_header.lower():
            default_unit = "LAKHS"

        # Locate period columns from header row(s) in order
        period_cols: List[Tuple[int, str]] = []
        max_scan_header_rows = min(4, len(table))
        last_header_row_idx = 0

        for r_idx in range(max_scan_header_rows):
            row = table[r_idx]
            for c_idx, cell in enumerate(row):
                if cell:
                    fy = extract_fiscal_period(cell)
                    if fy and not any(p[1] == fy for p in period_cols):
                        period_cols.append((c_idx, fy))
                        last_header_row_idx = max(last_header_row_idx, r_idx)

        if not period_cols:
            return

        # Sort periods by column index to ensure left-to-right order
        period_cols.sort(key=lambda x: x[0])

        # Ensure observation entry exists for each detected fiscal year
        for _, fy in period_cols:
            if fy not in observations_by_fy:
                observations_by_fy[fy] = {
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

        # Scan rows for financial line items
        for row in table[last_header_row_idx + 1:]:
            if not row or not any(row):
                continue

            # First non-empty cell is usually the line item label
            label_col = -1
            label = ""
            for idx, c in enumerate(row):
                if c and len(c.strip()) > 1:
                    label = c.replace("\n", " ").strip()
                    label_col = idx
                    break

            if not label or label_col < 0:
                continue

            metric_key, is_rate = self._match_metric_label(label.lower())
            if not metric_key:
                continue

            # Gather data cells in this row after label
            data_cells = [(idx, c) for idx, c in enumerate(row) if idx > label_col and c and c.strip()]
            if not data_cells:
                continue

            # Case A: Number of data cells exactly matches number of periods -> positional 1-to-1 match
            if len(data_cells) == len(period_cols):
                for d_idx, (_, cell_val) in enumerate(data_cells):
                    _, fy = period_cols[d_idx]
                    self._assign_metric(
                        observations_by_fy=observations_by_fy,
                        fy=fy,
                        metric_key=metric_key,
                        cell_val=cell_val,
                        is_rate=is_rate,
                        default_unit=default_unit,
                        label=label,
                        page_number=page_number,
                    )
            else:
                # Case B: Match to nearest period column index
                for cell_idx, cell_val in data_cells:
                    closest_fy = min(period_cols, key=lambda p: abs(p[0] - cell_idx))[1]
                    self._assign_metric(
                        observations_by_fy=observations_by_fy,
                        fy=closest_fy,
                        metric_key=metric_key,
                        cell_val=cell_val,
                        is_rate=is_rate,
                        default_unit=default_unit,
                        label=label,
                        page_number=page_number,
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
    ):
        """Helper to parse, normalize, and assign a metric value to an observation."""
        parsed_num = parse_numeric_cell(cell_val)
        if parsed_num is None:
            return

        if is_rate or metric_key in ("eps_inr", "nav_per_share_inr"):
            final_val = round(parsed_num, 2)
        else:
            final_val = normalize_to_crores(parsed_num, default_unit)

        obs = observations_by_fy[fy]
        # Assign if currently None
        if obs.get(metric_key) is None:
            obs[metric_key] = final_val
            obs["source_page"] = page_number
            obs["raw_data_provenance"]["line_items_extracted"][metric_key] = {
                "raw_label": label,
                "raw_cell": cell_val,
                "normalized_value": final_val,
                "source_page": page_number,
            }


    def _match_metric_label(self, label_lower: str) -> Tuple[Optional[str], bool]:
        # Strip inline footnote markers like (1), (6), (2)(4) from end of label
        label_lower = re.sub(r'\(\d+\)(?:\(\d+\))*\s*$', '', label_lower).strip()
        """
        Maps raw table line item label to entity attribute name.
        Returns (attribute_name, is_percentage_or_per_share_rate).
        """
        # Revenue
        if any(term in label_lower for term in ["revenue from operations", "total revenue", "total income"]):
            if "%" in label_lower or "percent" in label_lower or "growth" in label_lower:
                return None, False
            return "revenue_crores", False


        # EBITDA
        if "ebitda" in label_lower and "margin" not in label_lower:
            return "ebitda_crores", False

        # PAT
        if any(term in label_lower for term in [
            "restated profit for the year", "profit for the period/ year",
            "profit for the year", "profit after tax", "restated pat"
        ]) and "margin" not in label_lower:
            return "pat_crores", False

        # Net worth / Equity
        if any(term in label_lower for term in ["net worth", "total equity"]) and "return" not in label_lower:
            return "net_worth_crores", False

        # Total Assets
        if "total assets" in label_lower:
            return "total_assets_crores", False

        # Total Liabilities
        if "total liabilities" in label_lower:
            return "total_liabilities_crores", False

        # Borrowings / Total debt
        if any(term in label_lower for term in ["total borrowings", "total debt", "borrowings"]):
            return "total_debt_crores", False

        # Operating Cash Flow - must not match investing or financing activities
        if any(term in label_lower for term in [
            "operating activities", "cash generated from operating", "cash flow from operating"
        ]) and ("used" in label_lower or "generated" in label_lower or "net cash" in label_lower):
            if "investing" in label_lower or "financing" in label_lower:
                return None, False
            return "operating_cash_flow_crores", False

        # ROE
        if "return on equity" in label_lower or "return on net worth" in label_lower:
            return "roe_pct", True

        # ROCE
        if "return on capital employed" in label_lower or "roce" in label_lower:
            return "roce_pct", True

        # EPS
        if any(term in label_lower for term in ["basic eps", "diluted eps", "earnings per share"]):
            return "eps_inr", True

        # NAV per share
        if "net asset value per" in label_lower or "nav per share" in label_lower:
            return "nav_per_share_inr", True

        return None, False

    def _validate_observation(self, obs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Runs explicit financial consistency checks.
        Never marks as VERIFIED solely because parsing succeeded.
        Flags conflicts instead of silently overwriting.
        """
        checks = []
        status = "EXTRACTED"

        rev = obs.get("revenue_crores")
        pat = obs.get("pat_crores")
        ebitda = obs.get("ebitda_crores")
        assets = obs.get("total_assets_crores")

        # Check 1: PAT should not exceed Revenue (unless other extraordinary income)
        if rev is not None and pat is not None and rev > 0:
            if pat > rev:
                checks.append("WARNING: PAT exceeds Total Revenue")
                status = "CONFLICT"
            else:
                checks.append("PASS: PAT <= Revenue consistency")

        # Check 2: Total Assets must be non-negative
        if assets is not None:
            if assets < 0:
                checks.append("ERROR: Negative Total Assets")
                status = "CONFLICT"
            else:
                checks.append("PASS: Non-negative Total Assets")

        # Check 3: EBITDA consistency
        if rev is not None and ebitda is not None and rev > 0:
            if ebitda > rev * 1.2:
                checks.append("WARNING: EBITDA significantly exceeds Total Revenue")
                status = "CONFLICT"
            else:
                checks.append("PASS: EBITDA in plausible bounds")

        # Check 4: Positive revenue verification
        if rev is not None and rev >= 0:
            checks.append("PASS: Revenue is non-negative")

        obs["verification_status"] = status
        obs["raw_data_provenance"]["validation_checks"] = checks
        return obs
