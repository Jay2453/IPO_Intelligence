import os
import io
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
        # Test on recent business day
        url = verifier.get_canonical_url(date(2024, 10, 15), exchange="NSE")
        try:
            with httpx.Client(headers=verifier.headers, timeout=5.0) as client:
                res = client.head(url)
                # Any valid HTTP response code indicates network route accessibility
                assert res.status_code in (200, 301, 302, 403, 404)
        except httpx.HTTPError:
            pytest.skip("NSE archives portal unreachable from current network environment")
