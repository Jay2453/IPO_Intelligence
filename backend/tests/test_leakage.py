from datetime import datetime, timezone, timedelta
import pytest
from app.ml.leakage_protection import assert_no_temporal_leakage, TemporalLeakageError
from app.pipeline.validation import ProvenanceValidator


def test_leakage_protection_future_timestamp():
    cutoff = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
    future_obs = datetime(2026, 3, 16, 10, 0, 0, tzinfo=timezone.utc)
    
    with pytest.raises(TemporalLeakageError, match="Temporal leakage detected"):
        assert_no_temporal_leakage(
            feature_vector={"pe_ratio": 22.5},
            observation_timestamp=future_obs,
            cutoff_timestamp=cutoff,
        )


def test_leakage_protection_prohibited_outcome_fields():
    cutoff = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
    valid_obs = datetime(2026, 3, 14, 10, 0, 0, tzinfo=timezone.utc)
    
    with pytest.raises(TemporalLeakageError, match="Data leakage detected"):
        assert_no_temporal_leakage(
            feature_vector={"listing_gain_pct": 25.4, "pe_ratio": 22.5},
            observation_timestamp=valid_obs,
            cutoff_timestamp=cutoff,
        )


def test_provenance_validator_sha256():
    validator = ProvenanceValidator()
    content = b"Official SEBI DRHP Filing Content"
    checksum = validator.compute_sha256(content)
    
    assert validator.verify_hash(content, checksum) is True
    assert validator.verify_hash(content, "invalid_checksum") is False
