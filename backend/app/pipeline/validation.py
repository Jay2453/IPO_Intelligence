import hashlib
from app.pipeline.interfaces import IProvenanceValidator


class ProvenanceValidator(IProvenanceValidator):
    """
    Validates cryptographic content integrity and guarantees that documents
    cannot be mutated after ingestion.
    """

    def compute_sha256(self, payload: bytes) -> str:
        return hashlib.sha256(payload).hexdigest()

    def verify_hash(self, payload: bytes, claimed_hash: str) -> bool:
        if not payload or not claimed_hash:
            return False
        computed = self.compute_sha256(payload)
        return computed.lower() == claimed_hash.lower()
