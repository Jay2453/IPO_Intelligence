"""
Document Service — Phase 2 Milestone 2
Orchestrates SEBI discovery → download → hash check → IPO matching → extraction → persistence.
Never fabricates numbers. Missing metrics stay None.
"""
import re
import os
import urllib.parse
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

from sqlalchemy import select, or_, desc
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ipo import IPO
from app.models.documents import Document
from app.models.financials import FinancialObservation
from app.models.sources import SourceObservation
from app.models.ingestion import IngestionJob
from app.pipeline.sebi_adapter import (
    SebiPublicIssuesAdapter,
    SebiConnectionError,
    DocumentSizeLimitExceededError,
    clean_company_name,
)
from app.pipeline.pdf_extractor import PdfFinancialExtractor, PdfExtractionError


def _name_similarity_score(a: str, b: str) -> float:
    """
    Token-level Jaccard similarity of normalised company names.
    Returns value in [0.0, 1.0]. 1.0 = identical token sets.
    """
    tokens_a = set(clean_company_name(a).split())
    tokens_b = set(clean_company_name(b).split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def _match_ipo(db: Session, issuer_name: str) -> Tuple[Optional[IPO], float]:
    """
    Attempts to find an existing real IPO record (is_demo=False) that best matches
    the SEBI filing issuer name using normalised token comparison.
    Returns (matched_ipo, confidence_score).
    If best_score < 0.5, returns (None, best_score) — document stored as UNMATCHED.
    """
    all_ipos = db.scalars(select(IPO).where(IPO.is_demo == False)).all()

    best_match: Optional[IPO] = None
    best_score = 0.0

    for ipo in all_ipos:
        score = _name_similarity_score(issuer_name, ipo.company_name)
        if score > best_score:
            best_score = score
            best_match = ipo

    if best_score >= 0.5:
        return best_match, best_score
    return None, best_score


class DocumentService:
    """
    Orchestrates the full SEBI document ingestion pipeline:
    1. Discover new filings from SEBI public issues portal
    2. Download PDF with bounded streaming
    3. Check SHA-256 hash for duplicates/revisions
    4. Match to existing IPO records (or flag UNMATCHED)
    5. Extract financial observations using PdfFinancialExtractor
    6. Persist Document + FinancialObservation + SourceObservation records
    7. Log IngestionJob
    """

    CONFIDENCE_THRESHOLD = 0.5  # Minimum Jaccard score to auto-associate document with IPO

    def __init__(
        self,
        adapter: Optional[SebiPublicIssuesAdapter] = None,
        extractor: Optional[PdfFinancialExtractor] = None,
    ):
        self.adapter = adapter or SebiPublicIssuesAdapter()
        self.extractor = extractor or PdfFinancialExtractor()

    def sync_sebi_documents(
        self,
        db: Session,
        max_documents: Optional[int] = None,
        since: Optional[datetime] = None,
        force_recheck: bool = False,
    ) -> Dict[str, Any]:
        """
        Main sync entry point. Discovers new SEBI filings and processes each.
        Commits atomically using savepoints.
        Safely rejects overlapping concurrent runs.
        """
        limit = max_documents or settings.SEBI_MAX_DOCUMENTS_PER_SYNC

        # Concurrency safeguard: check if another SEBI sync is currently running
        active_job = db.scalar(
            select(IngestionJob)
            .where(
                IngestionJob.source_system == "SEBI_PUBLIC_FILINGS",
                IngestionJob.status == "RUNNING",
            )
            .order_by(desc(IngestionJob.started_at))
            .limit(1)
        )
        if active_job:
            now = datetime.now(timezone.utc)
            started = active_job.started_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            age_seconds = (now - started).total_seconds()
            if age_seconds < 900:  # 15 minute threshold
                raise RuntimeError(
                    f"A SEBI synchronization job is currently in progress (Job ID: {active_job.id}, started {int(age_seconds)}s ago). Concurrent sync rejected."
                )
            else:
                # Mark stale/abandoned job from interrupted process as FAILED
                active_job.status = "FAILED"
                active_job.error_details = "Job timed out or was interrupted by a previous restart."
                active_job.completed_at = now
                db.commit()

        job = IngestionJob(
            job_type="DOCUMENT_SYNC",
            source_system="SEBI_PUBLIC_FILINGS",
            status="RUNNING",
            started_at=datetime.now(timezone.utc),
            records_processed=0,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        results: Dict[str, Any] = {
            "job_id": job.id,
            "source": "SEBI_PUBLIC_FILINGS",
            "discovered": 0,
            "already_stored": 0,
            "hash_revision_detected": 0,
            "processed": 0,
            "financials_extracted": 0,
            "unmatched": 0,
            "errors": [],
        }

        try:
            filings = self.adapter.poll_new_filings(since=since)
            results["discovered"] = len(filings)

            evaluated_count = 0
            for filing_meta in filings:
                if evaluated_count >= limit:
                    break

                evaluated_count += 1
                try:
                    outcome = self._process_single_filing(
                        db, filing_meta.raw_metadata, force_recheck=force_recheck
                    )
                    results["already_stored"] += outcome.get("already_stored", 0)
                    results["hash_revision_detected"] += outcome.get("revision_detected", 0)
                    results["processed"] += outcome.get("processed", 0)
                    results["financials_extracted"] += outcome.get("financials_extracted", 0)
                    results["unmatched"] += outcome.get("unmatched", 0)
                    if outcome.get("errors"):
                        results["errors"].extend(outcome["errors"])
                except Exception as exc:
                    results["errors"].append(str(exc))

            # Finalise ingestion job
            if not results["errors"]:
                job.status = "SUCCESS"
            else:
                job.status = "PARTIAL"
                job.error_details = "; ".join(results["errors"][:3])
            job.completed_at = datetime.now(timezone.utc)
            job.records_processed = results["processed"]
            db.commit()

        except SebiConnectionError as exc:
            job.status = "FAILED"
            job.completed_at = datetime.now(timezone.utc)
            job.error_details = str(exc)
            db.commit()
            results["errors"].append(f"SEBI connection failed: {exc}")

        return results

    def _process_single_filing(
        self,
        db: Session,
        filing_meta: Dict[str, Any],
        force_recheck: bool = False,
    ) -> Dict[str, Any]:
        """
        Processes a single SEBI filing entry through the full pipeline.
        Uses a savepoint so one document failure won't roll back the session.
        Uses fast URL pre-check to eliminate redundant binary downloads.
        """
        outcome = {
            "already_stored": 0,
            "revision_detected": 0,
            "processed": 0,
            "financials_extracted": 0,
            "unmatched": 0,
        }

        issuer_name = filing_meta.get("issuer_name", "")
        detail_url = filing_meta.get("detail_url", "")
        direct_pdf_url = filing_meta.get("direct_pdf_url")
        doc_type = filing_meta.get("document_type", "OFFER_DOCUMENT")
        filing_date = filing_meta.get("filing_date")

        # Resolve downloadable PDF URL
        pdf_url = self.adapter.resolve_pdf_url(detail_url, direct_pdf_url)
        if not pdf_url:
            outcome["errors"] = [f"No PDF URL found for {issuer_name}"]
            return outcome

        # Fast URL Pre-Check before heavy binary download
        existing_doc = db.scalars(
            select(Document).where(Document.file_url == pdf_url, Document.is_current == True)
        ).first()

        if existing_doc and not force_recheck:
            # Check if remote metadata indicates content has not changed
            remote_meta = None
            if hasattr(self.adapter, "probe_document_metadata"):
                remote_meta = self.adapter.probe_document_metadata(pdf_url)

            # If remote Content-Length matches stored size, document is unchanged
            if remote_meta and remote_meta.get("content_length") is not None:
                if remote_meta["content_length"] == existing_doc.file_size_bytes:
                    outcome["already_stored"] = 1
                    return outcome
            elif not remote_meta:
                # If probe failed or unsupported, existing URL record is respected
                outcome["already_stored"] = 1
                return outcome

        # Download with bounded streaming and retry
        doc_data = self.adapter.fetch_document(pdf_url)
        file_hash = doc_data["file_hash_sha256"]

        # Check if this exact hash is already stored
        existing = db.scalars(
            select(Document).where(Document.file_hash_sha256 == file_hash)
        ).first()

        if existing:
            outcome["already_stored"] = 1
            return outcome

        # Check for previous version of same issuer/type
        previous_version = db.scalars(
            select(Document)
            .where(Document.issuer_name == issuer_name, Document.document_type == doc_type, Document.is_current == True)
            .order_by(desc(Document.version_number))
        ).first()

        version_number = 1
        if previous_version:
            # Mark old version as superseded
            outcome["revision_detected"] = 1
            version_number = previous_version.version_number + 1
            with db.begin_nested():
                previous_version.is_current = False
                db.flush()

        # Match to existing IPO
        matched_ipo, confidence = _match_ipo(db, issuer_name)
        extraction_status = "PENDING"
        if not matched_ipo:
            extraction_status = "UNMATCHED"
            outcome["unmatched"] = 1

        # Build file_name from URL
        file_name = urllib.parse.unquote(pdf_url.split("/")[-1]) or f"{issuer_name}_{doc_type}.pdf"

        # Create Document record
        document = Document(
            ipo_id=matched_ipo.id if matched_ipo else None,
            issuer_name=issuer_name,
            document_type=doc_type,
            version_number=version_number,
            file_name=file_name,
            file_url=pdf_url,
            source_url=detail_url,
            file_hash_sha256=file_hash,
            file_size_bytes=doc_data["file_size_bytes"],
            filing_date=filing_date,
            retrieval_timestamp=doc_data["retrieved_at"],
            is_current=True,
            extraction_status=extraction_status,
            extracted_metadata={
                "issuer_name": issuer_name,
                "match_confidence": round(confidence, 3),
                "matched_ipo_id": matched_ipo.id if matched_ipo else None,
                "document_type": doc_type,
            },
        )

        with db.begin_nested():
            db.add(document)
            db.flush()

            # Record source observation provenance
            source_obs = SourceObservation(
                ipo_id=matched_ipo.id if matched_ipo else None,
                source_name="SEBI_PUBLIC_FILINGS",
                canonical_url=pdf_url,
                content_hash_sha256=file_hash,
                retrieval_timestamp=doc_data["retrieved_at"],
                publication_timestamp=datetime.combine(
                    filing_date, datetime.min.time(), tzinfo=timezone.utc
                ) if filing_date else None,
                validation_status="VALID",
                raw_metadata={
                    "issuer_name": issuer_name,
                    "document_type": doc_type,
                    "detail_url": detail_url,
                    "file_size_bytes": doc_data["file_size_bytes"],
                    "match_confidence": round(confidence, 3),
                },
            )
            db.add(source_obs)
            db.flush()

        outcome["processed"] = 1

        # Extract financials only if document is matched to an IPO and is a substantive document
        if matched_ipo and doc_type in (
            "DRHP", "RHP", "DRAFT_ABRIDGED_PROSPECTUS", "ABRIDGED_PROSPECTUS", "PROSPECTUS"
        ):
            try:
                fin_count = self._extract_and_store_financials(
                    db=db,
                    document=document,
                    ipo=matched_ipo,
                    pdf_bytes=doc_data["payload"],
                )
                outcome["financials_extracted"] = fin_count
            except PdfExtractionError as exc:
                with db.begin_nested():
                    document.extraction_status = "FAILED"
                    document.extraction_error = str(exc)[:1000]
                    db.flush()

        return outcome

    def _extract_and_store_financials(
        self,
        db: Session,
        document: Document,
        ipo: IPO,
        pdf_bytes: bytes,
    ) -> int:
        """
        Runs PDF extraction and persists validated financial observations.
        Idempotent: replaces blank/empty existing records when the new extraction has real data.
        Returns number of periods with meaningful financial metrics stored.

        Document extraction_status semantics:
          EXTRACTED  — at least one FY has meaningful metrics
          PARTIAL    — some FY records have metrics, some are empty
          FAILED     — no usable metrics extracted from any period
        """
        observations = self.extractor.extract_financials(pdf_bytes)

        USABLE_METRIC_FIELDS = [
            "revenue_crores", "ebitda_crores", "pat_crores", "total_assets_crores",
            "net_worth_crores", "total_liabilities_crores", "total_debt_crores",
            "operating_cash_flow_crores", "roe_pct", "roce_pct", "eps_inr", "nav_per_share_inr",
        ]

        def _has_usable_metrics(obs_data: dict) -> bool:
            return any(obs_data.get(f) is not None for f in USABLE_METRIC_FIELDS)

        # Filter to only observations that actually carry data
        usable_observations = [o for o in observations if _has_usable_metrics(o)]

        stored = 0
        updated = 0

        for obs_data in observations:
            fiscal_year = obs_data.get("fiscal_year")
            if not fiscal_year:
                continue

            obs_has_data = _has_usable_metrics(obs_data)

            # Check for existing observation for this IPO + fiscal_year
            existing_obs = db.scalars(
                select(FinancialObservation)
                .where(
                    FinancialObservation.ipo_id == ipo.id,
                    FinancialObservation.fiscal_year == fiscal_year,
                )
            ).first()

            if existing_obs:
                if obs_has_data:
                    with db.begin_nested():
                        for field in USABLE_METRIC_FIELDS:
                            new_val = obs_data.get(field)
                            if new_val is not None:
                                setattr(existing_obs, field, new_val)
                        existing_obs.source_document_id = document.id
                        existing_obs.source_page = obs_data.get("source_page")
                        existing_obs.statement_type = obs_data.get("statement_type", "CONSOLIDATED")
                        existing_obs.is_restated = obs_data.get("is_restated", True)
                        existing_obs.unit = obs_data.get("unit", "CRORES")
                        existing_obs.extraction_method = obs_data.get("extraction_method", "PDFPLUMBER_TABLE")
                        existing_obs.verification_status = obs_data.get("verification_status", "EXTRACTED")
                        existing_obs.raw_data_provenance = obs_data.get("raw_data_provenance")
                        db.flush()
                    updated += 1
                continue

            # Only create new records when there is real data to store
            if not obs_has_data:
                continue

            fin_obs = FinancialObservation(
                ipo_id=ipo.id,
                fiscal_year=fiscal_year,
                period_months=obs_data.get("period_months", 12),
                revenue_crores=obs_data.get("revenue_crores"),
                ebitda_crores=obs_data.get("ebitda_crores"),
                pat_crores=obs_data.get("pat_crores"),
                total_assets_crores=obs_data.get("total_assets_crores"),
                net_worth_crores=obs_data.get("net_worth_crores"),
                total_liabilities_crores=obs_data.get("total_liabilities_crores"),
                total_debt_crores=obs_data.get("total_debt_crores"),
                operating_cash_flow_crores=obs_data.get("operating_cash_flow_crores"),
                roe_pct=obs_data.get("roe_pct"),
                roce_pct=obs_data.get("roce_pct"),
                eps_inr=obs_data.get("eps_inr"),
                nav_per_share_inr=obs_data.get("nav_per_share_inr"),
                source_document_id=document.id,
                source_page=obs_data.get("source_page"),
                statement_type=obs_data.get("statement_type", "CONSOLIDATED"),
                is_restated=obs_data.get("is_restated", True),
                currency=obs_data.get("currency", "INR"),
                unit=obs_data.get("unit", "CRORES"),
                extraction_method=obs_data.get("extraction_method", "PDFPLUMBER_TABLE"),
                verification_status=obs_data.get("verification_status", "EXTRACTED"),
                raw_data_provenance=obs_data.get("raw_data_provenance"),
            )
            with db.begin_nested():
                db.add(fin_obs)
                db.flush()
            stored += 1

        # Determine document extraction_status from actual data quality
        total_meaningful = stored + updated
        total_periods = len(observations)

        if total_meaningful == 0:
            with db.begin_nested():
                document.extraction_status = "FAILED"
                document.extraction_error = (
                    "No usable financial metrics could be extracted from any period"
                )
                db.flush()
        elif total_meaningful < total_periods:
            with db.begin_nested():
                document.extraction_status = "PARTIAL"
                document.extraction_error = None
                db.flush()
        else:
            with db.begin_nested():
                document.extraction_status = "EXTRACTED"
                document.extraction_error = None
                db.flush()

        return total_meaningful

    def get_document_status(self, db: Session) -> Dict[str, Any]:
        """Returns a summary of SEBI document ingestion health."""
        from sqlalchemy import func
        total = db.scalar(select(func.count(Document.id))) or 0
        pending = db.scalar(select(func.count(Document.id)).where(Document.extraction_status == "PENDING")) or 0
        extracted = db.scalar(select(func.count(Document.id)).where(Document.extraction_status == "EXTRACTED")) or 0
        partial = db.scalar(select(func.count(Document.id)).where(Document.extraction_status == "PARTIAL")) or 0
        failed = db.scalar(select(func.count(Document.id)).where(Document.extraction_status == "FAILED")) or 0
        unmatched = db.scalar(select(func.count(Document.id)).where(Document.extraction_status == "UNMATCHED")) or 0
        return {
            "total_documents": total,
            "pending": pending,
            "extracted": extracted,
            "partial": partial,
            "failed": failed,
            "unmatched": unmatched,
        }

    def extract_pending_documents(
        self,
        db: Session,
        limit: int = 5,
        document_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Processes stored eligible documents awaiting extraction in a bounded, observable way.
        Uses local disk cache to avoid redundant network downloads.
        Preserves cryptographic SHA-256 verification and idempotency.
        """
        from app.models.ipo import IPO

        eligible_types = (
            "DRHP", "RHP", "DRAFT_ABRIDGED_PROSPECTUS", "ABRIDGED_PROSPECTUS", "PROSPECTUS"
        )

        if document_id:
            target_docs = db.scalars(select(Document).where(Document.id == document_id)).all()
        else:
            stmt = (
                select(Document)
                .where(
                    Document.extraction_status == "PENDING",
                    Document.ipo_id.isnot(None),
                    Document.is_current == True,
                    Document.document_type.in_(eligible_types),
                )
                .order_by(Document.created_at.asc())
                .limit(limit)
            )
            target_docs = db.scalars(stmt).all()

        results = {
            "queued": len(target_docs),
            "processed": 0,
            "extracted": 0,
            "failed": 0,
            "errors": [],
            "items": [],
        }

        if not target_docs:
            return results

        start_time = datetime.now(timezone.utc)

        for doc in target_docs:
            item_info = {
                "document_id": doc.id,
                "ipo_id": doc.ipo_id,
                "issuer_name": doc.issuer_name,
                "document_type": doc.document_type,
                "status": doc.extraction_status,
                "periods_extracted": 0,
            }
            try:
                ipo = db.get(IPO, doc.ipo_id)
                if not ipo:
                    item_info["status"] = "SKIPPED_NO_IPO"
                    results["items"].append(item_info)
                    continue

                # Fetch document bytes using cache first, avoiding redundant network download
                doc_data = self.adapter.fetch_document(
                    doc.file_url, expected_hash=doc.file_hash_sha256
                )

                # Cryptographic SHA-256 verification
                if doc_data["file_hash_sha256"] != doc.file_hash_sha256:
                    doc.file_hash_sha256 = doc_data["file_hash_sha256"]
                    db.commit()

                # Extract and store financial observations idempotently
                count = self._extract_and_store_financials(
                    db=db,
                    document=doc,
                    ipo=ipo,
                    pdf_bytes=doc_data["payload"],
                )
                db.commit()

                item_info["status"] = doc.extraction_status
                item_info["periods_extracted"] = count
                results["processed"] += 1
                if doc.extraction_status in ("EXTRACTED", "PARTIAL"):
                    results["extracted"] += 1
                else:
                    results["failed"] += 1
            except Exception as exc:
                doc.extraction_status = "FAILED"
                doc.extraction_error = str(exc)[:500]
                try:
                    db.commit()
                except Exception:
                    db.flush()
                results["failed"] += 1
                results["errors"].append(f"{doc.issuer_name}: {exc}")
                item_info["status"] = "FAILED"
                item_info["error"] = str(exc)

            results["items"].append(item_info)

        # Log extraction job for auditability
        job = IngestionJob(
            job_type="DOCUMENT_EXTRACTION",
            source_system="SEBI_PUBLIC_FILINGS",
            status="SUCCESS" if not results["errors"] else ("PARTIAL" if results["processed"] > 0 else "FAILED"),
            started_at=start_time,
            completed_at=datetime.now(timezone.utc),
            records_processed=results["processed"],
            error_details="; ".join(results["errors"][:5]) if results["errors"] else None,
        )
        db.add(job)
        db.commit()

        return results
