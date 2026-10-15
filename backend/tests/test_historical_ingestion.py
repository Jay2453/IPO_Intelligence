import os
import io
import zipfile
from datetime import date, datetime, timezone
from unittest.mock import patch, MagicMock
import httpx
import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.ipo import IPO
from app.models.market import MarketObservation
from app.models.financials import FinancialObservation
from app.models.ingestion import IngestionJob
from app.pipeline.bhavcopy_verifier import (
    BhavcopyOutcomeVerifier,
    BhavcopyParseError,
    BhavcopyNotFoundError,
    compute_sha256,
    UDIFF_TRANSITION_DATE,
    BSE_ISIN_LEGACY_DATE,
)
from app.pipeline.historical_archive_parser import (
    HistoricalArchiveParser,
    ArchiveParseError,
    is_valid_isin,
    parse_flexible_date,
    clean_company_name,
)
from app.services.historical_ingestion_service import HistoricalIngestionService


# ---------------------------------------------------------------------------
# Synthetic Test Fixtures
# ---------------------------------------------------------------------------

SYNTHETIC_NSE_MODERN_BHAVCOPY = """SYMBOL, SERIES, DATE1, PREV_CLOSE, OPEN_PRICE, HIGH_PRICE, LOW_PRICE, LAST_PRICE, CLOSE_PRICE, AVG_PRICE, TTL_TRD_QNTY, TURNOVER_LACS, NO_OF_TRADES, DELIV_QTY, DELIV_PER
RELIANCE, EQ, 15-Oct-2024, 2750.00, 2755.00, 2780.00, 2740.00, 2772.00, 2770.50, 2765.20, 1500000, 41478.00, 45000, 800000, 53.33
NITYAS, EQ, 15-Oct-2024, 100.00, 125.00, 132.50, 120.00, 128.00, 130.00, 127.10, 500000, 635.50, 12000, 300000, 60.00
NITYAS, SM, 15-Oct-2024, 100.00, 124.00, 130.00, 119.00, 127.00, 129.00, 126.00, 10000, 12.60, 500, 8000, 80.00
INFY, EQ, 15-Oct-2024, 1900.00, 1910.00, 1925.00, 1895.00, 1915.00, 1920.00, 1912.40, 2000000, 38248.00, 60000, 1200000, 60.00
"""

SYNTHETIC_NSE_LEGACY_BHAVCOPY = """SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,TOTTRDVAL,TIMESTAMP,TOTALTRADES,ISIN
RELIANCE,EQ,2755.00,2780.00,2740.00,2770.50,2772.00,2750.00,1500000,4147800000,15-OCT-2024,45000,INE002A01018
ACME,EQ,250.00,275.00,245.00,270.00,268.00,200.00,800000,216000000,15-OCT-2024,15000,INE123A01099
"""

SYNTHETIC_BSE_BHAVCOPY = """SC_CODE,SC_NAME,SC_GROUP,SC_TYPE,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,NO_TRADES,NO_OF_SHRS,NET_TURNOV,TDCLO_IND,ISIN_CODE
500325,RELIANCE,A,Q,2755.00,2780.00,2740.00,2770.50,2772.00,2750.00,5000,100000,27650000,,INE002A01018
543999,SWIGGY,B,Q,390.00,420.00,385.00,412.00,410.00,350.00,12000,500000,206000000,,INE00H101014
"""

SYNTHETIC_UDIFF_BHAVCOPY = """TradDt,BizDt,Sgmt,Src,FinInstrmTp,FinInstrmId,ISIN,TckrSymb,SctySrs,OpnPric,HghPric,LwPric,ClsPric,LastPric,PrvsClsgPric,TtlTradgVol
2024-10-22,2024-10-22,CM,NSE,STK,544274,INE0V6F01027,HYUNDAI,EQ,1934.00,1970.00,1807.00,1819.60,1845.00,1960.00,28619978
2024-10-22,2024-10-22,CM,NSE,STK,20372,INE002A01018,RELIANCE,EQ,2755.00,2780.00,2740.00,2770.50,2772.00,2750.00,1500000
2024-10-22,2024-10-22,CM,NSE,STK,24786,INE0V6F01027,HYUNDAI,BE,1920.00,1950.00,1800.00,1810.00,1815.00,1960.00,50000
"""

SYNTHETIC_BSE_OLDER_BHAVCOPY = """SC_CODE,SC_NAME,SC_GROUP,SC_TYPE,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,NO_TRADES,NO_OF_SHRS,NET_TURNOV,TDCLOINDI
500002,ABB LTD.    ,A ,Q,1115.10,1132.95,1101.25,1127.25,1127.25,1101.60,486,4290,4815974.00,
500325,RELIANCE IND,A ,Q,850.00,865.00,845.00,860.00,858.00,840.00,5000,100000,85000000.00,
"""


