import os
import re
import hashlib
from datetime import datetime, date, timezone
from typing import List, Dict, Any, Optional, Tuple
import urllib.parse
import httpx
from bs4 import BeautifulSoup

from app.core.config import settings
from app.pipeline.interfaces import IDiscoveryProvider, DiscoveryResult, IDocumentFetcher


class SebiConnectionError(Exception):
    """Raised when communication with official SEBI portal fails."""
    pass


class SebiParseError(Exception):
    """Raised when SEBI filings page structure cannot be parsed."""
    pass


class DocumentSizeLimitExceededError(Exception):
    """Raised when document download exceeds configured safety limit."""
    pass


def compute_sha256(payload: bytes) -> str:
    """Computes SHA-256 hex digest of raw binary payload."""
    return hashlib.sha256(payload).hexdigest()


def parse_sebi_date(date_str: Optional[str]) -> Optional[date]:
    """Parses SEBI filing date strings such as 'Oct 07, 2026', '07-Oct-2026', '2026-10-07'."""
    if not date_str or not isinstance(date_str, str):
        return None
    cleaned = date_str.strip()
    if cleaned in ("-", "", "N/A", "null", "None"):
        return None
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%d-%b-%Y", "%d-%B-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            pass
    return None


def clean_company_name(name: str) -> str:
    """Normalizes company names for fuzzy/token comparison."""
    if not name:
        return ""
    cleaned = name.upper()
    cleaned = re.sub(r"\b(LIMITED|LTD|PRIVATE|PVT|CORPORATION|CORP|LLP|INDIA|HOLDINGS?|COMPANY|CO)\b", "", cleaned)
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def detect_document_type(title: str, url: str) -> str:
    """Classifies document into standard regulatory categories."""
    combined = f"{title} {url}".upper()
    if "DRAFT ABRIDGED PROSPECTUS" in combined or "DAP" in combined:
        return "DRAFT_ABRIDGED_PROSPECTUS"
    if "ABRIDGED PROSPECTUS" in combined:
        return "ABRIDGED_PROSPECTUS"
    if "DRHP" in combined or "DRAFT RED HERRING" in combined:
        return "DRHP"
    if "RHP" in combined or "RED HERRING" in combined:
        return "RHP"
    if "CORRIGENDUM" in combined or "ADDENDUM" in combined:
        return "CORRIGENDUM"
    if "PROSPECTUS" in combined:
        return "PROSPECTUS"
    return "OFFER_DOCUMENT"


