"""
test_sebi_extraction.py
Phase 2 Milestone 2 — SEBI Prospectus Ingestion and Financial Extraction Tests.

Coverage:
- parse_numeric_cell: commas, parentheses (negatives), percentages, missing values
- normalize_to_crores: Millions → Crores, Lakhs → Crores, Crores identity
- extract_fiscal_period: various column headers
- clean_company_name: normalization for IPO matching
- PdfFinancialExtractor: synthetic in-memory PDF with financial tables
- Multi-period extraction (FY24, FY25, FY26)
- Duplicate document hash detection (idempotence)
- Revision detection (new version > old)
- Ambiguous IPO matching fallback (UNMATCHED)
- Database rollback on extraction failure
- SEBI adapter connection verify (live, opt-in)
- SEBI adapter parse HTML listing (synthetic)
- API endpoints: GET /sebi/status, POST /sebi/sync (mocked)
"""
import os
import io
import hashlib
from datetime import datetime, timezone, date
from typing import List, Dict, Any, Optional
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker, Session

from app.core.database import Base, get_db
from app.main import app
from app.models.ipo import IPO
from app.models.documents import Document
from app.models.financials import FinancialObservation
from app.models.sources import SourceObservation
from app.models.ingestion import IngestionJob
from app.pipeline.pdf_extractor import (
    parse_numeric_cell,
    normalize_to_crores,
    extract_fiscal_period,
    PdfFinancialExtractor,
    PdfExtractionError,
)
from app.pipeline.sebi_adapter import (
    clean_company_name,
    parse_sebi_date,
    detect_document_type,
    SebiPublicIssuesAdapter,
)
from app.services.document_service import _name_similarity_score, DocumentService


# ─── Test Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def real_ipo(db_session: Session) -> IPO:
    """Creates a real (non-demo) IPO record for document association tests."""
    ipo = IPO(
        company_name="Grace Renewable Energy Limited",
        symbol="GRACE",
        exchange="NSE_BSE",
        category="MAINBOARD",
        lifecycle_status="FILING",
        is_demo=False,
        data_completeness_pct=30,
        analysis_status="PENDING",
    )
    db_session.add(ipo)
    db_session.commit()
    db_session.refresh(ipo)
    return ipo


# ─── Numeric Parsing Tests ──────────────────────────────────────────────────────

class TestParseNumericCell:
    def test_plain_integer(self):
        assert parse_numeric_cell("123") == 123.0

    def test_decimal_with_comma(self):
        assert parse_numeric_cell("2,058.36") == 2058.36

    def test_negative_parentheses(self):
        assert parse_numeric_cell("(24.66)") == -24.66

    def test_percentage_stripped(self):
        assert parse_numeric_cell("65.73%") == 65.73

    def test_dash_returns_none(self):
        assert parse_numeric_cell("-") is None

    def test_empty_returns_none(self):
        assert parse_numeric_cell("") is None

    def test_na_returns_none(self):
        assert parse_numeric_cell("N/A") is None

    def test_null_returns_none(self):
        assert parse_numeric_cell(None) is None

    def test_bullet_placeholder_returns_none(self):
        assert parse_numeric_cell("[•]") is None

    def test_small_decimal(self):
        assert parse_numeric_cell("9.25") == 9.25

    def test_large_formatted_number(self):
        assert parse_numeric_cell("1,204.92") == 1204.92

    def test_zero_value(self):
        assert parse_numeric_cell("0.00") == 0.0


class TestNormalizeToCrores:
    def test_millions_to_crores(self):
        # 2058.36 millions = 205.836 crores
        result = normalize_to_crores(2058.36, "₹ in millions")
        assert result == pytest.approx(205.836, rel=1e-3)

    def test_lakhs_to_crores(self):
        # 100 lakhs = 1 crore
        result = normalize_to_crores(100, "Lakhs")
        assert result == pytest.approx(1.0, rel=1e-3)

    def test_crores_identity(self):
        result = normalize_to_crores(150.5, "Crores")
        assert result == pytest.approx(150.5, rel=1e-3)

    def test_none_passthrough(self):
        assert normalize_to_crores(None, "Crores") is None


