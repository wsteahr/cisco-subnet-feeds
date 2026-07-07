"""subnet_scraper — modular IP/CIDR scraper with pluggable source adapters."""

from . import core
from .adapters import ADAPTERS

__all__ = ["core", "ADAPTERS"]