"""Six months of sold single-family, condo and townhome listings across the 94 profile ZIPs.

Supersedes /tmp/rdc_wide.py, which fetched one month of single-family only. Six months is
fetched once and the report's window selector filters on sold_date in the browser, so one and
three months cost nothing extra.

Two things this adds beyond scope:

  * **Retry with backoff.** The old script recorded any exception as a permanent per-home
    error, so a burst of 429s would have been written into the checkpoint and quietly excluded
    from the report. A throttle must cost a delay, never a record.

  * **Telemetry.** Interval is a command-line argument and every request's status and latency
    is recorded, because the safe rate is a measurement rather than a guess. A small sample at
    a fast interval proves little on its own: rate limits usually trigger on a rolling window,
    so a test has to run long enough to cross one.

    python /tmp/rdc_v2.py --phase1
    python /tmp/rdc_v2.py --probe 500 --interval 0.15
    python /tmp/rdc_v2.py --interval 0.9
"""

import json
import os
import pickle
import statistics
import sys
import time

import pathlib

import paths

_HERE = pathlib.Path(__file__).parent
import requests

sys.path.insert(0, __import__("os").path.dirname(__file__))
from rdc_history import GQL_URL, HEADERS, SUGGEST  # noqa: E402

ZIPS = str(_HERE / "zips_wide.json")
INDEX = paths.INDEX        # phase 1: property_id -> search row
DETAILS = paths.DETAILS    # phase 2: property_id -> full record
TELEMETRY = paths.p("rate.json")

SINCE, UNTIL = "2026-03-22", "2026-09-28"
TYPES = '"single_family","condos","townhomes"'

RETRY_STATUS = (403, 408, 429, 500, 502, 503, 504)
MAX_RETRY = 6

SEARCH = """query GetHomeSearch($search_location: SearchLocation, $offset: Int) {
    homeSearch: home_search(
        query: {
            search_location: $search_location
            status: [sold]
            sold_date: { min: "%s", max: "%s" }
            type: [%s]
        }
        sort: [{ field: sold_date, direction: desc }]
        limit: 200
        offset: $offset
    ) {
        count total
        results {
            property_id
            location { address { line city state_code postal_code } }
            description { sqft beds baths year_built type }
        }
    }
}""" % (SINCE, UNTIL, TYPES)

DETAIL = """query GetHomeDetails($property_id: ID!) {
    home(property_id: $property_id) {
        property_id
        href
        list_date
        list_price
        pending_date
        status
        mls_status
        location { address { line city state_code postal_code
                            coordinate { lat lon } } }
        description { sqft beds baths year_built type }
        property_history { date event_name price }
    }
}"""

STATS = {"n": 0, "retries": 0, "status": {}, "latency": []}


def post(session, query, variables, operation, interval):
    """One request, retried on the statuses that mean "slow down" rather than "no"."""
    payload = {"operationName": operation, "query": " ".join(query.split()),
               "variables": variables}
    body = json.dumps(payload, separators=(",", ":"))
    for attempt in range(MAX_RETRY):
        t0 = time.time()
        r = session.post(GQL_URL, headers=HEADERS, data=body, timeout=60)
        STATS["n"] += 1
        STATS["latency"].append(round(time.time() - t0, 3))
        STATS["status"][r.status_code] = STATS["status"].get(r.status_code, 0) + 1
        if r.status_code in RETRY_STATUS:
            STATS["retries"] += 1
            wait = min(60, (2 ** attempt) * max(interval, 0.5))
            print(f"    HTTP {r.status_code}, backing off {wait:.1f}s "
                  f"(attempt {attempt + 1}/{MAX_RETRY})", flush=True)
            time.sleep(wait)
            continue
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:160]}")
        out = r.json()
        if out.get("errors"):
            raise RuntimeError(f"graphql: {json.dumps(out['errors'])[:200]}")
        return out.get("data") or {}
    raise RuntimeError(f"gave up after {MAX_RETRY} retries")


def report(label):
    lat = STATS["latency"]
    if not lat:
        print(f"{label}: no requests")
        return
    ok = STATS["status"].get(200, 0)
    bad = {k: v for k, v in STATS["status"].items() if k != 200}
    print(f"{label}: {STATS['n']} requests, {ok} ok"
          f"{', ' + str(bad) if bad else ''}, {STATS['retries']} retried")
    print(f"   latency  median {statistics.median(lat):.3f}s  "
          f"p95 {sorted(lat)[int(len(lat) * .95)]:.3f}s  max {max(lat):.3f}s")
    half = len(lat) // 2
    if half >= 10:
        # Latency creeping across the run is how soft throttling shows up before any 429.
        print(f"   first half median {statistics.median(lat[:half]):.3f}s  "
              f"second half {statistics.median(lat[half:]):.3f}s")
    json.dump({"status": STATS["status"], "retries": STATS["retries"],
               "latency": lat}, open(TELEMETRY, "w"))