SYNTHETIC_NSE_ARCHIVE_JSON = """[
  {
    "symbol": "SWIGGY",
    "companyName": "Swiggy Limited",
    "series": "EQ",
    "issuePrice": 390.00,
    "issueSize": 11327.43,
    "lotSize": 38,
    "issueStartDate": "06-Nov-2024",
    "issueEndDate": "08-Nov-2024",
    "listingDate": "13-Nov-2024",
    "isin": "INE00H101014"
  },
  {
    "symbol": "HYUNDAI",
    "companyName": "Hyundai Motor India Limited",
    "series": "EQ",
    "issuePrice": 1960.00,
    "issueSize": 27870.16,
    "lotSize": 7,
    "issueStartDate": "15-Oct-2024",
    "issueEndDate": "17-Oct-2024",
    "listingDate": "22-Oct-2024",
    "isin": "INE00C801012"
  }
]"""

SYNTHETIC_NSE_ARCHIVE_CSV = """Company Name,Symbol,Series,Issue Start,Issue End,Listing Date,Issue Price,Issue Size (Rs. Cr),ISIN
Nityas Gems Limited,NITYAS,EQ,10-Oct-2024,14-Oct-2024,18-Oct-2024,100,50.50,INE999A01011
Premier Energies Limited,PREMIER,EQ,27-Aug-2024,29-Aug-2024,03-Sep-2024,450,2830.40,INE028A01025
"""

SYNTHETIC_BSE_ARCHIVE_CSV = """Scrip Code,Company Name,ISIN,Issue Type,Open Date,Close Date,Listing Date,Issue Price,Issue Size
543999,Swiggy Limited,INE00H101014,Book Building,06-Nov-2024,08-Nov-2024,13-Nov-2024,390.00,11327.43
544275,Hyundai Motor India Limited,INE00C801012,Book Building,15-Oct-2024,17-Oct-2024,22-Oct-2024,1960.00,27870.16
544001,SME Star Enterprise,INE888B01019,SME,01-Sep-2024,04-Sep-2024,09-Sep-2024,85.00,15.20
"""


# ---------------------------------------------------------------------------
# Tests: Bhavcopy Outcome Verifier
# ---------------------------------------------------------------------------

