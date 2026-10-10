from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy import select, or_, desc
from sqlalchemy.orm import Session
from app.models.ipo import IPO
from app.models.events import IPOEvent
from app.models.sources import SourceObservation
from app.models.ingestion import IngestionJob
from app.pipeline.nse_adapter import NseIpoSourceAdapter, NseConnectionError, NseParseError


class IngestionService:
    def __init__(self, adapter: Optional[NseIpoSourceAdapter] = None):
        self.adapter = adapter or NseIpoSourceAdapter()

    def sync_nse_ipos(self, db: Session, include_recent_past: bool = True, past_limit: int = 30) -> Dict[str, Any]:
        """
        Executes a synchronization run against official NSE IPO endpoints.
        Maintains transactional integrity, logs IngestionJob, creates SourceObservation
        provenance records, and deduplicates real records.
        """
        job = IngestionJob(
            job_type="DISCOVERY_POLL",
            source_system="NSE_FEED",
            status="RUNNING",
            started_at=datetime.now(timezone.utc),
            records_processed=0,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        inserted_count = 0
        updated_count = 0
        skipped_count = 0
        errors: List[str] = []

        try:
            with db.begin_nested():
                # 1. Fetch from NSE upcoming issues
                upcoming_items, upcoming_url, upcoming_hash = self.adapter.fetch_raw_upcoming_issues()
                
                # 2. Fetch from NSE current active issues
                current_items, current_url, current_hash = self.adapter.fetch_raw_current_issues()
                
                # 3. Optionally fetch recent past/closed issues
                past_items, past_url, past_hash = [], "", ""
                if include_recent_past:
                    past_items, past_url, past_hash = self.adapter.fetch_raw_past_issues(limit=past_limit)

                all_tasks = [
                    (upcoming_items, upcoming_url, upcoming_hash, False),
                    (current_items, current_url, current_hash, False),
                    (past_items, past_url, past_hash, True),
                ]

                now = datetime.now(timezone.utc)

                for raw_list, source_url, content_hash, is_past in all_tasks:
                    for raw_rec in raw_list:
                        try:
                            norm = self.adapter.normalize_record(raw_rec, is_past=is_past)
                            if not norm:
                                skipped_count += 1
                                continue

                            company_name = norm["company_name"]
                            symbol = norm.get("symbol")

                            # Deduplication Rule:
                            # Find existing real record (is_demo == False) by matching symbol or company_name
                            match_conditions = [IPO.is_demo == False]
                            if symbol:
                                match_conditions.append(
                                    or_(
                                        IPO.symbol == symbol,
                                        IPO.company_name.ilike(company_name),
                                    )
                                )
                            else:
                                match_conditions.append(IPO.company_name.ilike(company_name))

                            existing_ipo = db.scalar(
                                select(IPO).where(*match_conditions).limit(1)
                            )

                            if existing_ipo:
                                # Check if status transitioned or dates updated
                                changed = False
                                old_status = existing_ipo.lifecycle_status
                                new_status = norm["lifecycle_status"]

                                if old_status != new_status and old_status != "OUTCOME_VERIFIED":
                                    existing_ipo.lifecycle_status = new_status
                                    changed = True
                                    db.add(
                                        IPOEvent(
                                            ipo_id=existing_ipo.id,
                                            event_type="STATUS_CHANGED",
                                            from_status=old_status,
                                            to_status=new_status,
                                            headline=f"Lifecycle State Updated to {new_status}",
                                            description=f"Status updated based on official NSE feed observation.",
                                            event_timestamp=now,
                                        )
                                    )

                                # Update pricing or dates if discovered
                                if norm["min_price"] and existing_ipo.min_price != norm["min_price"]:
                                    existing_ipo.min_price = norm["min_price"]
                                    changed = True
                                if norm["max_price"] and existing_ipo.max_price != norm["max_price"]:
                                    existing_ipo.max_price = norm["max_price"]
                                    changed = True
                                if norm["open_date"] and existing_ipo.open_date != norm["open_date"]:
                                    existing_ipo.open_date = norm["open_date"]
                                    changed = True
                                if norm["close_date"] and existing_ipo.close_date != norm["close_date"]:
                                    existing_ipo.close_date = norm["close_date"]
                                    changed = True
                                if norm["listing_date"] and existing_ipo.listing_date != norm["listing_date"]:
                                    existing_ipo.listing_date = norm["listing_date"]
                                    changed = True

                                existing_ipo.data_completeness_pct = norm["data_completeness_pct"]
                                existing_ipo.updated_at = now

                                # Preserve source observation
                                db.add(
                                    SourceObservation(
                                        ipo_id=existing_ipo.id,
                                        source_name="NSE_FEED",
                                        canonical_url=source_url,
                                        content_hash_sha256=content_hash,
                                        retrieval_timestamp=now,
                                        validation_status="VALID",
                                        raw_metadata=raw_rec,
                                    )
                                )
                                updated_count += 1
                            else:
                                # Insert new real record
                                new_ipo = IPO(**norm)
                                db.add(new_ipo)
                                db.flush()  # Flush to generate new_ipo.id

                                # Create discovery milestone event
                                db.add(
                                    IPOEvent(
                                        ipo_id=new_ipo.id,
                                        event_type="DISCOVERED",
                                        headline="Discovered on NSE Official Portal",
                                        description=f"Captured from NSE public circular feed ({source_url})",
                                        event_timestamp=now,
                                    )
                                )

                                # Create source provenance record
                                db.add(
                                    SourceObservation(
                                        ipo_id=new_ipo.id,
                                        source_name="NSE_FEED",
                                        canonical_url=source_url,
                                        content_hash_sha256=content_hash,
                                        retrieval_timestamp=now,
                                        validation_status="VALID",
                                        raw_metadata=raw_rec,
                                    )
                                )
                                inserted_count += 1

                        except Exception as item_err:
                            errors.append(f"Failed to process record '{raw_rec}': {str(item_err)}")

            total_processed = inserted_count + updated_count
            job.status = "SUCCESS" if not errors else ("PARTIAL" if total_processed > 0 else "FAILED")
            job.records_processed = total_processed
            job.completed_at = datetime.now(timezone.utc)
            if errors:
                job.error_details = "\n".join(errors[:10])
            db.commit()

            return {
                "status": job.status,
                "job_id": job.id,
                "records_inserted": inserted_count,
                "records_updated": updated_count,
                "records_skipped": skipped_count,
                "total_processed": total_processed,
                "errors": errors,
            }

        except Exception as e:
            job.status = "FAILED"
            job.error_details = str(e)
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            raise e
