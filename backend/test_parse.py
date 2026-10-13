import sys
import re

sys.stdout.reconfigure(encoding='utf-8')


header_tests = [
    'Particular Fiscal 2026 Fiscal 2025 Fiscal 2024',
    'Particulars Fiscal\n2026 2025 2024',
    'Fiscal 2026 Fiscal 2025 Fiscal 2024',
    'FY 2026 FY 2025 FY 2024',
    'FY26 FY25 FY24',
    'For the year ended March 31, 2026 March 31, 2025 March 31, 2024',
    'Particulars 2026 2025 2024',
]

def find_fiscal_periods_in_header(lines, idx):
    # Check current line, or current line + next line if current line has 'fiscal' or 'particulars'
    line = lines[idx]
    next_line = lines[idx + 1] if idx + 1 < len(lines) else ""
    
    # Try finding periods in combined or individual line
    for candidate in [line, f"{line} {next_line}"]:
        periods = []
        # Pattern 1: Explicit 'Fiscal 2026', 'FY26', etc.
        # Find all occurrences
        matches = re.findall(r'(?:(?:Fiscal(?:\s+Year)?|FY)\s*(20\d{2}|\d{2})|March\s*(?:31,?\s*)?(20\d{2}))', candidate, re.IGNORECASE)
        if matches:
            for m in matches:
                yr = m[0] or m[1]
                fy = f"FY{yr[2:]}" if len(yr) == 4 else f"FY{yr}"
                if fy not in periods:
                    periods.append(fy)
            if len(periods) >= 2:
                # Determine how many lines were consumed (1 or 2)
                lines_consumed = 2 if candidate != line and any(yr in next_line for yr in [p[2:] for p in periods]) else 1
                return periods, lines_consumed
        
        # Pattern 2: Context of 'fiscal' or 'year' and list of 4-digit years like '2026 2025 2024'
        if any(kw in candidate.lower() for kw in ["fiscal", "year", "particular", "ended", "as on", "as at"]):
            year_matches = re.findall(r'\b(20\d{2})\b', candidate)
            if len(year_matches) >= 2:
                for yr in year_matches:
                    fy = f"FY{yr[2:]}"
                    if fy not in periods:
                        periods.append(fy)
                lines_consumed = 2 if candidate != line and any(yr in next_line for yr in year_matches) else 1
                return periods, lines_consumed

    return [], 1

for ht in header_tests:
    h_lines = ht.split('\n')
    periods, consumed = find_fiscal_periods_in_header(h_lines, 0)
    print(f"{ht!r:65} -> {periods} (consumed {consumed})")


NUM_TOKEN_RE = re.compile(r'(\(\s*[\d,]+(?:\.\d+)?%?\s*\)|-?[\d,]+(?:\.\d+)?%?|-|N/A|\[•\]|\[●\])')

