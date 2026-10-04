"""Stats at region and ZIP level, plus every sale, for the three-tier map.

Three levels because the reader chooses where to spend attention before being shown 81 ZIP
codes: 7 regions -> the ZIPs inside one region -> the homes inside one ZIP.

Two things this adds over the single-level version:

  * The discount is decomposed. A "price cut" was only ever a published list reduction, which
    misses where most of the money actually goes: across 1,374 sales, 47% of all the discount
    given away was a list cut and 53% was conceded at the table. 390 of the 850 homes that
    never cut still sold below ask, median -4.08%, and every cut metric reported them as zero.
    So each unit now carries the published cut and the at-table concession separately. Merged
    they would just restate sold-vs-ask; split they say where the seller gave way.

  * Stats are pooled from the sales at every level, never averaged from the level below.
    Averaging 16-sale ZIP medians into a region would carry their sampling error upward
    instead of cancelling it.
"""

import json
import paths
import pickle
import sys
from datetime import date, datetime

import pandas as pd

sys.path.insert(0, __import__("os").path.dirname(__file__))
from areas import (AREA_TO_REGION, ZIP_TO_AREA, ZIP_TO_REGION, check,  # noqa: E402
                   check_regions)
from campaign import campaign  # noqa: E402
from ziplabels import label_for  # noqa: E402

DETAILS = paths.DETAILS

# Six months of all three residential types. One and three months are cut from this in the
# browser, so the window selector costs no extra fetching.
WINDOW_FROM, WINDOW_TO = date(2026, 3, 22), date(2026, 9, 28)

# Single letters. `pt` is written 15,874 times and the words would cost 180 kB for nothing.
PT = {"single_family": "s", "condos": "c", "townhomes": "t"}

# Every href shares this prefix, verified on all 7,903 fetched so far. Stored once in the
# payload and put back by the browser: 50 bytes x 15,874 is 790 kB of the same string.
HREF_PREFIX = "https://www.realtor.com/realestateandhomes-detail/"

# The hover panel shows six events and then "+N earlier", so six plus the count is all the
# payload needs. Full histories were a quarter of the points payload.
EV_SHOWN = 6

# Events go out as [dayOffset, code, price] tuples rather than keyed objects. At 15,874 sales
# the keys alone were a third of a megabyte, and only seven event names exist across 67,000
# rows. The browser puts the words and the dates back.
EV_CODE = {"Sold": 0, "Listed": 1, "Listing removed": 2, "Price Changed": 3,
           "Listed for rent": 4, "Relisted": 5, "Price Changed for rent": 6}
EV_NAME = [k for k, _ in sorted(EV_CODE.items(), key=lambda kv: kv[1])]
EPOCH = date(2026, 1, 1)


