import csv
import io
import json
import re
import hashlib
from datetime import datetime, date, timezone
from typing import Dict, Any, List, Optional, Tuple


class ArchiveParseError(Exception):
    """Raised when historical archive data is malformed or unreadable."""
    pass


ISIN_REGEX = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")


def is_valid_isin(val: Optional[str]) -> bool:
    """Validates international securities identification number (ISO 6166)."""
    if not val or not isinstance(val, str):
        return False
    cleaned = val.strip().upper()
    return bool(ISIN_REGEX.match(cleaned))


def parse_flexible_date(date_val: Any) -> Optional[date]:
    """Parses various date representations found across exchange archival files."""
    if not date_val:
        return None
    if isinstance(date_val, date) and not isinstance(date_val, datetime):
        return date_val
    if isinstance(date_val, datetime):
        return date_val.date()
    if not isinstance(date_val, str):
        return None

    cleaned = date_val.strip()
    if cleaned in ("-", "", "N/A", "null", "None", "--", "NA"):
        return None

    # Common formats across NSE and BSE archives
    for fmt in (
        "%d-%b-%Y",  # 15-Oct-2024
        "%d-%B-%Y",  # 15-October-2024
        "%d-%m-%Y",  # 15-10-2024
        "%Y-%m-%d",  # 2024-10-15
        "%d/%m/%Y",  # 15/10/2024
        "%m/%d/%Y",  # 10/15/2024
        "%d-%b-%y",  # 15-Oct-24
        "%d-%m-%y",  # 15-10-24
    ):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            pass

    return None


