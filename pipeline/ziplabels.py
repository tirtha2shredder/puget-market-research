"""Place names for the ZIP codes, so a leaderboard row says where it is.

The postal city is useless for this: 23 of the 86 ZIPs with sales are simply "Seattle", and 66
of 86 share a city name with at least one other ZIP. A row reading "98126 Seattle" next to
"98136 Seattle" tells a reader nothing they can act on.

Every label below was chosen from the street names actually present in that ZIP's sales rather
than from memory -- 98107's sales are on NW 60th St, 3rd Ave NW and NW 63rd St, which is
Ballard; 98136's are on SW Mills St, SW Portland St and 41st Ave SW, which is Fauntleroy and
Morgan Junction. `verify()` re-runs that check.

Where the postal city is also the plain answer, the city stands. The entries here are the
cases where it is ambiguous (all of Seattle) or actively misleading: 98042 is postal Kent but
is Covington, 98087 is postal Lynnwood but is Martha Lake, 98296 is postal Snohomish but is
Maltby.
"""

LABELS = {
    # ---- Seattle, north of the Ship Canal
    "98103": "Wallingford & Green Lake",
    "98107": "Ballard",
    "98115": "Ravenna & Wedgwood",
    "98117": "Crown Hill & Loyal Hts",
    "98125": "Lake City & Northgate",
    "98133": "Bitter Lake & Shoreline",
    "98177": "Broadview & Richmond Bch",
    "98155": "Lake Forest Park",
    # ---- Seattle, central
    "98102": "Eastlake & Montlake",
    "98105": "U District & Laurelhurst",
    "98109": "South Lake Union",
    "98112": "Madison Park",
    "98119": "Queen Anne",
    "98121": "Belltown",
    "98122": "Central District",
    "98199": "Magnolia",
    # ---- Seattle, south and west
    "98106": "Delridge & Highland Park",
    "98108": "Beacon Hill & Georgetown",
    "98116": "Alki & Admiral",
    "98118": "Columbia City & Rainier",
    "98126": "Gatewood & High Point",
    "98136": "Fauntleroy & Morgan Jct",
    "98144": "Mount Baker",
    "98146": "White Center",
    "98178": "Skyway & Bryn Mawr",
    # ---- postal city misleading
    "98042": "Covington",
    "98087": "Martha Lake",
    "98296": "Maltby",
    "98204": "South Everett",
    "98208": "Silver Lake",
    "98053": "Redmond Ridge",
    "98057": "Renton downtown",
    "98058": "Fairwood",
    "98059": "Renton Highlands",
    "98006": "Newcastle & Factoria",
    "98077": "Hollywood Hill",
    "98050": "Preston",
    "98024": "Fall City",
    "98014": "Carnation",
    "98019": "Duvall",
    "98065": "Snoqualmie",
    "98010": "Black Diamond",
    "98047": "Pacific",
    "98070": "Vashon Island",
    "98040": "Mercer Island",
    "98039": "Medina",
    "98043": "Mountlake Terrace",
    "98028": "Kenmore",
    "98188": "SeaTac",
    "98168": "Tukwila",
    "98198": "Des Moines",
    "98148": "Normandy Park & SeaTac",
    "98166": "Burien",
    # ---- multi-ZIP cities where a qualifier is corroborated by the street names below
    "98033": "Kirkland downtown",
    "98034": "Juanita & Totem Lake",
    "98004": "West Bellevue",
    "98007": "Crossroads",
    "98008": "Lake Hills",
    "98005": "Bridle Trails",
    "98029": "Issaquah Highlands",
    "98074": "Sammamish & Sahalee",
    "98075": "Klahanie & Beaver Lake",
    "98012": "Mill Creek",
    "98021": "Canyon Park",
    "98036": "Lynnwood south & Alderwd",
    "98026": "Edmonds east",
    "98023": "Federal Way west",
    "98003": "Federal Way east",
    "98032": "Kent west",
    "98030": "Kent East Hill",
    "98056": "Renton north & Kennydale",
    "98001": "Auburn west",
    "98002": "Auburn central",
    "98092": "Lakeland & Lea Hill",
}