def day(v):
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def extract():
    rows, pts, nocoord = [], [], 0
    for _pid, h in pickle.load(open(DETAILS, "rb")).items():
        if "error" in h:
            continue
        ev = [e for e in (h.get("property_history") or []) if e.get("date")]
        for e in ev:
            e["_d"] = day(e["date"])
        ev = [e for e in ev if e["_d"]]
        # Realtor.com returns some events twice -- 261 of 12,597 rows across 107 homes, where
        # the MLS record and the public record both land in the history. Left in, they double
        # a home's price-cut count: 12710 NE 72nd St showed 16 cuts for 8 real ones, and across
        # 57 homes 284 recorded cuts were really 178. Same date, same event, same price is a
        # duplicate; a genuine second cut on one day to the identical price is indistinguishable
        # and vanishingly rare.
        seen, uniq = set(), []
        for e in ev:
            k = (e["_d"], str(e.get("event_name")), e.get("price"))
            if k not in seen:
                seen.add(k)
                uniq.append(e)
        ev = uniq
        if not ev:
            continue
        run, first = campaign(ev)
        if run is None:
            continue
        sale = max((e for e in run if e.get("event_name") == "Sold" and e.get("price")),
                   key=lambda e: e["_d"], default=None)
        if sale is None:
            continue
        a = (h.get("location") or {}).get("address") or {}
        z = str(a.get("postal_code") or "")
        if z not in ZIP_TO_AREA:
            continue
        # A handful of records come back whose only Sold event predates the requested window
        # by decades -- 1983 and 1988 among the first 7,903 -- so the window is enforced here
        # rather than trusted from the search filter.
        if not (WINDOW_FROM <= sale["_d"] <= WINDOW_TO):
            continue
        changes = sorted([e for e in run if e.get("event_name") == "Price Changed"
                          and e.get("price")], key=lambda e: e["_d"])
        listed = [e for e in run if e.get("event_name") in ("Listed", "Relisted")]
        ask = first["price"] if first else None
        lo = first["_d"] if first else None
        po = day(h.get("pending_date"))
        dp = (po - lo).days if (po and lo and po >= lo) else None
        final = changes[-1]["price"] if changes else ask
        d = h.get("description") or {}
        rec = {"address": a.get("line"), "zip": z, "city": a.get("city"),
               "area": ZIP_TO_AREA[z], "region": ZIP_TO_REGION[z],
               "sqft": d.get("sqft"), "sold_price": sale["price"],
               "sold_date": sale["_d"], "original_ask": ask, "final_ask": final,
               "price_changes": len(changes), "relisted": len(listed) > 1,
               "campaign_days": (sale["_d"] - lo).days if lo else None,
               "days_to_pending": dp}
        rows.append(rec)
        # Every sale goes in, plottable or not. Seven have no coordinate from realtor.com, and
        # dropping them made the on-screen summary count 1,376 where the stats and the subtitle
        # both said 1,383 -- two numbers on one page disagreeing. They now appear in the list
        # and the counts with no marker on the map, which is the truth about them.
        co = a.get("coordinate") or {}
        if co.get("lat") is None:
            nocoord += 1
        pts.append({
            "i": len(pts),           # stable id, so a row can find its marker if it has one
            # No `ar`/`rg`: a sale's area and region follow from its ZIP, and the browser has
            # that mapping already. Storing them per sale cost 43 bytes x 15,874.
            "a": a.get("line"), "z": z, "c": a.get("city"),
            "pt": PT.get((d or {}).get("type"), "?"),
            "lat": None if co.get("lat") is None else round(co["lat"], 5),
            "lon": None if co.get("lon") is None else round(co["lon"], 5),
            "u": (h.get("href") or "").replace(HREF_PREFIX, ""),
            "sp": sale["price"], "sd": (sale["_d"] - EPOCH).days, "oa": ask,
            "fa": final, "nc": len(changes), "dp": dp,
            "dc": rec["campaign_days"], "sq": d.get("sqft"), "bd": d.get("beds"),
            "ba": d.get("baths"), "yr": d.get("year_built"), "rl": rec["relisted"],
            # Six decimals, not four. The above/at/below test is a +/-0.5% band, i.e. 0.005,
            # and four decimals puts anything from 0.00495 to 0.00505 exactly on the boundary
            # -- which misclassified 24 sales once the browser started doing the counting.
            "va": round(sale["price"] / ask - 1, 6) if ask else None,
            # The two halves of the discount, so a home list can show either.
            "cd": round(final / ask - 1, 6) if ask and final else None,
            "ng": round(sale["price"] / final - 1, 6) if final else None,
            "nev": len(run),
            "ev": [[(e["_d"] - EPOCH).days, EV_CODE.get(e["event_name"], -1),
                    e.get("price")]
                   for e in sorted(run, key=lambda e: e["_d"],
                                   reverse=True)[:EV_SHOWN]]})
    return pd.DataFrame(rows), pts, nocoord


