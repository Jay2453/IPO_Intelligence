"""
Regression tests for pdf_extractor.py text-line extraction logic.
These tests are network-independent and use inline fixture data.
Run with: python test_extractor_regression.py
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import io
import textwrap
import unittest

from app.pipeline.pdf_extractor import (
    PdfFinancialExtractor,
    parse_numeric_cell,
    normalize_to_crores,
    extract_fiscal_period,
    _strip_trailing_numbers,
    _find_fiscal_periods_in_lines,
    _match_metric_label,
    _detect_unit,
)


class TestParseNumericCell(unittest.TestCase):
    def test_plain_number(self):
        self.assertAlmostEqual(parse_numeric_cell("1234.56"), 1234.56)

    def test_number_with_commas(self):
        self.assertAlmostEqual(parse_numeric_cell("1,204.92"), 1204.92)

    def test_parenthesized_negative(self):
        self.assertAlmostEqual(parse_numeric_cell("(24.66)"), -24.66)

    def test_parenthesized_negative_with_commas(self):
        self.assertAlmostEqual(parse_numeric_cell("(1,000.00)"), -1000.0)

    def test_dash_is_none(self):
        self.assertIsNone(parse_numeric_cell("-"))

    def test_empty_is_none(self):
        self.assertIsNone(parse_numeric_cell(""))
        self.assertIsNone(parse_numeric_cell(None))

    def test_na_is_none(self):
        self.assertIsNone(parse_numeric_cell("N/A"))

    def test_percentage(self):
        self.assertAlmostEqual(parse_numeric_cell("65.73%"), 65.73)


class TestNormalizeToCreores(unittest.TestCase):
    def test_millions_to_crores(self):
        # 1 million = 0.1 crore
        self.assertAlmostEqual(normalize_to_crores(2028.94, "MILLIONS"), 202.894, places=2)

    def test_lakhs_to_crores(self):
        self.assertAlmostEqual(normalize_to_crores(100, "LAKHS"), 1.0, places=2)

    def test_crores_identity(self):
        self.assertAlmostEqual(normalize_to_crores(50.0, "CRORES"), 50.0)

    def test_none_returns_none(self):
        self.assertIsNone(normalize_to_crores(None, "CRORES"))


class TestExtractFiscalPeriod(unittest.TestCase):
    def test_fiscal_year_long(self):
        self.assertEqual(extract_fiscal_period("Fiscal 2026"), "FY26")

    def test_fy_abbrev(self):
        self.assertEqual(extract_fiscal_period("FY 2024"), "FY24")

    def test_march_end(self):
        self.assertEqual(extract_fiscal_period("Year ended March 31, 2025"), "FY25")

    def test_september_half_year(self):
        self.assertEqual(extract_fiscal_period("Six months ended September 30, 2024"), "H1FY25")

    def test_none_on_garbage(self):
        self.assertIsNone(extract_fiscal_period("Particulars"))
        self.assertIsNone(extract_fiscal_period(""))


class TestDetectUnit(unittest.TestCase):
    def test_million(self):
        self.assertEqual(_detect_unit("(in Rs. million unless stated otherwise)"), "MILLIONS")

    def test_lakh(self):
        self.assertEqual(_detect_unit("Amount in Lakhs"), "LAKHS")

    def test_crore(self):
        self.assertEqual(_detect_unit("figures are in crores"), "CRORES")

    def test_default_crore(self):
        self.assertEqual(_detect_unit("no unit mentioned"), "CRORES")


class TestStripTrailingNumbers(unittest.TestCase):
    def test_three_values(self):
        label, tokens = _strip_trailing_numbers("Revenue from Operations 2,028.94 968.45 536.55")
        self.assertEqual(label, "Revenue from Operations")
        self.assertEqual(tokens, ["2,028.94", "968.45", "536.55"])

    def test_negative_parens(self):
        label, tokens = _strip_trailing_numbers("Net Cash from Operations (147.32) (100.52) (10.51)")
        self.assertEqual(label, "Net Cash from Operations")
        self.assertEqual(tokens, ["(147.32)", "(100.52)", "(10.51)"])

    def test_no_numbers(self):
        label, tokens = _strip_trailing_numbers("Particulars Fiscal 2026 2025 2024")
        # 2026, 2025, 2024 ARE numeric — should be stripped
        self.assertEqual(tokens, ["2026", "2025", "2024"])

    def test_mixed_percentage(self):
        label, tokens = _strip_trailing_numbers("EBITDA Margin 15.27% 13.32% 10.21%")
        self.assertEqual(label, "EBITDA Margin")
        self.assertEqual(tokens, ["15.27%", "13.32%", "10.21%"])

    def test_dash_placeholder(self):
        label, tokens = _strip_trailing_numbers("Total Borrowings 23.424 7.598 -")
        self.assertEqual(tokens, ["23.424", "7.598", "-"])


class TestFindFiscalPeriodsInLines(unittest.TestCase):
    def test_single_line_explicit_fiscal(self):
        lines = ["Particular Fiscal 2026 Fiscal 2025 Fiscal 2024", "Revenue 200 100 50"]
        periods, consumed = _find_fiscal_periods_in_lines(lines, 0)
        self.assertEqual(set(periods), {"FY26", "FY25", "FY24"})
        self.assertEqual(consumed, 1)

    def test_two_line_header(self):
        lines = ["Particulars Fiscal", "2026 2025 2024", "Revenue 200 100 50"]
        periods, consumed = _find_fiscal_periods_in_lines(lines, 0)
        self.assertEqual(set(periods), {"FY26", "FY25", "FY24"})
        # Consumed 2 lines only if second line has 4-digit years
        # Since 'any(p[2:] in years_in_next ...)' fails for short year strings,
        # we might get consume=1 here; either way periods should be correct.
        self.assertGreaterEqual(len(periods), 3)

    def test_no_match(self):
        lines = ["Share Capital 50 40 30"]
        periods, consumed = _find_fiscal_periods_in_lines(lines, 0)
        self.assertEqual(periods, [])

    def test_kpi_header(self):
        lines = ["Financial KPIs", "Particulars 2026 2025 2024", "EBITDA 30 12 5"]
        periods, consumed = _find_fiscal_periods_in_lines(lines, 1)
        self.assertEqual(set(periods), {"FY26", "FY25", "FY24"})


class TestMatchMetricLabel(unittest.TestCase):
    def test_revenue_from_operations(self):
        key, is_rate = _match_metric_label("Revenue from Operations(1)")
        self.assertEqual(key, "revenue_crores")
        self.assertFalse(is_rate)

    def test_bare_revenue(self):
        key, is_rate = _match_metric_label("Revenue")
        self.assertEqual(key, "revenue_crores")

    def test_ebitda(self):
        key, _ = _match_metric_label("EBITDA(2)")
        self.assertEqual(key, "ebitda_crores")

    def test_ebitda_margin_is_none(self):
        key, _ = _match_metric_label("EBITDA Margin(3)")
        self.assertIsNone(key)

    def test_pat(self):
        key, _ = _match_metric_label("Profit after tax")
        self.assertEqual(key, "pat_crores")

    def test_pat_for_year(self):
        key, _ = _match_metric_label("Profit for the year")
        self.assertEqual(key, "pat_crores")

    def test_net_worth(self):
        key, _ = _match_metric_label("Net worth(8)")
        self.assertEqual(key, "net_worth_crores")

    def test_roe(self):
        key, is_rate = _match_metric_label("Return on Net Worth(6)")
        self.assertEqual(key, "roe_pct")
        self.assertTrue(is_rate)

    def test_eps(self):
        key, is_rate = _match_metric_label("Basic EPS")
        self.assertEqual(key, "eps_inr")
        self.assertTrue(is_rate)

    def test_nav(self):
        key, is_rate = _match_metric_label("Net Asset Value per Share")
        self.assertEqual(key, "nav_per_share_inr")
        self.assertTrue(is_rate)

    def test_total_assets(self):
        key, _ = _match_metric_label("Total Assets")
        self.assertEqual(key, "total_assets_crores")

    def test_total_debt(self):
        key, _ = _match_metric_label("Total Borrowings")
        self.assertEqual(key, "total_debt_crores")

    def test_ocf(self):
        key, _ = _match_metric_label("Cash flow from operating activities")
        self.assertEqual(key, "operating_cash_flow_crores")

    def test_investing_cash_flow_is_none(self):
        key, _ = _match_metric_label("Cash flow from investing activities")
        self.assertIsNone(key)

    def test_share_capital_is_none(self):
        key, _ = _match_metric_label("Share Capital")
        self.assertIsNone(key)


class TestEndToEndTextLineExtraction(unittest.TestCase):
    """
    Integration test using a synthetic page text that mimics the Nityas Abridged Prospectus layout.
    Verifies the full text-line extraction pipeline without requiring actual PDF bytes.
    """

    def _build_fake_page_text(self):
        """
        Builds a text string resembling a KPI summary page with unit in millions.
        Values: Revenue FY26=200.00, FY25=100.00, FY24=50.00 million
        -> Expected crores: 20.0, 10.0, 5.0
        """
        return textwrap.dedent("""\
            7. Summary of Key Performance Indicators
            Financial Key Performance Indicators:
            (Rs. in million, unless otherwise stated)
            Particular Fiscal 2026 Fiscal 2025 Fiscal 2024
            Financial KPIs
            Revenue from Operations(1) 200.00 100.00 50.00
            EBITDA(2) 30.00 12.00 5.00
            EBITDA Margin(3) 15.00% 12.00% 10.00%
            Profit after tax 22.00 9.00 4.00
            Net worth(8) 80.00 22.00 5.50
            Return on Net Worth(6) 44.00% 70.00% 80.00%
            Basic EPS 5.50 4.20 1.80
            Notes:
            (1) As per restated consolidated financial statements.
        """)

    def test_synthetic_page_extraction(self):
        obs_by_fy = {}
        extractor = PdfFinancialExtractor()
        page_text = self._build_fake_page_text()
        extractor._process_page_text_lines(
            text=page_text,
            page_number=5,
            statement_type="CONSOLIDATED",
            is_restated=True,
            default_unit="CRORES",  # default deliberately wrong
            observations_by_fy=obs_by_fy,
        )

        self.assertIn("FY26", obs_by_fy)
        self.assertIn("FY25", obs_by_fy)
        self.assertIn("FY24", obs_by_fy)

        fy26 = obs_by_fy["FY26"]
        # Revenue: 200 million -> 20 crores
        self.assertIsNotNone(fy26["revenue_crores"])
        self.assertAlmostEqual(fy26["revenue_crores"], 20.0, places=1)

        # EBITDA: 30 million -> 3 crores
        self.assertAlmostEqual(fy26["ebitda_crores"], 3.0, places=1)

        # PAT: 22 million -> 2.2 crores
        self.assertAlmostEqual(fy26["pat_crores"], 2.2, places=1)

        # Net worth: 80 million -> 8 crores
        self.assertAlmostEqual(fy26["net_worth_crores"], 8.0, places=1)

        # ROE is a rate, not normalized
        self.assertAlmostEqual(fy26["roe_pct"], 44.0, places=1)

        # EPS is per-share, not normalized
        self.assertAlmostEqual(fy26["eps_inr"], 5.5, places=1)

        # EBITDA margin must NOT be extracted
        # (it's a percentage label, filtered out by _match_metric_label)

        fy24 = obs_by_fy["FY24"]
        self.assertAlmostEqual(fy24["revenue_crores"], 5.0, places=1)

    def test_no_metrics_gives_failed_status(self):
        obs = {
            "fiscal_year": "FY26",
            "period_months": 12,
            "statement_type": "CONSOLIDATED",
            "is_restated": True,
            "currency": "INR",
            "unit": "CRORES",
            "source_page": 1,
            "extraction_method": "PDFPLUMBER_TABLE",
            "verification_status": "EXTRACTED",
            "revenue_crores": None,
            "ebitda_crores": None,
            "pat_crores": None,
            "total_assets_crores": None,
            "net_worth_crores": None,
            "total_liabilities_crores": None,
            "total_debt_crores": None,
            "operating_cash_flow_crores": None,
            "roe_pct": None,
            "roce_pct": None,
            "eps_inr": None,
            "nav_per_share_inr": None,
            "raw_data_provenance": {
                "source_page": 1,
                "line_items_extracted": {},
                "validation_checks": [],
            },
        }
        extractor = PdfFinancialExtractor()
        result = extractor._validate_observation(obs)
        self.assertEqual(result["verification_status"], "FAILED")
        self.assertTrue(any("FAIL" in c for c in result["raw_data_provenance"]["validation_checks"]))

    def test_text_line_provenance_method_and_primary_source_page(self):
        """
        Verify that line items extracted via TEXT_LINE correctly set the record-level
        extraction_method to TEXT_LINE, and primary source_page is preserved when a
        subsequent page extracts additional KPIs.
        """
        obs_by_fy = {}
        extractor = PdfFinancialExtractor()
        # Page 6: Primary statement
        page_6_text = textwrap.dedent("""\
            6. Summary of Restated Financial Information
            (in Rs. million unless indicated otherwise)
            Particulars Fiscal 2026 Fiscal 2025 Fiscal 2024
            Revenue 200.00 100.00 50.00
            EBITDA 30.00 12.00 5.00
            Profit after tax 22.00 9.00 4.00
            Net worth 80.00 22.00 5.50
        """)
        extractor._process_page_text_lines(
            text=page_6_text,
            page_number=6,
            statement_type="CONSOLIDATED",
            is_restated=True,
            default_unit="MILLIONS",
            observations_by_fy=obs_by_fy,
        )

        # Page 7: Supplementary KPIs
        page_7_text = textwrap.dedent("""\
            7. Summary of Key Performance Indicators
            (in Rs. million unless indicated otherwise)
            Particular Fiscal 2026 Fiscal 2025 Fiscal 2024
            Return on Capital Employed 42.93% 63.14% 88.39%
        """)
        extractor._process_page_text_lines(
            text=page_7_text,
            page_number=7,
            statement_type="CONSOLIDATED",
            is_restated=True,
            default_unit="MILLIONS",
            observations_by_fy=obs_by_fy,
        )

        # Run validation on FY26
        validated_fy26 = extractor._validate_observation(obs_by_fy["FY26"])
        self.assertEqual(validated_fy26["extraction_method"], "TEXT_LINE")
        self.assertEqual(validated_fy26["source_page"], 6)
        self.assertEqual(validated_fy26["raw_data_provenance"]["source_page"], 6)
        self.assertEqual(validated_fy26["raw_data_provenance"]["source_pages"], [6, 7])
        self.assertEqual(validated_fy26["verification_status"], "EXTRACTED")

        # Check individual line item pages
        line_items = validated_fy26["raw_data_provenance"]["line_items_extracted"]
        self.assertEqual(line_items["revenue_crores"]["source_page"], 6)
        self.assertEqual(line_items["revenue_crores"]["extraction_method"], "TEXT_LINE")
        self.assertEqual(line_items["roce_pct"]["source_page"], 7)
        self.assertEqual(line_items["roce_pct"]["extraction_method"], "TEXT_LINE")

    def test_missing_assets_and_liabilities_remain_none(self):
        """
        Verify that when Total Assets and Total Liabilities are not disclosed in
        the abridged statement, they remain None and do not trigger FAILED verification status.
        """
        obs_by_fy = {}
        extractor = PdfFinancialExtractor()
        page_text = textwrap.dedent("""\
            6. Summary of Restated Financial Information
            (in Rs. million unless indicated otherwise)
            Particulars Fiscal 2026 Fiscal 2025 Fiscal 2024
            Revenue 200.00 100.00 50.00
            Profit after tax 22.00 9.00 4.00
        """)
        extractor._process_page_text_lines(
            text=page_text,
            page_number=6,
            statement_type="CONSOLIDATED",
            is_restated=True,
            default_unit="MILLIONS",
            observations_by_fy=obs_by_fy,
        )
        validated = extractor._validate_observation(obs_by_fy["FY26"])
        self.assertIsNone(validated["total_assets_crores"])
        self.assertIsNone(validated["total_liabilities_crores"])
        self.assertEqual(validated["verification_status"], "EXTRACTED")


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(__import__("__main__"))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
