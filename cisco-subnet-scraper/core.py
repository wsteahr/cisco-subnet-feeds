"""
core.py — reusable machinery shared by every source-specific adapter.

Nothing in this file should know anything about a specific website's HTML
structure. That logic belongs in adapters/<source>.py instead.

Provides:
    - fetch_rendered_html(url): render a JS page with a headless browser
    - IP_PATTERN: regex for validating IPv4 addresses/CIDRs
    - to_network(cidr): parse a CIDR or bare IP into an ipaddress.IPv4Network
    - write_csv(rows, path): write [{"category":..., "ip_subnet":...}, ...] to CSV
    - write_edl_files(rows, base_path): write "<base>_cidr.txt" and
      "<base>_mask.txt" firewall-ready plain text files
"""

import csv
import ipaddress
import re

from playwright.sync_api import sync_playwright

# Matches a dotted IPv4 address, optionally with a /prefix, e.g.
# "23.89.0.0" or "23.89.0.0/16".
IP_PATTERN = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?\b")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)


def fetch_rendered_html(
    url: str,
    wait_selector: str = "table",
    wait_selector_timeout_ms: int = 15000,
    goto_timeout_ms: int = 60000,
    user_agent: str = DEFAULT_USER_AGENT,
) -> str:
    """Load `url` in a headless Chromium browser and return the fully
    rendered HTML, after the page's JavaScript has run.

    `wait_selector` is an extra safety wait for some element that only
    appears once the page's data has actually loaded (defaults to any
    <table>). Pass None to skip this extra wait.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=user_agent)
        page.goto(url, wait_until="networkidle", timeout=goto_timeout_ms)

        if wait_selector:
            try:
                page.wait_for_selector(wait_selector, timeout=wait_selector_timeout_ms)
            except Exception:
                pass  # fall through; caller's parser will raise if content is missing

        html = page.content()
        browser.close()
        return html


def to_network(cidr: str) -> ipaddress.IPv4Network:
    """'23.89.0.0/16' -> IPv4Network. A bare IP like '3.14.211.49' is
    treated as a /32 host."""
    if "/" not in cidr:
        cidr = f"{cidr}/32"
    return ipaddress.ip_network(cidr, strict=False)


def try_parse_network(token: str):
    """Attempt to parse `token` as an IPv4 or IPv6 network/host. Returns
    an ipaddress network object on success, or None if `token` isn't a
    valid address/CIDR. Safer and more general than IP_PATTERN for
    sources that list arbitrary tokens (e.g. bullet lists) — this covers
    IPv6 and bare hosts too, not just IPv4-with-optional-prefix strings.
    """
    token = token.strip()
    if not token:
        return None
    if "/" not in token:
        token = f"{token}/32" if ":" not in token else f"{token}/128"
    try:
        return ipaddress.ip_network(token, strict=False)
    except ValueError:
        return None


def write_csv(rows: list[dict], path: str) -> None:
    """Write rows (each a dict with at least 'category' and 'ip_subnet'
    keys) to a CSV file at `path`."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["category", "ip_subnet"])
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {"category": row.get("category", ""), "ip_subnet": row.get("ip_subnet", "")}
            )


def write_edl_files(rows: list[dict], base_path: str) -> tuple[str, str]:
    """Write two firewall-ready plain text files from `rows`:
        <base_path>_cidr.txt  - one CIDR per line, e.g. "23.89.0.0/16"
                                 (IPv4 and IPv6 both included)
        <base_path>_mask.txt  - one "network mask" pair per line,
                                 e.g. "23.89.0.0 255.255.0.0"
                                 (IPv4 only — dotted-decimal masks don't
                                 apply to IPv6; those entries are skipped
                                 here but still appear in the CIDR file)
    Returns (cidr_path, mask_path). Rows with invalid IP data are skipped.
    """
    cidr_path = f"{base_path}_cidr_plaintext"
    mask_path = f"{base_path}_mask_plaintext"

    cidr_lines = []
    mask_lines = []

    for row in rows:
        raw = row.get("ip_subnet", "").strip()
        if not raw:
            continue
        network = try_parse_network(raw)
        if network is None:
            continue
        cidr_lines.append(f"{network.network_address}/{network.prefixlen}")
        if network.version == 4:
            mask_lines.append(f"{network.network_address} {network.netmask}")

    with open(cidr_path, "w", encoding="utf-8") as f:
        f.write("\n".join(cidr_lines) + "\n")

    with open(mask_path, "w", encoding="utf-8") as f:
        f.write("\n".join(mask_lines) + "\n")

    return cidr_path, mask_path