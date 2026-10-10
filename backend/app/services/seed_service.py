import hashlib
from datetime import date, datetime, timezone, timedelta
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from app.models.ipo import IPO
from app.models.events import IPOEvent
from app.models.sources import SourceObservation
from app.models.documents import Document
from app.models.financials import FinancialObservation
from app.models.subscriptions import SubscriptionSnapshot
from app.models.market import MarketObservation
from app.models.ml_model import ModelVersion
from app.models.predictions import Prediction
from app.models.ingestion import IngestionJob


def sha256_str(val: str) -> str:
    return hashlib.sha256(val.encode("utf-8")).hexdigest()


def seed_demo_dataset(db: Session, force: bool = False) -> dict:
    """
    Safely seeds realistic demonstration IPO records into the database.
    Every record is unequivocally tagged with `is_demo=True`.
    """
    existing_count = db.scalar(select(IPO).where(IPO.is_demo == True))
    if existing_count and not force:
        return {"status": "skipped", "message": "Demo data already populated. Pass force=True to reset."}

    # Clean existing demo records if force
    if force:
        demo_ipos = db.scalars(select(IPO).where(IPO.is_demo == True)).all()
        for ipo in demo_ipos:
            db.delete(ipo)
        db.commit()

    now = datetime.now(timezone.utc)
    today = now.date()

    # 1. Seed Model Versions
    baseline_model = ModelVersion(
        model_name="BASELINE_LOGISTIC_REGRESSOR",
        version_tag="v0.1.0-alpha",
        algorithm="LogisticRegression(C=1.0, L2)",
        training_cutoff_date=today - timedelta(days=90),
        validation_metrics={"brier_score": 0.182, "roc_auc": 0.735, "ece": 0.041},
        feature_manifest=["revenue_cagr_3y", "pat_margin", "roe_pct", "qib_oversubscription", "market_regime"],
        is_active=True,
    )
    catboost_model = ModelVersion(
        model_name="CATBOOST_LISTING_V1",
        version_tag="v1.0.0-beta",
        algorithm="CatBoostClassifier(depth=5, l2_leaf_reg=3)",
        training_cutoff_date=today - timedelta(days=60),
        validation_metrics={"brier_score": 0.144, "roc_auc": 0.812, "ece": 0.027},
        feature_manifest=["qib_sub", "nii_sub", "pe_ratio_issue", "roe_pct", "fresh_issue_ratio", "market_volatility"],
        is_active=True,
    )
    db.add(baseline_model)
    db.add(catboost_model)
    db.flush()

    # 2. Record 1: Premier Clean Energy Technologies Ltd (Mainboard, SUBSCRIPTION_OPEN)
    ipo1 = IPO(
        symbol="PREMIERCL",
        company_name="Premier Clean Energy Technologies Ltd",
        exchange="NSE_BSE",
        category="MAINBOARD",
        lifecycle_status="SUBSCRIPTION_OPEN",
        min_price=475.0,
        max_price=500.0,
        lot_size=30,
        issue_size_crores=1250.0,
        fresh_issue_crores=750.0,
        ofs_crores=500.0,
        open_date=today - timedelta(days=1),
        close_date=today + timedelta(days=1),
        allotment_date=today + timedelta(days=3),
        refund_date=today + timedelta(days=4),
        credit_date=today + timedelta(days=4),
        listing_date=today + timedelta(days=5),
        face_value=10.0,
        lead_managers="Kotak Mahindra Capital, ICICI Securities, Axis Capital",
        registrar="KFin Technologies Ltd",
        data_completeness_pct=92,
        analysis_status="COMPLETED",
        is_demo=True,
    )
    db.add(ipo1)
    db.flush()

    # Events for ipo1
    db.add(IPOEvent(
        ipo_id=ipo1.id,
        event_type="SUBSCRIPTION_STARTED",
        from_status="PRICE_BAND_AVAILABLE",
        to_status="SUBSCRIPTION_OPEN",
        headline="Public Bidding Commenced",
        description="Issue open for institutional and retail bidding at price band INR 475 - 500.",
        event_timestamp=now - timedelta(days=1),
    ))
    db.add(IPOEvent(
        ipo_id=ipo1.id,
        event_type="RHP_FILED",
        from_status="PRELIMINARY_ANALYSIS",
        to_status="PRICE_BAND_AVAILABLE",
        headline="Red Herring Prospectus Filed with ROC",
        description="Price band discovered at INR 475 to 500 per equity share. Total issue size INR 1,250 Crores.",
        event_timestamp=now - timedelta(days=5),
    ))

    # Documents for ipo1
    doc_rhp1 = Document(
        ipo_id=ipo1.id,
        document_type="RHP",
        version_number=1,
        file_name="Premier_Clean_Energy_RHP.pdf",
        file_url="https://www.sebi.gov.in/filings/approved/premier_rhp.pdf",
        file_hash_sha256=sha256_str("premier_clean_energy_rhp_content_mock"),
        file_size_bytes=14258900,
        filing_date=today - timedelta(days=5),
        is_current=True,
    )
    db.add(doc_rhp1)
    db.flush()

    # Financials for ipo1
    db.add(FinancialObservation(
        ipo_id=ipo1.id,
        fiscal_year="FY24",
        period_months=12,
        revenue_crores=842.50,
        ebitda_crores=185.30,
        pat_crores=112.40,
        total_assets_crores=1450.00,
        net_worth_crores=620.00,
        total_debt_crores=210.00,
        roe_pct=18.13,
        roce_pct=21.45,
        eps_inr=16.80,
        nav_per_share_inr=92.50,
        source_document_id=doc_rhp1.id,
    ))
    db.add(FinancialObservation(
        ipo_id=ipo1.id,
        fiscal_year="FY23",
        period_months=12,
        revenue_crores=610.20,
        ebitda_crores=128.00,
        pat_crores=74.60,
        total_assets_crores=1120.00,
        net_worth_crores=450.00,
        total_debt_crores=235.00,
        roe_pct=16.58,
        roce_pct=18.90,
        eps_inr=11.20,
        nav_per_share_inr=75.10,
        source_document_id=doc_rhp1.id,
    ))

    # Subscriptions for ipo1
    db.add(SubscriptionSnapshot(
        ipo_id=ipo1.id,
        snapshot_time=now - timedelta(hours=2),
        qib_subscription_times=4.82,
        nii_subscription_times=8.15,
        rii_subscription_times=3.40,
        employee_subscription_times=1.10,
        total_subscription_times=5.65,
        total_shares_bid=141250000,
    ))

    # Market sentiment (GMP) for ipo1
    db.add(MarketObservation(
        ipo_id=ipo1.id,
        observation_type="GMP_OBSERVATION",
        observation_time=now - timedelta(hours=3),
        gmp_inr=125.0,
        gmp_percent=25.0,
        bhavcopy_verified=False,
    ))

    # Prediction for ipo1
    db.add(Prediction(
        ipo_id=ipo1.id,
        model_version_id=catboost_model.id,
        prediction_timestamp=now - timedelta(hours=4),
        forecast_horizon="LISTING_DAY_CLOSE",
        positive_return_prob=0.8420,
        predicted_return_pct=22.50,
        risk_decile=3,
        feature_snapshot={"qib_sub": 4.82, "nii_sub": 8.15, "pe_ratio_issue": 29.76, "roe_pct": 18.13},
        evidence_summary={"top_positive_factors": ["High institutional bid velocity", "Healthy ROE (>18%)", "Clean promoter track record"], "top_negative_factors": ["P/E valuation at top quartile of peer group"]},
        prediction_status="ACTIVE",
    ))

    # 3. Record 2: Precision Aerospace Components Ltd (SME, PRICE_BAND_AVAILABLE)
    ipo2 = IPO(
        symbol="PRECAERO",
        company_name="Precision Aerospace Components Ltd",
        exchange="NSE",
        category="SME",
        lifecycle_status="PRICE_BAND_AVAILABLE",
        min_price=118.0,
        max_price=125.0,
        lot_size=1000,
        issue_size_crores=48.50,
        fresh_issue_crores=48.50,
        ofs_crores=0.0,
        open_date=today + timedelta(days=3),
        close_date=today + timedelta(days=5),
        allotment_date=today + timedelta(days=6),
        listing_date=today + timedelta(days=9),
        face_value=10.0,
        lead_managers="Hem Securities Ltd",
        registrar="Bigshare Services Pvt Ltd",
        data_completeness_pct=84,
        analysis_status="COMPLETED",
        is_demo=True,
    )
    db.add(ipo2)
    db.flush()

    db.add(IPOEvent(
        ipo_id=ipo2.id,
        event_type="PRICE_BAND_DISCOVERED",
        from_status="PRELIMINARY_ANALYSIS",
        to_status="PRICE_BAND_AVAILABLE",
        headline="Price Band Fixed for SME Issue",
        description="Issue to open on NSE Emerge platform at INR 118-125 with lot size 1,000 shares.",
        event_timestamp=now - timedelta(days=2),
    ))

    db.add(MarketObservation(
        ipo_id=ipo2.id,
        observation_type="GMP_OBSERVATION",
        observation_time=now - timedelta(hours=5),
        gmp_inr=35.0,
        gmp_percent=28.0,
        bhavcopy_verified=False,
    ))

    db.add(Prediction(
        ipo_id=ipo2.id,
        model_version_id=baseline_model.id,
        prediction_timestamp=now - timedelta(days=1),
        forecast_horizon="LISTING_DAY_CLOSE",
        positive_return_prob=0.7610,
        predicted_return_pct=26.00,
        risk_decile=5,
        feature_snapshot={"revenue_cagr_3y": 32.4, "pat_margin": 14.2, "roe_pct": 22.8},
        evidence_summary={"top_positive_factors": ["High order book visibility", "100% fresh issue proceeds deployed in capex"], "top_negative_factors": ["SME liquidity concentration risk", "Customer concentration in top 3 clients"]},
        prediction_status="ACTIVE",
    ))

    # 4. Record 3: Bharat Fintech Infrastructure Ltd (Mainboard, PRELIMINARY_ANALYSIS)
    ipo3 = IPO(
        symbol=None,  # No ticker assigned yet
        company_name="Bharat Fintech Infrastructure Ltd",
        exchange="NSE_BSE",
        category="MAINBOARD",
        lifecycle_status="PRELIMINARY_ANALYSIS",
        min_price=None,  # Not yet discovered
        max_price=None,
        lot_size=None,
        issue_size_crores=2400.0,
        fresh_issue_crores=1600.0,
        ofs_crores=800.0,
        open_date=None,
        close_date=None,
        face_value=2.0,
        lead_managers="Morgan Stanley India, BofA Securities, SBI Capital Markets",
        registrar="Link Intime India Pvt Ltd",
        data_completeness_pct=58,
        analysis_status="IN_PROGRESS",
        is_demo=True,
    )
    db.add(ipo3)
    db.flush()

    db.add(IPOEvent(
        ipo_id=ipo3.id,
        event_type="DRHP_FILED",
        from_status="DOCUMENTS_PENDING",
        to_status="PRELIMINARY_ANALYSIS",
        headline="Draft Red Herring Prospectus (DRHP) Filed with SEBI",
        description="Issuer filed preliminary draft document for INR 2,400 Crore public offering.",
        event_timestamp=now - timedelta(days=14),
    ))

    # 5. Record 4: Surya Logistics Global Ltd (Mainboard, OUTCOME_VERIFIED)
    ipo4 = IPO(
        symbol="SURYALOG",
        company_name="Surya Logistics Global Ltd",
        exchange="NSE_BSE",
        category="MAINBOARD",
        lifecycle_status="OUTCOME_VERIFIED",
        min_price=315.0,
        max_price=332.0,
        lot_size=45,
        issue_size_crores=860.0,
        fresh_issue_crores=500.0,
        ofs_crores=360.0,
        open_date=today - timedelta(days=20),
        close_date=today - timedelta(days=18),
        allotment_date=today - timedelta(days=16),
        listing_date=today - timedelta(days=14),
        face_value=5.0,
        lead_managers="JM Financial, Edelweiss Financial Services",
        registrar="KFin Technologies Ltd",
        data_completeness_pct=100,
        analysis_status="COMPLETED",
        is_demo=True,
    )
    db.add(ipo4)
    db.flush()

    # Listing outcome verified with official Bhavcopy
    db.add(MarketObservation(
        ipo_id=ipo4.id,
        observation_type="LISTING_OUTCOME",
        observation_time=now - timedelta(days=14),
        final_issue_price_inr=332.0,
        listing_open_price_inr=415.0,
        listing_close_price_inr=428.5,
        listing_gain_pct=29.07,
        bhavcopy_verified=True,
    ))

    # 6. Record 5: Zenith Retail Networks Ltd (Mainboard, WITHDRAWN)
    ipo5 = IPO(
        symbol=None,
        company_name="Zenith Retail Networks Ltd",
        exchange="NSE_BSE",
        category="MAINBOARD",
        lifecycle_status="WITHDRAWN",
        min_price=None,
        max_price=None,
        issue_size_crores=650.0,
        data_completeness_pct=30,
        analysis_status="FAILED",
        is_demo=True,
    )
    db.add(ipo5)
    db.flush()

    db.add(IPOEvent(
        ipo_id=ipo5.id,
        event_type="ISSUE_WITHDRAWN",
        from_status="DOCUMENTS_PENDING",
        to_status="WITHDRAWN",
        headline="DRHP Withdrawn by Merchant Bankers",
        description="Filing formally withdrawn from SEBI due to market conditions and revised promoter funding plan.",
        event_timestamp=now - timedelta(days=10),
    ))

    # 7. Record 6: Nova BioHealth Innovations Ltd (Mainboard, DOCUMENTS_PENDING)
    ipo6 = IPO(
        symbol=None,
        company_name="Nova BioHealth Innovations Ltd",
        exchange="BSE",
        category="MAINBOARD",
        lifecycle_status="DOCUMENTS_PENDING",
        issue_size_crores=450.0,
        data_completeness_pct=22,
        analysis_status="PENDING",
        is_demo=True,
    )
    db.add(ipo6)
    db.flush()

    # 8. Seed Ingestion Jobs
    db.add(IngestionJob(
        job_type="DISCOVERY_POLL",
        source_system="SEBI_PORTAL",
        status="SUCCESS",
        started_at=now - timedelta(hours=1),
        completed_at=now - timedelta(minutes=58),
        records_processed=6,
        error_details=None,
    ))
    db.add(IngestionJob(
        job_type="DOCUMENT_SYNC",
        source_system="NSE_FEED",
        status="PARTIAL",
        started_at=now - timedelta(hours=3),
        completed_at=now - timedelta(hours=2, minutes=55),
        records_processed=2,
        error_details="Circular attachment download timeout on 1 document; retrying on next scheduled poll.",
    ))

    db.commit()

    return {
        "status": "success",
        "message": "Demo IPO dataset successfully seeded with 6 diverse IPO lifecycle records.",
        "records_created": 6,
    }
