from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime


class DiscoveryResult:
    def __init__(
        self,
        company_name: str,
        source_system: str,
        canonical_url: str,
        raw_metadata: Dict[str, Any],
        discovered_at: datetime,
    ):
        self.company_name = company_name
        self.source_system = source_system
        self.canonical_url = canonical_url
        self.raw_metadata = raw_metadata
        self.discovered_at = discovered_at


class IDiscoveryProvider(ABC):
    """Protocol for scanning authorized regulatory feeds and circulars."""

    @abstractmethod
    def poll_new_filings(self, since: datetime) -> List[DiscoveryResult]:
        """Polls regulatory portals for new filings published since given timestamp."""
        pass


class IDocumentFetcher(ABC):
    """Protocol for fetching public filing documents with SHA-256 provenance."""

    @abstractmethod
    def fetch_document(self, url: str) -> Dict[str, Any]:
        """Fetches a document and returns its bytes, content-type, and SHA-256 checksum."""
        pass


class IStructuredExtractor(ABC):
    """Protocol for extracting financial statements and issue parameters from filings."""

    @abstractmethod
    def extract_financials(self, document_bytes: bytes) -> List[Dict[str, Any]]:
        """Extracts restated financial statement periods (FY22, FY23, FY24) from DRHP/RHP."""
        pass

    @abstractmethod
    def extract_issue_terms(self, document_bytes: bytes) -> Dict[str, Any]:
        """Extracts price band, issue size, fresh issue vs OFS, and lot size."""
        pass


class IProvenanceValidator(ABC):
    """Protocol for verifying data provenance and cryptographic hash integrity."""

    @abstractmethod
    def verify_hash(self, payload: bytes, claimed_hash: str) -> bool:
        """Verifies if calculated SHA-256 matches claimed hash."""
        pass


class IOutcomeVerifier(ABC):
    """Protocol for verifying post-listing day-1 opening and closing prices."""

    @abstractmethod
    def reconcile_bhavcopy(self, symbol: str, listing_date: datetime) -> Optional[Dict[str, Any]]:
        """Matches against official NSE/BSE daily bhavcopy report."""
        pass
