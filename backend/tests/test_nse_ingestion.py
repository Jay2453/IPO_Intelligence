import os
import pytest
from unittest.mock import MagicMock, patch
from datetime import date
from sqlalchemy import select
from app.models.ipo import IPO
from app.models.events import IPOEvent
from app.models.sources import SourceObservation
from app.models.ingestion import IngestionJob
from app.pipeline.nse_adapter import (
    NseIpoSourceAdapter,
    NseConnectionError,
    NseParseError,
    parse_nse_date,
    parse_nse_price_range,
)
from app.services.ingestion_service import IngestionService
from app.core.config import settings

SAMPLE_UPCOMING_RAW = [
    {
        "companyName": "HD Fire Protect Limited",
        "symbol": "HDFIRE",
        "series": "EQ",
        "status": "Forthcoming",
        "issuePrice": "Rs.258 to Rs.271",
        "issueSize": "26284500",
        "issueStartDate": "13-Oct-2026",
        "issueEndDate": "15-Oct-2026",
    },
    {
        "companyName": "Vaibhav Vyapaar Limited",
        "symbol": "LOANFRONT",
        "series": "SME",
        "status": "Forthcoming",
        "priceBand": "Rs.51 to Rs.54",
        "lotSize": "2000",
        "issueSize": "7796000",
        "issueStartDate": "13-Oct-2026",
        "issueEndDate": "15-Oct-2026",
    },
]

SAMPLE_PAST_RAW = [
    {
        "companyName": "Eventions Limited",
        "symbol": "EVENTIONS",
        "securityType": "SME",
        "priceRange": "Rs.112 to Rs.118",
        "issuePrice": "118",
        "ipoStartDate": "30-SEP-2026",
        "ipoEndDate": "05-OCT-2026",
        "listingDate": "08-OCT-2026",
    }
]


def test_nse_date_and_price_parser():
    assert parse_nse_date("13-Oct-2026") == date(2026, 10, 13)
    assert parse_nse_date("05-OCT-2026") == date(2026, 10, 5)
    assert parse_nse_date("-") is None
    assert parse_nse_date("") is None

    p_min, p_max = parse_nse_price_range("Rs.258 to Rs.271")
    assert p_min == 258.0
    assert p_max == 271.0

    p_val, _ = parse_nse_price_range("118")
    assert p_val == 118.0


def test_nse_adapter_normalize_record():
    adapter = NseIpoSourceAdapter()
    norm = adapter.normalize_record(SAMPLE_UPCOMING_RAW[1])
    assert norm is not None
    assert norm["company_name"] == "Vaibhav Vyapaar Limited"
    assert norm["symbol"] == "LOANFRONT"
    assert norm["exchange"] == "NSE"
    assert norm["category"] == "SME"
    assert norm["min_price"] == 51.0
    assert norm["max_price"] == 54.0
    assert norm["lot_size"] == 2000
    assert norm["is_demo"] is False


def test_sync_nse_ipos_mocked_success(db_session):
    mock_adapter = MagicMock(spec=NseIpoSourceAdapter)
    mock_adapter.fetch_raw_upcoming_issues.return_value = (
        SAMPLE_UPCOMING_RAW,
        "https://www.nseindia.com/api/all-upcoming-issues?category=ipo",
        "dummy_hash_upcoming_123",
    )
    mock_adapter.fetch_raw_current_issues.return_value = (
        [],
        "https://www.nseindia.com/api/ipo-current-issue",
        "dummy_hash_current_123",
    )
    mock_adapter.fetch_raw_past_issues.return_value = (
        SAMPLE_PAST_RAW,
        "https://www.nseindia.com/api/public-past-issues",
        "dummy_hash_past_123",
    )
    # Use real normalization
    real_adapter = NseIpoSourceAdapter()
    mock_adapter.normalize_record.side_effect = real_adapter.normalize_record

    service = IngestionService(adapter=mock_adapter)
    result = service.sync_nse_ipos(db=db_session, include_recent_past=True)

    assert result["status"] == "SUCCESS"
    assert result["records_inserted"] == 3
    assert result["records_updated"] == 0

    # Verify records in database
    real_ipos = db_session.scalars(select(IPO).where(IPO.is_demo == False)).all()
    assert len(real_ipos) == 3

    # Check that each real IPO has an initial DISCOVERED event and SourceObservation
    for ipo in real_ipos:
        assert ipo.is_demo is False
        assert ipo.exchange == "NSE"
        events = db_session.scalars(select(IPOEvent).where(IPOEvent.ipo_id == ipo.id)).all()
        assert len(events) >= 1
        assert events[0].event_type == "DISCOVERED"

        sources = db_session.scalars(select(SourceObservation).where(SourceObservation.ipo_id == ipo.id)).all()
        assert len(sources) >= 1
        assert sources[0].source_name == "NSE_FEED"
        assert sources[0].validation_status == "VALID"

    # Verify IngestionJob was logged
    job = db_session.scalar(select(IngestionJob).where(IngestionJob.source_system == "NSE_FEED"))
    assert job is not None
    assert job.status == "SUCCESS"
    assert job.records_processed == 3


