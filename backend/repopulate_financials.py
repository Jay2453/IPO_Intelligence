"""
Clears stale blank FinancialObservation records for the target IPO and re-triggers
extraction via the document service directly (no HTTP needed).
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.append('.')

os.environ.setdefault("DATABASE_URL", "sqlite:///./ipo_intelligence.db")

from app.core.database import SessionLocal
from app.models.financials import FinancialObservation
from app.models.documents import Document
from app.models.ipo import IPO
from sqlalchemy import select

IPO_ID = "e30bca21-94df-4cde-b3dc-9c7241f218d1"
DOC_ID = "e16082cb-7fa6-4769-baee-0164eb253597"

db = SessionLocal()

# 1. List existing observations
existing = db.scalars(
    select(FinancialObservation).where(FinancialObservation.ipo_id == IPO_ID)
).all()
print(f"Existing observations before cleanup: {len(existing)}")
for o in existing:
    print(f"  {o.fiscal_year}: rev={o.revenue_crores} pat={o.pat_crores} status={o.verification_status}")

# 2. Delete all blank observations so re-extraction creates fresh ones
blanks = [o for o in existing if o.revenue_crores is None and o.pat_crores is None]
print(f"\nDeleting {len(blanks)} blank/empty observations...")
for b in blanks:
    db.delete(b)
db.commit()

# 3. Re-fetch document
doc = db.get(Document, DOC_ID)
if not doc:
    print("Document not found!")
    sys.exit(1)
print(f"\nDocument: {doc.id}, status={doc.extraction_status}")
print(f"Source URL: {doc.file_url}")

# 4. Get PDF bytes
SCRATCH_PDF = "scratch_nityas.pdf"
if os.path.exists(SCRATCH_PDF):
    with open(SCRATCH_PDF, 'rb') as f:
        pdf_bytes = f.read()
    print(f"Using local scratch PDF: {len(pdf_bytes)} bytes")
else:
    print(f"Downloading from: {doc.file_url}")
    import httpx
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        resp = client.get(doc.file_url)
        resp.raise_for_status()
        pdf_bytes = resp.content
    print(f"Downloaded: {len(pdf_bytes)} bytes")

# 5. Run extraction
from app.services.document_service import DocumentService
svc = DocumentService()
ipo = db.get(IPO, IPO_ID)
stored = svc._extract_and_store_financials(db, doc, ipo, pdf_bytes)
db.commit()

print(f"\nStored/updated: {stored} observations")
print(f"Document extraction_status: {doc.extraction_status}")

# 6. Show final state
final = db.scalars(
    select(FinancialObservation).where(FinancialObservation.ipo_id == IPO_ID)
).all()
print(f"\nFinal observations: {len(final)}")
for o in final:
    prov = o.raw_data_provenance or {}
    items = prov.get("line_items_extracted", {}) if isinstance(prov, dict) else {}
    checks = prov.get("validation_checks", []) if isinstance(prov, dict) else []
    print(f"  {o.fiscal_year}: rev={o.revenue_crores} ebitda={o.ebitda_crores} pat={o.pat_crores} nw={o.net_worth_crores}")
    print(f"          debt={o.total_debt_crores} ocf={o.operating_cash_flow_crores} roe={o.roe_pct} eps={o.eps_inr} nav={o.nav_per_share_inr}")
    print(f"          status={o.verification_status} page={o.source_page}")
    print(f"          items={list(items.keys())}")
    print(f"          checks={checks}")

db.close()
