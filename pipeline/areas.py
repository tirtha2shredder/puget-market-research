"""Market areas over the 89-ZIP footprint, and the dissolved polygons for them.

Why areas rather than postal cities: measured on this data, replacing ZIP with postal city as
the grouping throws away 60% of the sold-vs-ask signal (eta^2 0.109 -> 0.043), 59% of the
price-cut signal and 50% of days-to-pending. Only $/sqft survives a city merge well (23%
lost), because price level genuinely is a city-scale fact and negotiation outcome is not.

The loss is concentrated, not spread evenly. Postal "Seattle" is 23 ZIPs and 337 sales -- a
quarter of everything -- spanning $396 to $709 per square foot, 16.3 points of sold-vs-ask and
121 days of time-to-contract. One Seattle tile would report -1.92% and $545 for all of it.
Bellevue has the same problem at smaller scale, 5 ZIPs across $363 of $/sqft.

So the divergent cities are split along the lines a realtor would actually draw, and only the
cities measured homogeneous are merged whole -- Lynnwood spans 1.5 points internally,
Sammamish 1.7, Auburn 2.1, Federal Way 2.4.

Boundaries follow water and ridge lines where those are what separate the markets: the Ship
Canal splits north Seattle from Queen Anne, the Duwamish splits West Seattle from the valley.
"""

import json
import pathlib

_HERE = pathlib.Path(__file__).parent

AREAS = {
    # ---- Snohomish
    "Mukilteo & S Everett":      ["98275", "98204", "98208"],
    "Lynnwood & Martha Lake":    ["98036", "98037", "98087"],
    "Mountlake Terrace":         ["98043"],
    "Edmonds":                   ["98020", "98026"],
    "Bothell & Mill Creek":      ["98012", "98021", "98296"],
    "Monroe & Snohomish":        ["98272", "98290"],
    # ---- King, north end
    "Shoreline & Lake Forest Pk": ["98133", "98155"],
    "Kenmore":                   ["98028"],
    "Bothell (King)":            ["98011"],
    "North Seattle":             ["98103", "98107", "98115", "98117", "98125", "98177"],
    # Downtown/SLU/Belltown carry almost no single-family stock; they ride with Queen Anne
    # rather than becoming their own near-empty tiles.
    "Queen Anne & Magnolia":     ["98109", "98119", "98199", "98102", "98121",
                                  "98101", "98104", "98134", "98154", "98164", "98174"],
    "Capitol Hill & U District": ["98105", "98112", "98122", "98195"],
    "Central & SE Seattle":      ["98144", "98118", "98108", "98178"],
    "West Seattle":              ["98116", "98126", "98136"],
    "White Center & Delridge":   ["98106", "98146"],
    # ---- King, Eastside
    "Kirkland":                  ["98033", "98034"],
    "Redmond":                   ["98052"],
    "Redmond Ridge & Union Hill": ["98053"],
    "Woodinville":               ["98072", "98077"],
    "Bellevue West & Medina":    ["98004", "98005", "98039"],
    "Bellevue East":             ["98007", "98008"],
    "Bellevue South & Newcastle": ["98006"],
    "Mercer Island":             ["98040"],
    "Sammamish":                 ["98074", "98075"],
    "Issaquah":                  ["98027", "98029"],
    # ---- King, south
    "Renton North":              ["98055", "98056", "98057"],
    "Renton East & Fairwood":    ["98058", "98059"],
    "Tukwila & SeaTac":          ["98168", "98188", "98158"],
    "Burien":                    ["98166", "98148"],
    "Des Moines":                ["98198"],
    "Federal Way":               ["98003", "98023"],
    "Kent":                      ["98030", "98031", "98032"],
    "Covington & East Kent":     ["98042"],
    "Auburn & Pacific":          ["98001", "98002", "98092", "98047"],
    "Maple Valley & Black Diamond": ["98038", "98010"],
    "Vashon Island":             ["98070"],
    # Named for what it is. Fall City and Snoqualmie were added because without Fall City the
    # region was literally two disconnected pieces -- Preston touches only Fall City (6.2 km
    # of shared border) and nothing else here -- and without Snoqualmie the remaining four
    # wrapped around it on three sides, leaving a bite out of the middle. Both sit entirely
    # inside the longitude strip the other three already span (-122.03 to -121.67). North Bend
    # does not: it reaches -121.34, deep into the Cascades, so it stays out.
    "Snoqualmie Valley":         ["98019", "98014", "98024", "98065", "98050"],
}

ZIP_TO_AREA = {z: a for a, zs in AREAS.items() for z in zs}


