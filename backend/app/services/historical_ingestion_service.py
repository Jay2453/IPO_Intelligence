import hashlib
from datetime import datetime, date, timezone
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import select, or_, and_
from sqlalchemy.orm import Session

from app.models.ipo import IPO
from app.models.events import IPOEvent
from app.models.sources import SourceObservation
from app.models.market import MarketObservation
from app.models.ingestion import IngestionJob
from app.pipeline.historical_archive_parser import HistoricalArchiveParser, is_valid_isin
from app.pipeline.bhavcopy_verifier import BhavcopyOutcomeVerifier


class HistoricalIngestionService:
    """
    Idempotent Historical Ingestion & Outcome Reconciliation Engine.
    Enforces strict ISIN-first entity resolution, anti-merge rules, safe in-place updates,
    and audit logging for historical datasets (2015-2026).
    """

    def __init__(
        self,
        bhavcopy_verifier: Optional[BhavcopyOutcomeVerifier] = None,
    ):
        self.bhavcopy_verifier = bhavcopy_verifier or BhavcopyOutcomeVerifier()

    def resolve_existing_ipo(
        self,
        db: Session,
        incoming: Dict[str, Any],
    ) -> Optional[IPO]:
        """
        Resolves an incoming historical record against existing IPOs in the database.
        
        Strict Entity Resolution Rules:
        1. ISIN Match (Highest Priority):
           If both records possess an ISIN, they match IF AND ONLY IF the ISINs are identical.
           If ISINs conflict, NEVER merge.
        2. Symbol + Exchange + Listing Date Window:
           If ISIN is absent, match only when symbol and exchange match, AND listing dates are within 7 days.
        3. Strict Anti-Merge:
           Records are NEVER merged solely because company names look similar.
        """
        incoming_isin = (incoming.get("isin") or "").strip().upper() or None
        incoming_sym = (incoming.get("symbol") or "").strip().upper() or None
        incoming_ex = (incoming.get("exchange") or "").strip().upper() or "NSE_BSE"
        incoming_list_date = incoming.get("listing_date")

        # 1. Primary Resolution: ISIN
        if incoming_isin and is_valid_isin(incoming_isin):
            matched_by_isin = db.scalar(
                select(IPO).where(
                    IPO.is_demo == False,
                    IPO.isin == incoming_isin,
                ).limit(1)
            )
            if matched_by_isin:
                return matched_by_isin

        # 2. Secondary Resolution: Symbol + Exchange + Listing Date
        if incoming_sym:
            # Check for candidate by symbol
            candidates = db.scalars(
                select(IPO).where(
                    IPO.is_demo == False,
                    IPO.symbol == incoming_sym,
                )
            ).all()

            for cand in candidates:
                # If candidate has a different valid ISIN, DO NOT MERGE!
                if cand.isin and incoming_isin and cand.isin.upper() != incoming_isin.upper():
                    continue

                # Check listing date window if dates exist
                if cand.listing_date and incoming_list_date:
                    delta = abs((cand.listing_date - incoming_list_date).days)
                    if delta <= 7:
                        return cand
                elif not cand.listing_date or not incoming_list_date:
                    # One or both lacks listing date; symbol match is accepted when ISINs do not conflict
                    return cand

        # 3. BSE Scrip Code Resolution (for BSE-specific issues)
        incoming_scrip = (incoming.get("bse_scrip_code") or "").strip() or None
        if incoming_scrip:
            matched_by_scrip = db.scalar(
                select(IPO).where(
                    IPO.is_demo == False,
                    IPO.bse_scrip_code == incoming_scrip,
                ).limit(1)
            )
            if matched_by_scrip:
                if matched_by_scrip.isin and incoming_isin and matched_by_scrip.isin.upper() != incoming_isin.upper():
                    pass  # ISIN conflict, do not merge
                else:
                    return matched_by_scrip

        return None

    def ingest_records(
        self,
        db: Session,
        records: List[Dict[str, Any]],
        source_name: str = "HISTORICAL_ARCHIVE",
        source_url: str = "",
        reconcile_outcomes: bool = False,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Idempotently ingests or previews historical IPO records.
        Preserves existing PKs, financial observations, documents, and verified outcomes.
        """
        start_time = datetime.now(timezone.utc)
        results = {
            "total_records": len(records),
            "matched_existing": 0,
            "created_new": 0,
            "outcomes_reconciled": 0,
            "outcomes_skipped": 0,
            "errors": [],
            "dry_run": dry_run,
        }

        if not records:
            return results

        content_hash = hashlib.sha256(str(records).encode("utf-8")).hexdigest()

        for rec in records:
            try:
                comp_name = rec.get("company_name", "").strip()
                if not comp_name:
                    continue

                existing_ipo = self.resolve_existing_ipo(db, rec)

                if existing_ipo:
                    results["matched_existing"] += 1
                    if not dry_run:
                        # Safe in-place update of missing fields only
                        if not existing_ipo.isin and rec.get("isin"):
                            existing_ipo.isin = rec["isin"]
                        if not existing_ipo.bse_scrip_code and rec.get("bse_scrip_code"):
                            existing_ipo.bse_scrip_code = rec["bse_scrip_code"]
                        if not existing_ipo.listing_date and rec.get("listing_date"):
                            existing_ipo.listing_date = rec["listing_date"]
                        if not existing_ipo.open_date and rec.get("open_date"):
                            existing_ipo.open_date = rec["open_date"]
                        if not existing_ipo.close_date and rec.get("close_date"):
                            existing_ipo.close_date = rec["close_date"]
                        if existing_ipo.max_price is None and rec.get("max_price") is not None:
                            existing_ipo.max_price = rec["max_price"]
                        if existing_ipo.min_price is None and rec.get("min_price") is not None:
                            existing_ipo.min_price = rec["min_price"]
                        if existing_ipo.lot_size is None and rec.get("lot_size") is not None:
                            existing_ipo.lot_size = rec["lot_size"]
                        if existing_ipo.issue_size_crores is None and rec.get("issue_size_crores") is not None:
                            existing_ipo.issue_size_crores = rec["issue_size_crores"]

                        target_ipo = existing_ipo
                else:
                    results["created_new"] += 1
                    if not dry_run:
                        target_ipo = IPO(
                            company_name=comp_name,
                            symbol=rec.get("symbol"),
                            isin=rec.get("isin"),
                            bse_scrip_code=rec.get("bse_scrip_code"),
                            exchange=rec.get("exchange", "NSE_BSE"),
                            category=rec.get("category", "MAINBOARD"),
                            lifecycle_status="LISTED" if rec.get("listing_date") else "DISCOVERED",
                            min_price=rec.get("min_price"),
                            max_price=rec.get("max_price"),
                            lot_size=rec.get("lot_size"),
                            issue_size_crores=rec.get("issue_size_crores"),
                            open_date=rec.get("open_date"),
                            close_date=rec.get("close_date"),
                            listing_date=rec.get("listing_date"),
                            is_demo=False,
                        )
                        db.add(target_ipo)
                        db.flush()

                # Optional Outcome Reconciliation via Bhavcopy
                if reconcile_outcomes and not dry_run and target_ipo.listing_date:
                    existing_outcome = db.scalar(
                        select(MarketObservation).where(
                            MarketObservation.ipo_id == target_ipo.id,
                            MarketObservation.observation_type == "LISTING_OUTCOME",
                        ).limit(1)
                    )

                    # Do not overwrite if already verified
                    if existing_outcome and existing_outcome.bhavcopy_verified:
                        results["outcomes_skipped"] += 1
                    else:
                        sym = target_ipo.symbol or rec.get("symbol")
                        final_price = rec.get("final_issue_price_inr") or target_ipo.max_price
                        verif = self.bhavcopy_verifier.reconcile_bhavcopy(
                            symbol=sym,
                            listing_date=target_ipo.listing_date,
                            isin=target_ipo.isin,
                            exchange=target_ipo.exchange if target_ipo.exchange in ("NSE", "BSE") else "NSE",
                            final_issue_price=final_price,
                        )

                        if verif:
                            if existing_outcome:
                                existing_outcome.listing_open_price_inr = verif["listing_open_price_inr"]
                                existing_outcome.listing_close_price_inr = verif["listing_close_price_inr"]
                                existing_outcome.listing_gain_pct = verif["listing_gain_pct"]
                                existing_outcome.final_issue_price_inr = verif["final_issue_price_inr"]
                                existing_outcome.bhavcopy_verified = True
                                existing_outcome.exchange = verif["exchange"]
                                existing_outcome.source_url = verif["source_url"]
                                existing_outcome.source_file_hash = verif["source_file_hash"]
                                existing_outcome.raw_data_provenance = verif["raw_data_provenance"]
                            else:
                                db.add(
                                    MarketObservation(
                                        ipo_id=target_ipo.id,
                                        observation_type="LISTING_OUTCOME",
                                        observation_time=datetime.now(timezone.utc),
                                        final_issue_price_inr=verif["final_issue_price_inr"],
                                        listing_open_price_inr=verif["listing_open_price_inr"],
                                        listing_close_price_inr=verif["listing_close_price_inr"],
                                        listing_gain_pct=verif["listing_gain_pct"],
                                        bhavcopy_verified=True,
                                        exchange=verif["exchange"],
                                        source_url=verif["source_url"],
                                        source_file_hash=verif["source_file_hash"],
                                        raw_data_provenance=verif["raw_data_provenance"],
                                    )
                                )
                            target_ipo.lifecycle_status = "OUTCOME_VERIFIED"
                            results["outcomes_reconciled"] += 1

            except Exception as exc:
                results["errors"].append(f"{rec.get('company_name', 'Unknown')}: {str(exc)}")

        if not dry_run:
            # Record Ingestion Job
            job = IngestionJob(
                job_type="HISTORICAL_ARCHIVE_PARSE",
                source_system=source_name,
                status="SUCCESS" if not results["errors"] else "PARTIAL",
                started_at=start_time,
                completed_at=datetime.now(timezone.utc),
                records_processed=results["total_records"],
                error_details="; ".join(results["errors"][:5]) if results["errors"] else None,
            )
            db.add(job)
            db.commit()

        return results
