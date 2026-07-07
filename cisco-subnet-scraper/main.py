"""
main.py — CLI runner. Fetches + parses a registered adapter's source,
then writes CSV and firewall-ready plain text files via core.

Usage:
    python -m subnet_scraper.main <adapter_name> <output_basename> [options]

Examples:
    python -m subnet_scraper.main webex_calling data/section1_call_signaling
    python -m subnet_scraper.main webex_calling data/section2_device_config \\
        --target-section "(2) Device configuration"

Adding a new source later:
    1. Write adapters/<new_source>.py following webex_calling.py's shape
       (SOURCE_NAME, URL, fetch(), extract(html, **options)).
    2. Register it in adapters/__init__.py's ADAPTERS dict.
    3. Run: python -m subnet_scraper.main <new_source> <output_basename>
    No changes to core.py or main.py needed.
"""

import argparse
import sys

from . import core
from .adapters import ADAPTERS


def main():
    parser = argparse.ArgumentParser(description="Scrape IP subnet lists into CSV + EDL files.")
    parser.add_argument("--adapter", choices=sorted(ADAPTERS.keys()), help="Which source to scrape")
    parser.add_argument("--output_basename", help="e.g. data/section1_call_signaling")
    parser.add_argument(
        "--target-section",
        default=None,
        help='Adapter-specific section filter, e.g. "(2) Device configuration" '
        "(only meaningful for adapters that support sectioned pages)",
    )
    args = parser.parse_args()

    adapter = ADAPTERS[args.adapter]

    print(f"Fetching {adapter.URL} ...")
    html = adapter.fetch()

    extract_kwargs = {}
    if args.target_section is not None:
        extract_kwargs["target_section"] = args.target_section

    rows = adapter.extract(html, **extract_kwargs)
    if not rows:
        print("No rows parsed — the source page structure may have changed.", file=sys.stderr)
        sys.exit(1)

    #csv_path = f"{args.output_basename}.csv"
    #core.write_csv(rows, csv_path)
    cidr_path, mask_path = core.write_edl_files(rows, args.output_basename)

    print(f"Wrote {len(rows)} rows to:")
    #print(f"  {csv_path}")
    print(f"  {cidr_path}")
    print(f"  {mask_path}")


if __name__ == "__main__":
    main()
