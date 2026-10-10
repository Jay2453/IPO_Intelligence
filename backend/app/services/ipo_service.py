from typing import Optional, List, Tuple
from sqlalchemy import select, func, or_, desc, asc
from sqlalchemy.orm import Session, selectinload
from app.models.ipo import IPO
from app.models.events import IPOEvent
from app.models.documents import Document
from app.models.predictions import Prediction
from app.models.market import MarketObservation
from app.models.subscriptions import SubscriptionSnapshot
from app.schemas.ipo import IPOSummaryResponse, IPODetailResponse


def get_ipos_query(
    db: Session,
    exchange: Optional[str] = None,
    category: Optional[str] = None,
    lifecycle_status: Optional[str] = None,
    analysis_status: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[IPOSummaryResponse], int]:
    stmt = select(IPO)

    # Filtering
    if exchange and exchange != "ALL":
        stmt = stmt.where(IPO.exchange == exchange)
    if category and category != "ALL":
        stmt = stmt.where(IPO.category == category)
    if lifecycle_status and lifecycle_status != "ALL":
        stmt = stmt.where(IPO.lifecycle_status == lifecycle_status)
    if analysis_status and analysis_status != "ALL":
        stmt = stmt.where(IPO.analysis_status == analysis_status)
    if search:
        search_pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                IPO.company_name.ilike(search_pattern),
                IPO.symbol.ilike(search_pattern),
            )
        )

    # Total count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0

    # Sorting
    sort_column = getattr(IPO, sort_by, IPO.created_at)
    if sort_order.lower() == "asc":
        stmt = stmt.order_by(asc(sort_column))
    else:
        stmt = stmt.order_by(desc(sort_column))

    # Pagination
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    # Eager load related observations for summary view
    stmt = stmt.options(
        selectinload(IPO.market_observations),
        selectinload(IPO.subscriptions),
        selectinload(IPO.predictions),
    )

    records = db.scalars(stmt).all()

    summary_items = []
    for ipo in records:
        # Extract latest GMP
        latest_gmp_inr = None
        latest_gmp_percent = None
        for mo in ipo.market_observations:
            if mo.observation_type == "GMP_OBSERVATION" and mo.gmp_inr is not None:
                latest_gmp_inr = mo.gmp_inr
                latest_gmp_percent = mo.gmp_percent
                break

        # Extract latest subscription
        latest_sub = ipo.subscriptions[0].total_subscription_times if ipo.subscriptions else None

        # Extract latest active prediction
        latest_prob = None
        latest_risk = None
        for pred in ipo.predictions:
            if pred.prediction_status == "ACTIVE":
                latest_prob = pred.positive_return_prob
                latest_risk = pred.risk_decile
                break

        summary_item = IPOSummaryResponse(
            id=ipo.id,
            symbol=ipo.symbol,
            company_name=ipo.company_name,
            exchange=ipo.exchange,
            category=ipo.category,
            lifecycle_status=ipo.lifecycle_status,
            min_price=ipo.min_price,
            max_price=ipo.max_price,
            lot_size=ipo.lot_size,
            issue_size_crores=ipo.issue_size_crores,
            fresh_issue_crores=ipo.fresh_issue_crores,
            ofs_crores=ipo.ofs_crores,
            open_date=ipo.open_date,
            close_date=ipo.close_date,
            allotment_date=ipo.allotment_date,
            refund_date=ipo.refund_date,
            credit_date=ipo.credit_date,
            listing_date=ipo.listing_date,
            face_value=ipo.face_value,
            lead_managers=ipo.lead_managers,
            registrar=ipo.registrar,
            data_completeness_pct=ipo.data_completeness_pct,
            analysis_status=ipo.analysis_status,
            is_demo=ipo.is_demo,
            created_at=ipo.created_at,
            updated_at=ipo.updated_at,
            latest_gmp_inr=latest_gmp_inr,
            latest_gmp_percent=latest_gmp_percent,
            total_subscription_times=latest_sub,
            positive_return_prob=latest_prob,
            risk_decile=latest_risk,
        )
        summary_items.append(summary_item)

    return summary_items, total


def get_ipo_by_id(db: Session, ipo_id: str) -> Optional[IPO]:
    stmt = (
        select(IPO)
        .where(IPO.id == ipo_id)
        .options(
            selectinload(IPO.events),
            selectinload(IPO.documents),
            selectinload(IPO.financials),
            selectinload(IPO.subscriptions),
            selectinload(IPO.market_observations),
            selectinload(IPO.predictions).selectinload(Prediction.model_version),
            selectinload(IPO.sources),
        )
    )
    return db.scalar(stmt)
