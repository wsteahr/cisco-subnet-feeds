"""
adapters/webex_meetings.py — source-specific logic for scraping the
"IPv4 Subnets for Media Services" and "IPv6 Address Ranges for Media
Services" tables from Cisco's "Network Requirements for Webex Services"
help page (covers Webex Meetings / Messaging media services).

Both tables are located by their own caption text — there's no separate
preceding heading to anchor on for the IPv4 table (its caption cell IS
the anchor), so both are found by scanning all tables for one whose text
contains the expected caption and has enough IP/subnet-like entries.

Some IPv4 entries have a trailing "*", e.g. "4.152.214.0/24*". Per
Cisco's own footnote on this page, the asterisk marks Azure data center
subnets used only for Video Integration for Microsoft Teams (CVI) — not
general Webex media traffic — so these are excluded by default
(skip_starred=True).

Every adapter module exposes:
    SOURCE_NAME: str
    URL: str
    fetch() -> str
    extract(html: str, **options) -> list[dict]   (rows: category, ip_subnet)
"""

from bs4 import BeautifulSoup

from .. import core  # fetch_rendered_html, try_parse_network

SOURCE_NAME = "webex_meetings"
URL = "https://help.webex.com/en-us/article/WBX000028782/Network-Requirements-for-Webex-Services"

IPV4_TABLE_CAPTION = "IPv4 Subnets for Media Services"
IPV6_TABLE_CAPTION = "IPv6 Address Ranges for Media Services"

IPV4_CATEGORY_LABEL = "IPv4 Subnets for Media Services"
IPV6_CATEGORY_LABEL = "IPv6 Address Ranges for Media Services"

MIN_VALID_ENTRIES_IPV4 = 10  # the real IPv4 table has ~30 entries
MIN_VALID_ENTRIES_IPV6 = 2   # the real IPv6 table only has a few entries


def fetch() -> str:
    """Render the page and return its HTML."""
    return core.fetch_rendered_html(URL, wait_selector="table")


def _count_valid_entries(table) -> int:
    """Count cells in `table` that parse as a valid IPv4/IPv6 network
    (ignoring a trailing '*', which some cells use for footnote markers)."""
    valid = 0
    for cell in table.find_all(["td", "th"]):
        token = cell.get_text(strip=True).replace("*", "").strip()
        if token and core.try_parse_network(token) is not None:
            valid += 1
    return valid


def _find_table_by_caption(soup: BeautifulSoup, caption: str, min_valid: int):
    """Find the table whose own text contains `caption` and which has
    enough IP-subnet-like content to confirm it's the right one (guards
    against a stray mention of the caption text elsewhere, e.g. a TOC)."""
    for table in soup.find_all("table"):
        text = table.get_text(" ", strip=True)
        if caption.lower() not in text.lower():
            continue
        if _count_valid_entries(table) >= min_valid:
            return table
    return None


def _rows_from_table(table, category_label: str, skip_starred: bool) -> list[dict]:
    rows = []
    for tr in table.find_all("tr"):
        for cell in tr.find_all(["td", "th"]):
            text = cell.get_text(strip=True)
            if not text:
                continue

            has_star = "*" in text
            token = text.replace("*", "").strip()

            network = core.try_parse_network(token)
            if network is None:
                continue  # not a real IP/subnet (e.g. the caption cell itself)

            if has_star and skip_starred:
                continue

            rows.append({"category": category_label, "ip_subnet": token})
    return rows


def extract(
    html: str,
    skip_starred: bool = True,
    include_ipv6: bool = True,
) -> list[dict]:
    """Parse `html` and return rows from the IPv4 Subnets for Media
    Services table, plus the IPv6 Address Ranges for Media Services
    table if `include_ipv6` is True (default).

    Cells containing a trailing "*" (Azure/CVI-only subnets) are skipped
    by default — pass skip_starred=False to include them anyway.
    """
    soup = BeautifulSoup(html, "html.parser")

    ipv4_table = _find_table_by_caption(soup, IPV4_TABLE_CAPTION, MIN_VALID_ENTRIES_IPV4)
    if ipv4_table is None:
        raise ValueError(
            f"Could not find a table containing {IPV4_TABLE_CAPTION!r} "
            "with IP-subnet-like content."
        )
    rows = _rows_from_table(ipv4_table, IPV4_CATEGORY_LABEL, skip_starred)

    if include_ipv6:
        ipv6_table = _find_table_by_caption(soup, IPV6_TABLE_CAPTION, MIN_VALID_ENTRIES_IPV6)
        if ipv6_table is not None:
            rows += _rows_from_table(ipv6_table, IPV6_CATEGORY_LABEL, skip_starred)
        # If the IPv6 table isn't found, silently skip it rather than
        # failing the whole extraction — the IPv4 table is the primary
        # target and may still be usable on its own.

    return rows