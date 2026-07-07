"""
adapters/ — one module per source website. Each module exposes:
    SOURCE_NAME, URL, fetch(), extract(html, **options)

To add a new source, drop a new module in here following the pattern in
webex_calling.py, then register it in ADAPTERS below.
"""

from . import webex_calling
from . import webex_fedramp
from . import webex_meetings

ADAPTERS = {
    webex_calling.SOURCE_NAME: webex_calling,
    webex_fedramp.SOURCE_NAME: webex_fedramp,
    webex_meetings.SOURCE_NAME: webex_meetings,
    # Add future sources here, e.g.:
    # some_other_site.SOURCE_NAME: some_other_site,
}