def unit_stats(keep, df, key, label_members=None):
    """One row per unit, pooled from that unit's sales."""
    per = []
    for k, g in keep.groupby(key):
        allk = df[df[key] == k]
        fastk = g[(g.days_to_pending < 10) & g.days_to_pending.notna()]
        cut = g[g.price_changes > 0]
        nocut = g[g.price_changes == 0]
        row = {
            "zip": k,                       # the unit key, whatever level this is
            "members": label_members(g) if label_members else "",
            "n": len(g),
            "median_vs_ask": round(g.vs_original.median() * 100, 2),
            "over_ask_pct": round((g.vs_original > 0.005).mean() * 100, 1),
            "over_ask_n": int((g.vs_original > 0.005).sum()),
            "at_ask_pct": round((g.vs_original.abs() <= 0.005).mean() * 100, 1),
            "at_ask_n": int((g.vs_original.abs() <= 0.005).sum()),
            "below_ask_pct": round((g.vs_original < -0.005).mean() * 100, 1),
            "below_ask_n": int((g.vs_original < -0.005).sum()),
            "net_ask_pct": round((g.vs_original > 0.005).mean() * 100
                                 - (g.vs_original < -0.005).mean() * 100, 1),
            # Distance from an even three-way split, for ranking "most balanced". A net near
            # zero will not do: 50/0/50 and 0/100/0 both net zero and mean opposite things.
            "even_dev": round(sum(abs(v - 100/3) for v in (
                (g.vs_original > 0.005).mean() * 100,
                (g.vs_original.abs() <= 0.005).mean() * 100,
                (g.vs_original < -0.005).mean() * 100)), 1),
            "median_days": (None if g.days_to_pending.isna().all()
                            else int(g.days_to_pending.median())),
            "fast_pct": round(len(allk[(allk.days_to_pending < 10)
                                       & allk.days_to_pending.notna()])
                              / max(len(allk), 1) * 100, 1),
            "median_price": int(g.sold_price.median()),
            "median_ppsf": None if g.ppsf.isna().all() else int(g.ppsf.median()),
            "cut_pct": round((g.price_changes > 0).mean() * 100, 1),
            "cuts_mean": round(g.price_changes.mean(), 2),
            "cuts_median": float(g.price_changes.median()),
            "cuts_max": int(g.price_changes.max()),
            "cut_size_median": (None if not len(cut) else
                                round((cut.final_ask / cut.original_ask - 1).median() * 100, 2)),
            "cutters_n": int(len(cut)),
            "cuts_median_among_cutters": (None if not len(cut) else
                                          float(cut.price_changes.median())),
            # What the buyer negotiated off the *final* ask -- the half the cut metrics missed.
            "negotiated_median": round(g.negotiated.median() * 100, 2),
            "negotiated_n": int((g.negotiated < -0.005).sum()),
            "negotiated_pct": round((g.negotiated < -0.005).mean() * 100, 1),
            # Homes that never published a cut and still sold under ask.
            "silent_n": int((nocut.vs_original < -0.005).sum()),
            "silent_pct": (None if not len(nocut) else
                           round((nocut.vs_original < -0.005).mean() * 100, 1)),
            "silent_median": (None if not (nocut.vs_original < -0.005).any() else
                              round(nocut[nocut.vs_original < -0.005]
                                    .vs_original.median() * 100, 2)),
            "fast_n": int(len(fastk)),
            "relist_pct": round(g.relisted.mean() * 100, 1),
        }
        for nm, col in (("fast_over", fastk.vs_original > 0.005),
                        ("fast_at", fastk.vs_original.abs() <= 0.005),
                        ("fast_below", fastk.vs_original < -0.005)):
            row[nm + "_pct"] = None if not len(fastk) else round(col.mean() * 100, 1)
            row[nm + "_n"] = int(col.sum())
        row["fast_net_pct"] = (None if not len(fastk) else
                               round(row["fast_over_pct"] - row["fast_below_pct"], 1))
        per.append(row)
    return sorted(per, key=lambda r: -r["median_vs_ask"])