def check():
    """Every swept ZIP is in exactly one area, and no area names a ZIP we did not sweep."""
    swept = set(json.load(open(str(_HERE / "zips_wide.json"))))
    mapped = [z for zs in AREAS.values() for z in zs]
    assert len(mapped) == len(set(mapped)), \
        f"ZIP in two areas: {sorted({z for z in mapped if mapped.count(z) > 1})}"
    missing, extra = swept - set(mapped), set(mapped) - swept
    assert not missing, f"unmapped ZIPs: {sorted(missing)}"
    assert not extra, f"areas name unswept ZIPs: {sorted(extra)}"
    return len(AREAS), len(swept)


# ---------------------------------------------------------------------------------------
# Regions: the top tier. Seven of them, so the first view is readable at a glance and the
# reader chooses where to spend attention before seeing 81 ZIP codes.
#
# Grouped as asked. Two notes on where the lines fell:
#   * Seattle splits at the central core rather than at the Ship Canal -- Queen Anne and
#     Capitol Hill ride with the north end because they price like it ($662 and $684 against
#     $559 for North Seattle), while West Seattle and the Rainier valley price like the south
#     ($513, $452, $412).
#   * Newcastle stays inside Bellevue because 98006 is a Bellevue ZIP, and a ZIP cannot be
#     split across two regions.
#   * Mercer Island and Vashon Island each stand alone. Both are islands with one ZIP and a
#     market that does not behave like anything they touch -- Mercer Island at $831 a foot
#     against $622 for the Eastside around it, Vashon reachable only by ferry.
#   * The old "North Eastside" is gone: once Redmond moved east and Bothell and Woodinville
#     moved into their own corridor, Monroe and Snohomish were all that remained, so they
#     carry the region themselves rather than sitting under a name that no longer described
#     them.
REGIONS = {
    # The north Sound shore, across the county line. Grouped on price: Mountlake Terrace at
    # $543 a foot sits with Shoreline's $467 and Edmonds' $503, not with Lynnwood's $403.
    "Shoreline & Edmonds": ["Shoreline & Lake Forest Pk", "Edmonds", "Mountlake Terrace"],
    "Lynnwood & Mukilteo": ["Lynnwood & Martha Lake", "Mukilteo & S Everett"],
    "Bothell & Woodinville": ["Bothell & Mill Creek", "Woodinville", "Bothell (King)"],
    "Monroe & Snohomish": ["Monroe & Snohomish"],
    "Seattle North":  ["North Seattle", "Queen Anne & Magnolia",
                       "Capitol Hill & U District"],
    "Seattle South":  ["Central & SE Seattle", "West Seattle",
                       "White Center & Delridge"],
    "Central Eastside": ["Kirkland", "Redmond", "Redmond Ridge & Union Hill", "Kenmore",
                         "Bellevue West & Medina", "Bellevue East",
                         "Bellevue South & Newcastle", "Sammamish", "Issaquah"],
    "Mercer Island":  ["Mercer Island"],
    "Far East King":  ["Snoqualmie Valley"],
    "Southeast King": ["Renton North", "Renton East & Fairwood",
                       "Covington & East Kent", "Maple Valley & Black Diamond"],
    "South King":     ["Federal Way", "Kent", "Auburn & Pacific", "Burien",
                       "Tukwila & SeaTac", "Des Moines"],
    "Vashon Island":  ["Vashon Island"],
}

AREA_TO_REGION = {a: r for r, aa in REGIONS.items() for a in aa}
ZIP_TO_REGION = {z: AREA_TO_REGION[a] for z, a in ZIP_TO_AREA.items()}


def check_regions():
    """Every area belongs to exactly one region."""
    named = [a for aa in REGIONS.values() for a in aa]
    assert len(named) == len(set(named)), \
        f"area in two regions: {sorted({a for a in named if named.count(a) > 1})}"
    missing, extra = set(AREAS) - set(named), set(named) - set(AREAS)
    assert not missing, f"areas with no region: {sorted(missing)}"
    assert not extra, f"regions name unknown areas: {sorted(extra)}"
    return len(REGIONS)


if __name__ == "__main__":
    n_area, n_zip = check()
    n_reg = check_regions()
    print(f"{n_zip} ZIPs -> {n_area} market areas -> {n_reg} regions, coverage exact")
    for r, aa in REGIONS.items():
        zs = sum(len(AREAS[a]) for a in aa)
        print(f"   {r:<22} {len(aa):>2} areas, {zs:>2} ZIPs")