def phase1(session, interval):
    state = (pickle.load(open(INDEX, "rb")) if os.path.exists(INDEX)
             else {"index": {}, "done": {}})
    index, done = state["index"], state["done"]
    todo = [z for z in json.load(open(ZIPS)) if z not in done]
    print(f"phase 1: {len(todo)} ZIPs to sweep, {len(done)} done, "
          f"{len(index)} homes indexed", flush=True)
    # Geo labels resolved by the previous run are reused rather than re-asked.
    # Geo labels resolved by any previous run, so a re-index does not re-ask for 94 of them.
    cached = {}
    if os.path.exists(paths.INDEX):
        old = pickle.load(open(paths.INDEX, "rb")).get("done", {})
        cached = {z: v["geo"] for z, v in old.items() if v.get("geo")}
    for n, z in enumerate(todo, 1):
        try:
            label = cached.get(z)
            if not label:
                geo = ((post(session, SUGGEST, {"searchInput": {"search_term": z}},
                             "Search_suggestions", interval).get("search_suggestions")
                        or {}).get("geo_results") or [])
                if not geo:
                    done[z] = {"n": 0, "error": "no geo match"}
                    continue
                label = geo[0]["text"]
                time.sleep(interval)
            offset, total, got = 0, None, 0
            while total is None or offset < total:
                block = post(session, SEARCH,
                             {"search_location": {"location": label}, "offset": offset},
                             "GetHomeSearch", interval).get("homeSearch") or {}
                total = block.get("total") or 0
                rows = block.get("results") or []
                for h in rows:
                    index[h["property_id"]] = h
                got += len(rows)
                offset += len(rows) or 200
                if not rows:
                    break
                time.sleep(interval)
            done[z] = {"n": total, "geo": label}
            print(f"  [{n}/{len(todo)}] {z} ({label}): {total} sold, {got} indexed",
                  flush=True)
        except Exception as exc:
            done[z] = {"n": None, "error": f"{type(exc).__name__}: {str(exc)[:90]}"}
            print(f"  [{n}/{len(todo)}] {z}: FAILED {str(exc)[:80]}", flush=True)
        pickle.dump({"index": index, "done": done}, open(INDEX, "wb"))
        time.sleep(interval)
    failed = [z for z, v in done.items() if v.get("error")]
    print(f"\nphase 1 complete: {len(index)} distinct homes, {len(failed)} ZIPs failed "
          f"{failed}", flush=True)
    return index


def phase2(session, index, interval, limit=None):
    done = pickle.load(open(DETAILS, "rb")) if os.path.exists(DETAILS) else {}
    todo = [p for p in index if p not in done]
    if limit:
        todo = todo[:limit]
    print(f"phase 2: {len(todo)} to fetch at {interval}s "
          f"(~{len(todo) * (interval + 0.35) / 3600:.1f} h), "
          f"{len(index) - len(todo)} cached\n", flush=True)
    for n, pid in enumerate(todo, 1):
        try:
            home = (post(session, DETAIL, {"property_id": pid}, "GetHomeDetails",
                         interval).get("home") or {})
            done[pid] = ({**home, "_search": index[pid]} if home
                         else {"error": "no home returned"})
        except Exception as exc:
            done[pid] = {"error": f"{type(exc).__name__}: {str(exc)[:90]}"}
        if n % 200 == 0:
            pickle.dump(done, open(DETAILS, "wb"))
            ok = sum(1 for v in done.values() if "error" not in v)
            print(f"  [{n}/{len(todo)}] {ok} fetched, {len(done) - ok} failed", flush=True)
            report("   rate")
        time.sleep(interval)
    pickle.dump(done, open(DETAILS, "wb"))
    ok = sum(1 for v in done.values() if "error" not in v)
    print(f"\nDONE: {ok} fetched, {len(done) - ok} failed", flush=True)


def main():
    a = sys.argv
    interval = float(a[a.index("--interval") + 1]) if "--interval" in a else 1.5
    session = requests.Session()
    if "--phase1" in a:
        phase1(session, interval)
        report("phase 1")
        return
    index = pickle.load(open(INDEX, "rb"))["index"]
    limit = int(a[a.index("--probe") + 1]) if "--probe" in a else None
    phase2(session, index, interval, limit)
    report("phase 2" if not limit else f"probe of {limit} at {interval}s")


if __name__ == "__main__":
    main()