class TestBhavcopyOutcomeVerifier:
    def test_parse_nse_modern_bhavcopy_success(self, tmp_path):
        verifier = BhavcopyOutcomeVerifier(cache_dir=str(tmp_path))
        rows = verifier.parse_bhavcopy_rows(SYNTHETIC_NSE_MODERN_BHAVCOPY, exchange="NSE")
        assert len(rows) == 4
        reliance = next(r for r in rows if r["symbol"] == "RELIANCE")
        assert reliance["open_price"] == 2755.00
        assert reliance["close_price"] == 2770.50
        assert reliance["total_traded_qty"] == 1500000
        assert reliance["series"] == "EQ"

    def test_parse_nse_legacy_bhavcopy_with_isin(self, tmp_path):
        verifier = BhavcopyOutcomeVerifier(cache_dir=str(tmp_path))
        rows = verifier.parse_bhavcopy_rows(SYNTHETIC_NSE_LEGACY_BHAVCOPY, exchange="NSE")
        assert len(rows) == 2
        acme = next(r for r in rows if r["symbol"] == "ACME")
        assert acme["isin"] == "INE123A01099"
        assert acme["open_price"] == 250.00
        assert acme["close_price"] == 270.00

    def test_parse_bse_bhavcopy_success(self, tmp_path):
        verifier = BhavcopyOutcomeVerifier(cache_dir=str(tmp_path))
        rows = verifier.parse_bhavcopy_rows(SYNTHETIC_BSE_BHAVCOPY, exchange="BSE")
        assert len(rows) == 2
        swiggy = next(r for r in rows if r["scrip_code"] == "543999")
        assert swiggy["symbol"] == "SWIGGY"
        assert swiggy["isin"] == "INE00H101014"
        assert swiggy["open_price"] == 390.00
        assert swiggy["close_price"] == 412.00

    def test_reconcile_match_by_isin(self, tmp_path):
        """When ISIN is provided, matches security regardless of symbol changes."""
        verifier = BhavcopyOutcomeVerifier(cache_dir=str(tmp_path))
        result = verifier.reconcile_bhavcopy(
            symbol="OLD_SYMBOL_XYZ",
            listing_date=date(2024, 10, 15),
            isin="INE123A01099",
            exchange="NSE",
            final_issue_price=200.00,
            cached_csv_override=SYNTHETIC_NSE_LEGACY_BHAVCOPY,
        )
        assert result is not None
        assert result["matched_by"] == "ISIN"
        assert result["symbol"] == "ACME"
        assert result["isin"] == "INE123A01099"
        assert result["listing_open_price_inr"] == 250.00
        assert result["listing_close_price_inr"] == 270.00
        # Return calculations: (250 - 200) / 200 = +25.0%, (270 - 200) / 200 = +35.0%
        assert result["listing_open_gain_pct"] == 25.0
        assert result["listing_gain_pct"] == 35.0
        assert result["bhavcopy_verified"] is True
        assert result["raw_data_provenance"]["source"] == "NSE_BHAVCOPY"

    def test_reconcile_match_by_symbol_series_priority(self, tmp_path):
        """When matching by symbol with multiple series, EQ is prioritized over SM."""
        verifier = BhavcopyOutcomeVerifier(cache_dir=str(tmp_path))
        result = verifier.reconcile_bhavcopy(
            symbol="NITYAS",
            listing_date=date(2024, 10, 15),
            isin=None,
            exchange="NSE",
            final_issue_price=100.00,
            cached_csv_override=SYNTHETIC_NSE_MODERN_BHAVCOPY,
        )
        assert result is not None
        assert result["matched_by"] == "SYMBOL"
        assert result["series"] == "EQ"
        assert result["listing_open_price_inr"] == 125.00
        assert result["listing_close_price_inr"] == 130.00
        assert result["listing_gain_pct"] == 30.0

    def test_bhavcopy_malformed_csv_raises(self, tmp_path):
        verifier = BhavcopyOutcomeVerifier(cache_dir=str(tmp_path))
        with pytest.raises(BhavcopyParseError):
            verifier.parse_bhavcopy_rows("", exchange="NSE")
        with pytest.raises(BhavcopyParseError):
            verifier.parse_bhavcopy_rows("FOO,BAR\n1,2", exchange="NSE")

    def test_security_not_in_bhavcopy_returns_none(self, tmp_path):
        verifier = BhavcopyOutcomeVerifier(cache_dir=str(tmp_path))
        result = verifier.reconcile_bhavcopy(
            symbol="NONEXISTENT_IPO",
            listing_date=date(2024, 10, 15),
            exchange="NSE",
            cached_csv_override=SYNTHETIC_NSE_MODERN_BHAVCOPY,
        )
        assert result is None

    def test_bhavcopy_disk_caching_and_hash_integrity(self, tmp_path):
        verifier = BhavcopyOutcomeVerifier(cache_dir=str(tmp_path))
        test_date = date(2024, 10, 15)
        cache_file = verifier._get_cache_path("NSE", test_date)

        # Write to disk cache
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        with open(cache_file, "wb") as f:
            f.write(SYNTHETIC_NSE_MODERN_BHAVCOPY.encode("utf-8"))

        # Fetch without network call
        csv_text, url, sha256_hash = verifier.fetch_bhavcopy(test_date, exchange="NSE")
        assert "RELIANCE" in csv_text
        assert sha256_hash == compute_sha256(SYNTHETIC_NSE_MODERN_BHAVCOPY.encode("utf-8"))

    def test_bhavcopy_404_raises_not_found(self, tmp_path):
        verifier = BhavcopyOutcomeVerifier(cache_dir=str(tmp_path))
        with patch("httpx.Client.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 404
            mock_get.return_value = mock_resp
            with pytest.raises(BhavcopyNotFoundError):
                verifier.fetch_bhavcopy(date(2020, 1, 1), exchange="NSE", force_refresh=True)

    def test_canonical_url_date_boundary_routing(self, tmp_path):
        """Verifies date boundary routing across modern (UDiFF), legacy ZIP, and older archives."""
        verifier = BhavcopyOutcomeVerifier(cache_dir=str(tmp_path))

        # 1. NSE Boundary Routing (Transition date: 2024-07-08)
        # On or after transition date -> modern sec_bhavdata_full
        assert verifier.get_canonical_url(date(2024, 7, 8), exchange="NSE") == (
            "https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_08072024.csv"
        )
        assert verifier.get_canonical_url(date(2024, 10, 15), exchange="NSE") == (
            "https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_15102024.csv"
        )
        # Before transition date -> legacy CM archive zip
        assert verifier.get_canonical_url(date(2024, 7, 7), exchange="NSE") == (
            "https://nsearchives.nseindia.com/content/historical/EQUITIES/2024/JUL/cm07JUL2024bhav.csv.zip"
        )
        assert verifier.get_canonical_url(date(2018, 10, 15), exchange="NSE") == (
            "https://nsearchives.nseindia.com/content/historical/EQUITIES/2018/OCT/cm15OCT2018bhav.csv.zip"
        )

        # 2. BSE Boundary Routing (Transition date: 2024-07-08, Legacy ISIN date: 2017-01-01)
        # On or after transition date -> modern standardized UDiFF CSV
        assert verifier.get_canonical_url(date(2024, 7, 8), exchange="BSE") == (
            "https://www.bseindia.com/download/BhavCopy/Equity/BhavCopy_BSE_CM_0_0_0_20240708_F_0000.CSV"
        )
        assert verifier.get_canonical_url(date(2024, 10, 15), exchange="BSE") == (
            "https://www.bseindia.com/download/BhavCopy/Equity/BhavCopy_BSE_CM_0_0_0_20241015_F_0000.CSV"
        )
        # Between 2017 and 2024-07-07 -> EQ_ISINCODE ZIP
        assert verifier.get_canonical_url(date(2024, 7, 7), exchange="BSE") == (
            "https://www.bseindia.com/download/BhavCopy/Equity/EQ_ISINCODE_070724.zip"
        )
        assert verifier.get_canonical_url(date(2020, 10, 15), exchange="BSE") == (
            "https://www.bseindia.com/download/BhavCopy/Equity/EQ_ISINCODE_151020.zip"
        )
        # Older than 2017 -> EQ{ddMMyy}_CSV.ZIP
        assert verifier.get_canonical_url(date(2016, 12, 31), exchange="BSE") == (
            "https://www.bseindia.com/download/BhavCopy/Equity/EQ311216_CSV.ZIP"
        )
        assert verifier.get_canonical_url(date(2015, 10, 15), exchange="BSE") == (
            "https://www.bseindia.com/download/BhavCopy/Equity/EQ151015_CSV.ZIP"
        )

    def test_candidate_urls_failover_routing(self, tmp_path):
        """Verifies candidate URLs generation provides ordered mirrors for failover."""
        verifier = BhavcopyOutcomeVerifier(cache_dir=str(tmp_path))

        # Modern NSE provides UDiFF as secondary fallback candidate
        nse_modern_candidates = verifier.get_candidate_urls(date(2024, 10, 15), exchange="NSE")
        assert len(nse_modern_candidates) >= 2
        assert "sec_bhavdata_full_15102024.csv" in nse_modern_candidates[0]
        assert "BhavCopy_NSE_CM_0_0_0_20241015_F_0000.csv.zip" in nse_modern_candidates[1]

        # Legacy BSE provides both EQ_ISINCODE and EQ..._CSV variants
        bse_legacy_candidates = verifier.get_candidate_urls(date(2020, 10, 15), exchange="BSE")
        assert len(bse_legacy_candidates) >= 2
        assert any("EQ_ISINCODE" in u for u in bse_legacy_candidates)
        assert any("EQ151020_CSV" in u for u in bse_legacy_candidates)

    def test_parse_nse_udiff_bhavcopy_normalization(self, tmp_path):
        """Verifies UDiFF column aliases normalize cleanly into internal schema for NSE."""
        verifier = BhavcopyOutcomeVerifier(cache_dir=str(tmp_path))
        rows = verifier.parse_bhavcopy_rows(SYNTHETIC_UDIFF_BHAVCOPY, exchange="NSE")
        assert len(rows) == 3

        hyundai = next(r for r in rows if r["symbol"] == "HYUNDAI" and r["series"] == "EQ")
        assert hyundai["symbol"] == "HYUNDAI"
        assert hyundai["series"] == "EQ"
        assert hyundai["isin"] == "INE0V6F01027"
        assert hyundai["scrip_code"] == "544274"
        assert hyundai["open_price"] == 1934.00
        assert hyundai["high_price"] == 1970.00
        assert hyundai["low_price"] == 1807.00
        assert hyundai["close_price"] == 1819.60
        assert hyundai["prev_close"] == 1960.00
        assert hyundai["total_traded_qty"] == 28619978

    def test_parse_bse_udiff_bhavcopy_normalization(self, tmp_path):
        """Verifies UDiFF column aliases normalize cleanly into internal schema for BSE."""
        verifier = BhavcopyOutcomeVerifier(cache_dir=str(tmp_path))
        rows = verifier.parse_bhavcopy_rows(SYNTHETIC_UDIFF_BHAVCOPY, exchange="BSE")
        assert len(rows) == 3

        hyundai = next(r for r in rows if r["symbol"] == "HYUNDAI" and r["series"] == "EQ")
        assert hyundai["symbol"] == "HYUNDAI"
        assert hyundai["scrip_code"] == "544274"
        assert hyundai["isin"] == "INE0V6F01027"
        assert hyundai["open_price"] == 1934.00
        assert hyundai["close_price"] == 1819.60
        assert hyundai["total_traded_qty"] == 28619978

    def test_parse_bse_older_bhavcopy_without_isin(self, tmp_path):
        """Verifies older 2015-2016 BSE bhavcopy without ISIN parses scrip code, names, and prices."""
        verifier = BhavcopyOutcomeVerifier(cache_dir=str(tmp_path))
        rows = verifier.parse_bhavcopy_rows(SYNTHETIC_BSE_OLDER_BHAVCOPY, exchange="BSE")
        assert len(rows) == 2

        abb = next(r for r in rows if r["scrip_code"] == "500002")
        assert abb["symbol"] == "ABB LTD."
        assert abb["isin"] is None  # ISIN not present in 2015 BSE format
        assert abb["series"] == "A"
        assert abb["open_price"] == 1115.10
        assert abb["close_price"] == 1127.25
        assert abb["prev_close"] == 1101.60
        assert abb["total_traded_qty"] == 4290

    def test_extract_csv_from_valid_zip(self, tmp_path):
        """Verifies safe decompression and CSV extraction from in-memory ZIP payload."""
        verifier = BhavcopyOutcomeVerifier(cache_dir=str(tmp_path))
        csv_payload = "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE\nFOO,EQ,10.0,12.0,9.0,11.0\n"

        # Pack into ZIP archive in memory
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("test_bhav.csv", csv_payload.encode("utf-8"))
        zip_bytes = zip_buf.getvalue()

        extracted = verifier._extract_csv_from_payload(zip_bytes)
        assert extracted == csv_payload

    def test_extract_csv_from_corrupt_zip_raises(self, tmp_path):
        """Verifies corrupt ZIP payload raises BhavcopyParseError."""
        verifier = BhavcopyOutcomeVerifier(cache_dir=str(tmp_path))
        corrupt_zip = b"PK\x03\x04" + b"CorruptGarbageDataNotValidZip" * 10
        with pytest.raises(BhavcopyParseError) as exc_info:
            verifier._extract_csv_from_payload(corrupt_zip)
        assert "Corrupt or invalid ZIP archive" in str(exc_info.value)

    def test_extract_csv_from_empty_zip_raises(self, tmp_path):
        """Verifies ZIP archive without CSV files raises BhavcopyParseError."""
        verifier = BhavcopyOutcomeVerifier(cache_dir=str(tmp_path))
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w") as zf:
            zf.writestr("notes.txt", b"No CSV here!")
        zip_bytes = zip_buf.getvalue()

        with pytest.raises(BhavcopyParseError) as exc_info:
            verifier._extract_csv_from_payload(zip_bytes)
        assert "ZIP archive contains no CSV files" in str(exc_info.value)

    def test_extract_csv_empty_payload_raises(self, tmp_path):
        """Verifies empty or truncated payload raises BhavcopyParseError."""
        verifier = BhavcopyOutcomeVerifier(cache_dir=str(tmp_path))
        with pytest.raises(BhavcopyParseError):
            verifier._extract_csv_from_payload(b"")
        with pytest.raises(BhavcopyParseError):
            verifier._extract_csv_from_payload(b"short")

    def test_bhavcopy_missing_columns_raises(self, tmp_path):
        """Verifies missing required columns raise descriptive parse errors for both exchanges."""
        verifier = BhavcopyOutcomeVerifier(cache_dir=str(tmp_path))
        # Missing OPEN / CLOSE on NSE
        with pytest.raises(BhavcopyParseError) as exc_nse:
            verifier.parse_bhavcopy_rows("SYMBOL,SERIES,FOO,BAR\nRELIANCE,EQ,1,2", exchange="NSE")
        assert "missing OPEN or CLOSE columns" in str(exc_nse.value)

        # Missing SC_CODE on BSE
        with pytest.raises(BhavcopyParseError) as exc_bse:
            verifier.parse_bhavcopy_rows("FOO,BAR,BAZ\n1,2,3", exchange="BSE")
        assert "missing required columns" in str(exc_bse.value)

    def test_reconcile_duplicate_symbol_volume_tie_breaker(self, tmp_path):
        """When multiple rows share the same series, the more liquid/higher volume line is matched."""
        verifier = BhavcopyOutcomeVerifier(cache_dir=str(tmp_path))
        synthetic_duplicate = """SYMBOL, SERIES, DATE1, PREV_CLOSE, OPEN_PRICE, HIGH_PRICE, LOW_PRICE, LAST_PRICE, CLOSE_PRICE, AVG_PRICE, TTL_TRD_QNTY, TURNOVER_LACS, NO_OF_TRADES, DELIV_QTY, DELIV_PER
ACME, EQ, 15-Oct-2024, 100.0, 105.0, 110.0, 102.0, 108.0, 108.0, 106.0, 50000, 53.0, 500, 20000, 40.0
ACME, EQ, 15-Oct-2024, 100.0, 115.0, 120.0, 112.0, 118.0, 118.0, 116.0, 500000, 580.0, 5000, 200000, 40.0
"""
        result = verifier.reconcile_bhavcopy(
            symbol="ACME",
            listing_date=date(2024, 10, 15),
            exchange="NSE",
            final_issue_price=100.00,
            cached_csv_override=synthetic_duplicate,
        )
        assert result is not None
        # Should pick the row with 500,000 volume (open 115, close 118)
        assert result["listing_open_price_inr"] == 115.0
        assert result["listing_close_price_inr"] == 118.0
        assert result["total_traded_qty"] == 500000

    def test_reconcile_match_by_isin_with_udiff(self, tmp_path):
        """Verifies reconcile_bhavcopy accurately matches by ISIN in UDiFF formats."""
        verifier = BhavcopyOutcomeVerifier(cache_dir=str(tmp_path))
        result = verifier.reconcile_bhavcopy(
            symbol="HYUNDAI",
            listing_date=date(2024, 10, 22),
            isin="INE0V6F01027",
            exchange="NSE",
            final_issue_price=1960.00,
            cached_csv_override=SYNTHETIC_UDIFF_BHAVCOPY,
        )
        assert result is not None
        assert result["matched_by"] == "ISIN"
        assert result["symbol"] == "HYUNDAI"
        assert result["isin"] == "INE0V6F01027"
        assert result["listing_open_price_inr"] == 1934.00
        assert result["listing_close_price_inr"] == 1819.60
        assert result["final_issue_price_inr"] == 1960.00
        assert result["listing_open_gain_pct"] == round(((1934.00 - 1960.00) / 1960.00) * 100.0, 4)
        assert result["listing_gain_pct"] == round(((1819.60 - 1960.00) / 1960.00) * 100.0, 4)
        assert result["bhavcopy_verified"] is True


# ---------------------------------------------------------------------------
# Tests: Historical Archive Parser
# ---------------------------------------------------------------------------

class TestHistoricalArchiveParser:
    def test_isin_validation_rule(self):
        assert is_valid_isin("INE002A01018") is True
        assert is_valid_isin("INE00H101014") is True
        assert is_valid_isin("US0378331005") is True
        assert is_valid_isin("INVALID_ISIN") is False
        assert is_valid_isin("INE123") is False
        assert is_valid_isin(None) is False
        assert is_valid_isin("") is False

    def test_parse_flexible_date(self):
        assert parse_flexible_date("15-Oct-2024") == date(2024, 10, 15)
        assert parse_flexible_date("15-10-2024") == date(2024, 10, 15)
        assert parse_flexible_date("2024-10-15") == date(2024, 10, 15)
        assert parse_flexible_date("15/10/2024") == date(2024, 10, 15)
        assert parse_flexible_date("-") is None
        assert parse_flexible_date("N/A") is None
        assert parse_flexible_date(None) is None

    def test_parse_nse_past_issues_json_success(self):
        records = HistoricalArchiveParser.parse_nse_past_issues_json(SYNTHETIC_NSE_ARCHIVE_JSON)
        assert len(records) == 2
        swiggy = records[0]
        assert swiggy["symbol"] == "SWIGGY"
        assert swiggy["company_name"] == "Swiggy Limited"
        assert swiggy["isin"] == "INE00H101014"
        assert swiggy["final_issue_price_inr"] == 390.00
        assert swiggy["issue_size_crores"] == 11327.43
        assert swiggy["lot_size"] == 38
        assert swiggy["open_date"] == date(2024, 11, 6)
        assert swiggy["close_date"] == date(2024, 11, 8)
        assert swiggy["listing_date"] == date(2024, 11, 13)

    def test_parse_nse_past_issues_csv_success(self):
        records = HistoricalArchiveParser.parse_nse_past_issues_csv(SYNTHETIC_NSE_ARCHIVE_CSV)
        assert len(records) == 2
        premier = records[1]
        assert premier["symbol"] == "PREMIER"
        assert premier["company_name"] == "Premier Energies Limited"
        assert premier["isin"] == "INE028A01025"
        assert premier["final_issue_price_inr"] == 450.0
        assert premier["issue_size_crores"] == 2830.40

    def test_parse_bse_past_issues_csv_success(self):
        records = HistoricalArchiveParser.parse_bse_past_issues_csv(SYNTHETIC_BSE_ARCHIVE_CSV)
        assert len(records) == 3
        sme = records[2]
        assert sme["bse_scrip_code"] == "544001"
        assert sme["company_name"] == "SME Star Enterprise"
        assert sme["category"] == "SME"
        assert sme["final_issue_price_inr"] == 85.0
        assert sme["isin"] == "INE888B01019"

    def test_malformed_archive_content_raises(self):
        with pytest.raises(ArchiveParseError):
            HistoricalArchiveParser.parse_nse_past_issues_json("INVALID_JSON")
        with pytest.raises(ArchiveParseError):
            HistoricalArchiveParser.parse_nse_past_issues_csv("")


# ---------------------------------------------------------------------------
# Tests: Historical Ingestion Service & Entity Resolution Rules
# ---------------------------------------------------------------------------

class TestHistoricalIngestionService:
    def test_isin_match_priority_over_symbol_and_name(self, db_session: Session):
        """If incoming record has identical ISIN, it matches in-place even if symbol changed."""
        existing_ipo = IPO(
            company_name="Acme Technology Limited",
            symbol="ACME_OLD",
            isin="INE123A01099",
            exchange="NSE",
            category="MAINBOARD",
            is_demo=False,
        )
        db_session.add(existing_ipo)
        db_session.commit()

        service = HistoricalIngestionService()
        incoming_record = {
            "company_name": "Acme Technologies Global Ltd.",  # Slightly changed name
            "symbol": "ACME_NEW",                             # Rebranded symbol
            "isin": "INE123A01099",                           # Immutable ISIN match
            "exchange": "NSE",
            "listing_date": date(2024, 10, 15),
            "max_price": 250.0,
        }

        matched = service.resolve_existing_ipo(db_session, incoming_record)
        assert matched is not None
        assert matched.id == existing_ipo.id  # Same entity!

    def test_anti_merge_rule_different_isins_never_merged(self, db_session: Session):
        """Even with similar company names, different ISINs must NEVER merge."""
        existing_adani_power = IPO(
            company_name="Adani Power Limited",
            symbol="ADANIPOWER",
            isin="INE814H01011",
            exchange="NSE",
            is_demo=False,
        )
        db_session.add(existing_adani_power)
        db_session.commit()

        service = HistoricalIngestionService()
        # Incoming record with very similar name but distinct security ISIN
        incoming_adani_green = {
            "company_name": "Adani Power (Solar) Limited",
            "symbol": "ADANISOLAR",
            "isin": "INE364U01010",
            "exchange": "NSE",
        }

        matched = service.resolve_existing_ipo(db_session, incoming_adani_green)
        assert matched is None  # Must NOT merge!

    def test_symbol_and_listing_date_window_match(self, db_session: Session):
        """When ISIN is absent, matches if symbol matches and listing date is within 7 days."""
        existing_ipo = IPO(
            company_name="Swastika Infra Ltd.",
            symbol="SWASTIKA",
            isin=None,
            listing_date=date(2024, 9, 20),
            exchange="NSE",
            is_demo=False,
        )
        db_session.add(existing_ipo)
        db_session.commit()

        service = HistoricalIngestionService()
        incoming = {
            "company_name": "Swastika Infra",
            "symbol": "SWASTIKA",
            "isin": None,
            "listing_date": date(2024, 9, 21),  # Within 7-day window
            "exchange": "NSE",
        }

        matched = service.resolve_existing_ipo(db_session, incoming)
        assert matched is not None
        assert matched.id == existing_ipo.id

    def test_in_place_update_preserves_primary_key_and_relationships(self, db_session: Session):
        """In-place updates preserve the existing primary key and all existing child observations."""
        existing_ipo = IPO(
            company_name="Orient Cables Limited",
            symbol="ORIENTCABLE",
            exchange="NSE",
            is_demo=False,
        )
        db_session.add(existing_ipo)
        db_session.flush()

        # Add existing financial observation to verify it is NOT deleted or touched
        fin_obs = FinancialObservation(
            ipo_id=existing_ipo.id,
            fiscal_year="FY25",
            period_months=12,
            revenue_crores=500.0,
            net_worth_crores=150.0,
        )
        db_session.add(fin_obs)
        db_session.commit()

        original_id = existing_ipo.id

        service = HistoricalIngestionService()
        records = [{
            "company_name": "Orient Cables Limited",
            "symbol": "ORIENTCABLE",
            "isin": "INE999C01012",
            "bse_scrip_code": "544123",
            "listing_date": date(2024, 10, 10),
            "max_price": 180.0,
            "lot_size": 80,
        }]

        result = service.ingest_records(db_session, records, dry_run=False)
        assert result["matched_existing"] == 1
        assert result["created_new"] == 0

        db_session.refresh(existing_ipo)
        assert existing_ipo.id == original_id  # Primary key preserved!
        assert existing_ipo.isin == "INE999C01012"
        assert existing_ipo.bse_scrip_code == "544123"
        assert existing_ipo.listing_date == date(2024, 10, 10)
        assert existing_ipo.max_price == 180.0

        # Verify child financial observation remains completely intact
        child_fin = db_session.scalars(
            select(FinancialObservation).where(FinancialObservation.ipo_id == original_id)
        ).all()
        assert len(child_fin) == 1
        assert child_fin[0].revenue_crores == 500.0

    def test_verified_market_outcome_not_overwritten(self, db_session: Session):
        """A verified bhavcopy outcome (bhavcopy_verified = True) is never overwritten by unverified data."""
        ipo = IPO(
            company_name="Verified IPO Limited",
            symbol="VERIFIED",
            listing_date=date(2024, 10, 15),
            is_demo=False,
        )
        db_session.add(ipo)
        db_session.flush()

        verified_outcome = MarketObservation(
            ipo_id=ipo.id,
            observation_type="LISTING_OUTCOME",
            final_issue_price_inr=100.0,
            listing_open_price_inr=130.0,
            listing_close_price_inr=135.0,
            listing_gain_pct=35.0,
            bhavcopy_verified=True,
        )
        db_session.add(verified_outcome)
        db_session.commit()

        service = HistoricalIngestionService()
        records = [{
            "company_name": "Verified IPO Limited",
            "symbol": "VERIFIED",
            "listing_date": date(2024, 10, 15),
            "final_issue_price_inr": 100.0,
        }]

        # Run with outcome reconciliation enabled
        res = service.ingest_records(db_session, records, reconcile_outcomes=True, dry_run=False)
        assert res["outcomes_skipped"] == 1
        assert res["outcomes_reconciled"] == 0

        db_session.refresh(verified_outcome)
        assert verified_outcome.listing_close_price_inr == 135.0  # Unchanged!

    def test_dry_run_mode_creates_no_database_rows(self, db_session: Session):
        """When dry_run=True, service reports preview metrics but writes ZERO rows to DB."""
        count_before = db_session.scalar(select(func.count(IPO.id)))
        service = HistoricalIngestionService()

        records = [
            {"company_name": "Hypothetical A Ltd", "symbol": "HYPO_A", "isin": "INE111A01011"},
            {"company_name": "Hypothetical B Ltd", "symbol": "HYPO_B", "isin": "INE222A01012"},
        ]

        result = service.ingest_records(db_session, records, dry_run=True)
        assert result["dry_run"] is True
        assert result["created_new"] == 2

        count_after = db_session.scalar(select(func.count(IPO.id)))
        assert count_after == count_before  # Zero rows written!


# ---------------------------------------------------------------------------
# Tests: Live Historical Source Connectivity (Opt-in)
# ---------------------------------------------------------------------------

class TestLiveHistoricalSourceConnectivity:
    @pytest.mark.live
    def test_nse_bhavcopy_portal_reachable(self):
        """Verifies whether official NSE archive portal is reachable over HTTP."""
        verifier = BhavcopyOutcomeVerifier()
        url = verifier.get_canonical_url(date(2024, 10, 15), exchange="NSE")
        try:
            with httpx.Client(headers=verifier.headers, timeout=5.0) as client:
                res = client.head(url)
                assert res.status_code in (200, 301, 302, 403, 404)
        except httpx.HTTPError:
            pytest.skip("NSE archives portal unreachable from current network environment")

    @pytest.mark.live
    def test_bse_udiff_bhavcopy_portal_reachable(self):
        """Verifies whether official BSE modern UDiFF endpoint is reachable over HTTP."""
        verifier = BhavcopyOutcomeVerifier()
        url = verifier.get_canonical_url(date(2024, 10, 15), exchange="BSE")
        try:
            with httpx.Client(headers=verifier.headers, timeout=5.0) as client:
                res = client.head(url)
                assert res.status_code in (200, 301, 302, 403, 404)
        except httpx.HTTPError:
            pytest.skip("BSE portal unreachable from current network environment")

    @pytest.mark.live
    def test_nse_legacy_archive_live_zip_extract(self, tmp_path):
        """Verifies downloading and parsing a real historical legacy NSE ZIP archive."""
        verifier = BhavcopyOutcomeVerifier(cache_dir=str(tmp_path))
        test_date = date(2023, 10, 16)
        try:
            csv_text, url, content_hash = verifier.fetch_bhavcopy(test_date, exchange="NSE", force_refresh=True)
            assert "SYMBOL" in csv_text
            rows = verifier.parse_bhavcopy_rows(csv_text, exchange="NSE")
            assert len(rows) > 1000
        except (BhavcopyVerificationError, httpx.HTTPError) as e:
            pytest.skip(f"NSE legacy archive fetch skipped: {e}")

    @pytest.mark.live
    def test_nse_public_past_issues_live_download(self):
        """Verifies downloading and parsing real historical IPO records from NSE endpoint."""
        from app.pipeline.nse_adapter import NseIpoSourceAdapter
        adapter = NseIpoSourceAdapter()
        try:
            with httpx.Client(headers=adapter.headers, timeout=8.0, follow_redirects=True) as client:
                client.get(f"{adapter.base_url}/market-data/all-upcoming-issues-ipo")
                res = client.get(f"{adapter.base_url}/api/public-past-issues")
                if res.status_code != 200:
                    pytest.skip(f"NSE past issues API returned status {res.status_code}")
                records = HistoricalArchiveParser.parse_nse_past_issues_json(res.text)
                assert len(records) > 500
        except httpx.HTTPError as e:
            pytest.skip(f"NSE past issues live connection skipped: {e}")

