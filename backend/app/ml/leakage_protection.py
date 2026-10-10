from datetime import datetime
from typing import Dict, Any, List


class TemporalLeakageError(ValueError):
    """Raised when an attempt is made to use information dated after the prediction cutoff."""
    pass


# Strict blacklist of post-listing and post-allotment fields that must NEVER appear in pre-listing inference
PROHIBITED_PRE_LISTING_FIELDS = {
    "listing_open_price_inr",
    "listing_close_price_inr",
    "listing_gain_pct",
    "bhavcopy_verified",
    "actual_return",
    "post_listing_volume",
    "day1_high",
    "day1_low",
}


def assert_no_temporal_leakage(
    feature_vector: Dict[str, Any],
    observation_timestamp: datetime,
    cutoff_timestamp: datetime,
) -> None:
    """
    Enforces the temporal barrier:
    1. Rejects any observation dated after the prediction cutoff timestamp.
    2. Rejects any feature vector containing post-listing outcome columns.
    """
    if observation_timestamp > cutoff_timestamp:
        raise TemporalLeakageError(
            f"Temporal leakage detected! Observation timestamp ({observation_timestamp.isoformat()}) "
            f"is after the prediction cutoff ({cutoff_timestamp.isoformat()}). "
            f"Pre-listing models must only observe information available at or before cutoff."
        )

    for field in PROHIBITED_PRE_LISTING_FIELDS:
        if field in feature_vector and feature_vector[field] is not None:
            raise TemporalLeakageError(
                f"Data leakage detected! Post-listing outcome field '{field}' was found in pre-listing feature vector."
            )
