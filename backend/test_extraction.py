import sys
sys.path.append('.')
sys.stdout.reconfigure(encoding='utf-8')
from app.pipeline.pdf_extractor import PdfFinancialExtractor

with open('scratch_nityas.pdf', 'rb') as f:
    pdf_bytes = f.read()

ext = PdfFinancialExtractor()
obs = ext.extract_financials(pdf_bytes)
print(f'Total observations: {len(obs)}')
for o in obs:
    fy = o['fiscal_year']
    rev = o['revenue_crores']
    ebitda = o['ebitda_crores']
    pat = o['pat_crores']
    nw = o['net_worth_crores']
    debt = o['total_debt_crores']
    ocf = o['operating_cash_flow_crores']
    roe = o['roe_pct']
    eps = o['eps_inr']
    nav = o['nav_per_share_inr']
    status = o['verification_status']
    page = o['source_page']
    print(f'  {fy}: rev={rev} ebitda={ebitda} pat={pat} nw={nw} debt={debt} ocf={ocf}')
    print(f'       roe={roe} eps={eps} nav={nav} status={status} page={page}')
    prov = o.get('raw_data_provenance', {})
    line_items = prov.get('line_items_extracted', {})
    checks = prov.get('validation_checks', [])
    print(f'    Line items: {list(line_items.keys())}')
    print(f'    Checks: {checks}')
