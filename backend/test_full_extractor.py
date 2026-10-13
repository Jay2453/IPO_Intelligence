import io
import re
import sys
import pdfplumber

sys.stdout.reconfigure(encoding='utf-8')

with open('scratch_nityas.pdf', 'rb') as f:
    pdf_bytes = f.read()

from app.pipeline.pdf_extractor import (
    parse_numeric_cell,
    normalize_to_crores,
    extract_fiscal_period,
)

# Test full extraction logic
METRIC_FIELDS = [
    "revenue_crores", "ebitda_crores", "pat_crores", "total_assets_crores",
    "net_worth_crores", "total_liabilities_crores", "total_debt_crores",
    "operating_cash_flow_crores", "roe_pct", "roce_pct", "eps_inr", "nav_per_share_inr"
]

CORE_METRICS = [
    "revenue_crores", "ebitda_crores", "pat_crores", "net_worth_crores", "total_assets_crores"
]

def has_usable_metrics(obs):
    return any(obs.get(m) is not None for m in METRIC_FIELDS)

print("Starting test...")