def match_metric_label(raw_label: str):
    label_lower = raw_label.lower().strip()
    # Remove footnote markers like (1), (2)(3), (5) (6)
    label_cleaned = re.sub(r'\(\d+\)', ' ', label_lower)
    label_cleaned = re.sub(r'\(in\s*[₹rs\.]*\)', ' ', label_cleaned)
    label_cleaned = re.sub(r'\s+', ' ', label_cleaned).strip()

    # Revenue
    if any(term in label_cleaned for term in ["revenue from operations", "total revenue", "total income"]) or re.search(r'\brevenue\b', label_cleaned):
        if any(term in label_cleaned for term in ["%", "percent", "growth", "margin", "share of", "% of"]):
            return None, False
        return "revenue_crores", False

    # EBITDA
    if "ebitda" in label_cleaned and "margin" not in label_cleaned and "%" not in label_cleaned:
        return "ebitda_crores", False

    # PAT
    if any(term in label_cleaned for term in [
        "profit/(loss) after tax", "profit / (loss) after tax", "profit/(loss) for the",
        "restated profit for the year", "profit for the period/ year", "profit for the period",
        "profit for the year", "profit after tax", "net profit after tax", "restated pat"
    ]) and "margin" not in label_cleaned and "%" not in label_cleaned:
        return "pat_crores", False

    # Net worth / Equity
    if any(term in label_cleaned for term in ["net worth", "total equity"]) and not any(term in label_cleaned for term in ["return", "%", "per share", "per equity"]):
        return "net_worth_crores", False

    # Total Assets
    if "total assets" in label_cleaned:
        return "total_assets_crores", False

    # Total Liabilities
    if "total liabilities" in label_cleaned:
        return "total_liabilities_crores", False

    # Borrowings / Total debt
    if any(term in label_cleaned for term in ["total borrowings", "total debt", "borrowings"]):
        return "total_debt_crores", False

    # Operating Cash Flow
    if any(term in label_cleaned for term in [
        "operating activities", "cash generated from operating", "cash flow from operating"
    ]):
        if "investing" in label_cleaned or "financing" in label_cleaned:
            return None, False
        return "operating_cash_flow_crores", False

    # ROE
    if any(term in label_cleaned for term in ["return on equity", "return on net worth", "ronw", "roe"]):
        return "roe_pct", True

    # ROCE
    if any(term in label_cleaned for term in ["return on capital employed", "roce"]):
        return "roce_pct", True

    # EPS
    if any(term in label_cleaned for term in ["basic eps", "diluted eps", "earnings per share"]):
        return "eps_inr", True

    # NAV per share
    if any(term in label_cleaned for term in ["net asset value per", "nav per share"]):
        return "nav_per_share_inr", True

    return None, False

N = 3
test_lines = [
    # Revenue variants
    "Revenue from Operations(1) 2,028.94 968.45 536.55",
    "Revenue 2,028.94 968.45 536.55",
    "Total Revenue from Operations 2,028.94 968.45 536.55",
    # EBITDA
    "EBITDA(2) 309.74 129.01 54.76",
    # EBITDA margin must NOT match (has %)
    "EBITDA Margin(3) 15.27% 13.32% 10.21%",
    # PAT variants
    "Profit/(loss) after tax 223.15 97.88 40.24",
    "Profit for the year 223.15 97.88 40.24",
    "Profit after tax 223.15 97.88 40.24",
    # Net worth
    "Net worth(8) 794.30 225.72 53.29",
    # Total Assets / Liabilities
    "Total Assets 1,200.00 600.00 300.00",
    "Total Liabilities 400.00 374.28 246.71",
    # Borrowings
    "Total Borrowings(7) 234.24 75.98 36.84",
    # OCF (negative values in parens)
    "Cash flow from operating activities (147.32) (100.52) (10.51)",
    # ROE / RONW
    "Return on Net Worth(3)(4) 43.75% 70.17% 122.44%",
    "Return on Equity 43.75% 70.17% 122.44%",
    # ROCE
    "Return on Capital Employed 42.93% 68.52% 118.00%",
    # EPS
    "Earnings per share (basic) (in ₹)(1) 5.52 4.37 1.83",
    "Basic EPS 5.52 4.37 1.83",
    # NAV per share
    "Net Asset Value per Equity Share (in ₹)(5) 15.13 9.53 2.40",
    # Should produce None (unrecognised)
    "Share Capital 215.69 12.40 10.00",
    "Paid-up equity share capital 215.69 12.40 10.00",
]

for l in test_lines:

    tokens = []
    curr = l
    while True:
        m = re.search(r'[\s\t]+(\(\s*[\d,]+(?:\.\d+)?%?\s*\)|-?[\d,]+(?:\.\d+)?%?|-|N/A|\[•\]|\[●\])\s*$', curr)
        if not m:
            break
        val = m.group(1).strip()
        tokens.insert(0, val)
        curr = curr[:m.start()].rstrip()
    
    if len(tokens) >= N:
        excess = len(tokens) - N
        if excess > 0:
            curr = curr + ' ' + ' '.join(tokens[:excess])
            tokens = tokens[excess:]
    
    key, is_rate = match_metric_label(curr)
    print(f"{curr!r:45} -> {key!r:25} TOKENS: {tokens}")


