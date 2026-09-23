"""Realtor.com sold-listing price history across the expanded King/Snohomish footprint.

Same mechanism as /tmp/rdc_history.py -- see that file for the four HTTP-400 traps and for
why `property_history` needs a second phase. This one differs in three ways:

  * It reads the ZIP list from /tmp/zips_wide.json (89 ZIPs) rather than the profile.
  * Phase 1 is checkpointed too. At 89 ZIPs a mid-sweep failure is expensive enough to be
    worth resuming from, which it was not at 18.
  * It shares /tmp/rdc_history.pkl with the original run, so the ~400 homes already fetched
    for the first 18 ZIPs are not fetched again.

The window is held at the original 22 Aug - 21 Sep 2026 deliberately. Shifting it to a
rolling 30 days would invalidate every cached detail and make the expanded figures
non-comparable with what has already been reported.

    python /tmp/rdc_wide.py --phase1     # resolve geo + count, no detail fetches
    python /tmp/rdc_wide.py              # both phases, resumable
"""

import json
import os
import pickle
import sys
import time

import requests

sys.path.insert(0, "/tmp")
from rdc_history import GQL_URL, HEADERS, INTERVAL, SEARCH, SUGGEST, post  # noqa: E402

ZIPS = "/tmp/zips_wide.json"
INDEX = "/tmp/rdc_wide_index.pkl"       # phase 1: property_id -> search row
DETAILS = "/tmp/rdc_wide_details.pkl"   # phase 2

# `coordinate` and `href` carry the two things the Redfin sweep used to supply: a point to
# plot and a link to follow. Getting them here removes that whole second scrape, and with it
# the address-normalisation match that silently dropped homes whose street spelling differed
# between the two sites. `coordinate` sits on the *address*, not on the location -- three of
# the four plausible spellings return HTTP 400.
#
# Not shared with /tmp/rdc_history.pkl: those 400 records were fetched without these two
# fields, so reusing them would leave a subset of homes unplottable and unlinkable. Refetching
# all 1,563 costs ~40 minutes and keeps one record shape.
DETAIL = """query GetHomeDetails($property_id: ID!) {
    home(property_id: $property_id) {
        property_id
        href
        list_date
        list_price
        last_sold_price
        last_sold_date
        pending_date
        status
        mls_status
        location { address { line city state_code postal_code
                             coordinate { lat lon } } }
        description { sqft beds baths year_built type }
        property_history { date event_name price }
    }
}"""


def phase1(session, zips):
    """Every sold single-family home per ZIP, for its property_id. Checkpointed per ZIP."""
    state = pickle.load(open(INDEX, "rb")) if os.path.exists(INDEX) else {"index": {}, "done": {}}
    index, done = state["index"], state["done"]
    todo = [z for z in zips if z not in done]
    print(f"phase 1: {len(todo)} ZIPs to sweep, {len(done)} already done "
          f"({len(index)} homes indexed)", flush=True)
    for n, zip_code in enumerate(todo, 1):
        try:
            text = post(session, SUGGEST, {"searchInput": {"search_term": zip_code}},
                        "Search_suggestions")
            geo = ((text.get("search_suggestions") or {}).get("geo_results") or [])
            if not geo:
                done[zip_code] = {"n": 0, "geo": None, "error": "no geo match"}
                print(f"  [{n}/{len(todo)}] {zip_code}: no geo match", flush=True)
                continue
            label, offset, total, got = geo[0]["text"], 0, None, 0
            while total is None or offset < total:
                data = post(session, SEARCH,
                            {"search_location": {"location": label}, "offset": offset},
                            "GetHomeSearch")
                block = data.get("homeSearch") or {}
                total = block.get("total") or 0
                rows = block.get("results") or []
                for h in rows:
                    index[h["property_id"]] = h
                got += len(rows)
                offset += len(rows) or 200
                if not rows:
                    break
                time.sleep(INTERVAL)
            done[zip_code] = {"n": total, "geo": label}
            print(f"  [{n}/{len(todo)}] {zip_code} ({label}): {total} sold, {got} rows",
                  flush=True)
        except Exception as exc:
            done[zip_code] = {"n": None, "error": f"{type(exc).__name__}: {str(exc)[:90]}"}
            print(f"  [{n}/{len(todo)}] {zip_code}: FAILED {type(exc).__name__}: "
                  f"{str(exc)[:90]}", flush=True)
        pickle.dump({"index": index, "done": done}, open(INDEX, "wb"))
        time.sleep(INTERVAL)
    failed = [z for z, v in done.items() if v.get("error")]
    print(f"\nphase 1 complete: {len(index)} distinct sold homes across "
          f"{len(done) - len(failed)} ZIPs; {len(failed)} failed: {failed}", flush=True)
    return index


def phase2(session, index):
    """property_history per home. It lives on the Home type, so one call each."""
    done = pickle.load(open(DETAILS, "rb")) if os.path.exists(DETAILS) else {}
    todo = [pid for pid in index if pid not in done]
    print(f"\nphase 2: {len(todo)} to fetch, {len(index) - len(todo)} already cached "
          f"(~{len(todo) * INTERVAL / 60:.0f} min)\n", flush=True)
    for n, pid in enumerate(todo, 1):
        try:
            home = (post(session, DETAIL, {"property_id": pid},
                         "GetHomeDetails").get("home") or {})
            if home:
                home["_search"] = index[pid]
                done[pid] = home
            else:
                done[pid] = {"error": "no home returned"}
        except Exception as exc:
            done[pid] = {"error": f"{type(exc).__name__}: {str(exc)[:90]}"}
        if n % 25 == 0:
            pickle.dump(done, open(DETAILS, "wb"))
            ok = sum(1 for v in done.values() if "error" not in v)
            print(f"  [{n}/{len(todo)}] {ok} fetched, {len(done) - ok} failed", flush=True)
        time.sleep(INTERVAL)
    pickle.dump(done, open(DETAILS, "wb"))
    ok = sum(1 for v in done.values() if "error" not in v)
    hist = sum(1 for v in done.values() if "error" not in v
               and any(e.get("date") for e in (v.get("property_history") or [])))
    print(f"\nDONE: {ok} fetched, {len(done) - ok} failed, {hist} with a price history",
          flush=True)


def main():
    zips = json.load(open(ZIPS))
    session = requests.Session()
    index = phase1(session, zips)
    if "--phase1" in sys.argv:
        print("\nstopping after phase 1 (--phase1)", flush=True)
        return
    phase2(session, index)


if __name__ == "__main__":
    main()