def main():
    check(); check_regions()
    df, pts, nocoord = extract()
    keep = df[df.original_ask.notna()].copy()
    keep["vs_original"] = keep.sold_price / keep.original_ask - 1
    keep["negotiated"] = keep.sold_price / keep.final_ask - 1
    keep["ppsf"] = keep.sold_price / keep.sqft
    df = df.assign(vs_original=df.sold_price / df.original_ask - 1)

    import collections
    mix = collections.Counter(p["pt"] for p in pts)
    print(f"property types: " + "  ".join(f"{k}={v:,}" for k, v in mix.most_common()))
    print(f"{len(df)} sales, {len(keep)} with a priced campaign opening, "
          f"{len(pts)} points ({nocoord} of them without coordinates, listed but not mapped)")
    print(f"  median vs original ask {keep.vs_original.median():+.2%}   "
          f"negotiated off final ask {keep.negotiated.median():+.2%}")

    regions = unit_stats(keep, df, "region",
                         lambda g: ", ".join(sorted(g.area.unique())))
    zips = unit_stats(keep, df, "zip",
                      lambda g: (g.city.mode().iat[0] if len(g.city.mode()) else ""))
    for r in zips:
        r["area"] = ZIP_TO_AREA[r["zip"]]
        r["region"] = ZIP_TO_REGION[r["zip"]]
        # A place name, because the postal city is "Seattle" for 23 of these and shares a
        # name with another ZIP for 66 of 86. See ziplabels.py for how each was corroborated.
        r["label"] = label_for(r["zip"], r["members"])
    areas = unit_stats(keep, df, "area",
                       lambda g: " ".join(sorted(g.zip.astype(str).unique())))
    for r in areas:
        r["region"] = AREA_TO_REGION[r["zip"]]

    payload = json.load(open(paths.PAYLOAD))
    meta = {
        "region": {r["zip"]: {"members": r["members"]} for r in regions},
        "area": {r["zip"]: {"members": r["members"], "region": r["region"]}
                 for r in areas},
        "zip": {r["zip"]: {"members": r["members"], "label": r["label"],
                           "area": r["area"], "region": r["region"]} for r in zips},
    }
    payload.update({"meta": meta, "points": pts, "unplotted": {},
                    "href_prefix": HREF_PREFIX, "ev_names": EV_NAME,
                    "epoch": str(EPOCH),
                    "window": [(WINDOW_FROM - EPOCH).days, (WINDOW_TO - EPOCH).days]})
    payload.pop("stats", None); payload.pop("zips", None); payload.pop("areas", None)
    json.dump(payload, open(paths.PAYLOAD, "w"), separators=(",", ":"))
    json.dump({"regions": regions, "zips": zips, "areas": areas},
              open(paths.LEVELS, "w"), indent=1)
    keep.to_csv("closed_sales_30d.csv", index=False)

    print(f"\n{'region':<24}{'n':>5}{'vs ask':>9}{'cut':>8}{'at table':>10}"
          f"{'days':>6}{'$/sqft':>8}")
    for r in regions:
        print(f"{r['zip']:<24}{r['n']:>5}{r['median_vs_ask']:>+8.2f}%"
              f"{(r['cut_size_median'] or 0):>+7.2f}%{r['negotiated_median']:>+9.2f}%"
              f"{(r['median_days'] if r['median_days'] is not None else -1):>6}"
              f"{(r['median_ppsf'] or 0):>8}")
    print(f"\nthin regions (n<5): {[r['zip'] for r in regions if r['n'] < 5] or 'none'}")
    print(f"thin ZIPs (n<5): {sum(1 for r in zips if r['n'] < 5)} of {len(zips)}")
    thin_a = [r["zip"] for r in areas if r["n"] < 5]
    print(f"market areas: {len(areas)}, thin {thin_a or 'none'}, "
          f"median n {sorted(r['n'] for r in areas)[len(areas)//2]}")
    print(f"silent discounters: "
          f"{sum(r['silent_n'] for r in regions)} homes never cut yet sold under ask")


if __name__ == "__main__":
    main()
