from datetime import datetime, timezone
from sqlalchemy import text, select, func, desc
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.ipo import IPO
from app.models.ingestion import IngestionJob
from app.schemas.system import HealthCheckResponse, SystemStatusResponse, IntegrationStatus


def check_db_health(db: Session) -> bool:
    """Verifies actual relational database connectivity."""
    try:
        db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def get_health_status(db: Session) -> HealthCheckResponse:
    is_healthy = check_db_health(db)
    return HealthCheckResponse(
        status="healthy" if is_healthy else "unhealthy",
        database="connected" if is_healthy else "disconnected",
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(timezone.utc),
        version="1.0.0",
    )


def get_system_status(db: Session) -> SystemStatusResponse:
    db_connected = check_db_health(db)
    
    total_ipos = 0
    real_ipos = 0
    demo_ipos = 0
    last_sync = None
    last_sync_status = None
    recent_errors = []

    if db_connected:
        try:
            total_ipos = db.scalar(select(func.count(IPO.id))) or 0
            real_ipos = db.scalar(select(func.count(IPO.id)).where(IPO.is_demo == False)) or 0
            demo_ipos = db.scalar(select(func.count(IPO.id)).where(IPO.is_demo == True)) or 0
            
            # Clean up stranded RUNNING jobs older than 15 minutes
            now_utc = datetime.now(timezone.utc)
            stranded_jobs = db.scalars(
                select(IngestionJob).where(IngestionJob.status == "RUNNING")
            ).all()
            for s_job in stranded_jobs:
                s_started = s_job.started_at
                if s_started.tzinfo is None:
                    s_started = s_started.replace(tzinfo=timezone.utc)
                if (now_utc - s_started).total_seconds() > 900:
                    s_job.status = "FAILED"
                    s_job.error_details = "Process interrupted or timed out while running."
                    s_job.completed_at = now_utc
            if stranded_jobs:
                db.commit()

            # Query last ingestion job
            last_job = db.scalar(
                select(IngestionJob)
                .order_by(desc(IngestionJob.started_at))
                .limit(1)
            )
            if last_job:
                last_sync = last_job.completed_at or last_job.started_at
                last_sync_status = last_job.status
                if last_job.status == "FAILED" and last_job.error_details:
                    recent_errors.append(f"[{last_job.source_system}] {last_job.error_details}")
                elif last_job.status == "PARTIAL" and last_job.error_details:
                    recent_errors.append(f"[{last_job.source_system} Notice] {last_job.error_details}")
        except Exception as e:
            recent_errors.append(f"Failed to query system stats: {str(e)}")

    # Query NSE-specific job history
    nse_status = "NOT_CONFIGURED"
    nse_verified = False
    nse_last_check = None
    nse_last_success = None
    nse_errors_24h = 0
    nse_message = "National Stock Exchange public portal adapter ready; manual or scheduled synchronization pending."

    if db_connected:
        try:
            last_nse_job = db.scalar(
                select(IngestionJob)
                .where(IngestionJob.source_system == "NSE_FEED")
                .order_by(desc(IngestionJob.started_at))
                .limit(1)
            )
            last_nse_success = db.scalar(
                select(IngestionJob)
                .where(IngestionJob.source_system == "NSE_FEED", IngestionJob.status.in_(["SUCCESS", "PARTIAL"]))
                .order_by(desc(IngestionJob.started_at))
                .limit(1)
            )

            if last_nse_success:
                nse_last_success = last_nse_success.completed_at or last_nse_success.started_at

            if last_nse_job:
                nse_last_check = last_nse_job.completed_at or last_nse_job.started_at
                if last_nse_job.status == "SUCCESS":
                    nse_status = "CONNECTED"
                    nse_verified = True
                    nse_message = f"Verified official NSE connection. {real_ipos} live public IPO records synchronized."
                elif last_nse_job.status == "PARTIAL":
                    nse_status = "DEGRADED"
                    nse_verified = True
                    nse_message = f"Partial synchronization completed ({real_ipos} live records). Notices: {last_nse_job.error_details or 'None'}"
                elif last_nse_job.status == "FAILED":
                    nse_status = "FAILED"
                    nse_verified = False
                    nse_message = f"Last synchronization failed: {last_nse_job.error_details or 'Network error'}"
        except Exception:
            pass

    # Query SEBI-specific job history
    sebi_status = "NOT_CONFIGURED"
    sebi_verified = False
    sebi_last_check = None
    sebi_last_success = None
    sebi_message = "SEBI Public Issues portal adapter ready. Trigger POST /api/v1/sebi/sync to begin document discovery."

    if db_connected:
        try:
            from app.models.documents import Document
            sebi_doc_count = db.scalar(select(func.count(Document.id))) or 0
            sebi_extracted_count = db.scalar(
                select(func.count(Document.id)).where(Document.extraction_status.in_(["EXTRACTED", "PARTIAL"]))
            ) or 0

            last_sebi_job = db.scalar(
                select(IngestionJob)
                .where(IngestionJob.source_system == "SEBI_PUBLIC_FILINGS")
                .order_by(desc(IngestionJob.started_at))
                .limit(1)
            )
            last_sebi_success = db.scalar(
                select(IngestionJob)
                .where(IngestionJob.source_system == "SEBI_PUBLIC_FILINGS", IngestionJob.status.in_(["SUCCESS", "PARTIAL"]))
                .order_by(desc(IngestionJob.started_at))
                .limit(1)
            )

            if last_sebi_success:
                sebi_last_success = last_sebi_success.completed_at or last_sebi_success.started_at

            if last_sebi_job:
                sebi_last_check = last_sebi_job.completed_at or last_sebi_job.started_at
                if last_sebi_job.status == "SUCCESS":
                    sebi_status = "CONNECTED"
                    sebi_verified = True
                    sebi_message = f"{sebi_doc_count} documents stored; {sebi_extracted_count} financials extracted from DRHP/RHP/Abridged filings."
                elif last_sebi_job.status == "PARTIAL":
                    sebi_status = "DEGRADED"
                    sebi_verified = True
                    notices = f" Notices: {last_sebi_job.error_details}" if last_sebi_job.error_details else ""
                    sebi_message = f"Partial sync completed ({sebi_doc_count} documents, {sebi_extracted_count} extracted).{notices}"
                elif last_sebi_job.status == "FAILED":
                    sebi_status = "FAILED"
                    sebi_message = f"Last SEBI sync failed: {last_sebi_job.error_details or 'Network error'}"
            elif sebi_doc_count > 0:
                sebi_status = "CONNECTED"
                sebi_verified = True
                sebi_message = f"{sebi_doc_count} documents available; {sebi_extracted_count} financials extracted."
        except Exception:
            pass

    # Integrations status - honestly reported, NEVER claiming connected when not configured
    integrations = [
        IntegrationStatus(
            name="Relational Database (PostgreSQL / SQLite)",
            status="CONNECTED" if db_connected else "FAILED",
            verified=db_connected,
            last_check_timestamp=datetime.now(timezone.utc),
            last_successful_sync=datetime.now(timezone.utc) if db_connected else None,
            error_count_last_24h=0 if db_connected else 1,
            message="Database ping SELECT 1 succeeded" if db_connected else "Cannot connect to database",
        ),
        IntegrationStatus(
            name="NSE Official IPO Information Portal",
            status=nse_status,
            verified=nse_verified,
            last_check_timestamp=nse_last_check,
            last_successful_sync=nse_last_success,
            error_count_last_24h=nse_errors_24h,
            message=nse_message,
        ),
        IntegrationStatus(
            name="SEBI Public DRHP/RHP Filings Feed",
            status=sebi_status,
            verified=sebi_verified,
            last_check_timestamp=sebi_last_check,
            last_successful_sync=sebi_last_success,
            error_count_last_24h=0,
            message=sebi_message,
        ),
        IntegrationStatus(
            name="BSE Corporate Notices Feed",
            status="NOT_CONFIGURED",
            verified=False,
            last_check_timestamp=None,
            last_successful_sync=None,
            error_count_last_24h=0,
            message="Bombay Stock Exchange announcement feed unconfigured.",
        ),
    ]

    return SystemStatusResponse(
        database_connected=db_connected,
        total_ipos_tracked=total_ipos,
        real_ipos_count=real_ipos,
        demo_ipos_count=demo_ipos,
        last_successful_sync=last_sync,
        last_sync_status=last_sync_status,
        recent_errors=recent_errors,
        integrations=integrations,
        timestamp=datetime.now(timezone.utc),
    )