class SebiPublicIssuesAdapter(IDiscoveryProvider, IDocumentFetcher):
    """
    Official SEBI Public Issue Filings Adapter.
    Permitted public access to DRHP, RHP, and Draft Abridged Prospectus documents.
    """

    DRHP_URL = "https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=3&ssid=15&smid=10"
    RHP_URL = "https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=3&ssid=15&smid=11"

    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.sebi.gov.in/filings/public-issues.html",
    }

    def __init__(self, timeout: float = None, max_size_mb: int = None, cache_dir: Optional[str] = None):
        self.timeout = timeout or float(settings.SEBI_REQUEST_TIMEOUT_SECONDS)
        self.max_size_bytes = (max_size_mb or settings.SEBI_MAX_DOCUMENT_SIZE_MB) * 1024 * 1024
        if cache_dir:
            self.cache_dir = cache_dir
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.cache_dir = os.path.join(base_dir, "data", "pdf_cache")
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
        except Exception:
            pass

    def get_cached_document(self, file_hash: str) -> Optional[bytes]:
        """Returns raw bytes from local disk cache if SHA-256 matches, else None."""
        if not file_hash or len(file_hash) != 64:
            return None
        cache_path = os.path.join(self.cache_dir, f"{file_hash}.pdf")
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "rb") as f:
                    payload = f.read()
                if hashlib.sha256(payload).hexdigest() == file_hash:
                    return payload
            except Exception:
                return None
        return None

    def save_to_cache(self, file_hash: str, payload: bytes) -> None:
        """Saves validated document bytes to local disk cache."""
        if not file_hash or not payload:
            return
        try:
            cache_path = os.path.join(self.cache_dir, f"{file_hash}.pdf")
            with open(cache_path, "wb") as f:
                f.write(payload)
        except Exception:
            pass

    def verify_connection(self) -> Dict[str, Any]:
        """Performs a live HEAD or GET probe of official SEBI public issues portal."""
        try:
            with httpx.Client(headers=self.DEFAULT_HEADERS, timeout=self.timeout, follow_redirects=True) as client:
                resp = client.get("https://www.sebi.gov.in/filings/public-issues.html")
                return {
                    "source": "SEBI_PUBLIC_FILINGS",
                    "status": "UP" if resp.status_code == 200 else "DEGRADED",
                    "status_code": resp.status_code,
                    "endpoint": "https://www.sebi.gov.in/filings/public-issues.html",
                    "latency_ms": int(resp.elapsed.total_seconds() * 1000) if resp.elapsed else 0,
                    "verified_at": datetime.now(timezone.utc).isoformat(),
                }
        except Exception as e:
            return {
                "source": "SEBI_PUBLIC_FILINGS",
                "status": "DOWN",
                "error": str(e),
                "endpoint": "https://www.sebi.gov.in/filings/public-issues.html",
                "verified_at": datetime.now(timezone.utc).isoformat(),
            }

    def poll_new_filings(self, since: Optional[datetime] = None) -> List[DiscoveryResult]:
        """Discovers filings from both DRHP and RHP public issue listings."""
        filings = self.fetch_filings_listing(self.DRHP_URL, "DRHP")
        rhp_filings = self.fetch_filings_listing(self.RHP_URL, "RHP")
        all_filings = filings + rhp_filings

        results: List[DiscoveryResult] = []
        for f in all_filings:
            filing_date = f.get("filing_date")
            discovered_at = (
                datetime.combine(filing_date, datetime.min.time(), tzinfo=timezone.utc)
                if filing_date
                else datetime.now(timezone.utc)
            )

            if since and discovered_at < since:
                continue

            results.append(
                DiscoveryResult(
                    company_name=f["issuer_name"],
                    source_system="SEBI_PUBLIC_FILINGS",
                    canonical_url=f["detail_url"],
                    raw_metadata=f,
                    discovered_at=discovered_at,
                )
            )
        return results

    def fetch_filings_listing(self, listing_url: str, section_label: str) -> List[Dict[str, Any]]:
        """Parses HTML table listings from SEBI HomeAction portal."""
        try:
            with httpx.Client(headers=self.DEFAULT_HEADERS, timeout=self.timeout, follow_redirects=True) as client:
                resp = client.get(listing_url)
                if resp.status_code != 200:
                    raise SebiConnectionError(f"HTTP {resp.status_code} received from SEBI: {listing_url}")
                html = resp.text
        except httpx.RequestError as exc:
            raise SebiConnectionError(f"Network error accessing SEBI endpoint {listing_url}: {exc}") from exc

        return self.parse_filings_html(html, section_label)

    def parse_filings_html(self, html: str, default_section: str = "DRHP") -> List[Dict[str, Any]]:
        """Extracts structured filing rows from SEBI HTML table."""
        soup = BeautifulSoup(html, "html.parser")
        tables = soup.find_all("table")
        if not tables:
            return []

        filings: List[Dict[str, Any]] = []
        target_table = tables[0]
        rows = target_table.find_all("tr")

        for row in rows:
            tds = row.find_all(["td", "th"])
            if len(tds) < 2:
                continue

            date_text = tds[0].get_text(strip=True)
            if date_text.lower() == "date":
                continue

            filing_date = parse_sebi_date(date_text)
            links = row.find_all("a", href=True)
            if not links:
                continue

            first_link = links[0]
            raw_title = first_link.get_text(strip=True)
            detail_url = urllib.parse.urljoin("https://www.sebi.gov.in", first_link["href"])

            direct_pdf_url = None
            for link in links:
                href = link["href"]
                if ".pdf" in href.lower():
                    direct_pdf_url = urllib.parse.urljoin("https://www.sebi.gov.in", href)
                    break

            issuer_name, doc_type = self._parse_issuer_and_type(raw_title, default_section)

            filings.append({
                "issuer_name": issuer_name,
                "raw_title": raw_title,
                "document_type": doc_type,
                "filing_date": filing_date,
                "detail_url": detail_url,
                "direct_pdf_url": direct_pdf_url,
                "section": default_section,
            })

        return filings

    def resolve_pdf_url(self, detail_url: str, direct_pdf_url: Optional[str] = None) -> Optional[str]:
        """
        Resolves the preferred downloadable PDF URL from the detail page or direct link.
        Prefers Draft Abridged Prospectus (DAP) or primary DRHP/RHP PDF.
        """
        if direct_pdf_url:
            return direct_pdf_url

        try:
            with httpx.Client(headers=self.DEFAULT_HEADERS, timeout=self.timeout, follow_redirects=True) as client:
                resp = client.get(detail_url)
                if resp.status_code != 200:
                    return None
                soup = BeautifulSoup(resp.text, "html.parser")

                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if ".pdf" in href.lower():
                        return urllib.parse.urljoin("https://www.sebi.gov.in", href)

                for elem in soup.find_all(["iframe", "embed"]):
                    src = elem.get("src", "")
                    if "file=" in src:
                        parts = src.split("file=")
                        if len(parts) > 1:
                            target = urllib.parse.unquote(parts[1])
                            return urllib.parse.urljoin("https://www.sebi.gov.in", target)
                    elif ".pdf" in src.lower():
                        return urllib.parse.urljoin("https://www.sebi.gov.in", src)

        except Exception:
            return None
        return None

    def probe_document_metadata(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Lightweight HEAD probe to check Content-Length and Last-Modified
        without downloading the binary payload. Returns None if probe fails.
        """
        try:
            with httpx.Client(headers=self.DEFAULT_HEADERS, timeout=min(self.timeout, 10.0), follow_redirects=True) as client:
                resp = client.head(url)
                if resp.status_code == 200:
                    cl = resp.headers.get("content-length")
                    lm = resp.headers.get("last-modified")
                    return {
                        "content_length": int(cl) if cl and cl.isdigit() else None,
                        "last_modified": lm,
                        "status_code": resp.status_code,
                    }
        except Exception:
            return None
        return None

    def fetch_document(self, url: str, max_retries: int = 1, expected_hash: Optional[str] = None) -> Dict[str, Any]:
        """
        Streams document bytes with bounded size and timeouts.
        Computes SHA-256 fingerprint.
        Includes bounded retry for transient network and streaming drops.
        Checks local disk cache if expected_hash is provided.
        """
        if expected_hash:
            cached_bytes = self.get_cached_document(expected_hash)
            if cached_bytes:
                return {
                    "payload": cached_bytes,
                    "file_size_bytes": len(cached_bytes),
                    "file_hash_sha256": expected_hash,
                    "content_type": "application/pdf",
                    "retrieved_at": datetime.now(timezone.utc),
                    "source_url": url,
                    "from_cache": True,
                }

        last_exc: Optional[Exception] = None
        for attempt in range(max_retries + 1):
            try:
                with httpx.Client(headers=self.DEFAULT_HEADERS, timeout=self.timeout, follow_redirects=True) as client:
                    with client.stream("GET", url) as resp:
                        if resp.status_code != 200:
                            raise SebiConnectionError(f"HTTP {resp.status_code} downloading document from {url}")

                        content_length = resp.headers.get("content-length")
                        if content_length and int(content_length) > self.max_size_bytes:
                            raise DocumentSizeLimitExceededError(
                                f"Document size {int(content_length)/(1024*1024):.1f}MB exceeds safety limit "
                                f"{self.max_size_bytes/(1024*1024):.1f}MB"
                            )

                        chunks = []
                        total_bytes = 0
                        hasher = hashlib.sha256()

                        for chunk in resp.iter_bytes(chunk_size=65536):
                            total_bytes += len(chunk)
                            if total_bytes > self.max_size_bytes:
                                raise DocumentSizeLimitExceededError(
                                    f"Document download streamed {total_bytes/(1024*1024):.1f}MB, exceeding limit"
                                )
                            chunks.append(chunk)
                            hasher.update(chunk)

                        payload = b"".join(chunks)
                        file_hash = hasher.hexdigest()
                        self.save_to_cache(file_hash, payload)
                        return {
                            "payload": payload,
                            "file_size_bytes": total_bytes,
                            "file_hash_sha256": file_hash,
                            "content_type": resp.headers.get("content-type", "application/pdf"),
                            "retrieved_at": datetime.now(timezone.utc),
                            "source_url": url,
                            "from_cache": False,
                        }
            except DocumentSizeLimitExceededError:
                raise
            except (httpx.RequestError, httpx.HTTPError) as exc:
                last_exc = exc
                if attempt < max_retries:
                    import time
                    time.sleep(1.0)
                    continue
                raise SebiConnectionError(f"Download failed for {url} after {max_retries} retry: {exc}") from exc
        if last_exc:
            raise SebiConnectionError(f"Download failed for {url}: {last_exc}") from last_exc

    def _parse_issuer_and_type(self, raw_title: str, default_type: str) -> Tuple[str, str]:
        """Extracts cleaned issuer name and document type from row title."""
        doc_type = detect_document_type(raw_title, "")
        if doc_type == "OFFER_DOCUMENT":
            doc_type = default_type

        title_clean = raw_title
        for token in [
            "- Draft Abridged Prospectus", "Draft Abridged Prospectus",
            "- DRHP", "DRHP", "- RHP", "RHP", "- Prospectus", "Prospectus",
        ]:
            title_clean = re.sub(re.escape(token), "", title_clean, flags=re.IGNORECASE)

        clean_name = title_clean.strip(" -")
        return clean_name or raw_title.strip(), doc_type
