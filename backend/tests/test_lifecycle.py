import pytest
from app.services.lifecycle_service import (
    can_transition,
    validate_transition,
    InvalidLifecycleTransitionError,
)


def test_valid_lifecycle_transitions():
    assert can_transition("DISCOVERED", "DOCUMENTS_PENDING") is True
    assert can_transition("DOCUMENTS_PENDING", "PRELIMINARY_ANALYSIS") is True
    assert can_transition("PRELIMINARY_ANALYSIS", "PRICE_BAND_AVAILABLE") is True
    assert can_transition("PRICE_BAND_AVAILABLE", "SUBSCRIPTION_OPEN") is True
    assert can_transition("SUBSCRIPTION_OPEN", "SUBSCRIPTION_CLOSED") is True
    assert can_transition("SUBSCRIPTION_CLOSED", "FINAL_ANALYSIS") is True
    assert can_transition("FINAL_ANALYSIS", "LISTED") is True
    assert can_transition("LISTED", "OUTCOME_VERIFIED") is True
    assert can_transition("PRELIMINARY_ANALYSIS", "WITHDRAWN") is True


def test_invalid_lifecycle_transitions():
    # Out-of-order jumps
    assert can_transition("DISCOVERED", "LISTED") is False
    assert can_transition("SUBSCRIPTION_OPEN", "OUTCOME_VERIFIED") is False
    assert can_transition("OUTCOME_VERIFIED", "DISCOVERED") is False

    with pytest.raises(InvalidLifecycleTransitionError):
        validate_transition("DISCOVERED", "LISTED")
