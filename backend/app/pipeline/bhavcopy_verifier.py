import csv
import io
import os
import re
import hashlib
import zipfile
from datetime import datetime, date, timezone
from typing import Dict, Any, List, Optional, Tuple
import httpx

from app.pipeline.interfaces import IOutcomeVerifier


# SEBI MDAC Standardization Transition Date (rollout of Unified Distilled File Format - UDiFF)
UDIFF_TRANSITION_DATE = date(2024, 7, 8)

# BSE introduction of EQ_ISINCODE ZIP archives (prior to 2017, BSE used EQ{ddMMyy}_CSV.ZIP)
BSE_ISIN_LEGACY_DATE = date(2017, 1, 1)


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
    ZIP archive decompression, and multi-format parsing for modern (UDiFF), legacy, and exchange reports.
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
            if trade_date >= UDIFF_TRANSITION_DATE:
                # Modern NSE security-wise bhavcopy
                d_str = trade_date.strftime("%d%m%Y")
                return f"https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{d_str}.csv"
            else:
                # Legacy NSE CM archive zip
                yyyy = trade_date.strftime("%Y")
                mmm = trade_date.strftime("%b").upper()
                dd_mmm_yyyy = trade_date.strftime("%d%b%Y").upper()
                return f"https://nsearchives.nseindia.com/content/historical/EQUITIES/{yyyy}/{mmm}/cm{dd_mmm_yyyy}bhav.csv.zip"
        elif ex == "BSE":
            if trade_date >= UDIFF_TRANSITION_DATE:
                # Modern BSE UDiFF standardized format
                d_str = trade_date.strftime("%Y%m%d")
                return f"https://www.bseindia.com/download/BhavCopy/Equity/BhavCopy_BSE_CM_0_0_0_{d_str}_F_0000.CSV"
            elif trade_date >= BSE_ISIN_LEGACY_DATE:
                # Legacy BSE EQ with ISIN ZIP format
                d_str = trade_date.strftime("%d%m%y")
                return f"https://www.bseindia.com/download/BhavCopy/Equity/EQ_ISINCODE_{d_str}.zip"
            else:
                # Older legacy BSE format (2015-2016)
                d_str = trade_date.strftime("%d%m%y")
                return f"https://www.bseindia.com/download/BhavCopy/Equity/EQ{d_str}_CSV.ZIP"
        else:
            raise ValueError(f"Unsupported exchange for bhavcopy: {exchange}")

    def get_candidate_urls(self, trade_date: date, exchange: str = "NSE") -> List[str]:
        """
        Returns an ordered list of candidate URLs to probe for the specified exchange and date,
        providing resilient fallback across exchange mirror domains and naming variants.
        """
        primary = self.get_canonical_url(trade_date, exchange=exchange)
        candidates = [primary]
        ex = exchange.upper()

        if ex == "NSE":
            if trade_date >= UDIFF_TRANSITION_DATE:
                d_udiff = trade_date.strftime("%Y%m%d")
                candidates.append(
                    f"https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{d_udiff}_F_0000.csv.zip"
                )
            else:
                yyyy = trade_date.strftime("%Y")
                mmm = trade_date.strftime("%b").upper()
                dd_mmm_yyyy = trade_date.strftime("%d%b%Y").upper()
                candidates.append(
                    f"https://archives.nseindia.com/content/historical/EQUITIES/{yyyy}/{mmm}/cm{dd_mmm_yyyy}bhav.csv.zip"
                )
        elif ex == "BSE":
            if trade_date < UDIFF_TRANSITION_DATE:
                d_str = trade_date.strftime("%d%m%y")
                alt_urls = [
                    f"https://www.bseindia.com/download/BhavCopy/Equity/EQ_ISINCODE_{d_str}.zip",
                    f"https://www.bseindia.com/download/BhavCopy/Equity/EQ_ISINCODE_{d_str}.ZIP",
                    f"https://www.bseindia.com/download/BhavCopy/Equity/EQ{d_str}_CSV.ZIP",
                    f"https://www.bseindia.com/download/BhavCopy/Equity/EQ{d_str}_CSV.zip",
                ]
                for u in alt_urls:
                    if u not in candidates:
                        candidates.append(u)

        return candidates

    def _extract_csv_from_payload(self, raw_bytes: bytes) -> str:
        """
        Safely extracts CSV text from raw payload, handling both plain CSV text
        and compressed ZIP archives containing CSV files.
        """
        if not raw_bytes or len(raw_bytes) < 50:
            raise BhavcopyParseError("Bhavcopy payload unexpectedly empty or truncated")

        # Check for ZIP archive magic header
        if raw_bytes[:4] == b"PK\x03\x04":
            try:
                with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
                    csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
                    if not csv_names:
                        raise BhavcopyParseError("ZIP archive contains no CSV files")
                    csv_content = zf.read(csv_names[0])
                    return csv_content.decode("utf-8", errors="replace")
            except zipfile.BadZipFile as e:
                raise BhavcopyParseError(f"Corrupt or invalid ZIP archive: {e}") from e

        return raw_bytes.decode("utf-8", errors="replace")

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

        # Bounded network fetch with candidate failover and retry
        candidate_urls = self.get_candidate_urls(trade_date, exchange=ex)
        last_exc: Optional[Exception] = None

        with httpx.Client(headers=self.headers, timeout=self.timeout, follow_redirects=True) as client:
            for url in candidate_urls:
                for attempt in range(self.max_retries + 1):
                    try:
                        res = client.get(url)
                        c_type = res.headers.get("content-type", "").lower()
                        # BSE/NSE web server returns HTML landing page on invalid requests
                        if res.status_code == 200 and ("text/html" in c_type) and (not url.endswith(".html")):
                            last_exc = BhavcopyNotFoundError(
                                f"Bhavcopy endpoint returned HTML redirect instead of data for {ex} on {trade_date} at {url}"
                            )
                            break

                        if res.status_code == 404:
                            last_exc = BhavcopyNotFoundError(
                                f"Bhavcopy not found for {ex} on {trade_date.isoformat()} (HTTP 404 at {url})"
                            )
                            break

                        if res.status_code != 200:
                            last_exc = BhavcopyVerificationError(
                                f"HTTP {res.status_code} downloading {ex} bhavcopy from {url}"
                            )
                            if attempt < self.max_retries:
                                continue
                            break

                        raw_bytes = res.content
                        if not raw_bytes or len(raw_bytes) < 100:
                            last_exc = BhavcopyParseError(f"Bhavcopy payload unexpectedly empty or truncated for {trade_date}")
                            if attempt < self.max_retries:
                                continue
                            break

                        csv_text = self._extract_csv_from_payload(raw_bytes)
                        content_hash = compute_sha256(raw_bytes)

                        # Save extracted CSV to local cache
                        with open(cache_path, "wb") as f:
                            f.write(csv_text.encode("utf-8"))

                        return csv_text, url, content_hash

                    except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as e:
                        last_exc = e
                        if attempt == self.max_retries:
                            break

        if isinstance(last_exc, BhavcopyNotFoundError):
            raise last_exc
        raise BhavcopyVerificationError(
            f"Failed to fetch {ex} bhavcopy for {trade_date} after trying candidate URLs: {last_exc}"
        )

    def parse_bhavcopy_rows(self, csv_text: str, exchange: str = "NSE") -> List[Dict[str, Any]]:
        """
        Parses bhavcopy CSV text and normalizes column headers across NSE and BSE formats,
        including legacy archives and modern standardized SEBI UDiFF files.
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

        def _safe_float(row: List[str], idx: Optional[int]) -> Optional[float]:
            if idx is None or idx >= len(row):
                return None
            val = row[idx].strip().replace(",", "")
            try:
                return float(val) if val not in ("-", "", "N/A", "NULL") else None
            except ValueError:
                return None

        def _safe_int(row: List[str], idx: Optional[int]) -> Optional[int]:
            if idx is None or idx >= len(row):
                return None
            val = row[idx].strip().replace(",", "")
            try:
                return int(float(val)) if val not in ("-", "", "N/A", "NULL") else None
            except ValueError:
                return None

        if ex == "NSE":
            # Support:
            # 1. Modern sec_bhavdata_full: SYMBOL, SERIES, DATE1, OPEN_PRICE, CLOSE_PRICE, PREV_CLOSE, TTL_TRD_QNTY
            # 2. Modern UDiFF: TCKRSYMB, SCTYSRS, TRADDT, OPNPRIC, CLSPRIC, PRVSCLSGPRIC, TTLTRADGVOL, FININSTRMID, ISIN
            # 3. Legacy cm...bhav: SYMBOL, SERIES, OPEN, CLOSE, PREVCLOSE, TOTTRDQTY, ISIN
            col_map = {col: idx for idx, col in enumerate(header)}

            sym_idx = col_map.get("SYMBOL", col_map.get("TCKRSYMB"))
            series_idx = col_map.get("SERIES", col_map.get("SCTYSRS"))
            open_idx = col_map.get("OPEN_PRICE", col_map.get("OPEN", col_map.get("OPNPRIC")))
            high_idx = col_map.get("HIGH_PRICE", col_map.get("HIGH", col_map.get("HGHPRIC")))
            low_idx = col_map.get("LOW_PRICE", col_map.get("LOW", col_map.get("LWPRIC")))
            close_idx = col_map.get("CLOSE_PRICE", col_map.get("CLOSE", col_map.get("CLSPRIC")))
            prev_idx = col_map.get("PREV_CLOSE", col_map.get("PREVCLOSE", col_map.get("PRVSCLSGPRIC")))
            qty_idx = col_map.get("TTL_TRD_QNTY", col_map.get("TOTTRDQTY", col_map.get("TTLTRADGVOL")))
            isin_idx = col_map.get("ISIN", col_map.get("ISIN_CODE"))
            sc_code_idx = col_map.get("FININSTRMID")

            if sym_idx is None:
                raise BhavcopyParseError(f"NSE bhavcopy missing SYMBOL column. Found columns: {header[:8]}")

            if open_idx is None or close_idx is None:
                raise BhavcopyParseError(f"NSE bhavcopy missing OPEN or CLOSE columns: {header[:10]}")

            min_len = max(filter(None, [sym_idx, open_idx, close_idx]))

            for line_no, row in enumerate(reader, start=2):
                if not row or len(row) <= min_len:
                    continue
                sym = row[sym_idx].strip()
                if not sym:
                    continue

                isin_val = row[isin_idx].strip() if isin_idx is not None and isin_idx < len(row) else None
                if isin_val in ("-", "", "N/A", "NULL"):
                    isin_val = None

                rec = {
                    "exchange": "NSE",
                    "symbol": sym,
                    "scrip_code": row[sc_code_idx].strip() if sc_code_idx is not None and sc_code_idx < len(row) else None,
                    "series": row[series_idx].strip() if series_idx is not None and series_idx < len(row) else "EQ",
                    "isin": isin_val,
                    "open_price": _safe_float(row, open_idx),
                    "high_price": _safe_float(row, high_idx),
                    "low_price": _safe_float(row, low_idx),
                    "close_price": _safe_float(row, close_idx),
                    "prev_close": _safe_float(row, prev_idx),
                    "total_traded_qty": _safe_int(row, qty_idx),
                    "raw_row": {header[i]: row[i].strip() for i in range(min(len(header), len(row)))},
                }
                records.append(rec)

        elif ex == "BSE":
            # Support:
            # 1. Modern UDiFF: TCKRSYMB, SCTYSRS, FININSTRMID, ISIN, OPNPRIC, CLSPRIC, HGHPRIC, LWPRIC, PRVSCLSGPRIC, TTLTRADGVOL
            # 2. Legacy EQ_ISINCODE: SC_CODE, SC_NAME, SC_GROUP, OPEN, CLOSE, HIGH, LOW, PREVCLOSE, NO_OF_SHRS, ISIN_CODE
            # 3. Older legacy (2015-2016): SC_CODE, SC_NAME, SC_GROUP, OPEN, CLOSE, HIGH, LOW, PREVCLOSE, NO_OF_SHRS
            col_map = {col: idx for idx, col in enumerate(header)}

            sc_code_idx = col_map.get("FININSTRMID", col_map.get("SC_CODE", col_map.get("SCRIP_CODE")))
            sc_name_idx = col_map.get("FININSTRMNM", col_map.get("SC_NAME", col_map.get("SCRIP_NAME")))
            sym_idx = col_map.get("TCKRSYMB", col_map.get("SYMBOL", col_map.get("SC_NAME", col_map.get("SCRIP_NAME"))))
            isin_idx = col_map.get("ISIN", col_map.get("ISIN_CODE"))
            open_idx = col_map.get("OPNPRIC", col_map.get("OPEN"))
            high_idx = col_map.get("HGHPRIC", col_map.get("HIGH"))
            low_idx = col_map.get("LWPRIC", col_map.get("LOW"))
            close_idx = col_map.get("CLSPRIC", col_map.get("CLOSE"))
            prev_idx = col_map.get("PRVSCLSGPRIC", col_map.get("PREVCLOSE", col_map.get("PREV_CLOSE")))
            qty_idx = col_map.get("TTLTRADGVOL", col_map.get("NO_OF_SHRS", col_map.get("NET_TURNOV")))
            group_idx = col_map.get("SCTYSRS", col_map.get("SC_GROUP"))

            if (sc_code_idx is None and sym_idx is None) or open_idx is None or close_idx is None:
                raise BhavcopyParseError(f"BSE bhavcopy missing required columns: {header[:10]}")

            req_indices = [idx for idx in [sc_code_idx, sym_idx, open_idx, close_idx] if idx is not None]
            min_len = max(req_indices) if req_indices else 0

            for line_no, row in enumerate(reader, start=2):
                if not row or len(row) <= min_len:
                    continue

                sc_code = row[sc_code_idx].strip() if sc_code_idx is not None and sc_code_idx < len(row) else ""
                sym_val = row[sym_idx].strip() if sym_idx is not None and sym_idx < len(row) else ""
                if not sym_val and sc_name_idx is not None and sc_name_idx < len(row):
                    sym_val = row[sc_name_idx].strip()

                isin_val = row[isin_idx].strip() if isin_idx is not None and isin_idx < len(row) else None
                if isin_val in ("-", "", "N/A", "NULL"):
                    isin_val = None

                rec = {
                    "exchange": "BSE",
                    "scrip_code": sc_code,
                    "symbol": sym_val,
                    "series": row[group_idx].strip() if group_idx is not None and group_idx < len(row) else "B",
                    "isin": isin_val,
                    "open_price": _safe_float(row, open_idx),
                    "high_price": _safe_float(row, high_idx),
                    "low_price": _safe_float(row, low_idx),
                    "close_price": _safe_float(row, close_idx),
                    "prev_close": _safe_float(row, prev_idx),
                    "total_traded_qty": _safe_int(row, qty_idx),
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
        2. Fallback: matches by symbol (case-insensitive) prioritizing equity series (EQ, A, BE, B, SM).
        
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

        # 2. Fallback Match: Symbol (with series ranking and liquidity tie-breaker)
        if matched_row is None and symbol and symbol.strip():
            clean_sym = symbol.strip().upper()
            # Series preference order: EQ / A (Mainboard normal), BE / B (Trade-to-trade / Group B), SM / T / M
            series_priority = {"EQ": 1, "A": 1, "BE": 2, "B": 2, "SM": 3, "T": 3, "ST": 4, "M": 4}
            candidate_rows = []
            for r in rows:
                r_sym = (r.get("symbol") or "").strip().upper()
                r_code = (r.get("scrip_code") or "").strip().upper()
                if r_sym == clean_sym or (ex == "BSE" and r_code == clean_sym):
                    candidate_rows.append(r)

            if candidate_rows:
                # Pick the row with highest series priority, tie-breaking by highest trading volume
                candidate_rows.sort(
                    key=lambda x: (
                        series_priority.get(x.get("series", "").upper(), 99),
                        -(x.get("total_traded_qty") or 0),
                    )
                )
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
            "scrip_code": matched_row.get("scrip_code"),
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

