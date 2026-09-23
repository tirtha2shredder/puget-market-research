"""Realtor.com sold-listing price history for the profile ZIPs.

Temporary market research, at the user's direction. Replicated from
ZacharyHampton/HomeHarvest. Against realtor.com's terms and fragile by design -- it depends
on an internal `rdc-client-version` header and an undocumented schema -- so this is a
throwaway research script, not part of the application.

Four details that each return HTTP 400 if wrong, all found the hard way:

  * `operationName` must be present and match the query's operation name.
  * The query must be whitespace-minified.
  * **No Authorization header.** The frontdoor endpoint is unauthenticated. A device token
    from graph.realtor.com is for other endpoints and sending it here breaks the call --
    which is why the public website returns 429 to an anonymous browser while this works.
    A different door, not better credentials.
  * `search_location` wants resolved geo text ("98028, Kenmore, WA"), not a raw ZIP, and
    `type` wants `["single_family"]` quoted rather than an enum.

And the reason there are two phases: `property_history` lives on the **`Home`** type, not on
the `SearchHome` type that `home_search` returns. Asking for it in the search yields one
all-null row, and batching ids through `home_search(query: {property_id: [...]})` returns
zero homes. So phase 1 collects ids per ZIP and phase 2 fetches each home individually.

Resumable: the checkpoint is keyed by property_id, so re-running skips what it already has.

    python /tmp/rdc_history.py
"""

import json
import os
import pickle
import sys
import time

import requests

sys.path.insert(0, "/Users/tirthanu/workspaces/REMaxxing")

GQL_URL = "https://www.realtor.com/frontdoor/graphql"
CHECKPOINT = "/tmp/rdc_history.pkl"

# Window matching the Redfin sold sweep, so the two are directly comparable.
SINCE, UNTIL = "2026-08-22", "2026-09-21"

# No throttling observed on this endpoint across ~15 calls, but paced anyway: a research
# script has no reason to be the fastest client they see.
INTERVAL = 1.5

HEADERS = {
    "Content-Type": "application/json", "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9", "Cache-Control": "no-cache",
    "Origin": "https://www.realtor.com", "Pragma": "no-cache",
    "Referer": "https://www.realtor.com/",
    "rdc-client-name": "RDC_WEB_SRP_FS_PAGE", "rdc-client-version": "3.0.2515",
    "sec-ch-ua": '"Google Chrome";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
    "sec-ch-ua-mobile": "?0", "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty", "sec-fetch-mode": "cors", "sec-fetch-site": "same-site",
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"),
    "x-is-bot": "false",
}

SUGGEST = """query Search_suggestions($searchInput: SearchSuggestionsInput!) {
  search_suggestions(search_input: $searchInput) {
    geo_results { type text geo { area_type postal_code city state_code } }
  }
}"""

# Narrow on purpose. The full HOMES_DATA fragment returns photos, schools, agent records and
# popularity metrics that would be discarded immediately.
SEARCH = """query GetHomeSearch($search_location: SearchLocation, $offset: Int) {
    homeSearch: home_search(
        query: {
            search_location: $search_location
            status: [sold]
            sold_date: { min: "%s", max: "%s" }
            type: ["single_family"]
        }
        sort: [{ field: sold_date, direction: desc }]
        limit: 200
        offset: $offset
    ) {
        count
        total
        results {
            property_id
            location { address { line city state_code postal_code } }
            description { sqft beds baths year_built }
            last_sold_price
            last_sold_date
        }
    }
}""" % (SINCE, UNTIL)

DETAIL = """query GetHomeDetails($property_id: ID!) {
    home(property_id: $property_id) {
        property_id
        list_date
        list_price
        last_sold_price
        last_sold_date
        pending_date
        status
        mls_status
        location { address { line city state_code postal_code } }
        description { sqft beds baths year_built type }
        property_history { date event_name price }
    }
}"""


def post(session, query, variables, operation):
    payload = {"operationName": operation, "query": " ".join(query.split()),
               "variables": variables}
    r = session.post(GQL_URL, headers=HEADERS,
                     data=json.dumps(payload, separators=(",", ":")), timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:160]}")
    body = r.json()
    if body.get("errors"):
        raise RuntimeError(f"graphql: {json.dumps(body['errors'])[:240]}")
    return body.get("data") or {}


def profile_zips():
    from remaxxing import db, profiles
    conn = db.connect("/Users/tirthanu/workspaces/REMaxxing/remaxxing.db")
    try:
        return sorted(profiles.load_active_profiles(conn)[0].zips)
    finally:
        conn.close()


def main():
    session = requests.Session()
    done = pickle.load(open(CHECKPOINT, "rb")) if os.path.exists(CHECKPOINT) else {}
    print(f"checkpoint holds {len(done)} homes already", flush=True)

    # ---- phase 1: every sold single-family home per ZIP, for its property_id
    index = {}
    for n, zip_code in enumerate(profile_zips(), 1):
        try:
            text = post(session, SUGGEST, {"searchInput": {"search_term": zip_code}},
                        "Search_suggestions")
            geo = ((text.get("search_suggestions") or {}).get("geo_results") or [])
            if not geo:
                print(f"  [{n}] {zip_code}: no geo match", flush=True)
                continue
            offset, total = 0, None
            while total is None or offset < total:
                data = post(session, SEARCH,
                            {"search_location": {"location": geo[0]["text"]},
                             "offset": offset}, "GetHomeSearch")
                block = data.get("homeSearch") or {}
                total = block.get("total") or 0
                rows = block.get("results") or []
                for h in rows:
                    index[h["property_id"]] = h
                offset += len(rows) or 200
                if not rows:
                    break
                time.sleep(INTERVAL)
            print(f"  [{n}] {zip_code} ({geo[0]['text']}): {total} sold", flush=True)
        except Exception as exc:
            print(f"  [{n}] {zip_code}: FAILED {type(exc).__name__}: "
                  f"{str(exc)[:110]}", flush=True)
        time.sleep(INTERVAL)

    print(f"\nphase 1: {len(index)} distinct sold homes across the ZIPs", flush=True)

    # ---- phase 2: property_history, one call per home, because it is on the Home type
    todo = [pid for pid in index if pid not in done]
    print(f"phase 2: fetching history for {len(todo)} ({len(index) - len(todo)} cached)\n",
          flush=True)
    for n, pid in enumerate(todo, 1):
        try:
            data = post(session, DETAIL, {"property_id": pid}, "GetHomeDetails")
            home = data.get("home") or {}
            if not home:
                done[pid] = {"error": "no home returned"}
            else:
                home["_search"] = index[pid]
                done[pid] = home
        except Exception as exc:
            done[pid] = {"error": f"{type(exc).__name__}: {str(exc)[:90]}"}
        if n % 20 == 0:
            pickle.dump(done, open(CHECKPOINT, "wb"))
            ok = sum(1 for v in done.values() if "error" not in v)
            print(f"  [{n}/{len(todo)}] {ok} fetched, {len(done) - ok} failed", flush=True)
        time.sleep(INTERVAL)

    pickle.dump(done, open(CHECKPOINT, "wb"))
    ok = sum(1 for v in done.values() if "error" not in v)
    hist = sum(1 for v in done.values()
               if "error" not in v and any(
                   e.get("date") for e in (v.get("property_history") or [])))
    print(f"\nDONE: {ok} fetched, {len(done) - ok} failed, "
          f"{hist} with a real property_history", flush=True)
    print(f"checkpoint: {CHECKPOINT}", flush=True)


if __name__ == "__main__":
    main()
