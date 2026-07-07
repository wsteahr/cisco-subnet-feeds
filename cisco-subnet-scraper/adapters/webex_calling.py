"""
adapters/webex_calling.py — source-specific logic for scraping the
"IP Subnets for Webex Calling services" table from Cisco's Webex Calling
port-reference help page.

Every adapter module is expected to expose:
    SOURCE_NAME: str
    URL: str
    fetch() -> str                          (rendered HTML)
    extract(html: str, **options) -> list[dict]   (rows: category, ip_subnet)

This keeps all of Cisco's page-specific quirks (the table-of-contents
duplicate headings, the 2-column IP grid layout, "(N) ..." section
headers) isolated from core.py and from other adapters.
"""

import re

from bs4 import BeautifulSoup

from .. import core  # fetch_rendered_html, IP_PATTERN

SOURCE_NAME = "webex_calling"
URL = "https://help.webex.com/en-us/article/b2exve/Port-Reference-Information-for-Webex-Calling"

# The heading text (also repeated in the page's table-of-contents, which
# is why find_target_table() below has to validate by content, not just
# proximity to a heading).
HEADING_TEXT = "IP Subnets for Webex Calling services"

# Matches a section header cell, e.g. "(1) Call Signaling, Media, NTP & CScan"
SECTION_HEADER_PATTERN = re.compile(r"^\(\d+\)\s")

# Default section to extract if the caller doesn't specify one.
DEFAULT_TARGET_SECTION = "(1) Call Signaling"


def fetch() -> str:
    """Render the page and return its HTML."""
    return core.fetch_rendered_html(URL, wait_selector="table")


def _table_looks_like_ip_subnets(table) -> bool:
    """Heuristic: the real table's cells are full of dotted IPv4 subnets."""
    text = table.get_text(" ", strip=True)
    return len(core.IP_PATTERN.findall(text)) >= 5


def _find_target_table(soup: BeautifulSoup):
    """The page repeats every section heading in a table-of-contents near
    the top, so a naive "find heading, take next table" grabs the wrong
    table. Instead: check every element matching HEADING_TEXT, and accept
    the first one whose following table actually looks like IP subnets."""
    candidates = soup.find_all(
        lambda tag: tag.name in ("h1", "h2", "h3", "h4", "h5", "strong", "b", "p", "a")
        and HEADING_TEXT.lower() in tag.get_text(strip=True).lower()
    )
    if not candidates:
        raise ValueError(f"Could not find any heading containing: {HEADING_TEXT!r}")

    for heading in candidates:
        table = heading.find_next("table")
        if table is not None and _table_looks_like_ip_subnets(table):
            return table

    for table in soup.find_all("table"):
        if _table_looks_like_ip_subnets(table):
            return table

    raise ValueError("Found heading(s) but no table with IP-subnet-like content nearby.")


def _parse_table(table, target_section: str) -> list[dict]:
    """Walk the table's rows. Cisco lays this out as a 2-column grid with
    section-header rows interspersed (e.g. "(1) Call Signaling..."), not a
    clean category+value column pairing. Only text that actually looks
    like an IP/subnet is kept, and parsing stops as soon as the NEXT
    section header (i.e. we've moved past the target section) appears."""
    rows = []
    current_section = ""
    started = False

    for tr in table.find_all("tr"):
        cells = tr.find_all(["td", "th"])
        if not cells:
            continue
        texts = [c.get_text(separator="\n", strip=True) for c in cells]

        if tr.find("th") and not started:
            continue

        header_match = next((t for t in texts if SECTION_HEADER_PATTERN.match(t)), None)
        if header_match:
            current_section = header_match
            if target_section.lower() in current_section.lower():
                started = True
                continue
            elif started:
                break  # moved past the target section — stop
            else:
                continue  # not our section yet

        if not started:
            continue

        for cell_text in texts:
            for line in cell_text.splitlines():
                line = line.strip()
                if core.IP_PATTERN.fullmatch(line):
                    rows.append({"category": current_section, "ip_subnet": line})

    return rows


def extract(html: str, target_section: str = DEFAULT_TARGET_SECTION) -> list[dict]:
    """Parse `html` and return rows for the given section, e.g.
    "(1) Call Signaling", "(2) Device configuration", "(3) Webex App"."""
    soup = BeautifulSoup(html, "html.parser")
    table = _find_target_table(soup)
    return _parse_table(table, target_section)
