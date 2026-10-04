"""Where the pipeline keeps its working data.

Everything here was in /tmp, and /tmp got cleared: 15,874 fetched listings and 21 MB of
census geometry, both recoverable only by downloading them again. The scripts survived because
they were committed; the data did not because it was gitignored and parked somewhere the OS
reclaims.

So working data lives under a durable cache root instead, overridable with
PUGET_CACHE for anyone who wants it elsewhere. Still gitignored -- the point is that it
survives a reboot, not that it belongs in the repository.
"""

import os
from pathlib import Path

CACHE = Path(os.environ.get("PUGET_CACHE")
             or (Path.home() / ".cache" / "puget-market-research"))
CACHE.mkdir(parents=True, exist_ok=True)


def p(name: str) -> str:
    """A path inside the cache, as a string, so call sites read like the old literals."""
    return str(CACHE / name)


# Reference data: static, large, and expensive to re-download.
WA_ZIPS = p("wa_zips.json")              # census ZCTA geometry for Washington
ZCTA_COUNTY = p("zcta_county.txt")       # ZCTA-to-county relationship file
WATER = p("water_geo.json")              # TIGER AREAWATER for King and Snohomish

# Fetched data: checkpointed, so losing it costs hours rather than correctness.
INDEX = p("index.pkl")
DETAILS = p("details.pkl")

# Build intermediates.
PAYLOAD = p("map_payload.json")
LEVELS = p("levels.json")
