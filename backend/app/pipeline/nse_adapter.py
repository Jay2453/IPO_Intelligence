import re
import hashlib
from datetime import datetime, date, timezone
from typing import List, Dict, Any, Optional, Tuple
import httpx
from app.core.config import settings
from app.pipeline.interfaces import IDiscoveryProvider, DiscoveryResult


class NseConnectionError(Exception):
    """Raised when communication with official NSE endpoints fails."""
    pass


class NseParseError(Exception):
    """Raised when source records are malformed or cannot be parsed."""
    pass


def parse_nse_date(date_str: Optional[str]) -> Optional[date]:
    """Parses various NSE date formats such as '13-Oct-2026', '05-OCT-2026', '2026-10-13'."""
    if not date_str or not isinstance(date_str, str):
        return None
    cleaned = date_str.strip()
    if cleaned in ("-", "", "N/A", "null", "None"):
        return None
    for fmt in ("%d-%b-%Y", "%d-%B-%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            pass
    return None


def parse_nse_price_range(price_str: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
    """Extracts floor and cap prices from strings like 'Rs.258 to Rs.271' or 'Rs.1000' or '220'."""
    if not price_str or not isinstance(price_str, str):
        return None, None
    cleaned = price_str.replace("Rs.", "").replace("Rs", "").replace(",", "").strip()
    if cleaned in ("-", "", "N/A", "null", "None"):
        return None, None

    if "to" in cleaned.lower():
        parts = re.split(r"\s+to\s+", cleaned, flags=re.IGNORECASE)
        try:
            p_min = float(parts[0].strip())
            p_max = float(parts[1].strip())
            return p_min, p_max
        except (ValueError, IndexError):
            pass

    try:
        val = float(cleaned)
        return val, val
    except ValueError:
        return None, None


def compute_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


class NseIpoSourceAdapter(IDiscoveryProvider):
    """
    Official NSE IPO Information Source Adapter.
    Communicates via official permitted public interfaces on nseindia.com.
    """

    def __init__(self, base_url: Optional[str] = None, timeout: float = 12.0):
        self.base_url = (base_url or settings.NSE_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": f"{self.base_url}/market-data/all-upcoming-issues-ipo",
        }

    def _get_client(self) -> httpx.Client:
        return httpx.Client(
            headers=self.headers,
            follow_redirects=True,
            timeout=self.timeout,
        )

    def verify_live_connection(self) -> Dict[str, Any]:
        """Performs a live connectivity check against NSE public portal."""
        with self._get_client() as client:
            try:
                # 1. Warm-up session cookie on market-data page
                page_res = client.get(f"{self.base_url}/market-data/all-upcoming-issues-ipo")
                page_ok = page_res.status_code == 200
                
                # 2. Check API endpoint
                api_res = client.get(f"{self.base_url}/api/all-upcoming-issues?category=ipo")
                api_ok = api_res.status_code == 200
                
                return {
                    "connected": page_ok and api_ok,
                    "page_status_code": page_res.status_code,
                    "api_status_code": api_res.status_code,
                    "cookies_acquired": len(client.cookies) > 0,
                }
            except httpx.HTTPError as e:
                return {
                    "connected": False,
                    "error": str(e),
                }

    def fetch_raw_upcoming_issues(self, client: Optional[httpx.Client] = None) -> Tuple[List[Dict[str, Any]], str, str]:
        """
        Fetches upcoming IPOs from /api/all-upcoming-issues?category=ipo.
        Returns: (data_list, canonical_url, sha256_hash)
        """
        url = f"{self.base_url}/api/all-upcoming-issues?category=ipo"
        should_close = False
        if client is None:
            client = self._get_client()
            should_close = True

        try:
            # Pre-establish session
            client.get(f"{self.base_url}/market-data/all-upcoming-issues-ipo")
            res = client.get(url)
            if res.status_code != 200:
                raise NseConnectionError(f"NSE upcoming issues API returned status {res.status_code}")
            
            raw_bytes = res.content
            content_hash = compute_sha256(raw_bytes)
            data = res.json()
            if not isinstance(data, list):
                raise NseParseError(f"Unexpected response format: expected list, got {type(data)}")
            return data, url, content_hash
        except httpx.HTTPError as e:
            raise NseConnectionError(f"Network error communicating with NSE: {str(e)}") from e
        finally:
            if should_close:
                client.close()

    def fetch_raw_current_issues(self, client: Optional[httpx.Client] = None) -> Tuple[List[Dict[str, Any]], str, str]:
        """
        Fetches currently open bidding IPOs from /api/ipo-current-issue.
        """
        url = f"{self.base_url}/api/ipo-current-issue"
        should_close = False
        if client is None:
            client = self._get_client()
            should_close = True

        try:
            res = client.get(url)
            if res.status_code != 200:
                raise NseConnectionError(f"NSE current issues API returned status {res.status_code}")
            
            raw_bytes = res.content
            content_hash = compute_sha256(raw_bytes)
            data = res.json()
            if not isinstance(data, list):
                data = []
            return data, url, content_hash
        except httpx.HTTPError as e:
            raise NseConnectionError(f"Network error communicating with NSE: {str(e)}") from e
        finally:
            if should_close:
                client.close()

    def fetch_raw_past_issues(self, limit: int = 50, client: Optional[httpx.Client] = None) -> Tuple[List[Dict[str, Any]], str, str]:
        """
        Fetches recent past and closed issues from /api/public-past-issues.
        """
        url = f"{self.base_url}/api/public-past-issues"
        should_close = False
        if client is None:
            client = self._get_client()
            should_close = True

        try:
            res = client.get(url)
            if res.status_code != 200:
                raise NseConnectionError(f"NSE past issues API returned status {res.status_code}")
            
            raw_bytes = res.content
            content_hash = compute_sha256(raw_bytes)
            data = res.json()
            if not isinstance(data, list):
                raise NseParseError(f"Unexpected past issues format: expected list, got {type(data)}")
            return data[:limit], url, content_hash
        except httpx.HTTPError as e:
            raise NseConnectionError(f"Network error communicating with NSE: {str(e)}") from e
        finally:
            if should_close:
                client.close()

    def poll_new_filings(self, since: Optional[datetime] = None) -> List[DiscoveryResult]:
        """Implementation of IDiscoveryProvider."""
        items, url, _ = self.fetch_raw_upcoming_issues()
        results: List[DiscoveryResult] = []
        now = datetime.now(timezone.utc)
        for it in items:
            name = it.get("companyName") or it.get("company")
            if not name:
                continue
            results.append(
                DiscoveryResult(
                    company_name=name.strip(),
                    source_system="NSE_FEED",
                    canonical_url=url,
                    raw_metadata=it,
                    discovered_at=now,
                )
            )
        return results

    def normalize_record(self, raw: Dict[str, Any], is_past: bool = False) -> Optional[Dict[str, Any]]:
        """
        Normalizes a raw NSE API record into the standardized IPO schema attributes.
        """
        company_name = (raw.get("companyName") or raw.get("company") or "").strip()
        if not company_name:
            return None

        symbol = (raw.get("symbol") or "").strip() or None
        series = (raw.get("series") or raw.get("securityType") or "").strip().upper()
        
        # Determine category: SME vs MAINBOARD
        category = "SME" if "SME" in series else "MAINBOARD"

        # Dates
        open_date = parse_nse_date(raw.get("issueStartDate") or raw.get("ipoStartDate"))
        close_date = parse_nse_date(raw.get("issueEndDate") or raw.get("ipoEndDate"))
        listing_date = parse_nse_date(raw.get("listingDate"))

        # Price band
        price_str = raw.get("priceBand") or raw.get("priceRange") or raw.get("issuePrice")
        min_price, max_price = parse_nse_price_range(price_str)

        # Lot size
        lot_size = None
        raw_lot = raw.get("lotSize")
        if raw_lot:
            try:
                lot_size = int(str(raw_lot).replace(",", "").strip())
            except ValueError:
                pass

        # Issue size (if shares or crores)
        issue_size_crores = None
        raw_size = raw.get("issueSize")
        if raw_size:
            try:
                # Often given as number of shares or amount; if > 100,000,000, can be evaluated
                val = float(str(raw_size).replace(",", "").strip())
                if val > 0:
                    # If price is known, approximate issue size in crores, else keep as shares or None
                    if max_price and max_price > 0 and val > 1000:
                        issue_size_crores = round((val * max_price) / 10000000.0, 2)
            except ValueError:
                pass

        # Determine lifecycle status accurately
        today = date.today()
        status_raw = (raw.get("status") or "").strip().lower()
        
        if listing_date and listing_date <= today:
            lifecycle_status = "LISTED"
        elif close_date and close_date < today:
            lifecycle_status = "SUBSCRIPTION_CLOSED"
        elif open_date and close_date and open_date <= today <= close_date:
            lifecycle_status = "SUBSCRIPTION_OPEN"
        elif min_price is not None or max_price is not None:
            lifecycle_status = "PRICE_BAND_AVAILABLE"
        elif status_raw == "forthcoming":
            lifecycle_status = "PRELIMINARY_ANALYSIS"
        elif is_past:
            lifecycle_status = "SUBSCRIPTION_CLOSED"
        else:
            lifecycle_status = "DISCOVERED"

        # Calculate data completeness %
        fields = [company_name, symbol, min_price, max_price, lot_size, open_date, close_date, category]
        populated = sum(1 for f in fields if f is not None)
        completeness = int((populated / len(fields)) * 100)

        return {
            "symbol": symbol,
            "company_name": company_name,
            "exchange": "NSE",
            "category": category,
            "lifecycle_status": lifecycle_status,
            "min_price": min_price,
            "max_price": max_price,
            "lot_size": lot_size,
            "issue_size_crores": issue_size_crores,
            "open_date": open_date,
            "close_date": close_date,
            "listing_date": listing_date,
            "data_completeness_pct": completeness,
            "analysis_status": "PENDING",
            "is_demo": False,  # REAL RECORD
        }
