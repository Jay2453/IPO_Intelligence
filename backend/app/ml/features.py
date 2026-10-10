from typing import Dict, Any, Optional


def extract_pre_listing_features(
    financials_latest: Optional[Dict[str, Any]],
    financials_prev: Optional[Dict[str, Any]],
    issue_terms: Dict[str, Any],
    subscription_final: Optional[Dict[str, Any]],
    market_sentiment: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Constructs normalized pre-listing feature vectors with full missing-value handling.
    All inputs must have occurred prior to or at issue close date.
    """
    features: Dict[str, Any] = {}

    # 1. Valuation & Size Features
    issue_size = issue_terms.get("issue_size_crores")
    fresh_issue = issue_terms.get("fresh_issue_crores")
    max_price = issue_terms.get("max_price")
    
    features["issue_size_crores"] = issue_size
    features["fresh_issue_ratio"] = (fresh_issue / issue_size) if (fresh_issue and issue_size) else None
    features["is_sme"] = 1.0 if issue_terms.get("category") == "SME" else 0.0

    # 2. Financial Quality & Growth Features
    if financials_latest:
        features["revenue_latest_crores"] = financials_latest.get("revenue_crores")
        features["pat_margin"] = (
            (financials_latest.get("pat_crores") / financials_latest.get("revenue_crores"))
            if financials_latest.get("revenue_crores") and financials_latest.get("pat_crores")
            else None
        )
        features["roe_pct"] = financials_latest.get("roe_pct")
        features["roce_pct"] = financials_latest.get("roce_pct")
        features["debt_to_equity"] = (
            (financials_latest.get("total_debt_crores") / financials_latest.get("net_worth_crores"))
            if financials_latest.get("total_debt_crores") and financials_latest.get("net_worth_crores")
            else None
        )
        
        # Growth over previous period
        if financials_prev and financials_prev.get("revenue_crores"):
            rev_growth = (
                (financials_latest.get("revenue_crores", 0) - financials_prev.get("revenue_crores", 0))
                / financials_prev.get("revenue_crores")
            )
            features["revenue_growth_yoy"] = rev_growth
        else:
            features["revenue_growth_yoy"] = None
    else:
        features["revenue_latest_crores"] = None
        features["pat_margin"] = None
        features["roe_pct"] = None
        features["roce_pct"] = None
        features["debt_to_equity"] = None
        features["revenue_growth_yoy"] = None

    # 3. Institutional & Retail Demand Features (Available post-close)
    if subscription_final:
        features["qib_oversubscription"] = subscription_final.get("qib_subscription_times")
        features["nii_oversubscription"] = subscription_final.get("nii_subscription_times")
        features["rii_oversubscription"] = subscription_final.get("rii_subscription_times")
        features["total_oversubscription"] = subscription_final.get("total_subscription_times")
    else:
        features["qib_oversubscription"] = None
        features["nii_oversubscription"] = None
        features["rii_oversubscription"] = None
        features["total_oversubscription"] = None

    # 4. Market Sentiment (Pre-listing GMP)
    if market_sentiment:
        features["gmp_percent"] = market_sentiment.get("gmp_percent")
    else:
        features["gmp_percent"] = None

    return features
