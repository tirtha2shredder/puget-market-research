# Greater Seattle Area Home Sales Analysis

**[View the report →](https://tirtha2shredder.github.io/puget-market-research/)**

An interactive study of what homes actually sold for against what they asked, across 90 ZIP
codes in King and Snohomish counties. 15,835 closed sales in the six months to
21 September 2026: houses, townhomes and condos.

One self-contained HTML file. No server, no build step to view it, and no network requests
except Leaflet's stylesheet.

## What it answers

Seven views over the same sales, each filterable by property type, time window and price band:

| View | Question |
|---|---|
| Sold vs ask | How far did the median home land from its opening ask? |
| Above / at / below | What share beat the ask, matched it, or came in under? |
| — fast sales | The same split for homes that went pending inside ten days |
| Days to pending | How long from listing to contract? |
| Price cuts | How often did sellers publish a reduction? |
| Cut depth | How far did the ask fall, and how much more was conceded at the table? |
| $ / sqft | Price level |

Three tiers throughout: 12 regions → the ZIP codes inside one → the individual homes inside
one, each linking out to its listing.

## Findings that survived checking

Every figure in the report is computed in the browser from the individual sales, so it moves
with the filters. These are the conclusions that held up:

- **A published price cut is under half the story.** Of all the discount given away, 47% was a
  list reduction and 53% was conceded at the table. 390 of the 856 single-family homes that
  never published a cut still sold below ask, median −4.00%. Every cuts-only metric reported
  those as zero.
- **Time on market predicts the discount best** (−0.76 across ZIPs). The cut rate is the
  weakest of the three signals (−0.54). The at-table concession read +0.96 at 7 regions and
  +0.65 at 12 — a region-level correlation moves with how the regions are drawn, so the
  ZIP-level figure is the one to quote.
- **Price is essentially unrelated to the outcome.** corr(log price, sold vs ask) = −0.01.
- **Place predicts price level 7.1 standard deviations better than chance, but sold-vs-ask only
  1.5.** Geography tells you what a house costs far better than how its negotiation goes.
- **Speed is the real divide.** Homes pending within ten days ran 40/41/19 above/at/below ask;
  slower ones ran 3/9/88.

## Limitations, stated plainly

- **One source.** Everything comes from realtor.com. Where it is wrong or incomplete, so is
  this. Its data is MLS-derived but not the MLS.
- **Scraped from an undocumented internal endpoint**, which may change or stop working without
  notice. This is research, not infrastructure.
- **A window, not a trend.** Six months to 21 September 2026. The 6-month median is −1.89%
  against −3.33% for the last month alone; that gap is season as much as sample size.
- **Mixing property types blurs $/sqft.** A condo's floor area excludes everything shared, so
  it is not the same measurement as a house's.
- **A sale is only measured when its own campaign has a priced opening.** Those that do not are
  excluded rather than measured against an older listing.
- **Thin samples are marked, not hidden.** Units under five sales are hatched on the map and
  kept out of the leaderboards, and the count travels with every figure.

## Rebuilding it

```
pipeline/rdc_v2.py      --phase1      resolve geography, index the sold listings
pipeline/rdc_v2.py      --interval 1  fetch each listing's price history (checkpointed)
pipeline/rebuild7.py                  per-sale records plus the metadata the browser needs
pipeline/build_geo3.py                dissolve region polygons, simplify ZCTAs (shapely)
pipeline/build_map.py                 emit index.html
```

`areas.py` holds the ZIP → market area → region grouping with coverage assertions;
`ziplabels.py` holds the place names, each corroborated against street names in that ZIP's
own sales or against ZCTA centroids; `campaign.py` segments a listing history into campaigns
and picks the one that produced the sale.

The fetch is checkpointed by `property_id`, so re-running only pulls what is missing.

## Why the campaign rules exist

Each one was added because it caught an answer that had already shipped wrong. A withdrawal
followed by silence, a stale listing never marked removed, and a list price corrected within
days of posting together produced four sales reported between +38% and +159% over ask — one of
which this report had presented as a finding before the rule was written.
