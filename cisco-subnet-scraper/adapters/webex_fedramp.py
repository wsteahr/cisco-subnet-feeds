"""
adapters/webex_fedramp.py — source-specific logic for scraping IP range
bullet-lists from Cisco's "Network requirements for Webex for Government
(FedRAMP)" help page.

Unlike webex_calling.py (which scrapes a <table>), this page presents its
IP ranges as a plain bullet list (<ul><li>), with entries like:
    23.89.18.0/23 (23.89.18.0 to 23.89.19.255)
    2607:fcf0:1100:1000::/52
i.e. a leading CIDR (IPv4 or IPv6), sometimes followed by a human-readable
"(x to y)" annotation that should be discarded.

Every adapter module exposes:
    SOURCE_NAME: str
    URL: str
    fetch() -> str
    extract(html: str, **options) -> list[dict]   (rows: category, ip_subnet)
"""

from bs4 import BeautifulSoup

from .. import core  # fetch_rendered_html, try_parse_network

SOURCE_NAME = "webex_fedramp"
URL = (
    "https://help.webex.com/en-us/article/n71sm9e/"
    "Network-requirements-for-Webex-for-Government-(FedRAMP)"
)

# The page has more than one bullet list of IP ranges. Pick which one to
# extract via the `target_section` option — this substring is matched
# against the nearest preceding heading/paragraph text (case-insensitive).
HEADINGS = {
    "meetings": "Meetings ports and IP ranges quick reference",
    "calling": "IP subnets for Webex Calling services",
}
DEFAULT_TARGET_HEADING = HEADINGS["meetings"]

MIN_VALID_ENTRIES = 5  # heuristic: a real IP list has several entries


def fetch() -> str:
    """Render the page and return its HTML."""
    return core.fetch_rendered_html(URL, wait_selector="ul")


def _list_looks_like_ip_ranges(ul) -> bool:
    """Heuristic: most <li> children parse as a valid IPv4/IPv6 network."""
    items = ul.find_all("li", recursive=False)
    if len(items) < MIN_VALID_ENTRIES:
        return False
    valid = 0
    for li in items:
        token = li.get_text(strip=True).split()[0] if li.get_text(strip=True) else ""
        if core.try_parse_network(token) is not None:
            valid += 1
    return valid >= MIN_VALID_ENTRIES


def _find_target_list(soup: BeautifulSoup, target_section: str):
    """Find the heading/paragraph matching `target_section`, then return
    the first following <ul> whose content actually looks like an IP
    range list (guards against picking up an unrelated bullet list that
    happens to appear nearby)."""
    candidates = soup.find_all(
        lambda tag: tag.name in ("h1", "h2", "h3", "h4", "h5", "strong", "b", "p", "a")
        and target_section.lower() in tag.get_text(strip=True).lower()
    )
    if not candidates:
        raise ValueError(f"Could not find any heading containing: {target_section!r}")

    for heading in candidates:
        ul = heading.find_next("ul")
        if ul is not None and _list_looks_like_ip_ranges(ul):
            return ul

    for ul in soup.find_all("ul"):
        if _list_looks_like_ip_ranges(ul):
            return ul

    raise ValueError("Found heading(s) but no <ul> with IP-range-like content nearby.")


def extract(html: str, target_section: str = DEFAULT_TARGET_HEADING) -> list[dict]:
    """Parse `html` and return rows for the bullet list under
    `target_section`. Each <li> may be a bare CIDR/IP (IPv4 or IPv6), or a
    CIDR followed by a "(x to y)" annotation — only the leading CIDR/IP
    token is kept, and the annotation is discarded."""
    soup = BeautifulSoup(html, "html.parser")
    ul = _find_target_list(soup, target_section)

    rows = []
    for li in ul.find_all("li", recursive=False):
        text = li.get_text(strip=True)
        if not text:
            continue
        token = text.split()[0]  # drop any trailing "(x to y)" annotation
        network = core.try_parse_network(token)
        if network is None:
            continue
        rows.append({"category": target_section, "ip_subnet": token})

    return rows