# Street fragments that must appear in a ZIP's sales for its label to be believable. Only the
# ones where a wrong label would mislead rather than merely be vague.
EXPECT = {
    "98107": ("NW",), "98117": ("NW",), "98199": (" W",), "98119": (" W",),
    "98116": ("SW",), "98126": ("SW",), "98136": ("SW",), "98106": ("SW",),
    "98146": ("SW",), "98118": (" S",), "98108": (" S",), "98144": (" S",),
    "98178": (" S",), "98042": ("SE",), "98296": ("SE",), "98208": ("SE",),
    "98023": ("SW",), "98034": ("NE",), "98074": ("NE",), "98075": ("SE",),
}

# (zip, direction, reference zip): the label says this ZIP lies that way from its neighbour,
# and the centroids have to agree. Checked on the dominant axis so "east" is not satisfied by a
# hair of easting on a pair that really differs north-south.
RELATIONS = [
    ("98026", "east",  "98020"),   # Edmonds east
    ("98036", "south", "98037"),   # Lynnwood south
    ("98056", "north", "98055"),   # Renton north
    ("98023", "west",  "98003"),   # Federal Way west
    ("98003", "east",  "98023"),   # Federal Way east
    ("98032", "west",  "98030"),   # Kent west
    ("98030", "east",  "98032"),   # Kent East Hill
    ("98001", "west",  "98002"),   # Auburn west
    ("98092", "east",  "98002"),   # Lakeland & Lea Hill
    ("98034", "north", "98033"),   # Juanita & Totem Lake
    ("98033", "south", "98034"),   # Kirkland downtown
]


def verify_relations(centroids):
    """Each directional label has to agree with the ZCTA centroids."""
    bad = []
    for z, want, ref in RELATIONS:
        if z not in centroids or ref not in centroids:
            continue
        (la, lo), (lb, lob) = centroids[z], centroids[ref]
        dlat, dlon = la - lb, lo - lob
        axis = "ns" if abs(dlat) > abs(dlon) else "ew"
        got = ("north" if dlat > 0 else "south") if axis == "ns" \
            else ("east" if dlon > 0 else "west")
        if got != want:
            bad.append((z, LABELS[z], f"claims {want}, centroid says {got}"))
    return bad


def label_for(zip_code, city):
    """The place name for a ZIP: curated where the city is ambiguous, city otherwise."""
    return LABELS.get(str(zip_code)) or (city or str(zip_code))


def verify(sales):
    """Check each expectation against the addresses actually in that ZIP.

    `sales` is a DataFrame with `zip` and `address`.
    """
    bad = []
    for z, frags in EXPECT.items():
        addrs = sales.loc[sales.zip.astype(str) == z, "address"].dropna().astype(str)
        if not len(addrs):
            continue
        share = max(addrs.str.contains(f, case=False).mean() for f in frags)
        if share < 0.6:
            bad.append((z, LABELS[z], frags, round(share, 2)))
    return bad


if __name__ == "__main__":
    import json
    import pandas as pd
    df = pd.read_csv("/Users/tirthanu/workspaces/REMaxxing/closed_sales_30d.csv")
    cent = {f["properties"]["ZCTA5CE10"]:
            (float(f["properties"]["INTPTLAT10"]), float(f["properties"]["INTPTLON10"]))
            for f in json.load(open(paths.WA_ZIPS))["features"]}
    bad = verify(df)
    badrel = verify_relations(cent)
    print(f"{len(LABELS)} curated labels")
    print(f"  {len(EXPECT)} neighbourhood names checked against street names: "
          f"{bad or 'all pass'}")
    print(f"  {len(RELATIONS)} directional names checked against centroids: "
          f"{badrel or 'all pass'}")
    seen = set(df.zip.astype(str))
    print(f"labels naming a ZIP with no sales: "
          f"{sorted(set(LABELS) - seen) or 'none'}")
    amb = df.groupby(df.zip.astype(str)).city.first()
    unlabelled = [z for z in sorted(seen) if z not in LABELS]
    dupes = {}
    for z in unlabelled:
        dupes.setdefault(amb[z], []).append(z)
    still = {c: zs for c, zs in dupes.items() if len(zs) > 1}
    print(f"\nunlabelled ZIPs still sharing a city name (ZIP number disambiguates):")
    for c, zs in sorted(still.items()):
        print(f"   {c}: {' '.join(zs)}")
