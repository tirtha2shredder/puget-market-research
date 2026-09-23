"""Segment a listing history into campaigns, and pick the one that produced the sale.

The cycle-since-last-sale rule was too coarse. 2234 NW 62nd St was listed at $1,198,000
in September 2024, removed that November, sat off market for 18 months, relisted at
$1,080,000 in May 2026 and sold for $1,030,000. Measuring from the 2024 price gave -14.0%
and then discarded the home as stale; the honest figure is -4.6% against the $1,080,000
the 2026 buyer actually negotiated against.

A campaign break is a `Listing removed` followed by a gap of more than GAP_DAYS before
the next listing. Below that, a removal is MLS bookkeeping rather than a real withdrawal
-- 5821 3rd Ave NW shows a removal one day after a re-list inside a single continuous
110-day campaign, and splitting there would throw away six genuine price cuts.
"""
from datetime import date

GAP_DAYS = 90

# A second listing this soon after the first, with no removal between, is the same post being
# corrected rather than a new campaign. 8809 Earl Ave NW was listed at $975,000 and re-listed
# at $1,575,000 four days later, then sold for exactly $1,575,000: the first figure was a
# data-entry error nobody negotiated against, and treating it as the ask reported +61.5% over
# ask on a home that sold at its ask. The window is deliberately short -- a week -- so it only
# ever collapses a correction, never a genuine re-pricing.
OPENING_DAYS = 7

def campaign(events):
    """The events of the campaign that ended in the sale, newest first.

    `events` is newest-first with `_d` dates set. Returns (events, opening_event) or
    (None, None) when the sale has no priced listing behind it.
    """
    order = sorted(events, key=lambda e: e["_d"])          # oldest first
    sale = None
    for e in reversed(order):
        if e.get("event_name") == "Sold" and e.get("price"):
            sale = e; break
    if sale is None:
        return None, None
    upto = [e for e in order if e["_d"] <= sale["_d"]]

    # Walk backwards from the sale, stopping at the first real break.
    start = 0
    for i in range(len(upto) - 1, -1, -1):
        e = upto[i]
        name = str(e.get("event_name") or "")
        if name == "Sold" and e is not sale:
            start = i + 1; break
        if "rent" in name.lower():
            start = i + 1; break
        # A listing that opens after a long silence starts a fresh campaign even when no
        # removal was ever recorded. 411 10th Ave carries a `Listed $1,350,000` dated one day
        # after its 2019 sale and then nothing until `Listed $1,950,000` in August 2026: no
        # removal to break on, so the run spanned 2,627 days, took the 2019 price as the ask
        # and reported +48.9% over ask on a home that actually sold 3.1% over its real one.
        if i + 1 < len(upto):
            nxt = upto[i + 1]
            if (str(nxt.get("event_name")) in ("Listed", "Relisted")
                    and (nxt["_d"] - e["_d"]).days > GAP_DAYS):
                start = i + 1
                break
        if name == "Listing removed":
            later = [x for x in upto[i + 1:]
                     if str(x.get("event_name")) in ("Listed", "Relisted")]
            if not later:
                # No listing after this removal, so the only thing following it is the sale.
                # Within GAP_DAYS that is MLS bookkeeping around going pending. Years later it
                # is a genuine withdrawal, and the sale had no campaign of its own -- walking
                # further back reaches an unrelated old listing and reports its price as the
                # ask. That shipped: 6030 21st Ave S was listed at $239,000 in 2006, withdrawn
                # in 2015 and sold for $620,000 in 2026, and came out as +159% over ask. Three
                # more sales cleared +38% the same way, including one flagged here as a
                # bidding war.
                if (sale["_d"] - e["_d"]).days > GAP_DAYS:
                    start = i + 1
                    break
                continue
            if (later[0]["_d"] - e["_d"]).days > GAP_DAYS:
                start = i + 1; break
    run = upto[start:]
    opens = [e for e in run
             if str(e.get("event_name")) in ("Listed", "Relisted") and e.get("price")]
    if not opens:
        return run, None
    earliest = min(opens, key=lambda e: e["_d"])
    cluster = [e for e in opens
               if (e["_d"] - earliest["_d"]).days <= OPENING_DAYS]
    return run, max(cluster, key=lambda e: e["_d"])
