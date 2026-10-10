from typing import Set, Dict

# Complete list of lifecycle states
LIFECYCLE_STATES = [
    "DISCOVERED",
    "DOCUMENTS_PENDING",
    "PRELIMINARY_ANALYSIS",
    "PRICE_BAND_AVAILABLE",
    "SUBSCRIPTION_OPEN",
    "SUBSCRIPTION_CLOSED",
    "FINAL_ANALYSIS",
    "LISTED",
    "OUTCOME_VERIFIED",
    "WITHDRAWN",
    "POSTPONED",
]

# Directed transition graph representing legitimate Indian IPO regulatory lifecycles
VALID_TRANSITIONS: Dict[str, Set[str]] = {
    "DISCOVERED": {"DOCUMENTS_PENDING", "PRELIMINARY_ANALYSIS", "WITHDRAWN"},
    "DOCUMENTS_PENDING": {"PRELIMINARY_ANALYSIS", "WITHDRAWN"},
    "PRELIMINARY_ANALYSIS": {"PRICE_BAND_AVAILABLE", "WITHDRAWN", "POSTPONED"},
    "PRICE_BAND_AVAILABLE": {"SUBSCRIPTION_OPEN", "POSTPONED", "WITHDRAWN"},
    "SUBSCRIPTION_OPEN": {"SUBSCRIPTION_CLOSED", "WITHDRAWN", "POSTPONED"},
    "SUBSCRIPTION_CLOSED": {"FINAL_ANALYSIS", "WITHDRAWN"},
    "FINAL_ANALYSIS": {"LISTED", "WITHDRAWN"},
    "LISTED": {"OUTCOME_VERIFIED"},
    "OUTCOME_VERIFIED": set(),
    "WITHDRAWN": set(),
    "POSTPONED": {"PRICE_BAND_AVAILABLE", "WITHDRAWN"},
}


class InvalidLifecycleTransitionError(ValueError):
    """Raised when an illegal IPO lifecycle transition is attempted."""
    pass


def can_transition(current_status: str, target_status: str) -> bool:
    """Returns True if transition from current_status to target_status is legally permitted."""
    if current_status == target_status:
        return True
    allowed = VALID_TRANSITIONS.get(current_status, set())
    return target_status in allowed


def validate_transition(current_status: str, target_status: str) -> None:
    """Validates the transition and raises InvalidLifecycleTransitionError if invalid."""
    if not can_transition(current_status, target_status):
        raise InvalidLifecycleTransitionError(
            f"Invalid lifecycle transition from '{current_status}' to '{target_status}'. "
            f"Permitted next states: {list(VALID_TRANSITIONS.get(current_status, set()))}"
        )