def test_duplicate_ingestion_idempotence(db_session):
    mock_adapter = MagicMock(spec=NseIpoSourceAdapter)
    mock_adapter.fetch_raw_upcoming_issues.return_value = (
        SAMPLE_UPCOMING_RAW,
        "https://www.nseindia.com/api/all-upcoming-issues?category=ipo",
        "hash_1",
    )
    mock_adapter.fetch_raw_current_issues.return_value = ([], "url_2", "hash_2")
    mock_adapter.fetch_raw_past_issues.return_value = ([], "url_3", "hash_3")
    real_adapter = NseIpoSourceAdapter()
    mock_adapter.normalize_record.side_effect = real_adapter.normalize_record

    service = IngestionService(adapter=mock_adapter)
    
    # Run 1
    res1 = service.sync_nse_ipos(db=db_session, include_recent_past=False)
    assert res1["records_inserted"] == 2

    count_after_run1 = db_session.scalar(select(IPO).where(IPO.is_demo == False))
    total_after_run1 = len(db_session.scalars(select(IPO).where(IPO.is_demo == False)).all())

    # Run 2 with same data (should update/deduplicate without inserting new rows)
    res2 = service.sync_nse_ipos(db=db_session, include_recent_past=False)
    assert res2["records_inserted"] == 0
    assert res2["records_updated"] == 2

    total_after_run2 = len(db_session.scalars(select(IPO).where(IPO.is_demo == False)).all())
    assert total_after_run1 == total_after_run2


def test_sync_source_failure_and_rollback(db_session):
    mock_adapter = MagicMock(spec=NseIpoSourceAdapter)
    mock_adapter.fetch_raw_upcoming_issues.side_effect = NseConnectionError("503 Gateway Unavailable")

    service = IngestionService(adapter=mock_adapter)
    with pytest.raises(NseConnectionError):
        service.sync_nse_ipos(db=db_session)

    # Verify IngestionJob recorded failure
    job = db_session.scalar(
        select(IngestionJob)
        .where(IngestionJob.source_system == "NSE_FEED")
        .order_by(IngestionJob.started_at.desc())
    )
    assert job is not None
    assert job.status == "FAILED"
    assert "503" in job.error_details


def test_malformed_records_handling(db_session):
    mock_adapter = MagicMock(spec=NseIpoSourceAdapter)
    malformed_items = [
        {"broken": "no company name"},
        {"companyName": "", "symbol": "EMPTY"},
        SAMPLE_UPCOMING_RAW[0],  # Valid item
    ]
    mock_adapter.fetch_raw_upcoming_issues.return_value = (
        malformed_items,
        "https://www.nseindia.com/api/all-upcoming-issues?category=ipo",
        "hash_malformed",
    )
    mock_adapter.fetch_raw_current_issues.return_value = ([], "url", "hash")
    mock_adapter.fetch_raw_past_issues.return_value = ([], "url", "hash")
    real_adapter = NseIpoSourceAdapter()
    mock_adapter.normalize_record.side_effect = real_adapter.normalize_record

    service = IngestionService(adapter=mock_adapter)
    result = service.sync_nse_ipos(db=db_session, include_recent_past=False)

    assert result["records_inserted"] == 1
    assert result["records_skipped"] == 2
    assert result["status"] == "SUCCESS"


def test_sync_api_endpoint(client, monkeypatch):
    # Mock IngestionService inside endpoints.ingestion
    with patch("app.api.v1.endpoints.ingestion.IngestionService") as mock_srv_cls:
        mock_instance = mock_srv_cls.return_value
        mock_instance.sync_nse_ipos.return_value = {
            "status": "SUCCESS",
            "job_id": "test-job-id",
            "records_inserted": 5,
            "records_updated": 0,
            "records_skipped": 0,
            "total_processed": 5,
            "errors": [],
        }

        # Case 1: No key required
        res = client.post("/api/v1/ingestion/sync?include_past=true&past_limit=10")
        assert res.status_code == 200
        assert res.json()["records_inserted"] == 5

        # Case 2: Key required
        monkeypatch.setattr(settings, "INGESTION_API_KEY", "secret-key-123")
        res_forbidden = client.post("/api/v1/ingestion/sync")
        assert res_forbidden.status_code == 403

        res_auth = client.post("/api/v1/ingestion/sync", headers={"X-API-Key": "secret-key-123"})
        assert res_auth.status_code == 200


@pytest.mark.skipif(
    not os.getenv("RUN_LIVE_TESTS") and not settings.RUN_LIVE_TESTS,
    reason="Opt-in live integration smoke test. Set RUN_LIVE_TESTS=true to run.",
)
def test_live_nse_connection_smoke():
    adapter = NseIpoSourceAdapter()
    check = adapter.verify_live_connection()
    assert check["connected"] is True
    assert check["api_status_code"] == 200