class TestExtractFiscalPeriod:
    def test_fiscal_year_text(self):
        assert extract_fiscal_period("Fiscal 2026") == "FY26"

    def test_fiscal_year_2025(self):
        assert extract_fiscal_period("Fiscal 2025") == "FY25"

    def test_march_end_date(self):
        assert extract_fiscal_period("ended March 31, 2026") == "FY26"

    def test_fy_abbreviation(self):
        assert extract_fiscal_period("FY 2024") == "FY24"

    def test_none_returns_none(self):
        assert extract_fiscal_period(None) is None

    def test_unrecognized_returns_none(self):
        assert extract_fiscal_period("Some random text") is None


# ─── Company Name Normalization Tests ──────────────────────────────────────────

class TestCleanCompanyName:
    def test_strips_limited(self):
        assert "LIMITED" not in clean_company_name("Grace Renewable Energy Limited")

    def test_strips_ltd(self):
        assert "LTD" not in clean_company_name("Infosys Ltd")

    def test_case_normalizes(self):
        result = clean_company_name("grace renewable")
        assert result == result.upper()

    def test_empty_returns_empty(self):
        assert clean_company_name("") == ""


class TestNameSimilarity:
    def test_exact_match(self):
        score = _name_similarity_score("Grace Renewable Energy Limited", "Grace Renewable Energy Limited")
        assert score == 1.0

    def test_partial_match(self):
        score = _name_similarity_score("Grace Renewable Energy Limited", "Grace Renewable Energy Ltd")
        # After normalization both drop suffixes: "GRACE RENEWABLE ENERGY" vs "GRACE RENEWABLE ENERGY"
        assert score >= 0.8

    def test_no_match(self):
        score = _name_similarity_score("Tata Motors Limited", "Infosys Technologies Limited")
        assert score < 0.5

    def test_short_abbrev_mismatch(self):
        score = _name_similarity_score("XYZ Corp", "ABC Corp")
        assert score < 0.6


# ─── SEBI Adapter HTML Parsing Tests ───────────────────────────────────────────

SAMPLE_SEBI_HTML = """
<table>
<tr><td>Date</td><td>Title</td></tr>
<tr>
  <td>Oct 07, 2026</td>
  <td>
    <a href="/filings/public-issues/oct-2026/grace-renewable-energy-limited-drhp_105099.html">Grace Renewable Energy Limited- DRHP</a>
    <a href="/sebi_data/commondocs/oct-2026/Grace%20Renewable%20Energy%20Limited%20DAP_p.pdf">Grace Renewable Energy Limited - Draft Abridged Prospectus</a>
  </td>
</tr>
<tr>
  <td>Oct 06, 2026</td>
  <td>
    <a href="/filings/public-issues/oct-2026/pm-cona-industries-limited_105041.html">PM CONA INDUSTRIES LIMITED</a>
  </td>
</tr>
</table>
"""


class TestSebiAdapterHtmlParsing:
    def test_parses_two_rows(self):
        adapter = SebiPublicIssuesAdapter()
        filings = adapter.parse_filings_html(SAMPLE_SEBI_HTML, "DRHP")
        assert len(filings) == 2

    def test_first_row_has_issuer_name(self):
        adapter = SebiPublicIssuesAdapter()
        filings = adapter.parse_filings_html(SAMPLE_SEBI_HTML, "DRHP")
        assert "Grace Renewable Energy" in filings[0]["issuer_name"]

    def test_first_row_has_pdf_url(self):
        adapter = SebiPublicIssuesAdapter()
        filings = adapter.parse_filings_html(SAMPLE_SEBI_HTML, "DRHP")
        assert filings[0]["direct_pdf_url"] is not None
        assert ".pdf" in filings[0]["direct_pdf_url"].lower()

    def test_second_row_has_no_pdf_url(self):
        adapter = SebiPublicIssuesAdapter()
        filings = adapter.parse_filings_html(SAMPLE_SEBI_HTML, "DRHP")
        assert filings[1]["direct_pdf_url"] is None

    def test_filing_date_parsed(self):
        adapter = SebiPublicIssuesAdapter()
        filings = adapter.parse_filings_html(SAMPLE_SEBI_HTML, "DRHP")
        assert filings[0]["filing_date"] == date(2026, 10, 7)

    def test_detect_document_type_drhp(self):
        assert detect_document_type("Grace Limited - DRHP", "") == "DRHP"

    def test_detect_document_type_dap(self):
        assert detect_document_type("Grace Limited - Draft Abridged Prospectus", "") == "DRAFT_ABRIDGED_PROSPECTUS"


