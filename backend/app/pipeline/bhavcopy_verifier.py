import csv
import io
import os
import re
import hashlib
from datetime import datetime, date, timezone
from typing import Dict, Any, List, Optional, Tuple
import httpx

from app.pipeline.interfaces import IOutcomeVerifier


class BhavcopyVerificationError(Exception):
    """Base exception for bhavcopy reconciliation errors."""
    pass


class BhavcopyNotFoundError(BhavcopyVerificationError):
    """Raised when bhavcopy for the specified date cannot be retrieved."""
    pass


class BhavcopyParseError(BhavcopyVerificationError):
    """Raised when bhavcopy CSV is malformed or missing required columns."""
    pass


class SecurityNotInBhavcopyError(BhavcopyVerificationError):
    """Raised when security (by ISIN or symbol) is not found in the day's bhavcopy."""
    pass


def compute_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


class BhavcopyOutcomeVerifier(IOutcomeVerifier):
    """
    Concrete implementation of IOutcomeVerifier using official NSE and BSE daily bhavcopy archives.
    Includes bounded network requests, local disk caching, SHA-256 integrity checks,
    and multi-format parsing for both modern and legacy exchange reports.
    """

    def __init__(
        self,
        cache_dir: Optional[str] = None,
        timeout: float = 12.0,
        max_retries: int = 2,
    ):
        base_cache = cache_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "data",
            "bhavcopy_cache",
        )
        self.cache_dir = os.path.abspath(base_cache)
        os.makedirs(self.cache_dir, exist_ok=True)
        self.timeout = timeout
        self.max_retries = max_retries
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def _get_cache_path(self, exchange: str, trade_date: date) -> str:
        exchange_dir = os.path.join(self.cache_dir, exchange.upper(), str(trade_date.year))
        os.makedirs(exchange_dir, exist_ok=True)
        return os.path.join(exchange_dir, f"{trade_date.isoformat()}.csv")

    def get_canonical_url(self, trade_date: date, exchange: str = "NSE") -> str:
        """Returns the canonical archive URL for the specified exchange and trade date."""
        ex = exchange.upper()
        if ex == "NSE":
            # Modern NSE security-wise bhavcopy
            d_str = trade_date.strftime("%d%m%Y")
            return f"https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{d_str}.csv"
        elif ex == "BSE":
            # Official BSE Equity Bhavcopy
            d_str = trade_date.strftime("%d%m%y")
            return f"https://www.bseindia.com/download/BhavCopy/Equity/EQ_ISIN_{d_str}.CSV"
        else:
            raise ValueError(f"Unsupported exchange for bhavcopy: {exchange}")

    def fetch_bhavcopy(
        self,
        trade_date: date,
        exchange: str = "NSE",
        force_refresh: bool = False,
    ) -> Tuple[str, str, str]:
        """
        Retrieves bhavcopy CSV content from local cache or remote archive.
        Returns: (csv_text, canonical_url, sha256_hash)
        """
        ex = exchange.upper()
        cache_path = self._get_cache_path(ex, trade_date)
        canonical_url = self.get_canonical_url(trade_date, exchange=ex)

        if not force_refresh and os.path.exists(cache_path):
            with open(cache_path, "rb") as f:
                cached_bytes = f.read()
            if cached_bytes:
                content_hash = compute_sha256(cached_bytes)
                return cached_bytes.decode("utf-8", errors="replace"), canonical_url, content_hash

        # Bounded network fetch with retry
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                with httpx.Client(headers=self.headers, timeout=self.timeout, follow_redirects=True) as client:
                    res = client.get(canonical_url)
                    if res.status_code == 404:
                        raise BhavcopyNotFoundError(
                            f"Bhavcopy not found for {ex} on {trade_date.isoformat()} (HTTP 404 at {canonical_url})"
                        )
                    if res.status_code != 200:
                        raise BhavcopyVerificationError(
                            f"HTTP {res.status_code} downloading {ex} bhavcopy from {canonical_url}"
                        )

                    raw_bytes = res.content
                    if not raw_bytes or len(raw_bytes) < 100:
                        raise BhavcopyParseError(f"Bhavcopy payload unexpectedly empty or truncated for {trade_date}")

                    content_hash = compute_sha256(raw_bytes)

                    # Save to local cache
                    with open(cache_path, "wb") as f:
                        f.write(raw_bytes)

                    return raw_bytes.decode("utf-8", errors="replace"), canonical_url, content_hash
            except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as e:
                last_exc = e
                if attempt == self.max_retries:
                    break

        raise BhavcopyVerificationError(
            f"Failed to fetch {ex} bhavcopy for {trade_date} after {self.max_retries + 1} attempts: {last_exc}"
        )

    def parse_bhavcopy_rows(self, csv_text: str, exchange: str = "NSE") -> List[Dict[str, Any]]:
        """
        Parses bhavcopy CSV text and normalizes column headers across NSE and BSE formats.
        Returns a list of standardized security trading records.
        """
        if not csv_text or not csv_text.strip():
            raise BhavcopyParseError("Empty bhavcopy content")

        reader = csv.reader(io.StringIO(csv_text.strip()))
        try:
            raw_header = next(reader)
        except StopIteration:
            raise BhavcopyParseError("Bhavcopy CSV has no header row")

        header = [col.strip().upper().replace(" ", "_") for col in raw_header]
        ex = exchange.upper()

        records: List[Dict[str, Any]] = []

        if ex == "NSE":
            # Check for modern sec_bhavdata_full format or legacy cm bhav format
            has_symbol = "SYMBOL" in header
            if not has_symbol:
                raise BhavcopyParseError(f"NSE bhavcopy missing SYMBOL column. Found columns: {header[:8]}")

            col_map = {col: idx for idx, col in enumerate(header)}
            sym_idx = col_map["SYMBOL"]
            series_idx = col_map.get("SERIES")
            open_idx = col_map.get("OPEN_PRICE", col_map.get("OPEN"))
            high_idx = col_map.get("HIGH_PRICE", col_map.get("HIGH"))
            low_idx = col_map.get("LOW_PRICE", col_map.get("LOW"))
            close_idx = col_map.get("CLOSE_PRICE", col_map.get("CLOSE"))
            prev_idx = col_map.get("PREV_CLOSE", col_map.get("PREVCLOSE"))
            qty_idx = col_map.get("TTL_TRD_QNTY", col_map.get("TOTTRDQTY"))
            isin_idx = col_map.get("ISIN")

            if open_idx is None or close_idx is None:
                raise BhavcopyParseError(f"NSE bhavcopy missing OPEN or CLOSE columns: {header[:10]}")

            for line_no, row in enumerate(reader, start=2):
                if not row or len(row) <= max(filter(None, [sym_idx, open_idx, close_idx])):
                    continue
                sym = row[sym_idx].strip()
                if not sym:
                    continue

                def _safe_float(idx: Optional[int]) -> Optional[float]:
                    if idx is None or idx >= len(row):
                        return None
                    val = row[idx].strip().replace(",", "")
                    try:
                        return float(val) if val not in ("-", "", "N/A", "NULL") else None
                    except ValueError:
                        return None

                def _safe_int(idx: Optional[int]) -> Optional[int]:
                    if idx is None or idx >= len(row):
                        return None
                    val = row[idx].strip().replace(",", "")
                    try:
                        return int(float(val)) if val not in ("-", "", "N/A", "NULL") else None
                    except ValueError:
                        return None

                rec = {
                    "exchange": "NSE",
                    "symbol": sym,
                    "series": row[series_idx].strip() if series_idx is not None and series_idx < len(row) else "EQ",
                    "isin": row[isin_idx].strip() if isin_idx is not None and isin_idx < len(row) else None,
                    "open_price": _safe_float(open_idx),
                    "high_price": _safe_float(high_idx),
                    "low_price": _safe_float(low_idx),
                    "close_price": _safe_float(close_idx),
                    "prev_close": _safe_float(prev_idx),
                    "total_traded_qty": _safe_int(qty_idx),
                    "raw_row": {header[i]: row[i].strip() for i in range(min(len(header), len(row)))},
                }
                records.append(rec)

        elif ex == "BSE":
            # BSE EQ_ISIN format: SC_CODE, SC_NAME, SC_GROUP, OPEN, HIGH, LOW, CLOSE, PREVCLOSE, NO_OF_SHRS, ISIN_CODE
            col_map = {col: idx for idx, col in enumerate(header)}
            sc_code_idx = col_map.get("SC_CODE", col_map.get("SCRIP_CODE"))
            sc_name_idx = col_map.get("SC_NAME", col_map.get("SCRIP_NAME"))
            isin_idx = col_map.get("ISIN_CODE", col_map.get("ISIN"))
            open_idx = col_map.get("OPEN")
            high_idx = col_map.get("HIGH")
            low_idx = col_map.get("LOW")
            close_idx = col_map.get("CLOSE")
            prev_idx = col_map.get("PREVCLOSE", col_map.get("PREV_CLOSE"))
            qty_idx = col_map.get("NO_OF_SHRS", col_map.get("NET_TURNOV"))
            group_idx = col_map.get("SC_GROUP")

            if (sc_code_idx is None and sc_name_idx is None) or open_idx is None or close_idx is None:
                raise BhavcopyParseError(f"BSE bhavcopy missing required columns: {header[:10]}")

            for line_no, row in enumerate(reader, start=2):
                if not row or len(row) <= max(filter(None, [open_idx, close_idx])):
                    continue

                def _safe_float(idx: Optional[int]) -> Optional[float]:
                    if idx is None or idx >= len(row):
                        return None
                    val = row[idx].strip().replace(",", "")
                    try:
                        return float(val) if val not in ("-", "", "N/A", "NULL") else None
                    except ValueError:
                        return None

                def _safe_int(idx: Optional[int]) -> Optional[int]:
                    if idx is None or idx >= len(row):
                        return None
                    val = row[idx].strip().replace(",", "")
                    try:
                        return int(float(val)) if val not in ("-", "", "N/A", "NULL") else None
                    except ValueError:
                        return None

                sc_code = row[sc_code_idx].strip() if sc_code_idx is not None and sc_code_idx < len(row) else ""
                sc_name = row[sc_name_idx].strip() if sc_name_idx is not None and sc_name_idx < len(row) else ""
                isin_val = row[isin_idx].strip() if isin_idx is not None and isin_idx < len(row) else None

                rec = {
                    "exchange": "BSE",
                    "scrip_code": sc_code,
                    "symbol": sc_name,
                    "series": row[group_idx].strip() if group_idx is not None and group_idx < len(row) else "B",
                    "isin": isin_val,
                    "open_price": _safe_float(open_idx),
                    "high_price": _safe_float(high_idx),
                    "low_price": _safe_float(low_idx),
                    "close_price": _safe_float(close_idx),
                    "prev_close": _safe_float(prev_idx),
                    "total_traded_qty": _safe_int(qty_idx),
                    "raw_row": {header[i]: row[i].strip() for i in range(min(len(header), len(row)))},
                }
                records.append(rec)

        return records

    def reconcile_bhavcopy(
        self,
        symbol: str,
        listing_date: date,
        isin: Optional[str] = None,
        exchange: str = "NSE",
        final_issue_price: Optional[float] = None,
        cached_csv_override: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Reconciles a security against the official exchange bhavcopy on its listing date.
        
        Priority matching:
        1. If ISIN is provided, strictly matches by ISIN (immutable securities identifier).
        2. Fallback: matches by symbol (case-insensitive) prioritizing equity series (EQ, BE, SM).
        
        Calculates:
        - listing_open_price_inr
        - listing_close_price_inr
        - listing_open_gain_pct
        - listing_gain_pct (close return)
        
        Preserves provenance:
        - source_url, source_file_hash, raw_data_provenance
        """
        ex = exchange.upper()
        if cached_csv_override is not None:
            csv_text = cached_csv_override
            canonical_url = f"file://synthetic/{ex}/{listing_date.isoformat()}.csv"
            content_hash = compute_sha256(csv_text.encode("utf-8"))
        else:
            csv_text, canonical_url, content_hash = self.fetch_bhavcopy(listing_date, exchange=ex)

        rows = self.parse_bhavcopy_rows(csv_text, exchange=ex)

        matched_row: Optional[Dict[str, Any]] = None

        # 1. Primary Match: ISIN (if provided)
        if isin and isin.strip():
            clean_isin = isin.strip().upper()
            for r in rows:
                r_isin = (r.get("isin") or "").strip().upper()
                if r_isin and r_isin == clean_isin:
                    matched_row = r
                    break

        # 2. Fallback Match: Symbol (with series ranking)
        if matched_row is None and symbol and symbol.strip():
            clean_sym = symbol.strip().upper()
            # Series preference order: EQ (Mainboard normal), BE (Trade-to-trade), SM (NSE SME), ST (SME T2T)
            series_priority = {"EQ": 1, "BE": 2, "SM": 3, "ST": 4, "A": 1, "B": 2, "T": 3, "M": 4}
            candidate_rows = []
            for r in rows:
                r_sym = (r.get("symbol") or "").strip().upper()
                r_code = (r.get("scrip_code") or "").strip().upper()
                if r_sym == clean_sym or (ex == "BSE" and r_code == clean_sym):
                    candidate_rows.append(r)

            if candidate_rows:
                # Pick the row with highest series priority
                candidate_rows.sort(key=lambda x: series_priority.get(x.get("series", "").upper(), 99))
                matched_row = candidate_rows[0]

        if matched_row is None:
            return None

        open_price = matched_row.get("open_price")
        close_price = matched_row.get("close_price")

        open_gain_pct: Optional[float] = None
        close_gain_pct: Optional[float] = None

        if final_issue_price and final_issue_price > 0:
            if open_price is not None:
                open_gain_pct = round(((open_price - final_issue_price) / final_issue_price) * 100.0, 4)
            if close_price is not None:
                close_gain_pct = round(((close_price - final_issue_price) / final_issue_price) * 100.0, 4)

        return {
            "exchange": ex,
            "matched_by": "ISIN" if (isin and matched_row.get("isin") == isin.strip().upper()) else "SYMBOL",
            "symbol": matched_row.get("symbol"),
            "isin": matched_row.get("isin") or isin,
            "series": matched_row.get("series"),
            "listing_date": listing_date,
            "final_issue_price_inr": final_issue_price,
            "listing_open_price_inr": open_price,
            "listing_close_price_inr": close_price,
            "day_high_inr": matched_row.get("high_price"),
            "day_low_inr": matched_row.get("low_price"),
            "total_traded_qty": matched_row.get("total_traded_qty"),
            "listing_open_gain_pct": open_gain_pct,
            "listing_gain_pct": close_gain_pct,
            "bhavcopy_verified": True,
            "source_url": canonical_url,
            "source_file_hash": content_hash,
            "raw_data_provenance": {
                "source": f"{ex}_BHAVCOPY",
                "trade_date": listing_date.isoformat(),
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "file_hash_sha256": content_hash,
                "raw_fields": matched_row.get("raw_row", {}),
            },
        }