def parse_numeric_clean(val: Any) -> Optional[float]:
    """Cleans numeric cells removing currency signs, commas, and whitespace."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if not isinstance(val, str):
        return None

    cleaned = val.replace("Rs.", "").replace("Rs", "").replace("₹", "").replace(",", "").strip()
    if cleaned in ("-", "", "N/A", "null", "None", "--", "NA"):
        return None

    try:
        return float(cleaned)
    except ValueError:
        return None


def clean_company_name(name: Optional[str]) -> str:
    """Normalizes company name for display and comparison without corrupting identity."""
    if not name:
        return ""
    cleaned = re.sub(r"\s+", " ", str(name)).strip()
    return cleaned


class HistoricalArchiveParser:
    """
    Parser for official NSE and BSE historical public offering archives.
    Extracts structured IPO metadata, validates ISINs, normalizes pricing,
    and preserves raw row provenance.
    """

    @staticmethod
    def parse_nse_past_issues_json(raw_json_str: str) -> List[Dict[str, Any]]:
        """
        Parses official NSE public issues JSON archive (e.g. from /api/public-past-issues).
        Expected fields: symbol, companyName, series, issueStartDate, issueEndDate, listingDate,
        issuePrice, issueSize, lotSize, isin (when available).
        """
        if not raw_json_str or not raw_json_str.strip():
            raise ArchiveParseError("Empty NSE JSON archive content")

        try:
            data = json.loads(raw_json_str)
        except json.JSONDecodeError as exc:
            raise ArchiveParseError(f"Invalid JSON in NSE archive: {exc}") from exc

        if not isinstance(data, list):
            raise ArchiveParseError(f"Expected list of records in NSE archive, got {type(data)}")

        results: List[Dict[str, Any]] = []

        for item in data:
            if not isinstance(item, dict):
                continue

            company_name = clean_company_name(
                item.get("companyName") or item.get("company_name") or item.get("name")
            )
            if not company_name:
                continue

            symbol = (item.get("symbol") or item.get("secSymbol") or "").strip().upper() or None
            isin = (item.get("isin") or item.get("isinCode") or "").strip().upper() or None
            if isin and not is_valid_isin(isin):
                isin = None

            series = (item.get("series") or "EQ").strip().upper()
            category = "SME" if series in ("SM", "ST") or "SME" in str(item.get("issueType", "")).upper() else "MAINBOARD"

            # Parse pricing
            price_val = item.get("issuePrice") or item.get("price") or item.get("issuePriceRs")
            final_price = parse_numeric_clean(price_val)
            min_price = parse_numeric_clean(item.get("minPrice") or item.get("floorPrice"))
            max_price = parse_numeric_clean(item.get("maxPrice") or item.get("capPrice")) or final_price

            # Issue size
            issue_size = parse_numeric_clean(item.get("issueSize") or item.get("issueSizeCr") or item.get("issueSizeCrores"))

            # Dates
            open_d = parse_flexible_date(item.get("issueStartDate") or item.get("openDate"))
            close_d = parse_flexible_date(item.get("issueEndDate") or item.get("closeDate"))
            list_d = parse_flexible_date(item.get("listingDate") or item.get("dateOfListing"))

            lot_size = None
            raw_lot = item.get("lotSize") or item.get("marketLot")
            if raw_lot:
                parsed_lot = parse_numeric_clean(raw_lot)
                if parsed_lot:
                    lot_size = int(parsed_lot)

            results.append({
                "exchange": "NSE",
                "company_name": company_name,
                "symbol": symbol,
                "isin": isin,
                "category": category,
                "series": series,
                "final_issue_price_inr": final_price,
                "min_price": min_price,
                "max_price": max_price,
                "lot_size": lot_size,
                "issue_size_crores": issue_size,
                "open_date": open_d,
                "close_date": close_d,
                "listing_date": list_d,
                "raw_record": item,
            })

        return results

    @staticmethod
    def parse_nse_past_issues_csv(csv_text: str) -> List[Dict[str, Any]]:
        """
        Parses NSE public issues archive CSV report.
        Headers typically: Company Name, Symbol, Series, Issue Start, Issue End, Listing Date, Issue Price, Issue Size (Rs. Cr), ISIN.
        """
        if not csv_text or not csv_text.strip():
            raise ArchiveParseError("Empty NSE CSV archive content")

        reader = csv.reader(io.StringIO(csv_text.strip()))
        try:
            raw_header = next(reader)
        except StopIteration:
            raise ArchiveParseError("NSE archive CSV has no header row")

        header = [
            re.sub(r"_+", "_", re.sub(r"[^A-Z0-9_]", "", col.strip().upper().replace(" ", "_").replace(".", ""))).strip("_")
            for col in raw_header
        ]
        col_map = {col: idx for idx, col in enumerate(header)}

        def _get_idx(*candidates: str) -> Optional[int]:
            for c in candidates:
                if c in col_map:
                    return col_map[c]
                for col_name, idx in col_map.items():
                    if c in col_name or col_name in c:
                        return idx
            return None

        comp_idx = _get_idx("COMPANY_NAME", "COMPANY", "SECURITY_NAME", "ISSUER_NAME")
        sym_idx = _get_idx("SYMBOL", "SECURITY_SYMBOL")
        isin_idx = _get_idx("ISIN", "ISIN_CODE", "SECURITY_ISIN")
        series_idx = _get_idx("SERIES", "SEC_SERIES")
        open_idx = _get_idx("ISSUE_START", "ISSUE_START_DATE", "OPEN_DATE")
        close_idx = _get_idx("ISSUE_END", "ISSUE_END_DATE", "CLOSE_DATE")
        list_idx = _get_idx("LISTING_DATE", "DATE_OF_LISTING")
        price_idx = _get_idx("ISSUE_PRICE", "PRICE", "FINAL_PRICE", "ISSUE_PRICE_RS")
        size_idx = _get_idx("ISSUE_SIZE", "ISSUE_SIZE_CR", "ISSUE_SIZE_RS_CR", "ISSUE_SIZE_CRORES")
        lot_idx = _get_idx("LOT_SIZE", "MARKET_LOT")

        if comp_idx is None:
            raise ArchiveParseError(f"NSE archive CSV missing COMPANY_NAME column: {header[:8]}")

        results: List[Dict[str, Any]] = []

        for row in reader:
            if not row or len(row) <= comp_idx:
                continue

            comp_name = clean_company_name(row[comp_idx])
            if not comp_name:
                continue

            sym = row[sym_idx].strip().upper() if sym_idx is not None and sym_idx < len(row) else None
            isin = row[isin_idx].strip().upper() if isin_idx is not None and isin_idx < len(row) else None
            if isin and not is_valid_isin(isin):
                isin = None

            series = row[series_idx].strip().upper() if series_idx is not None and series_idx < len(row) else "EQ"
            category = "SME" if series in ("SM", "ST") else "MAINBOARD"

            price = parse_numeric_clean(row[price_idx]) if price_idx is not None and price_idx < len(row) else None
            size = parse_numeric_clean(row[size_idx]) if size_idx is not None and size_idx < len(row) else None

            lot_size = None
            if lot_idx is not None and lot_idx < len(row):
                parsed_lot = parse_numeric_clean(row[lot_idx])
                if parsed_lot:
                    lot_size = int(parsed_lot)

            open_d = parse_flexible_date(row[open_idx]) if open_idx is not None and open_idx < len(row) else None
            close_d = parse_flexible_date(row[close_idx]) if close_idx is not None and close_idx < len(row) else None
            list_d = parse_flexible_date(row[list_idx]) if list_idx is not None and list_idx < len(row) else None

            results.append({
                "exchange": "NSE",
                "company_name": comp_name,
                "symbol": sym or None,
                "isin": isin,
                "category": category,
                "series": series,
                "final_issue_price_inr": price,
                "min_price": price,
                "max_price": price,
                "lot_size": lot_size,
                "issue_size_crores": size,
                "open_date": open_d,
                "close_date": close_d,
                "listing_date": list_d,
                "raw_record": {header[i]: row[i].strip() for i in range(min(len(header), len(row)))},
            })

        return results

    @staticmethod
    def parse_bse_past_issues_csv(csv_text: str) -> List[Dict[str, Any]]:
        """
        Parses official BSE public issues archive CSV.
        Expected headers: Scrip Code, Company Name, Security Name, ISIN, Issue Type, Open Date, Close Date, Listing Date, Issue Price, Issue Size.
        """
        if not csv_text or not csv_text.strip():
            raise ArchiveParseError("Empty BSE CSV archive content")

        reader = csv.reader(io.StringIO(csv_text.strip()))
        try:
            raw_header = next(reader)
        except StopIteration:
            raise ArchiveParseError("BSE archive CSV has no header row")

        header = [col.strip().upper().replace(" ", "_").replace(".", "") for col in raw_header]
        col_map = {col: idx for idx, col in enumerate(header)}

        def _get_idx(*candidates: str) -> Optional[int]:
            for c in candidates:
                if c in col_map:
                    return col_map[c]
            return None

        comp_idx = _get_idx("COMPANY_NAME", "SECURITY_NAME", "ISSUER_NAME", "NAME")
        scrip_idx = _get_idx("SCRIP_CODE", "SC_CODE", "CODE")
        isin_idx = _get_idx("ISIN", "ISIN_CODE", "SECURITY_ISIN")
        type_idx = _get_idx("ISSUE_TYPE", "SEGMENT", "CATEGORY")
        open_idx = _get_idx("OPEN_DATE", "ISSUE_OPEN", "START_DATE")
        close_idx = _get_idx("CLOSE_DATE", "ISSUE_CLOSE", "END_DATE")
        list_idx = _get_idx("LISTING_DATE", "DATE_OF_LISTING")
        price_idx = _get_idx("ISSUE_PRICE", "PRICE", "OFFER_PRICE")
        size_idx = _get_idx("ISSUE_SIZE", "ISSUE_SIZE_CRS", "SIZE_RS_CR")

        if comp_idx is None:
            raise ArchiveParseError(f"BSE archive CSV missing COMPANY_NAME column: {header[:8]}")

        results: List[Dict[str, Any]] = []

        for row in reader:
            if not row or len(row) <= comp_idx:
                continue

            comp_name = clean_company_name(row[comp_idx])
            if not comp_name:
                continue

            scrip_code = row[scrip_idx].strip() if scrip_idx is not None and scrip_idx < len(row) else None
            isin = row[isin_idx].strip().upper() if isin_idx is not None and isin_idx < len(row) else None
            if isin and not is_valid_isin(isin):
                isin = None

            raw_type = row[type_idx].strip().upper() if type_idx is not None and type_idx < len(row) else ""
            category = "SME" if "SME" in raw_type else "MAINBOARD"

            price = parse_numeric_clean(row[price_idx]) if price_idx is not None and price_idx < len(row) else None
            size = parse_numeric_clean(row[size_idx]) if size_idx is not None and size_idx < len(row) else None

            open_d = parse_flexible_date(row[open_idx]) if open_idx is not None and open_idx < len(row) else None
            close_d = parse_flexible_date(row[close_idx]) if close_idx is not None and close_idx < len(row) else None
            list_d = parse_flexible_date(row[list_idx]) if list_idx is not None and list_idx < len(row) else None

            results.append({
                "exchange": "BSE",
                "company_name": comp_name,
                "symbol": comp_name,
                "bse_scrip_code": scrip_code,
                "isin": isin,
                "category": category,
                "series": "B",
                "final_issue_price_inr": price,
                "min_price": price,
                "max_price": price,
                "lot_size": None,
                "issue_size_crores": size,
                "open_date": open_d,
                "close_date": close_d,
                "listing_date": list_d,
                "raw_record": {header[i]: row[i].strip() for i in range(min(len(header), len(row)))},
            })

        return results