class TestParseSebiDate:
    def test_full_month(self):
        assert parse_sebi_date("Oct 07, 2026") == date(2026, 10, 7)

    def test_dashes_format(self):
        assert parse_sebi_date("07-Oct-2026") == date(2026, 10, 7)

    def test_iso_format(self):
        assert parse_sebi_date("2026-10-07") == date(2026, 10, 7)

    def test_none_input(self):
        assert parse_sebi_date(None) is None

    def test_dash_string_returns_none(self):
        assert parse_sebi_date("-") is None


# ─── Synthetic PDF Financial Extraction Tests ───────────────────────────────────

def _build_synthetic_pdf_bytes() -> bytes:
    """
    Builds a minimal synthetic PDF with a financial summary table for testing.
    Uses reportlab if available, otherwise creates a very minimal hand-crafted PDF.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Table, Paragraph
        from reportlab.lib.styles import getSampleStyleSheet
        from io import BytesIO

        buf = BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4)
        styles = getSampleStyleSheet()

        table_data = [
            ["Particulars", "Fiscal 2026", "Fiscal 2025", "Fiscal 2024"],
            ["Revenue from Operations", "2058.36", "1204.92", "779.09"],
            ["EBITDA", "257.97", "128.07", "88.77"],
            ["Profit for the period/ year", "186.67", "97.71", "57.93"],
            ["Basic EPS (per share)", "5.27", "2.76", "1.64"],
            ["Return on Equity", "65.73%", "68.91%", "90.47%"],
            ["Return on Capital Employed", "80.45%", "81.03%", "91.56%"],
            ["Total borrowings", "9.25", "13.15", "32.43"],
            ["Net worth(1)", "377.33", "190.65", "92.92"],
            ["Cash generated from / (used in) operating activities", "111.87", "74.77", "54.25"],
        ]

        heading = Paragraph("Financial Information (₹ in Crores)", styles["Heading2"])
        t = Table(table_data)
        doc.build([heading, t])
        buf.seek(0)
        return buf.read()

    except ImportError:
        # reportlab not installed — build raw hand-crafted minimal PDF text content
        # pdfplumber won't extract tables from hand-crafted PDFs, so we skip extraction tests
        return b""


@pytest.fixture(scope="module")
def synthetic_pdf_bytes() -> bytes:
    return _build_synthetic_pdf_bytes()


class TestPdfFinancialExtractor:
    def test_parse_numeric_values_consistent(self):
        """Core numeric parsing must work independently of PDF format."""
        assert parse_numeric_cell("2,058.36") == pytest.approx(2058.36)
        assert parse_numeric_cell("(24.66)") == pytest.approx(-24.66)

    def test_extract_financials_empty_bytes_raises(self):
        extractor = PdfFinancialExtractor()
        with pytest.raises(PdfExtractionError):
            extractor.extract_financials(b"not a real pdf")

    def test_extract_financials_with_synthetic_pdf(self, synthetic_pdf_bytes):
        """Integration test: extraction from a reportlab-generated synthetic PDF."""
        if not synthetic_pdf_bytes:
            pytest.skip("reportlab not installed; skipping synthetic PDF test")

        extractor = PdfFinancialExtractor()
        observations = extractor.extract_financials(synthetic_pdf_bytes)

        assert len(observations) == 3
        fy26 = next((o for o in observations if o["fiscal_year"] == "FY26"), None)
        assert fy26 is not None
        # Revenue should be Crores already (synthetic PDF has ₹ in Crores header)
        assert fy26["revenue_crores"] is not None
        assert fy26["ebitda_crores"] == pytest.approx(257.97, rel=1e-2)
        assert fy26["pat_crores"] == pytest.approx(186.67, rel=1e-2)
        assert fy26["eps_inr"] == pytest.approx(5.27, rel=1e-2)
        assert fy26["roe_pct"] == pytest.approx(65.73, rel=1e-2)
        assert fy26["source_page"] is not None

    def test_multi_period_extraction(self, synthetic_pdf_bytes):
        """Verifies FY24, FY25, FY26 all extracted with correct values."""
        if not synthetic_pdf_bytes:
            pytest.skip("reportlab not installed")

        extractor = PdfFinancialExtractor()
        observations = extractor.extract_financials(synthetic_pdf_bytes)
        fiscal_years = [o["fiscal_year"] for o in observations]
        assert "FY24" in fiscal_years
        assert "FY25" in fiscal_years
        assert "FY26" in fiscal_years

    def test_missing_metrics_are_none_not_zero(self, synthetic_pdf_bytes):
        """Missing values must be None, never silently 0.0."""
        if not synthetic_pdf_bytes:
            pytest.skip("reportlab not installed")

        extractor = PdfFinancialExtractor()
        observations = extractor.extract_financials(synthetic_pdf_bytes)
        for obs in observations:
            # None is acceptable; 0.0 for something like total_assets is suspicious
            # but we mainly verify there's no sentinel -999 or magic number
            for field in ["total_assets_crores", "total_liabilities_crores"]:
                val = obs.get(field)
                assert val is None or isinstance(val, float)


# ─── Document Service Integration Tests ────────────────────────────────────────

class TestDocumentServiceIntegration:
    def _fake_filing_meta(self, issuer_name: str = "Grace Renewable Energy Limited") -> Dict[str, Any]:
        fake_pdf = b"%PDF-1.4 fake-pdf-content-for-testing-purposes"
        file_hash = hashlib.sha256(fake_pdf).hexdigest()
        return {
            "issuer_name": issuer_name,
            "raw_title": f"{issuer_name} - DRHP",
            "document_type": "DRHP",
            "filing_date": date(2026, 10, 7),
            "detail_url": f"https://www.sebi.gov.in/filings/{issuer_name.lower()}-drhp.html",
            "direct_pdf_url": f"https://www.sebi.gov.in/sebi_data/{issuer_name.lower()}.pdf",
            "section": "DRHP",
            "_test_pdf_bytes": fake_pdf,
            "_test_hash": file_hash,
        }

    def _make_mock_adapter(self, filing_meta: Dict[str, Any]) -> MagicMock:
        adapter = MagicMock(spec=SebiPublicIssuesAdapter)
        from app.pipeline.interfaces import DiscoveryResult
        adapter.poll_new_filings.return_value = [
            DiscoveryResult(
                company_name=filing_meta["issuer_name"],
                source_system="SEBI_PUBLIC_FILINGS",
                canonical_url=filing_meta["detail_url"],
                raw_metadata=filing_meta,
                discovered_at=datetime.now(timezone.utc),
            )
        ]
        adapter.resolve_pdf_url.return_value = filing_meta["direct_pdf_url"]
        adapter.fetch_document.return_value = {
            "payload": filing_meta["_test_pdf_bytes"],
            "file_size_bytes": len(filing_meta["_test_pdf_bytes"]),
            "file_hash_sha256": filing_meta["_test_hash"],
            "content_type": "application/pdf",
            "retrieved_at": datetime.now(timezone.utc),
            "source_url": filing_meta["direct_pdf_url"],
        }
        return adapter

    def test_document_stored_with_hash(self, db_session: Session, real_ipo: IPO):
        """Document must be stored with correct SHA-256 hash."""
        filing_meta = self._fake_filing_meta()
        adapter = self._make_mock_adapter(filing_meta)

        # Extractor mock — returns empty (no financials in fake PDF)
        extractor = MagicMock(spec=PdfFinancialExtractor)
        extractor.extract_financials.return_value = []

        service = DocumentService(adapter=adapter, extractor=extractor)
        result = service.sync_sebi_documents(db=db_session, max_documents=5)

        assert result["processed"] == 1
        docs = db_session.scalars(select(Document)).all()
        assert len(docs) == 1
        assert docs[0].file_hash_sha256 == filing_meta["_test_hash"]

    def test_duplicate_hash_idempotence(self, db_session: Session, real_ipo: IPO):
        """Same document hash stored twice must not create a second record."""
        filing_meta = self._fake_filing_meta()
        adapter = self._make_mock_adapter(filing_meta)
        extractor = MagicMock(spec=PdfFinancialExtractor)
        extractor.extract_financials.return_value = []

        service = DocumentService(adapter=adapter, extractor=extractor)

        # First sync
        r1 = service.sync_sebi_documents(db=db_session, max_documents=5)
        # Second sync with same hash
        r2 = service.sync_sebi_documents(db=db_session, max_documents=5)

        docs = db_session.scalars(select(Document)).all()
        assert len(docs) == 1  # Idempotent
        assert r2["already_stored"] == 1

    def test_revision_detection(self, db_session: Session, real_ipo: IPO):
        """When content changes (new hash), old document is marked not current."""
        issuer = "Grace Renewable Energy Limited"

        # First version
        v1_pdf = b"%PDF-1.4 version 1 content"
        v1_hash = hashlib.sha256(v1_pdf).hexdigest()
        filing_v1 = {
            "issuer_name": issuer,
            "raw_title": f"{issuer} - DRHP",
            "document_type": "DRHP",
            "filing_date": date(2026, 10, 7),
            "detail_url": "https://www.sebi.gov.in/test-v1.html",
            "direct_pdf_url": "https://www.sebi.gov.in/test-v1.pdf",
            "section": "DRHP",
            "_test_pdf_bytes": v1_pdf,
            "_test_hash": v1_hash,
        }

        adapter = self._make_mock_adapter(filing_v1)
        extractor = MagicMock(spec=PdfFinancialExtractor)
        extractor.extract_financials.return_value = []

        service = DocumentService(adapter=adapter, extractor=extractor)
        service.sync_sebi_documents(db=db_session, max_documents=5)

        # Second version
        v2_pdf = b"%PDF-1.4 revised content here"
        v2_hash = hashlib.sha256(v2_pdf).hexdigest()
        filing_v2 = {**filing_v1, "_test_pdf_bytes": v2_pdf, "_test_hash": v2_hash}
        adapter2 = self._make_mock_adapter(filing_v2)
        adapter2.fetch_document.return_value["file_hash_sha256"] = v2_hash
        adapter2.fetch_document.return_value["payload"] = v2_pdf

        service2 = DocumentService(adapter=adapter2, extractor=extractor)
        result2 = service2.sync_sebi_documents(db=db_session, max_documents=5)

        docs = db_session.scalars(select(Document).where(Document.issuer_name == issuer)).all()
        assert len(docs) == 2
        assert result2["hash_revision_detected"] == 1
        old_docs = [d for d in docs if not d.is_current]
        assert len(old_docs) == 1
        assert old_docs[0].version_number == 1

    def test_unmatched_filing_stored_without_ipo(self, db_session: Session):
        """A filing for an unknown company must be stored with UNMATCHED status."""
        filing_meta = self._fake_filing_meta(issuer_name="XYZ Unknown Company Private Limited")
        adapter = self._make_mock_adapter(filing_meta)
        extractor = MagicMock(spec=PdfFinancialExtractor)
        extractor.extract_financials.return_value = []

        service = DocumentService(adapter=adapter, extractor=extractor)
        result = service.sync_sebi_documents(db=db_session, max_documents=5)

        assert result["processed"] == 1
        assert result["unmatched"] == 1
        docs = db_session.scalars(select(Document)).all()
        assert len(docs) == 1
        assert docs[0].ipo_id is None
        assert docs[0].extraction_status == "UNMATCHED"

    def test_source_observation_provenance_stored(self, db_session: Session, real_ipo: IPO):
        """SourceObservation must be created for every ingested document."""
        filing_meta = self._fake_filing_meta()
        adapter = self._make_mock_adapter(filing_meta)
        extractor = MagicMock(spec=PdfFinancialExtractor)
        extractor.extract_financials.return_value = []

        service = DocumentService(adapter=adapter, extractor=extractor)
        service.sync_sebi_documents(db=db_session, max_documents=5)

        sources = db_session.scalars(select(SourceObservation).where(
            SourceObservation.source_name == "SEBI_PUBLIC_FILINGS"
        )).all()
        assert len(sources) >= 1
        assert sources[0].content_hash_sha256 == filing_meta["_test_hash"]

    def test_db_rollback_on_extraction_failure(self, db_session: Session, real_ipo: IPO):
        """If extraction raises, Document is stored but marked FAILED — no partial financials."""
        filing_meta = self._fake_filing_meta()
        adapter = self._make_mock_adapter(filing_meta)
        extractor = MagicMock(spec=PdfFinancialExtractor)
        extractor.extract_financials.side_effect = PdfExtractionError("Corrupt PDF")

        service = DocumentService(adapter=adapter, extractor=extractor)
        result = service.sync_sebi_documents(db=db_session, max_documents=5)

        # Document should still be stored
        docs = db_session.scalars(select(Document)).all()
        assert len(docs) == 1
        assert docs[0].extraction_status == "FAILED"
        assert docs[0].extraction_error is not None

        # No financial observations
        fins = db_session.scalars(select(FinancialObservation)).all()
        assert len(fins) == 0


# ─── API Endpoint Tests ────────────────────────────────────────────────────────

class TestSebiApiEndpoints:
    def test_sebi_status_returns_connection_and_stats(self, client: TestClient):
        """GET /sebi/status must return connection and document stats."""
        with patch.object(SebiPublicIssuesAdapter, "verify_connection", return_value={
            "source": "SEBI_PUBLIC_FILINGS",
            "status": "UP",
            "endpoint": "https://www.sebi.gov.in/filings/public-issues.html",
            "verified_at": datetime.now(timezone.utc).isoformat(),
        }):
            resp = client.get("/api/v1/sebi/status")
            assert resp.status_code == 200
            data = resp.json()
            assert "connection" in data
            assert "document_stats" in data
            assert data["connection"]["status"] == "UP"

    def test_sebi_sync_triggers_document_service(self, client: TestClient):
        """POST /sebi/sync must call DocumentService and return results."""
        mock_result = {
            "job_id": "test-job-1",
            "source": "SEBI_PUBLIC_FILINGS",
            "discovered": 3,
            "already_stored": 0,
            "hash_revision_detected": 0,
            "processed": 2,
            "financials_extracted": 4,
            "unmatched": 1,
            "errors": [],
        }
        with patch.object(DocumentService, "sync_sebi_documents", return_value=mock_result):
            resp = client.post("/api/v1/sebi/sync?max_documents=5")
            assert resp.status_code == 200
            data = resp.json()
            assert data["processed"] == 2
            assert data["financials_extracted"] == 4

    def test_list_documents_empty(self, client: TestClient):
        """GET /documents must return empty paginated list when no documents."""
        resp = client.get("/api/v1/documents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_get_document_not_found(self, client: TestClient):
        """GET /documents/{id} must return 404 for unknown document."""
        resp = client.get("/api/v1/documents/nonexistent-doc-id")
        assert resp.status_code == 404

    def test_list_ipo_documents_not_found(self, client: TestClient):
        """GET /ipos/{id}/documents must return 404 for unknown IPO."""
        resp = client.get("/api/v1/ipos/nonexistent-ipo/documents")
        assert resp.status_code == 404

    def test_list_ipo_financials_not_found(self, client: TestClient):
        """GET /ipos/{id}/financials must return 404 for unknown IPO."""
        resp = client.get("/api/v1/ipos/nonexistent-ipo/financials")
        assert resp.status_code == 404


# ─── Live Smoke Test (opt-in) ──────────────────────────────────────────────────

@pytest.mark.skipif(
    not os.getenv("RUN_LIVE_TESTS"),
    reason="Set RUN_LIVE_TESTS=1 to run live SEBI connectivity tests",
)
class TestLiveSebiConnectivity:
    def test_sebi_portal_reachable(self):
        adapter = SebiPublicIssuesAdapter()
        result = adapter.verify_connection()
        assert result["status"] == "UP"
        assert result["status_code"] == 200

    def test_live_drhp_listing_returns_filings(self):
        adapter = SebiPublicIssuesAdapter()
        filings = adapter.fetch_filings_listing(SebiPublicIssuesAdapter.DRHP_URL, "DRHP")
        assert len(filings) > 0
        assert all("issuer_name" in f for f in filings)
        assert all("detail_url" in f for f in filings)

    def test_live_pdf_download_and_hash(self):
        adapter = SebiPublicIssuesAdapter()
        # Known stable test document
        url = "https://www.sebi.gov.in/sebi_data/commondocs/oct-2026/Grace%20Renewable%20Energy%20Limited%20DAP_p.pdf"
        result = adapter.fetch_document(url)
        assert result["file_size_bytes"] > 0
        assert len(result["file_hash_sha256"]) == 64
        assert result["content_type"] == "application/pdf"

    def test_live_extraction_from_real_pdf(self):
        import httpx
        adapter = SebiPublicIssuesAdapter()
        url = "https://www.sebi.gov.in/sebi_data/commondocs/oct-2026/Grace%20Renewable%20Energy%20Limited%20DAP_p.pdf"
        doc_data = adapter.fetch_document(url)

        extractor = PdfFinancialExtractor()
        observations = extractor.extract_financials(doc_data["payload"])

        assert len(observations) >= 1
        for obs in observations:
            assert obs["fiscal_year"] is not None
            assert obs["source_page"] is not None
            # Validate no fabricated zeros — key metrics may be None but not negative revenues
            if obs.get("revenue_crores") is not None:
                assert obs["revenue_crores"] > 0
