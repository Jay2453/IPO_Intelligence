import sys
import re
import io
import pdfplumber

sys.stdout.reconfigure(encoding='utf-8')

with open('scratch_nityas.pdf', 'rb') as f:
    pdf_bytes = f.read()

from app.pipeline.pdf_extractor import (
    parse_numeric_cell,
    normalize_to_crores,
)

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

def find_fiscal_periods_in_header(lines, idx):
    line = lines[idx]
    next_line = lines[idx + 1] if idx + 1 < len(lines) else ""
    
    for candidate in [line, f"{line} {next_line}"]:
        periods = []
        matches = re.findall(r'(?:(?:Fiscal(?:\s+Year)?|FY)\s*(20\d{2}|\d{2})|March\s*(?:31,?\s*)?(20\d{2}))', candidate, re.IGNORECASE)
        if matches:
            for m in matches:
                yr = m[0] or m[1]
                fy = f"FY{yr[2:]}" if len(yr) == 4 else f"FY{yr}"
                if fy not in periods:
                    periods.append(fy)
            if len(periods) >= 2:
                lines_consumed = 2 if candidate != line and any(yr in next_line for yr in [p[2:] for p in periods]) else 1
                return periods, lines_consumed
        
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

def extract_from_page_text(page_text: str, page_number: int):
    # Detect unit
    default_unit = "CRORES"
    lower_text = page_text.lower()
    if "million" in lower_text:
        default_unit = "MILLIONS"
    elif "lakh" in lower_text:
        default_unit = "LAKHS"

    lines = [l.strip() for l in page_text.split('\n') if l.strip()]
    results = {}
    i = 0
    while i < len(lines):
        periods, consumed = find_fiscal_periods_in_header(lines, i)
        if not periods:
            i += 1
            continue

        print(f"Page {page_number}: Found periods {periods} at line {i}: {lines[i]}")
        i += consumed

        # Now scan subsequent lines for line items
        num_periods = len(periods)
        while i < len(lines):
            line = lines[i]
            # Stop if we hit a new section, notes, or empty-like boundary
            if line.lower().startswith("notes:") or line.lower().startswith("note:") or line.startswith("---"):
                break
            
            # Extract numbers from end of line
            curr = line
            tokens = []
            while True:
                m = re.search(r'[\s\t]+(\(\s*[\d,]+(?:\.\d+)?%?\s*\)|-?[\d,]+(?:\.\d+)?%?|-|N/A|\[•\]|\[●\])\s*$', curr)
                if not m:
                    break
                tokens.insert(0, m.group(1).strip())
                curr = curr[:m.start()].rstrip()

            if len(tokens) >= num_periods:
                excess = len(tokens) - num_periods
                if excess > 0:
                    curr = curr + ' ' + ' '.join(tokens[:excess])
                    tokens = tokens[excess:]
            elif len(tokens) < num_periods:
                # Might not be a valid table row
                # Check if it is a new header or something
                new_periods, _ = find_fiscal_periods_in_header(lines, i)
                if new_periods:
                    break
                i += 1
                continue

            metric_key, is_rate = match_metric_label(curr)
            if metric_key:
                for idx, fy in enumerate(periods):
                    if fy not in results:
                        results[fy] = {}
                    val_str = tokens[idx]
                    parsed = parse_numeric_cell(val_str)
                    if parsed is not None:
                        if is_rate or metric_key in ("eps_inr", "nav_per_share_inr"):
                            final_val = round(parsed, 2)
                        else:
                            final_val = normalize_to_crores(parsed, default_unit)
                        if results[fy].get(metric_key) is None:
                            results[fy][metric_key] = {
                                "val": final_val,
                                "raw_label": curr,
                                "raw_cell": val_str,
                                "page": page_number
                            }
            i += 1
    return results

with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
    for idx, page in enumerate(pdf.pages):
        text = page.extract_text() or ""
        res = extract_from_page_text(text, idx + 1)
        if res:
            print(f"=== Page {idx + 1} Extracted ===")
            for fy, metrics in res.items():
                print(f"  {fy}:")
                for k, v in metrics.items():
                    print(f"    {k}: {v}")
