"""Build the interactive ZIP choropleth as one self-contained HTML file."""
import json

payload = json.load(open("/tmp/map_payload.json"))


def price_steps(pl):
    """Slider stops: fine where the sales are, and stopping before the tail runs away.

    $50k increments to $2M, which covers 90% of the sales, then $250k to $5M, the 99th
    percentile. A linear sweep of the real range would be worse than useless: the top sale is
    $21.4M, so everything under $2M -- nine sales in ten -- would occupy a twelfth of the track.
    """
    steps, v = [0], 250_000
    while v <= 2_000_000:          # 90% of sales are under $2.09M
        steps.append(v)
        v += 50_000
    v = 2_250_000                  # resume on a round quarter-million, not at $2.05M
    while v <= 5_000_000:          # 99th percentile is $5.06M
        steps.append(v)
        v += 250_000
    return steps

HTML = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Greater Seattle Area Home Sales Analysis</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
:root{
  color-scheme:light;
  --surface-1:#fcfcfb; --plane:#f9f9f7;
  --text-primary:#0b0b0b; --text-secondary:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7; --border:rgba(11,11,11,0.10);
  --neutral:NEUTRAL_L; --water:#e8eaec; --series-link:#2a78d6;
}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){
  color-scheme:dark;
  --surface-1:#1a1a19; --plane:#0d0d0d;
  --text-primary:#fff; --text-secondary:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,0.10);
  --neutral:NEUTRAL_D; --water:#131316; --series-link:#3987e5;
}}
:root[data-theme="dark"]{
  color-scheme:dark;
  --surface-1:#1a1a19; --plane:#0d0d0d;
  --text-primary:#fff; --text-secondary:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,0.10);
  --neutral:NEUTRAL_D; --water:#131316; --series-link:#3987e5;
}
*{box-sizing:border-box}
body{margin:0;background:var(--plane);color:var(--text-primary);
  font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
.viz-root{position:relative;max-width:1180px;margin:0 auto;padding:24px 20px 56px;
  --col-h:724px}   /* map 620 + gap 14 + legend 90 */
h1{font-size:21px;font-weight:650;margin:0 0 4px;letter-spacing:-0.01em}
.sub{color:var(--text-secondary);margin:0 0 20px;font-size:13px}
/* Filters in one row above the chart. */
.controls{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:14px}
.seg{display:flex;background:var(--surface-1);border:1px solid var(--border);
  border-radius:8px;overflow:hidden}
.seg button{appearance:none;border:0;background:transparent;color:var(--text-secondary);
  padding:7px 13px;font:inherit;font-size:13px;cursor:pointer;
  border-right:1px solid var(--border)}
.seg button:last-child{border-right:0}
.seg button[aria-pressed="true"]{background:var(--plane);color:var(--text-primary);
  font-weight:600}
.seg button:hover{color:var(--text-primary)}
.spacer{flex:1}
.ghost{appearance:none;border:1px solid var(--border);background:var(--surface-1);
  color:var(--text-secondary);border-radius:8px;padding:7px 13px;font:inherit;
  font-size:13px;cursor:pointer}
.ghost:hover{color:var(--text-primary)}
.card{background:var(--surface-1);border:1px solid var(--border);border-radius:12px}
.pair{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:14px;
  align-items:start}
.pair>.col{display:flex;flex-direction:column;gap:14px}
.rank.cap{display:flex;flex-direction:column;overflow:hidden;max-height:var(--col-h)}
.rank.cap>h3{flex:0 0 auto}
.rank.cap>div{overflow-y:auto;scrollbar-width:thin;padding-right:3px}
/* With the leaderboards below it the chart takes the top half of the column, so the three
   cards together match the map's height rather than running past it. */
/* Height is set from JS instead, because the number of leaderboards varies by tab. */
#leaders{display:grid;grid-template-columns:minmax(0,1fr);gap:14px}
@media (max-width:940px){.rank.cap{max-height:none}}
@media (max-width:940px){.pair{grid-template-columns:1fr}}
/* The map pane itself is the water: land is drawn on top as ZCTA fills, so the
   gap left where no ZCTA exists is Puget Sound. */
#map{height:620px;border-radius:12px;z-index:0;background:var(--water)}
.place{font:11px/1.2 system-ui,sans-serif;color:var(--muted);white-space:nowrap;
  text-shadow:0 0 3px var(--surface-1),0 0 3px var(--surface-1);
  pointer-events:none;font-weight:500;letter-spacing:.01em;
  transform:translate(-50%,-50%)}
/* Ranked bars: the same metric, directly comparable. Bars are thin, 4px rounded
   at the data end only, anchored to a shared baseline. */
.rank{padding:12px 14px}
.rank h3{margin:0 0 10px;font-size:12.5px;font-weight:600;
  color:var(--text-secondary)}
.row{display:grid;grid-template-columns:168px 1fr 80px;gap:8px;align-items:center;
  padding:3px 4px;border-radius:6px;cursor:pointer}
.row:hover,.row.on{background:var(--plane)}
.row .z{font-size:11.5px;color:var(--text-secondary);overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap}
.row .v{font-size:12px;text-align:right;font-variant-numeric:tabular-nums;
  color:var(--text-primary)}
.row.comp{grid-template-columns:168px 1fr 74px}
.row.home{grid-template-columns:186px 1fr 74px;cursor:pointer}
.ghost.tiny{padding:2px 8px;font-size:11px;border-radius:6px;flex:0 0 auto;
  white-space:nowrap}
/* Two deliberate rows rather than letting flex wrap where it runs out: the label and the
   button on the first, the key beneath. Some of these labels and keys are long -- "Most fast
   sales settling under the ask" over "% of that area's sales that went pending within 10
   days" -- and left to wrap, five of the fifteen panels put the button on a line of its own. */
#leaders .rank h3{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:3px 8px;
  align-items:center}
#leaders .rank h3>span:first-child{grid-area:1/1/2/2}
#leaders .rank h3>button{grid-area:1/2/2/3}
#leaders .rank h3>.key{grid-area:2/1/3/3;margin-left:0;white-space:normal}
/* One track, two thumbs, and the price distribution drawn above it. The histogram is the
   point: it shows where the sales actually are, so a band is chosen against the shape of the
   market rather than by guessing at numbers. Both inputs are stacked over the same track with
   pointer-events off except on the thumbs, which is what lets either one be grabbed. */
.scopebar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:9px 14px;
  margin-bottom:14px;font-size:12.5px;color:var(--text-secondary)}
.scopebar .pttl{font-weight:600;flex:0 0 auto}
.scopebar .sout{margin-left:auto;color:var(--muted);text-align:right}
.scopebar .sout b{color:var(--text-primary)}
.seg.tiny{display:inline-flex;gap:0;border:1px solid var(--border);border-radius:7px;
  overflow:hidden}
.seg.tiny button{padding:4px 9px;font-size:12px;border:0;border-radius:0;
  background:var(--surface-1);color:var(--text-secondary);cursor:pointer}
.seg.tiny button + button{border-left:1px solid var(--border)}
.seg.tiny button[aria-pressed="true"]{background:var(--series-link);color:#fff;
  font-weight:600}
.pricebar{padding:10px 14px 14px;margin-bottom:16px;font-size:12.5px;
  color:var(--text-secondary)}
.pricebar .phead{display:flex;align-items:center;gap:10px;margin-bottom:6px}
.pricebar .pttl{font-weight:600;flex:0 0 auto}
.pricebar .pout{margin-left:auto;color:var(--text-secondary);
  font-variant-numeric:tabular-nums;text-align:right}
.pricebar .pout b{color:var(--text-primary)}
.pricebar .pout .warn{color:var(--muted)}
.phist{display:flex;align-items:flex-end;gap:1px;height:38px}
.phist i{flex:1 1 0;min-width:0;background:var(--axis);border-radius:2px 2px 0 0;
  transition:background .12s}
.phist i.on{background:var(--series-link)}
.prange{position:relative;height:20px;margin-top:2px}
.ptrack,.psel{position:absolute;top:8px;height:4px;border-radius:2px}
.ptrack{left:0;right:0;background:var(--grid)}
.psel{background:var(--series-link)}
.prange input{position:absolute;left:0;top:0;width:100%;height:20px;margin:0;
  -webkit-appearance:none;appearance:none;background:none;pointer-events:none}
.prange input:focus{outline:none}
.prange input::-webkit-slider-thumb{-webkit-appearance:none;pointer-events:auto;
  width:14px;height:14px;border-radius:50%;background:var(--surface-1);
  border:2px solid var(--series-link);cursor:grab;box-shadow:0 1px 3px rgba(0,0,0,.25)}
.prange input::-moz-range-thumb{pointer-events:auto;width:14px;height:14px;
  border-radius:50%;background:var(--surface-1);border:2px solid var(--series-link);
  cursor:grab;box-shadow:0 1px 3px rgba(0,0,0,.25)}
.pticks{position:relative;height:14px;color:var(--muted);font-size:10.5px;margin-top:1px}
.pticks span{position:absolute;transform:translateX(-50%);white-space:nowrap}
.pticks span:first-child{transform:none}
.pticks span:last-child{transform:translateX(-100%)}
.row.step{cursor:pointer}
.row.step:hover{background:var(--plane)}
.row.lead{grid-template-columns:202px 1fr 84px;cursor:pointer}
.row.lead .z{font-size:11.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
  cursor:help}
.row.lead .z .zc{color:var(--muted);font-size:10.5px;font-style:normal;margin-left:5px}
.row.lead .v .nb{margin-left:5px}
.row.lead:hover{background:var(--plane)}
.row.home .z{font-size:11.5px}
.row.home:hover{background:var(--plane)}
.crumb{background:none;border:0;padding:0 1px;font:inherit;color:var(--series-link);
  cursor:pointer;font-weight:600}
.crumb:hover{text-decoration:underline}
.drill .sep{color:var(--muted);margin:0 5px}
.row.cuts{grid-template-columns:168px 1fr 96px}
.row.comp .v .nb{margin-left:5px}
.row.faint{opacity:.55}
.stack{display:flex;height:13px;gap:2px}   /* 2px surface gap between fills */
.seg2{border-radius:2px}
.seg2.a{border-radius:3px 2px 2px 3px}
.seg2.c{border-radius:2px 3px 3px 2px}
.rank h3{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.key{margin-left:auto;font-weight:400;font-size:11px;color:var(--muted);
  display:flex;align-items:center;white-space:nowrap}
.key i{display:inline-block;width:8px;height:8px;border-radius:2px;
  margin:0 4px 0 0;vertical-align:0}
.sortbtn{appearance:none;border:1px solid transparent;background:transparent;
  color:var(--text-secondary);font:inherit;font-size:11px;cursor:pointer;
  padding:2px 6px;margin-left:3px;border-radius:5px}
.sortbtn:hover{background:var(--plane);color:var(--text-primary)}
.sortbtn.on{background:var(--plane);border-color:var(--border);
  color:var(--text-primary);font-weight:600}
.row .v .sl{font-style:normal;color:var(--muted);margin:0 1px}
.row .v b{font-weight:650}
.track{position:relative;height:13px}
.track .zero{position:absolute;top:-1px;bottom:-1px;width:1px;background:var(--axis)}
.bar{position:absolute;top:1px;height:11px;border-radius:2px}
.bar.pos{border-radius:2px 4px 4px 2px}
.bar.neg{border-radius:4px 2px 2px 4px}
/* Two rows rather than one: at half width the single flex row orphaned "sold over ask"
   onto a line of its own. Placed by grid area, so the source order stays as written. */
.legend{display:grid;grid-template-columns:auto 1fr auto;column-gap:10px;row-gap:7px;
  align-items:center;padding:12px 14px}
.legend .title{grid-area:1/1/2/4}
.legend #lo{grid-area:2/1/3/2}
.legend .swatches{grid-area:2/2/3/3;justify-self:center}
.legend #hi{grid-area:2/3/3/4;justify-self:end}
/* Its own row, and allowed to wrap: sharing row 1 put it in a column sized by "sold over
   ask", which clipped it mid-word at this width. */
.legend #legendNote{grid-area:3/1/4/4;justify-self:end;white-space:normal;
  text-align:right}
.swatches{display:flex;gap:2px}/* 2px surface gap between fills */
.sw{width:34px;height:14px;border-radius:2px;border:1px solid var(--border)}
.legend .ends{color:var(--muted);font-size:12px;white-space:nowrap}
.legend .title{font-weight:600;font-size:12.5px;color:var(--text-secondary)}
/* Tooltip */
.tip{font:13px/1.45 system-ui,sans-serif;min-width:210px}
.tip h4{margin:0 0 6px;font-size:13.5px;font-weight:650}
.tip .big{font-size:22px;font-weight:650;letter-spacing:-0.02em;margin:2px 0 6px}
.tip table{border-collapse:collapse;width:100%;margin-top:2px}
.tip td{padding:1px 0;font-size:12.5px;color:var(--text-secondary)}
.tip td.v{text-align:right;color:var(--text-primary);
  font-variant-numeric:tabular-nums}
.tip .ex{margin-top:7px;padding-top:6px;border-top:1px solid var(--border);
  font-size:12px;color:var(--text-secondary)}
.tip .ex b{color:var(--text-primary);font-weight:600}
.leaflet-tooltip.rdc{background:var(--surface-1);color:var(--text-primary);
  border:1px solid var(--border);border-radius:10px;
  box-shadow:0 6px 24px rgba(0,0,0,.16);padding:11px 12px}
.leaflet-tooltip.rdc:before{display:none}
/* Outside the map, so the map's overflow:hidden cannot cut it, and hoverable, so the link
   inside it is reachable. */
.tip-float{position:absolute;z-index:1200;background:var(--surface-1);
  color:var(--text-primary);border:1px solid var(--border);border-radius:10px;
  box-shadow:0 8px 28px rgba(0,0,0,.20);padding:11px 12px;max-width:330px;
  pointer-events:auto}
.tip-float.hidden{display:none}
/* The pinned version of the same panel. Matched to the tooltip so clicking a dot looks
   like the hover panel staying put rather than a different component appearing. */
.leaflet-popup.rdc .leaflet-popup-content-wrapper{background:var(--surface-1);
  color:var(--text-primary);border:1px solid var(--border);border-radius:10px;
  box-shadow:0 8px 28px rgba(0,0,0,.20);padding:2px}
.leaflet-popup.rdc .leaflet-popup-content{margin:9px 11px;width:auto!important}
.leaflet-popup.rdc .leaflet-popup-scrolled{border:0;scrollbar-width:thin;
  overscroll-behavior:contain}
.leaflet-popup.rdc .leaflet-popup-tip{background:var(--surface-1);
  border:1px solid var(--border);box-shadow:none}
.leaflet-popup.rdc a.leaflet-popup-close-button{color:var(--muted);top:5px;right:5px;
  width:20px;height:20px;font:16px/20px system-ui,sans-serif}
.leaflet-popup.rdc a.leaflet-popup-close-button:hover{color:var(--text-primary)}
.leaflet-popup.rdc .tip h4{padding-right:16px}
/* Table view */
table.data{width:100%;border-collapse:collapse;font-size:13px;margin-top:10px}
table.data td.zl{font-size:11.5px;color:var(--muted);text-align:left}
table.data th,table.data td{padding:7px 9px;text-align:right;
  border-bottom:1px solid var(--grid);font-variant-numeric:tabular-nums}
table.data th{color:var(--text-secondary);font-weight:600;font-size:12px;
  text-align:right;border-bottom:1px solid var(--axis)}
table.data th:first-child,table.data td:first-child,
table.data th:nth-child(2),table.data td:nth-child(2){text-align:left;
  font-variant-numeric:normal}
table.data tr:hover td{background:var(--plane)}
.hidden{display:none !important}
.drill{display:flex;align-items:center;gap:12px;padding:9px 13px;margin-bottom:10px;
  font-size:13px;color:var(--text-secondary)}
.drill b{color:var(--text-primary)}
.dotkey{white-space:nowrap}
.dotkey i{display:inline-block;width:10px;height:10px;border-radius:50%;
  vertical-align:-1px;margin:0 4px 0 10px}
.dotkey i.solid{background:var(--muted);border:2px solid var(--surface-1)}
.dotkey i.hollow{background:var(--surface-1);border:2px dashed var(--muted)}
.drill button{margin-left:auto}
.tip.sale{min-width:250px;max-width:320px}
.tip .warn{font-size:12px;color:var(--text-primary);background:var(--plane);
  border-left:2px solid var(--muted);padding:5px 7px;margin:0 0 7px;border-radius:0 4px 4px 0}
.bar.thin{background:repeating-linear-gradient(45deg,var(--grid) 0 3px,
  var(--axis) 3px 5px)}
.nb{font-style:normal;color:var(--muted);font-size:11px;margin-left:4px}
.tip .delta{font-size:12.5px;color:var(--text-secondary);margin:-4px 0 7px}
.tip .flag{margin-top:6px;font-size:12px;color:var(--text-secondary);
  border-left:2px solid var(--axis);padding-left:7px}
.tip .ex table{margin-top:3px}
.tip .ex td{font-size:11.5px;padding:0}
.tip a{color:var(--series-link);font-weight:600;text-decoration:none}
.tip a:hover{text-decoration:underline}
.note{color:var(--muted);font-size:12px;margin-top:14px;max-width:760px}
.note b{color:var(--text-primary);font-weight:600}
.note#summary{max-width:860px;font-size:13px;color:var(--text-secondary);margin-top:16px}
.note.howto{max-width:860px;margin-top:8px;color:var(--muted);font-size:12.5px}
/* Non-breaking space: a trailing literal space in `content` collapses, giving "it —Bar". */
.note.howto:before{content:"How to read it \2014\00a0";color:var(--text-secondary);
  font-weight:600}
</style></head>
<body><div class="viz-root">
<h1>Greater Seattle Area Home Sales Analysis</h1>
<p class="sub">__NREG__ regions &middot; __NZIP__ ZIP codes &middot;
 __NAREA__ market areas &middot; houses, townhomes and condos available &middot;
 every sale with a recorded asking price &middot; the ask is the opening of the campaign that
 produced the sale, so a home relisted after months off market is measured from its own
 campaign &middot; source: realtor.com</p>

<div class="card scopebar">
  <span class="pttl">Property type</span>
  <div class="seg tiny" id="ptSeg">
    <button data-pt="s" aria-pressed="true">Houses</button>
    <button data-pt="t" aria-pressed="false">Townhomes</button>
    <button data-pt="c" aria-pressed="false">Condos</button>
  </div>
  <span class="pttl">Sold within</span>
  <div class="seg tiny" id="winSeg">
    <button data-win="1" aria-pressed="true">1 month</button>
    <button data-win="3" aria-pressed="false">3 months</button>
    <button data-win="6" aria-pressed="false">6 months</button>
  </div>
  <span class="sout" id="sOut"></span>
</div>

<div class="card pricebar">
  <div class="phead">
    <span class="pttl">Price band</span>
    <span class="pout" id="pOut"></span>
    <button class="ghost tiny" id="pReset">Reset</button>
  </div>
  <div class="phist" id="pHist" aria-hidden="true"></div>
  <div class="prange">
    <div class="ptrack"></div><div class="psel" id="pSel"></div>
    <input type="range" id="pLo" min="0" step="1" aria-label="Lowest price">
    <input type="range" id="pHi" min="0" step="1" aria-label="Highest price">
  </div>
  <div class="pticks" id="pTicks"></div>
</div>

<div class="controls">
  <div class="seg" id="tabSeg" role="group" aria-label="Metric">
    <button data-v="vs_ask" aria-pressed="true">Sold vs&nbsp;ask</button>
    <button data-v="split" aria-pressed="false">Above / at / below</button>
    <button data-v="fast" aria-pressed="false">Above / at / below &mdash;
      fast&nbsp;sales</button>
    <button data-v="days" aria-pressed="false">Days to&nbsp;pending</button>
    <button data-v="cuts" aria-pressed="false">Price cuts</button>
    <button data-v="depth" aria-pressed="false">Cut depth</button>
    <button data-v="price" aria-pressed="false">Median price</button>
    <button data-v="ppsf" aria-pressed="false">$ / sqft</button>
  </div>
  <div class="spacer"></div>
  <button class="ghost" id="toggleTable" aria-pressed="false">Show table</button>
  <button class="ghost" id="toggleTheme">Dark</button>
</div>

<div id="drillBar" class="card drill hidden">
  <span id="drillText"></span>
  <button class="ghost" id="backBtn">Back</button>
</div>
<div id="floatTip" class="tip-float hidden"></div>

<div class="pair">
  <div class="col">
    <div class="card"><div id="map"></div></div>
    <div class="card legend">
      <span class="title" id="legendTitle"></span>
      <span class="ends" id="lo"></span>
      <span class="swatches" id="swatches"></span>
      <span class="ends" id="hi"></span>
      <span class="ends" id="legendNote" style="margin-left:auto"></span>
    </div>
  </div>
  <div class="col">
    <div class="card rank" id="chartCard">
      <h3 id="chartTitle"></h3><div id="chartRows"></div>
    </div>
    <div id="leaders">
      <div class="card rank cap"><h3 id="lowTitle"></h3><div id="lowRows"></div></div>
      <div class="card rank cap"><h3 id="highTitle"></h3><div id="highRows"></div></div>
    </div>
  </div>
</div>

<div id="tableWrap" class="hidden">
  <table class="data"><thead><tr>
    <th id="thUnit">Region</th><th id="thMembers">Market areas</th>
    <th>Sales</th><th>Sold vs ask</th>
    <th>Above</th><th>At</th><th>Below</th>
    <th>Days to pending</th><th>Sold &lt;10 days</th><th>Cut price</th>
    <th>Published cut</th><th>At table</th>
    <th>Median price</th><th>$/sqft</th>
  </tr></thead><tbody id="tbody"></tbody></table>
</div>

<p class="note" id="summary"></p>
<p class="note howto" id="howto"></p>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const DATA = __PAYLOAD__;
const fmt = {
  median_vs_ask: v => (v > 0 ? "+" : "") + v.toFixed(2) + "%",
  over_ask_pct:  v => v.toFixed(0) + "%",
  at_ask_pct:    v => v.toFixed(0) + "%",
  below_ask_pct: v => v.toFixed(0) + "%",
  median_days:   v => v == null ? "n/a" : v + " d",
  cuts_mean:     v => v == null ? "n/a" : v.toFixed(2),
  fast_over_pct: v => v == null ? "n/a" : v.toFixed(0) + "%",
  below_ask_pct: v => v == null ? "n/a" : v.toFixed(0) + "%",
  over_ask_pct2: v => v == null ? "n/a" : v.toFixed(0) + "%",
  fast_over_pct: v => v == null ? "n/a" : v.toFixed(0) + "%",
  even_dev:      v => v == null ? "n/a" : v.toFixed(0),
  cut_size_median: v => v == null ? "n/a" : v.toFixed(1) + "%",
  median_price:  v => v == null ? "n/a" : v >= 1e6
                   ? "$" + (v / 1e6).toFixed(2) + "M" : "$" + Math.round(v / 1000) + "k",
  median_ppsf:   v => v == null ? "n/a" : "$" + v.toLocaleString(),
};
const META = {
  median_vs_ask: {label:"Median sold vs original ask", diverging:true, mid:0,
                  lo:"sold under ask", hi:"sold over ask"},
  over_ask_pct:  {label:"Share of sales ABOVE ask (more than +0.5%)",
                  diverging:false, arm:"warm", lo:"none", hi:"most"},
  at_ask_pct:    {label:"Share of sales AT ask (within \u00b10.5%)",
                  diverging:false, arm:"grey", lo:"none", hi:"most"},
  fast_below_pct: {label:"Fast sales that settled under the ask", diverging:false,
                  arm:"cool", lo:"none", hi:"most"},
  /* Ranked on, never mapped: grey because a balance score has no favourable direction. */
  even_dev:      {label:"Distance from an even split", diverging:false, arm:"grey",
                  lo:"most balanced", hi:"least balanced"},
  cuts_mean:     {label:"Mean price cuts per listing", diverging:false, arm:"cool",
                  lo:"none", hi:"most"},
  median_days:   {label:"Median days from listing to contract", diverging:false,
                  lo:"fast", hi:"slow", invert:true},
  median_price:  {label:"Median sold price", diverging:false,
                  arm:"cool", lo:"lower", hi:"higher"},
  median_ppsf:   {label:"Median price per square foot", diverging:false,
                  lo:"lower", hi:"higher"},
  /* One hue, one share. The stacked bars beside the map carry the other two and the three
     leaderboards below rank on each in turn, so nothing is lost by not encoding all three in
     the fill -- which a literal three-colour blend was measured unable to do anyway: red and
     blue mix to purple, putting every unit in one band 0.6 to 8.4 apart in OKLab against a
     readable floor of 8. */
  below_ask_pct: {label:"Share of sales below the original ask", diverging:false,
                  arm:"cool", lo:"fewest", hi:"most"},
  fast_over_pct: {label:"Fast sales that beat the ask", diverging:false,
                  arm:"warm", lo:"none", hi:"most"},
  /* Every value is negative, so the *minimum* is the deepest cut. `invert` paints that
     end dark, the same way it does for days-to-pending, and the legend flips with it. */
  cut_size_median: {label:"Median cut, among homes that cut", diverging:false,
                  arm:"cool", lo:"deepest", hi:"shallowest", invert:true},
};

/* One tab, one chart, one map that colours by what the chart measures. Seven of them,
   because there are seven distinct readings here and the previous four-tab layout had to
   pair two unrelated charts per tab to fit -- which is what made it dense. Two of the
   pairings were also duplicates: the above/at/below split was the left panel of both the
   sold-vs-ask and the $/sqft tab, saying the same thing twice. */
const VIEWS = [
  {id:"vs_ask", metric:"median_vs_ask",   chart:rankedBars},
  {id:"split",  metric:"below_ask_pct",   chart:composition},
  {id:"fast", base:"fast_n", baseNoun:"fast sales",   metric:"fast_over_pct",  chart:fastSplit},
  {id:"days",   metric:"median_days",     chart:rankedBars},
  {id:"cuts",   metric:"cuts_mean",       chart:cutsList},
  {id:"depth", base:"cutters_n", baseNoun:"cutters",  metric:"cut_size_median", chart:cutDepth},
  {id:"price",  metric:"median_price",    chart:rankedBars},
  {id:"ppsf",   metric:"median_ppsf",     chart:rankedBars},
];
let view = VIEWS[0];
/* The denominator the current reading stands on, which is not always the ZIP's sale count. */
function baseN(r){ return r[view.base || "n"] ?? 0; }
/* Below this many sales a ZIP median is not a market reading and must not be
   coloured as though it were. At n=2 the median *is* the mean -- it has no outlier
   resistance at all, and 98107 came out the reddest tile in the region on
   [-0.47%, +23.81%], a pair that describes neither house and contradicts the other
   eight sales in its own ZIP. Hatched rather than hidden: the data exists, it just
   cannot carry a colour. */
const MIN_N = 5;
let metric = VIEWS[0].metric;
/* Which segment the composition list is ordered by. Sorting by "at" is the one that
   surfaces price-to-sell markets, which neither of the other two orderings reveals. */
let compSort = "above";
/* ---- the stats engine ----------------------------------------------------------------
   Every per-unit figure is derived here from the individual sales rather than read from a
   precomputed table. That is what makes the price filter possible at all: the numbers are a
   function of whichever sales are in scope, so narrowing the band re-answers every question
   instead of filtering a set of answers computed for a different question.

   It also removes a duplicate: the same medians used to exist in Python and would have needed
   a second implementation here, free to drift. Verified against the Python output with the
   filter wide open -- all 86 ZIPs, 37 areas and 12 regions match field for field. */
const STEPS = __STEPS__;                 /* index 0 and last mean "unbounded" */
const PRICE = {lo: null, hi: null};
/* Houses, townhomes and condos; all three on by default. Multi-select because they are three
   markets a buyer may weigh together, unlike the window, where 1, 3 and 6 months are three
   answers to the same question and only one can be on screen. */
const SCOPE = {types: new Set(["s"]), months: 1};
const PT_LABEL = {s: "houses", t: "townhomes", c: "condos"};
const WINDOW_DAYS = {1: 30, 3: 91, 6: 999};      /* 6 is the whole fetched span */
const ZMETA = DATA.meta.zip;
const WIN_END = DATA.window[1];
/* Dates travel as offsets from DATA.epoch; put them back only where one is displayed. */
const EPOCH_MS = Date.parse(DATA.epoch + "T00:00:00Z");
const dayStr = off => new Date(EPOCH_MS + off * 86400000).toISOString().slice(0, 10);
const cutoff = () => WIN_END - WINDOW_DAYS[SCOPE.months];

function inScope(p){
  return SCOPE.types.has(p.pt) && p.sd > cutoff();
}
function inBand(p){
  return (PRICE.lo == null || p.sp >= PRICE.lo) && (PRICE.hi == null || p.sp <= PRICE.hi);
}
/* Type and window only: what the price histogram must draw, since a histogram of the band
   would show nothing but the band. */
function scopeSales(){ return DATA.points.filter(inScope); }
function activeSales(){ return DATA.points.filter(p => inScope(p) && inBand(p)); }

const _med = a => { const v = a.filter(x => x != null).sort((x, y) => x - y);
  if (!v.length) return null;
  const h = v.length >> 1;
  return v.length % 2 ? v[h] : (v[h - 1] + v[h]) / 2; };
const _r1 = v => Math.round(v * 10) / 10;
const _r2 = v => Math.round(v * 100) / 100;

/* `all` is every sale in the unit; `keep` is those with a priced opening. Only `fast_pct` uses
   the wider denominator -- it answers "what share of this unit's sales went fast", which a
   missing ask does not disqualify. Everything else is measured on `keep`. */
function statsFor(key, all, kind){
  const keep = all.filter(p => p.oa != null);
  if (!keep.length) return null;
  const n = keep.length;
  const vs = keep.map(p => p.va * 100);
  const over = vs.filter(v => v > 0.5).length;
  const at = vs.filter(v => Math.abs(v) <= 0.5).length;
  const below = vs.filter(v => v < -0.5).length;
  const rawO = over / n * 100, rawA = at / n * 100, rawB = below / n * 100;
  const op = _r1(rawO), ap = _r1(rawA), bp = _r1(rawB);
  const days = keep.map(p => p.dp).filter(v => v != null);
  const ppsf = keep.filter(p => p.sq).map(p => p.sp / p.sq);
  const cutters = keep.filter(p => p.nc > 0);
  const fast = keep.filter(p => p.dp != null && p.dp < 10);
  const fv = fast.map(p => p.va * 100);
  const fo = fv.filter(v => v > 0.5).length;
  const fa = fv.filter(v => Math.abs(v) <= 0.5).length;
  const fb = fv.filter(v => v < -0.5).length;
  const allFast = all.filter(p => p.dp != null && p.dp < 10).length;
  const m = (DATA.meta[kind] || {})[key] || {};
  return {
    zip: key, members: m.members || "", label: m.label || key,
    area: m.area, region: m.region,
    n: n,
    median_vs_ask: _r2(_med(vs)),
    over_ask_pct: op, over_ask_n: over,
    at_ask_pct: ap, at_ask_n: at,
    below_ask_pct: bp, below_ask_n: below,
    /* From the unrounded shares. Summing the rounded ones drifts by up to a tenth, which
       showed up as a real disagreement against the reference figures. */
    even_dev: _r1(Math.abs(rawO - 100/3) + Math.abs(rawA - 100/3) + Math.abs(rawB - 100/3)),
    median_days: days.length ? Math.trunc(_med(days)) : null,
    fast_pct: _r1(allFast / Math.max(all.length, 1) * 100),
    median_price: Math.trunc(_med(keep.map(p => p.sp))),
    median_ppsf: ppsf.length ? Math.trunc(_med(ppsf)) : null,
    cut_pct: _r1(cutters.length / n * 100),
    cuts_mean: _r2(keep.reduce((t, p) => t + p.nc, 0) / n),
    cuts_median: _med(keep.map(p => p.nc)),
    cuts_max: Math.max(...keep.map(p => p.nc)),
    cut_size_median: cutters.length
      ? _r2(_med(cutters.map(p => p.cd * 100))) : null,
    cutters_n: cutters.length,
    cuts_median_among_cutters: cutters.length ? _med(cutters.map(p => p.nc)) : null,
    negotiated_median: _r2(_med(keep.map(p => p.ng * 100))),
    fast_n: fast.length,
    fast_over_pct: fast.length ? _r1(fo / fast.length * 100) : null, fast_over_n: fo,
    fast_at_pct: fast.length ? _r1(fa / fast.length * 100) : null, fast_at_n: fa,
    fast_below_pct: fast.length ? _r1(fb / fast.length * 100) : null, fast_below_n: fb,
  };
}
const UNITS = {region: [], zip: [], area: []};
function recompute(){
  const sales = activeSales();
  for (const [kind, field] of [["region", "rg"], ["zip", "z"], ["area", "ar"]]){
    const by = new Map();
    for (const p of sales){
      const m = ZMETA[p.z];
      if (!m) continue;
      const k = field === "z" ? p.z : field === "ar" ? m.area : m.region;
      if (k == null) continue;
      if (!by.has(k)) by.set(k, []);
      by.get(k).push(p);
    }
    UNITS[kind] = [...by].map(([k, g]) => statsFor(k, g, kind)).filter(Boolean)
      .sort((a, b) => b.median_vs_ask - a.median_vs_ask);
  }
}

/* Three tiers. The reader picks where to spend attention before being shown 81 ZIP codes:
   7 regions -> the ZIPs inside one region -> the homes inside one ZIP. `level` is the single
   source of truth; every lookup below derives from it rather than keeping parallel state,
   which is what made the old single-level drill-down leak a stale selection on redraw. */
let level = 0, openRegion = null, openZipCode = null;
/* Which ZIPs a region contains, from the metadata rather than from whatever survived a
   filter -- the polygon set must not change as the price band narrows, only the colours. */
const REGION_ZIPS = {};
Object.entries(DATA.meta.zip).forEach(([z, m]) =>
  (REGION_ZIPS[m.region] = REGION_ZIPS[m.region] || []).push(z));

/* The stat rows the current level charts and colours. */
function units(){
  if (level === 0) return UNITS.region;
  return UNITS.zip.filter(r => r.region === openRegion);
}
/* Keyed lookup for whatever the polygons currently are. */
let stats = {};
function reindex(){ stats = {}; units().forEach(r => stats[r.zip] = r); }
reindex();
/* The polygons for the current level: regions, or the ZIPs of the open region. */
function geoFor(){
  if (level === 0) return DATA.geo;
  const want = new Set(REGION_ZIPS[openRegion] || []);
  return {type:"FeatureCollection",
          features: DATA.zipgeo.features.filter(f => want.has(f.properties.zip))};
}

function isDark(){
  const t = document.documentElement.getAttribute("data-theme");
  if (t) return t === "dark";
  return matchMedia("(prefers-color-scheme: dark)").matches;
}
function ramp(){ return isDark() ? DATA.ramp.dark : DATA.ramp.light; }
function surface(){ return isDark() ? "#1a1a19" : "#fcfcfb"; }

/* Diverging: symmetric domain so the neutral sits exactly at parity.
   Sequential: one hue, light to dark, using the warm arm reversed for "more". */
function colourable(){
  const t = units().filter(r => (r[view.base || "n"] ?? 0) >= MIN_N);
  return t.length >= 3 ? t : units();         /* never leave the ramp without a domain */
}
function scaleFor(m){ return scaleOver(colourable(), m); }
function scaleOver(rows, m){
  const vals = rows.map(r => r[m]).filter(v => v != null);
  const R = ramp();
  if (META[m].diverging){
    const bound = Math.max(...vals.map(Math.abs));
    const step = bound / 3;
    /* The two arms are stored in opposite directions -- `warm` runs light->dark and
       `cool` runs dark->light -- so indexing both by magnitude paints them opposite ways.
       That shipped: at -11.30% 98011 took cool[2] (#b7d3f6, the palest step) while 98026
       at -1.42% took cool[0] (#2a78d6, the darkest), so the most-discounted ZIP in the
       region read as the least. The legend was inverted identically, which is why the two
       agreed with each other and neither looked wrong. `cool` is therefore indexed from
       the far end, and both now run light at parity to dark at the extreme. */
    const step3 = v => Math.min(2, Math.floor(v / step));
    return v => {
      if (v == null) return null;
      if (v >  step*0.15) return R.warm[step3(v)];
      if (v < -step*0.15) return R.cool[2 - step3(-v)];
      return R.neutral;
    };
  }
  const min = Math.min(...vals), max = Math.max(...vals);
  const arm = META[m].arm || "cool";
  /* One hue, light to dark. `warm` is stored dark-to-light, so it is reversed here to
     keep every ramp running the same direction. */
  const src = arm === "warm" ? [...R.warm].reverse() : R[arm];
  const seq = [src[2], src[1], src[0]];
  return v => {
    if (v == null) return null;
    let t = (v - min) / (max - min || 1);
    if (META[m].invert) t = 1 - t;
    return seq[Math.min(2, Math.floor(t * 3))];
  };
}

const map = L.map("map", {scrollWheelZoom:false, zoomControl:true});
map.createPane("landPane").style.zIndex   = 400;
map.createPane("dataPane").style.zIndex   = 450;
map.createPane("waterPane").style.zIndex  = 460;
map.createPane("salePane").style.zIndex   = 465;
map.createPane("labelPane").style.zIndex  = 470;
map.getPane("waterPane").style.pointerEvents = "none";
map.getPane("labelPane").style.pointerEvents = "none";
let tiles = null, layer = null;
/* No tile basemap, deliberately.
   CARTO now watermarks "API KEY REQUIRED" over every tile, and OpenStreetMap blocks
   the request outright -- "App is not following tile usage policy" -- because a
   file:// page sends no Referer and nothing identifies the app. Every remaining
   keyless provider has the same problem.

   So the geography is drawn from the boundary data we already have: neighbouring
   ZCTAs as hairline outlines. Puget Sound appears as the gap where no ZCTA exists,
   which is exactly where the water is. The upside is a file with no network
   dependency at all -- it renders offline and cannot be rate-limited. */
function addTiles(){
  if (tiles) map.removeLayer(tiles);
  tiles = L.geoJSON(DATA.context, {
    pane: "landPane", interactive: false,
    style: () => ({fill:true, fillColor:isDark() ? "#242423" : "#f1f0ec",
                   fillOpacity:1, color:isDark() ? "#2f2f2d" : "#e4e3dd",
                   weight:1, opacity:1}),
  }).addTo(map);
  waterLayer();
  labelLayer();
}

let water = null;
/* Lake Washington, Union, Sammamish, Ballinger and Green Lake, from Census
   TIGER AREAWATER for King and Snohomish -- the same source family as the ZCTAs, so
   the geometries line up exactly. They have to be drawn *above* the ZIP fills: a ZCTA
   includes its own water area, so the land-and-gap trick only ever revealed the outer
   coastline and every inland lake stayed hidden under a choropleth fill. */
function waterLayer(){
  if (water) map.removeLayer(water);
  water = L.geoJSON(DATA.water, {
    pane: "waterPane", interactive: false,
    style: () => ({fill:true, fillColor:isDark() ? "#101015" : "#dfe4e8",
                   fillOpacity:1, color:isDark() ? "#26262c" : "#cfd6dc",
                   weight:0.6, opacity:1}),
  }).addTo(map);
}

let labels = null;
const LABEL_GAP = 58;      /* px; ~4.5 characters of breathing room at 11px */
function labelLayer(){
  /* The collision filter projects to screen pixels, which throws until the map has a view.
     `addTiles()` runs before `draw()` sets one, so the first call is a no-op and the
     `fitBounds` inside `draw()` fires moveend, which calls this again with a live view. */
  if (!map._loaded) return;
  if (labels) map.removeLayer(labels);
  const placed = [];
  const keep = [];
  for (const l of DATA.labels){
    const pt = map.latLngToContainerPoint([l.lat, l.lon]);
    if (pt.x < -40 || pt.y < -20) continue;                  /* off-frame, skip silently */
    if (placed.some(q => Math.abs(q.x - pt.x) < LABEL_GAP
                      && Math.abs(q.y - pt.y) < 15)) continue;
    placed.push(pt); keep.push(l);
  }
  labels = L.layerGroup(keep.map(l => L.marker([l.lat, l.lon], {
    pane: "labelPane", interactive: false, keyboard: false,
    icon: L.divIcon({className:"place", html:l.n, iconSize:null}),
  }))).addTo(map);
}
/* Re-run the filter after any zoom or pan: which labels fit is a function of the view. */
map.on("zoomend moveend", () => labelLayer());

/* ---- drill-down: a ZIP opens into its individual sales ---- */
let sales = null, openZip = null;
const money = v => "$" + Number(v).toLocaleString();
const listingUrl = p => p && p.u ? DATA.href_prefix + p.u : null;

function saleTip(p){
  const t = [];
  t.push(`<h4>${p.a}</h4>`);
  const gap = p.va == null ? null : (p.va * 100);
  t.push(`<div class="big">${money(p.sp)}</div>`);
  t.push(`<div class="delta">${gap == null ? "no recorded ask"
    : (gap >= 0 ? "+" : "") + gap.toFixed(1) + "% vs original ask"}</div>`);
  t.push("<table>");
  if (p.oa) t.push(`<tr><td>Original ask</td><td class="v">${money(p.oa)}</td></tr>`);
  if (p.fa && p.fa !== p.oa)
    t.push(`<tr><td>Final ask</td><td class="v">${money(p.fa)}</td></tr>`);
  t.push(`<tr><td>Price cuts</td><td class="v">${p.nc}</td></tr>`);
  t.push(`<tr><td>Days to pending</td><td class="v">${p.dp == null ? "n/a" : p.dp + " d"}</td></tr>`);
  t.push(`<tr><td>Days to closing</td><td class="v">${p.dc == null ? "n/a" : p.dc + " d"}</td></tr>`);
  const spec = [p.bd ? p.bd + " bd" : null, p.ba ? p.ba + " ba" : null,
                p.sq ? p.sq.toLocaleString() + " sqft" : null,
                p.yr ? "built " + p.yr : null].filter(Boolean).join(" \u00b7 ");
  if (spec) t.push(`<tr><td>Home</td><td class="v">${spec}</td></tr>`);
  t.push("</table>");
  if (p.rl || p.rt){
    const flags = [p.rl ? "relisted" : null, p.rt ? "also listed for rent" : null]
      .filter(Boolean).join(", ");
    t.push(`<div class="flag">${flags} \u2014 excluded from the ZIP medians</div>`);
  }
  if (p.ev && p.ev.length){
    const MAX = 6;
    const shown = p.ev.slice(0, MAX);
    t.push('<div class="ex"><b>Listing history</b><table>');
    for (const e of shown) t.push(`<tr><td>${dayStr(e[0])}</td>` +
      `<td>${DATA.ev_names[e[1]] || "?"}</td>` +
      `<td class="v">${e[2] ? money(e[2]) : ""}</td></tr>`);
    if ((p.nev || 0) > p.ev.length)
      t.push(`<tr><td colspan="3">+ ${p.nev - p.ev.length} earlier event(s)</td></tr>`);
    t.push("</table></div>");
  }
  t.push(`<div class="ex"><a href="${listingUrl(p)}" target="_blank" rel="noopener">` +
         `View on realtor.com \u2192</a></div>`);
  return `<div class="tip sale">${t.join("")}</div>`;
}

/* Step in: region -> its ZIPs -> its homes. One entry point, because the level decides
   everything and a separate function per transition is how the old version ended up able to
   hold a ZIP selection that no longer existed on screen. */
function openUnit(key){
  if (level === 0){ level = 1; openRegion = key; openZipCode = null; }
  else if (level === 1){ level = 2; openZipCode = key; }
  else return;
  draw();
}
function goTo(l){
  level = l;
  if (l < 2) openZipCode = null;
  if (l < 1) openRegion = null;
  draw();
}
function undrill(){ goTo(Math.max(0, level - 1)); }

/* Sale markers for the open ZIP, keyed so a row in the list can reach its own dot. */
let saleMarks = {};
function addSales(zipCode){
  const mine = activeSales().filter(p => p.z === zipCode && p.lat != null);
  const color = scaleFor("median_vs_ask"), R = ramp();
  saleMarks = {};
  sales = L.layerGroup(mine.map(p => {
    /* A sale is coloured by its own outcome on the same diverging scale as the choropleth, so
       a red dot inside a blue ZIP reads immediately as the exception it is. Counted sales are
       solid; ones with no recorded asking price are hollow, because otherwise a ZIP showing
       seven dots against a median of n=2 gave no way to see which five did not count. */
    const counts = p.oa != null;
    const own = p.va == null ? R.neutral : color(p.va * 100);
    const m = L.circleMarker([p.lat, p.lon], {
      pane:"salePane", radius:counts ? 8 : 6.5, weight:2.5,
      color:counts ? (isDark() ? "#1a1a19" : "#fcfcfb") : own, opacity:1,
      fillColor:counts ? own : (isDark() ? "#1a1a19" : "#fcfcfb"),
      fillOpacity:1, dashArray:counts ? null : "3 2",
    }).on("mouseover mousemove", e => showTip(saleTip(p), e))
      .on("mouseout", () => hideTip())
      /* Click pins the panel into a card beside the map rather than opening a Leaflet popup:
         those live inside .leaflet-container, which sets overflow:hidden, so a 324 px panel
         anchored near the top edge opened clipped -- losing the address and the price, the two
         things it exists to show -- and panning it into view fought Leaflet's positioning. */
      /* A dot behaves like its row: hover for the detail panel, click to open the listing. */
      .on("click", () => { const u = listingUrl(p);
                           if (u) window.open(u, "_blank", "noopener"); });
    saleMarks[p.i] = m;
    return m;
  })).addTo(map);
  return mine;
}

/* The chart panel at level 2: the homes themselves, measured on whatever the active tab is
   about. Asked for directly -- on the cuts tab the figure that matters per home is how many
   cuts it took, on cut depth how far the ask fell, and so on. */
const HOME_COL = {
  vs_ask: {title:"Sold vs original ask", get:p => p.va == null ? null : p.va*100,
           fmt:v => (v>0?"+":"") + v.toFixed(1) + "%", diverge:true},
  split:  {title:"Sold vs original ask", get:p => p.va == null ? null : p.va*100,
           fmt:v => (v>0?"+":"") + v.toFixed(1) + "%", diverge:true},
  fast:   {title:"Days to pending", get:p => p.dp, fmt:v => v + " d", low:true},
  days:   {title:"Days to pending", get:p => p.dp, fmt:v => v + " d", low:true},
  cuts:   {title:"Price cuts taken", get:p => p.nc, fmt:v => String(v)},
  depth:  {title:"How far the ask fell", get:p => p.cd == null ? null : p.cd*100,
           fmt:v => v.toFixed(1) + "%", low:true},
  price:  {title:"Sold price", get:p => p.sp,
           fmt:v => "$" + Math.round(v).toLocaleString()},
  ppsf:   {title:"Price per square foot", get:p => p.sq ? p.sp/p.sq : null,
           fmt:v => "$" + Math.round(v).toLocaleString()},
};
let byIndex = {};
function homeList(){
  const col = HOME_COL[view.id], R = ramp();
  const mine = activeSales().filter(p => p.z === openZipCode);
  byIndex = {}; mine.forEach(q => { byIndex[q.i] = q; });
  const vals = mine.map(col.get).filter(v => v != null);
  const lo = Math.min(0, ...vals), hi = Math.max(0, ...vals), span = (hi - lo) || 1;
  const zeroPct = ((0 - lo) / span) * 100;
  document.getElementById("chartTitle").innerHTML =
    `<span>${col.title} — ${mine.length} homes in ${openZipCode}</span>` +
    '<span class="key">hover for detail \u00b7 click opens the listing on ' +
    'realtor.com</span>';
  const sorted = [...mine].sort((a, b) => {
    const x = col.get(a), y = col.get(b);
    if (x == null) return 1;
    if (y == null) return -1;
    return col.low ? x - y : y - x;
  });
  document.getElementById("chartRows").innerHTML = sorted.map(p => {
    const v = col.get(p);
    if (v == null) return `<div class="row home" data-i="${p.i}">
      <span class="z" title="${p.a}">${p.a}</span><span class="track"></span>
      <span class="v">n/a</span></div>`;
    const w = Math.abs(v) / span * 100;
    const left = v >= 0 ? zeroPct : zeroPct - w;
    /* Diverging metrics keep the warm/cool split so one bad sale in a good ZIP is obvious;
       the rest ride the cool arm, which is the direction the whole report treats as
       buyer-favourable. */
    const bg = col.diverge ? scaleFor("median_vs_ask")(v)
             : R.cool[2 - Math.min(2, Math.floor(Math.abs(v) / (Math.max(...vals.map(Math.abs)) || 1) * 3))];
    return `<div class="row home" data-i="${p.i}" title="${p.a} · ${money(p.sp)}">
      <span class="z" title="${p.a}">${p.a}</span>
      <span class="track"><span class="zero" style="left:${zeroPct}%"></span>
        <span class="bar ${v >= 0 ? "pos" : "neg"}" style="left:${left}%;
          width:${Math.max(w, 0.8)}%;background:${bg}"></span></span>
      <span class="v">${col.fmt(v)}</span></div>`;
  }).join("");
  document.querySelectorAll(".row.home").forEach(row => {
    const p = byIndex[row.dataset.i], m = saleMarks[row.dataset.i];
    row.onmouseenter = e => {
      if (m) m.setStyle({weight:4, color:isDark() ? "#fff" : "#0b0b0b"});
      if (p) showTip(saleTip(p), e);
    };
    row.onmousemove = e => { if (p) showTip(saleTip(p), e); };
    row.onmouseleave = () => {
      if (m) m.setStyle({weight:2.5, color:isDark() ? "#1a1a19" : "#fcfcfb"});
      hideTip();
    };
    row.onclick = () => { const u = listingUrl(p);
                          if (u) window.open(u, "_blank", "noopener"); };
  });
}

/* Each tab names its own panels, and each panel names the field it ranks on -- the split tab
   ranks three different shares, so one shared field would not do. `dir` is +1 for ascending
   (lowest first) and -1 for descending. Ends are named rather than called best and worst:
   "dearest" is not better than "cheapest". */
const LEAD = {
  median_vs_ask: [
    {label:"Deepest discounts",  field:"median_vs_ask", dir: 1},
    {label:"Highest premium",    field:"median_vs_ask", dir:-1,
     key:rows => { const n = rows.filter(r => r.median_vs_ask > 0.1).length;
       return n ? `${n} of ${rows.length} clear +0.1%` : "none clears +0.1%"; }},
  ],
  below_ask_pct: [
    {label:"Most sales above ask", field:"over_ask_pct",  dir:-1},
    /* Ranked on distance from an even 33/33/33, and shown as the split itself: a deviation
       score means nothing to a reader, and a net near zero would be the wrong test anyway
       since 50/0/50 and 0/100/0 both net zero and mean opposite things. */
    {label:"Most balanced split",  field:"even_dev",      dir: 1, stacked:true,
     key:"closest to an even 33/33/33"},
    {label:"Most sales below ask", field:"below_ask_pct", dir:-1},
  ],
  /* "Fast sales, most below ask" did not say what the percentage counted. The label names the
     numerator and the key names the denominator, which on this tab is not the area's sales but
     only those that went pending inside 10 days. */
  fast_over_pct: [
    {label:"Most fast sales beating the ask", field:"fast_over_pct", dir:-1,
     base:"fast_n", key:"% of that area's sales that went pending within 10 days"},
    {label:"Most fast sales settling under the ask", field:"fast_below_pct", dir:-1,
     base:"fast_n", key:"% of that area's sales that went pending within 10 days"},
  ],
  median_days: [
    {label:"Quickest to contract", field:"median_days", dir: 1},
    {label:"Slowest to contract",  field:"median_days", dir:-1},
  ],
  cuts_mean: [
    {label:"Fewest cuts per listing", field:"cuts_mean", dir: 1},
    {label:"Most cuts per listing",   field:"cuts_mean", dir:-1},
  ],
  cut_size_median: [
    {label:"Deepest published cuts",    field:"cut_size_median", dir: 1,
     base:"cutters_n", key:"among the homes that cut"},
    {label:"Shallowest published cuts", field:"cut_size_median", dir:-1,
     base:"cutters_n", key:"among the homes that cut"},
  ],
  median_price: [
    {label:"Most affordable", field:"median_price", dir: 1},
    {label:"Most expensive",  field:"median_price", dir:-1},
  ],
  median_ppsf: [
    {label:"Cheapest per square foot", field:"median_ppsf", dir: 1},
    {label:"Dearest per square foot",  field:"median_ppsf", dir:-1},
  ],
};
/* Five each. The ends of a distribution are what a leaderboard is for; a twelfth-place entry
   is the middle of the list arriving late. */
const LEAD_N = 5;
/* The finest unit a reader can act on, but only where there is enough of it to read. Without
   the floor the extremes are simply the thinnest ZIPs: the deepest-discount panel would open
   with 98121 at -15.64% on one sale and Preston at -14.03% on two. 78 of 86 ZIPs clear five
   sales; on the fast-sales tab, where the base is only the homes that went pending inside ten
   days, 44 do, and on cut depth 48. */
const BASE_NOUN = {n:"sales", fast_n:"fast sales", cutters_n:"cutters"};
const leadOpen = new Set();

function leaders(){
  const box = document.getElementById("leaders");
  if (level !== 0){ box.classList.add("hidden"); return; }
  box.classList.remove("hidden");
  const panels = LEAD[metric] || [];
  const unitsAll = UNITS.zip;
  const R = ramp();
  /* Panels are built fresh each draw because their count varies by tab -- three on the split
     tab, two elsewhere -- and the chart above has to be capped to match. */
  box.innerHTML = panels.map((_, i) =>
    `<div class="card rank cap"><h3 id="ldT${i}"></h3><div id="ldR${i}"></div></div>`).join("");

  panels.forEach((p, i) => {
    const f = p.field, bk = p.base || "n";
    const rows = unitsAll.filter(r => r[f] != null && (r[bk] ?? 0) >= MIN_N);
    const vals = rows.map(r => r[f]);
    /* One denominator per panel, over every area rather than the five shown, so a short bar
       means a small number instead of a differently scaled one. */
    const maxAbs = Math.max(...vals.map(Math.abs)) || 1;
    const color = scaleOver(rows, META[f] ? f : metric);
    const baseOf = r => r[bk] ?? 0;
    const okey = `${metric}#${i}`, open = leadOpen.has(okey);
    const shown = open ? rows.length : LEAD_N;
    const sorted = [...rows].sort((x, y) => (x[f] - y[f]) * p.dir).slice(0, shown);
    document.getElementById("ldT" + i).innerHTML =
      `<span>${p.label}</span><span class="key">${
        p.key ? (typeof p.key === "function" ? p.key(rows) : p.key) + " · " : ""}` +
      `${open ? "all" : "top " + LEAD_N} of ${rows.length} ZIPs with ${MIN_N}+ ` +
      `${BASE_NOUN[bk]}</span>` +
      `<button class="ghost tiny" data-lead="${okey}">${open
        ? "Top " + LEAD_N : "Show all " + rows.length}</button>`;
    document.getElementById("ldR" + i).innerHTML = sorted.map(r => {
      const v = r[f];
      /* The balanced panel shows the three shares as a stacked bar, which is the thing being
         ranked; a bar of the deviation score would encode the score, not the balance. */
      const track = p.stacked
        ? `<span class="stack">
             <span class="seg2 a" style="width:${r.over_ask_pct}%;background:${R.warm[2]}"></span>
             <span class="seg2 b" style="width:${r.at_ask_pct}%;background:${R.grey[1]}"></span>
             <span class="seg2 c" style="width:${r.below_ask_pct}%;background:${R.cool[0]}"></span>
           </span>`
        : `<span class="track"><span class="bar ${v >= 0 ? "pos" : "neg"}"
             style="left:${v >= 0 ? 0 : 100 - Math.abs(v) / maxAbs * 100}%;
             width:${Math.max(Math.abs(v) / maxAbs * 100, 1.2)}%;
             background:${color(v)}"></span></span>`;
      const shown = p.stacked
        ? `${Math.round(r.over_ask_pct)}<em class="sl">/</em>${Math.round(r.at_ask_pct)}` +
          `<em class="sl">/</em>${Math.round(r.below_ask_pct)}`
        : (fmt[f] || fmt[metric])(v);
      return `<div class="row lead" data-region="${r.region}" data-zip="${r.zip}"
          title="${r.label} — ${r.zip}, ${r.members} · ${r.n} sales · ${r.area}, ${r.region}">
        <span class="z">${r.label}<em class="zc">${r.zip}</em></span>${track}
        <span class="v">${shown}<em class="nb">${baseOf(r)}</em></span></div>`;
    }).join("");
  });

  document.querySelectorAll("#leaders button[data-lead]").forEach(b => {
    b.onclick = ev => {
      ev.stopPropagation();
      const k = b.dataset.lead;
      leadOpen.has(k) ? leadOpen.delete(k) : leadOpen.add(k);
      leaders();
    };
  });
  /* Hovering an area lights the region that contains it, clicking steps into that region --
     the leaderboard is the shortcut into the tier below, not a dead end. */
  document.querySelectorAll(".row.lead").forEach(row => {
    const rg = row.dataset.region, z = row.dataset.zip;
    row.onmouseenter = () => highlight(rg, true);
    row.onmouseleave = () => highlight(rg, false);
    /* Straight to the homes: the row already names a single ZIP, so stopping at its region
       would make the reader find it again in a list of fifteen. */
    row.onclick = () => { level = 2; openRegion = rg; openZipCode = z;
                          draw(); };
  });
}

function crumbs(){
  const bar = document.getElementById("drillBar");
  if (level === 0){ bar.classList.add("hidden"); return; }
  bar.classList.remove("hidden");
  document.getElementById("backBtn").textContent =
    level === 2 ? "Back to " + openRegion : "Back to all regions";
  const st = stats[openZipCode] || {};
  const parts = [`<button class="crumb" onclick="goTo(0)">All regions</button>`];
  parts.push(`<span class="sep">›</span>`);
  parts.push(level === 1 ? `<b>${openRegion}</b>`
    : `<button class="crumb" onclick="goTo(1)">${openRegion}</button>`);
  if (level === 2){
    const mine = activeSales().filter(p => p.z === openZipCode);
    const counted = mine.filter(p => p.oa != null).length;
    parts.push(`<span class="sep">›</span><b>${openZipCode}</b>`);
    parts.push(`<span class="dotkey">${st.members || ""} · <b>${mine.length}</b> homes, ` +
      `<b>${counted}</b> with a recorded ask ` +
      `<i class="solid"></i>counts<i class="hollow"></i>no ask</span>`);
  } else {
    parts.push(`<span class="dotkey">${(REGION_ZIPS[openRegion] || []).length} ZIP codes ` +
      `— click one for its homes</span>`);
  }
  document.getElementById("drillText").innerHTML = parts.join(" ");
}

function tip(r){
  const t = [];
  t.push(`<h4>${r.zip}</h4>`);
  /* Members are ZIP codes at region... no: they are area names at region level, comma
     separated, and a city name at ZIP level. Splitting on spaces turned "Monroe & Snohomish"
     into "Monroe · & · Snohomish", so the separator is chosen by what is actually there. */
  if (r.members) {
    const parts = r.members.includes(",") ? r.members.split(/,\s*/)
                : /^\d{5}( \d{5})*$/.test(r.members) ? r.members.split(" ")
                : [r.members];
    t.push(`<div class="delta">${parts.join(" \u00b7 ")}</div>`);
  }
  t.push(`<div class="big">${fmt[metric](r[metric])}</div>`);
  if (r.n < MIN_N)
    t.push(`<div class="warn">Only ${r.n} sales \u2014 too few to read. ` +
           (r.n <= 2 ? "With two, the median is just their average." :
            "Treat this as anecdote.") + `</div>`);
  t.push("<table>");
  t.push(`<tr><td>Sales</td><td class="v">${r.n}</td></tr>`);
  t.push(`<tr><td>Sold vs ask</td><td class="v">${fmt.median_vs_ask(r.median_vs_ask)}</td></tr>`);
  t.push(`<tr><td>Above ask</td><td class="v">${r.over_ask_n} of ${r.n} (${r.over_ask_pct}%)</td></tr>`);
  t.push(`<tr><td>At ask (\u00b10.5%)</td><td class="v">${r.at_ask_n} of ${r.n} (${r.at_ask_pct}%)</td></tr>`);
  t.push(`<tr><td>Below ask</td><td class="v">${r.below_ask_n} of ${r.n} (${r.below_ask_pct}%)</td></tr>`);
  t.push(`<tr><td>Days to pending</td><td class="v">${fmt.median_days(r.median_days)}</td></tr>`);
  t.push(`<tr><td>Sold &lt;10 days</td><td class="v">${r.fast_pct}%</td></tr>`);
  t.push(`<tr><td>Cut price at all</td><td class="v">${r.cut_pct}% of ${r.n}</td></tr>`);
  t.push(`<tr><td>Cuts per listing</td><td class="v">${r.cuts_mean.toFixed(2)} mean, ${
    r.cuts_median.toFixed(0)} median${r.cuts_max > 3 ? `, ${r.cuts_max} worst` : ""}</td></tr>`);
  if (r.cut_size_median != null)
    t.push(`<tr><td>Cut depth, if cut</td><td class="v">${
      r.cut_size_median.toFixed(1)}% over ${
      r.cuts_median_among_cutters.toFixed(0)} cut(s)</td></tr>`);
  t.push(`<tr><td>Median price</td><td class="v">$${r.median_price.toLocaleString()}</td></tr>`);
  t.push("</table>");
  t.push('<div class="ex">Click to see the individual sales</div>');
  if (r.top && r.top.length){
    const b = r.top[0], w = r.bottom[r.bottom.length-1];
    t.push(`<div class="ex">Best: <b>${b.a}</b> ${b.v > 0 ? "+" : ""}${b.v}%`);
    if (w && w.a !== b.a) t.push(`<br>Worst: <b>${w.a}</b> ${w.v}%`);
    t.push("</div>");
  }
  return `<div class="tip">${t.join("")}</div>`;
}

function hatchPattern(){
  const svg = document.querySelector("#map svg.leaflet-zoom-animated")
           || document.querySelector("#map svg");
  if (!svg || svg.querySelector("#thin")) return;
  const ns = "http://www.w3.org/2000/svg";
  const defs = document.createElementNS(ns, "defs");
  const pat = document.createElementNS(ns, "pattern");
  pat.setAttribute("id", "thin");
  pat.setAttribute("patternUnits", "userSpaceOnUse");
  pat.setAttribute("width", "7"); pat.setAttribute("height", "7");
  pat.setAttribute("patternTransform", "rotate(45)");
  const bg = document.createElementNS(ns, "rect");
  bg.setAttribute("width", "7"); bg.setAttribute("height", "7");
  bg.setAttribute("fill", isDark() ? "#2b2b29" : "#eceae4");
  const line = document.createElementNS(ns, "line");
  line.setAttribute("x1","0"); line.setAttribute("y1","0");
  line.setAttribute("x2","0"); line.setAttribute("y2","7");
  line.setAttribute("stroke", isDark() ? "#5a5a55" : "#b6b4ab");
  line.setAttribute("stroke-width","2.2");
  pat.appendChild(bg); pat.appendChild(line);
  defs.appendChild(pat); svg.appendChild(defs);
}

function draw(){
  recompute();
  reindex();
  const color = scaleFor(metric);
  if (layer) map.removeLayer(layer);
  if (sales){ map.removeLayer(sales); sales = null; }
  layer = L.geoJSON(geoFor(), {
    pane: "dataPane",
    style: f => {
      const r = stats[f.properties.zip];
      const thin = r && baseN(r) < MIN_N;
      return {
        fillColor: !r ? "transparent"
                 : thin ? "url(#thin)" : (color(r[metric]) || "transparent"),
        fillOpacity: r ? 0.82 : 0.15,
        color: surface(),   /* 2px surface gap between adjacent fills */
        weight: 2, opacity: 1,
      };
    },
    onEachFeature: (f, lyr) => {
      const r = stats[f.properties.zip];
      if (!r) return;
      shapes[f.properties.zip] = lyr;
      lyr.on("mouseover mousemove", e => showTip(tip(r), e));
      lyr.on("mouseout", () => hideTip());
      lyr.on("mouseover", () => highlight(f.properties.zip, true));
      lyr.on("mouseout", () => highlight(f.properties.zip, false));
      lyr.on("click", () => openUnit(f.properties.zip));
    }
  }).addTo(map);
  hatchPattern();
  layer.eachLayer(l => {            /* re-apply now that the pattern exists */
    const r = stats[l.feature.properties.zip];
    if (r && baseN(r) < MIN_N) l.setStyle({fillColor:"url(#thin)"});
  });
  /* At level 2 the open ZIP keeps its fill and its neighbours recede, so the dots are the
     most visible thing on screen rather than the least. */
  if (level === 2){
    layer.eachLayer(l => {
      l.setStyle(l.feature.properties.zip === openZipCode
        ? {fillOpacity:0.24, weight:2.5, color:isDark() ? "#fff" : "#0b0b0b"}
        : {fillOpacity:0.08, weight:1, color:surface()});
    });
    addSales(openZipCode);
  }
  /* Fit to what is actually on screen at this level. Fitting once at startup left the ZIPs
     occupying a third of the canvas; fitting per level is also what makes stepping in read
     as a zoom rather than a redraw. */
  const target = level === 2 && shapes[openZipCode]
    ? shapes[openZipCode].getBounds() : layer.getBounds();
  if (target.isValid())
    map.fitBounds(target, {padding: level === 2 ? [60, 60] : [18, 18]});
  document.getElementById("chartCard").classList.add("cap");
  legend(); table(); crumbs(); leaders(); priceOut(); scopeOut();
  if (level === 2) homeList(); else view.chart();
}

/* Both lists cross-highlight with the map, so one wiring pass covers either. */
function wireRows(){
  /* Scoped to the chart. A bare `.row` selector also matched the leaderboard rows, and since
     leaders() runs before the chart is drawn, this silently replaced their click handler --
     a leaderboard ZIP then drilled as if its ZIP code were a region name. */
  document.querySelectorAll("#chartRows .row").forEach(row => {
    const key = row.dataset.zip;
    row.onmouseenter = () => highlight(key, true);
    row.onmouseleave = () => highlight(key, false);
    /* Every chart row steps down a tier, matching the map beside it. The chart used to be the
       one place a click did nothing, while the polygons and the leaderboards both drilled. */
    if (level < 2 && key){ row.classList.add("step"); row.onclick = () => openUnit(key); }
  });
}

function composition(){
  /* 100% stacked: above | at | below, in the diverging pair plus a mid grey. All three
     are mutually exclusive and sum to 100, so one part-to-whole row says what three
     separate tabs said in three passes -- and it exposes what a median cannot, that
     98117 (30/41/30) and 98125 (28/6/67) have near-identical above-ask rates and
     completely different shapes.

     The "at" segment uses the grey ramp's mid step rather than the diverging neutral:
     the neutral is tuned to disappear into the chart surface, which is right for a
     choropleth midpoint and wrong for a segment that has to be told apart from its two
     neighbours. Segments carry a 2px surface gap so adjacent fills never bleed.  */
  const R = ramp();
  const AT = R.grey[1];
  const cols = {above: R.warm[2], at: AT, below: R.cool[0]};
  document.getElementById("chartTitle").innerHTML =
    "<span>Share above / at / below the original ask</span>" +
    `<span class="key">sort:` +
    ["above", "at", "below"].map(k =>
      `<button class="sortbtn${compSort === k ? " on" : ""}" data-sort="${k}">` +
      `<i style="background:${cols[k]}"></i>${k}</button>`).join("") +
    `</span>`;
  const field = {above: "over_ask_pct", at: "at_ask_pct", below: "below_ask_pct"}[compSort];
  const sorted = [...units()].sort((a, b) => b[field] - a[field]);
  document.getElementById("chartRows").innerHTML = sorted.map(r => {
    const seg = (w, c, cls) => w <= 0 ? "" :
      `<span class="seg2 ${cls}" style="width:${w}%;background:${c}"></span>`;
    const hi = v => `<b>${Math.round(v)}</b>`;
    return `<div class="row comp" data-zip="${r.zip}"
        title="${r.members || ""} \u00b7 ${r.n} sales">
      <span class="z">${r.zip}</span>
      <span class="stack">
        ${seg(r.over_ask_pct, cols.above, "a")}
        ${seg(r.at_ask_pct, cols.at, "b")}
        ${seg(r.below_ask_pct, cols.below, "c")}
      </span>
      <span class="v">${compSort === "above" ? hi(r.over_ask_pct) : Math.round(r.over_ask_pct)}<em
        class="sl">/</em>${compSort === "at" ? hi(r.at_ask_pct) : Math.round(r.at_ask_pct)}<em
        class="sl">/</em>${compSort === "below" ? hi(r.below_ask_pct) : Math.round(r.below_ask_pct)}</span>
    </div>`;
  }).join("");
  wireRows();
  document.querySelectorAll(".sortbtn").forEach(b => b.onclick = () => {
    compSort = b.dataset.sort; composition();
  });
}

function rankedBars(){
  const color = scaleFor(metric), m = META[metric];
  const vals = units().map(r => r[metric]).filter(v => v != null);
  const lo = Math.min(0, ...vals), hi = Math.max(0, ...vals);
  const span = (hi - lo) || 1;
  const zeroPct = ((0 - lo) / span) * 100;
  document.getElementById("chartTitle").textContent =
    m.label + (level === 0 ? " \u2014 by region" : " \u2014 by ZIP");
  const sorted = [...units()].sort((a, b) =>
    (b[metric] ?? -Infinity) - (a[metric] ?? -Infinity));
  document.getElementById("chartRows").innerHTML = sorted.map(r => {
    const v = r[metric];
    if (v == null) return `<div class="row" data-zip="${r.zip}">
      <span class="z">${r.zip}</span><span class="track"></span>
      <span class="v">n/a</span></div>`;
    const w = Math.abs(v - 0) / span * 100;
    const left = v >= 0 ? zeroPct : zeroPct - w;
    return `<div class="row" data-zip="${r.zip}" title="${r.members || ""} \u00b7 ${r.n} sales">
      <span class="z">${r.zip}</span>
      <span class="track"><span class="zero" style="left:${zeroPct}%"></span>
        <span class="bar ${v >= 0 ? "pos" : "neg"}${baseN(r) < MIN_N ? " thin" : ""}"
          style="left:${left}%;width:${Math.max(w, 0.6)}%;
          ${baseN(r) < MIN_N ? "" : "background:" + color(v)}"></span></span>
      <span class="v">${fmt[metric](v)}${baseN(r) < MIN_N
        ? `<em class="nb">n=${baseN(r)}</em>` : ""}</span></div>`;
  }).join("");
  wireRows();
}

/* ---- the hover panel ---- */
let tipTimer = null;
function showTip(html, e){
  const box = document.getElementById("floatTip");
  const root = document.querySelector(".viz-root").getBoundingClientRect();
  if (box.dataset.html !== html){ box.innerHTML = html; box.dataset.html = html; }
  box.classList.remove("hidden");
  clearTimeout(tipTimer);
  /* Positioned from the page, not the map, since it is no longer a child of the map. Flips to
     the left and upward near the edges so it is never the panel that decides what you can
     read -- the old one simply got cut off. */
  const pad = 14, w = box.offsetWidth, h = box.offsetHeight;
  /* Leaflet wraps the DOM event; a row hover hands one over directly. Reading
     `e.originalEvent` unconditionally threw on every row hover. */
  const ev = e.originalEvent || e;
  const px = ev.clientX - root.left, py = ev.clientY - root.top;
  let x = px + pad, y = py - h - pad;
  if (x + w > root.width - 4) x = px - w - pad;
  if (x < 4) x = 4;
  if (y < 4) y = py + pad;
  if (y + h > root.height - 4) y = Math.max(4, root.height - h - 4);
  box.style.left = Math.round(x) + "px";
  box.style.top = Math.round(y) + "px";
}
/* Leaving the shape starts a short countdown rather than hiding at once, and entering the
   panel cancels it. Without the gap there is a pixel of dead space between shape and panel
   that closes it mid-journey, which is exactly the reported behaviour. */
function hideTip(now){
  clearTimeout(tipTimer);
  const box = document.getElementById("floatTip");
  if (now){ box.classList.add("hidden"); return; }
  tipTimer = setTimeout(() => box.classList.add("hidden"), 260);
}
document.getElementById("floatTip").onmouseenter = () => clearTimeout(tipTimer);
document.getElementById("floatTip").onmouseleave = () => hideTip();

/* Hover in either view lights the other. */
const shapes = {};
function highlight(zip, on){
  if (level === 2) return;           /* drilled in: the dots own the hover */
  const lyr = shapes[zip];
  if (lyr) lyr.setStyle(on
    ? {weight:3, color:isDark() ? "#fff" : "#0b0b0b", fillOpacity:0.92}
    : {weight:2, color:surface(), fillOpacity:0.82});
  document.querySelectorAll(`.row[data-zip="${zip}"]`)
    .forEach(r => r.classList.toggle("on", on));
}

/* Two paragraphs under each tab, and neither is hand-written prose about the data.

   The old captions carried 39 hardcoded figures -- "across 1,383 sales the median is -3.33%",
   the cut ladder, every correlation. They were accurate the day they were written and would
   have gone silently stale on the next data refresh, describing last month's market beneath
   this month's charts. So the numbers are computed from DATA at render time and the prose that
   is left contains none.

   HOWTO is the part that genuinely does not change: what the encoding means and how to read
   it. It is safe to hand-write precisely because it makes no claim about any figure. */
const HOWTO = {
  vs_ask: "Bar length and fill are the median home's gap from the opening ask of its own " +
    "campaign. Grey is parity, blue is under, red is over. A median says nothing about " +
    "spread — two units with the same figure can be calm or violently mixed — so " +
    "step in when a number matters. Widening the window changes the figure for two reasons " +
    "at once: more sales, and a different time of year. Spring and late summer are not the " +
    "same market, so a 1-month and a 6-month median differ partly by season.",
  split: "Each bar splits a unit's sales three ways: above the ask, on it, below it. They sum " +
    "to 100, so the shape carries as much as the total: the same balance can be a " +
    "price-to-sell market where most land exactly on the ask, or a negotiated one where they " +
    "scatter either side. The map colours by the below-ask share alone.",
  fast: "The same three-way split, restricted to homes that went under contract within ten " +
    "days. Figures are counts rather than shares because the base is small. Read it against " +
    "the previous tab: the distance between the two is what speed is worth to a seller.",
  days: "Median days from listing to <em>contract</em>, not to closing — escrow adds " +
    "roughly another month. Darker is quicker. Read it beside Sold vs ask, which it tracks " +
    "closely; the units where the two disagree are the ones worth a second look.",
  cuts: "How often sellers publish a reduction — mean and median cuts per listing, and " +
    "the share that cut at all. Frequency only. How far the ask actually fell is the next " +
    "tab, and the two can point opposite ways.",
  depth: "How far the published ask fell among the homes that cut, shown beside what was then " +
    "conceded at the table. The two halves are kept separate because roughly half of all " +
    "discount is never published as a cut at all, and a cuts-only view reports those homes " +
    "as zero.",
  price: "Median sold price \u2014 the middle sale, not an average, so one mansion cannot " +
    "move it. Darker is dearer. This tab answers what a home here costs; $/sqft answers what " +
    "space here costs. A unit can be cheap per foot and expensive per house if the houses are " +
    "large, and the two disagreeing is usually a difference in what got built rather than in " +
    "what buyers will pay. Narrowing the price band above makes this tab converge by " +
    "construction, so read the two together.",
  ppsf: "Median sold price per square foot. Darker is dearer. Read it against the median " +
    "price in the table — a low figure can mean large houses rather than cheap ones. " +
    "This is the tab most distorted by mixing property types: a condo's floor area excludes " +
    "everything shared, so its $/sqft is not the same measurement as a house's. With more " +
    "than one type selected, read it as a price level rather than a comparison.",
};

/* ---- the computed half ---- */
const med = a => { const v = a.filter(x => x != null).sort((x, y) => x - y);
  if (!v.length) return null;
  const h = v.length >> 1;
  return v.length % 2 ? v[h] : (v[h - 1] + v[h]) / 2; };
const pc = v => (v > 0 ? "+" : "") + v.toFixed(2) + "%";
const sh = v => Math.round(v) + "%";

/* Whatever the reader is looking at: everything, one region, or one ZIP. */
function scopePoints(){
  const s = activeSales();
  if (level === 2) return s.filter(p => p.z === openZipCode);
  if (level === 1) return s.filter(p => (ZMETA[p.z] || {}).region === openRegion);
  return s;
}
const unitName = r => r.label || r.zip;
function ends(field, lowFirst){
  const u = units().filter(r => r[field] != null
    && (r[VIEWS.find(v => v.id === view.id).base || "n"] ?? 0) >= MIN_N);
  if (!u.length) return null;
  const s = [...u].sort((a, b) => a[field] - b[field]);
  return lowFirst ? [s[0], s[s.length - 1]] : [s[s.length - 1], s[0]];
}

function summarise(){
  const P = scopePoints();
  const withAsk = P.filter(p => p.va != null);
  const n = withAsk.length;
  const where = level === 0 ? `across all ${UNITS.region.length} regions`
    : level === 1 ? `in ${openRegion}` : `in ${openZipCode}`;
  const noun = level === 2 ? "home" : "unit";
  if (!n) return `No sales with a recorded ask ${where}.`;
  const vs = withAsk.map(p => p.va * 100);
  const above = vs.filter(v => v > 0.5).length, below = vs.filter(v => v < -0.5).length;
  const at = n - above - below;
  const named = (r, v) => `<b>${unitName(r)}</b> at ${v}`;
  const best = (field, lowFirst, fmt) => {
    if (level === 2){
      const s = [...withAsk].sort((a, b) => a.va - b.va);
      return [`<b>${s[s.length - 1].a}</b> at ${pc(s[s.length - 1].va * 100)}`,
              `<b>${s[0].a}</b> at ${pc(s[0].va * 100)}`];
    }
    const e = ends(field, lowFirst);
    return e ? [named(e[0], fmt(e[0][field])), named(e[1], fmt(e[1][field]))] : null;
  };

  switch (view.id){
    case "vs_ask": {
      const e = best("median_vs_ask", false, pc);
      return `<b>${n.toLocaleString()}</b> sales ${where}, median <b>${pc(med(vs))}</b>. ` +
        `${sh(above / n * 100)} sold over the ask, ${sh(at / n * 100)} on it, ` +
        `${sh(below / n * 100)} under.` + (e ? ` Strongest ${e[0]}, weakest ${e[1]}.` : "");
    }
    case "split": {
      const e = level === 2 ? null : ends("below_ask_pct", true);
      return `Of <b>${n.toLocaleString()}</b> sales ${where}, ` +
        `<b>${sh(above / n * 100)}/${sh(at / n * 100)}/${sh(below / n * 100)}</b> came in ` +
        `above, at and below the ask; ${vs.filter(v => v === 0).length} landed on it exactly.` +
        (e ? ` Least one-sided ${named(e[0], sh(e[0].below_ask_pct) + " below")}, most ` +
             `${named(e[1], sh(e[1].below_ask_pct) + " below")}.` : "");
    }
    case "fast": {
      const f = withAsk.filter(p => p.dp != null && p.dp < 10);
      const s = withAsk.filter(p => p.dp != null && p.dp >= 10);
      const trio = g => { const v = g.map(p => p.va * 100);
        return `${sh(v.filter(x => x > 0.5).length / g.length * 100)}/` +
               `${sh(v.filter(x => Math.abs(x) <= 0.5).length / g.length * 100)}/` +
               `${sh(v.filter(x => x < -0.5).length / g.length * 100)}`; };
      if (!f.length || !s.length) return `Too few fast sales ${where} to compare.`;
      return `<b>${f.length}</b> of ${n.toLocaleString()} sales ${where} went pending inside ` +
        `ten days. Those ran <b>${trio(f)}</b> at a median of <b>${pc(med(f.map(p => p.va*100)))}` +
        `</b>; the other ${s.length} ran ${trio(s)} at ${pc(med(s.map(p => p.va * 100)))}.`;
    }
    case "days": {
      const d = P.map(p => p.dp).filter(v => v != null);
      const e = level === 2 ? null : ends("median_days", true);
      return `Median <b>${med(d)} days</b> to contract ${where}, over ${d.length} sales with ` +
        `a recorded pending date.` +
        (e ? ` Quickest ${named(e[0], e[0].median_days + " d")}, slowest ` +
             `${named(e[1], e[1].median_days + " d")}.` : "");
    }
    case "cuts": {
      const cut = P.filter(p => p.nc > 0);
      const e = level === 2 ? null : ends("cuts_mean", true);
      return `<b>${cut.length}</b> of ${P.length.toLocaleString()} listings ${where} published ` +
        `a cut (<b>${sh(cut.length / P.length * 100)}</b>), averaging ` +
        `${(P.reduce((t, p) => t + p.nc, 0) / P.length).toFixed(2)} per listing.` +
        (e ? ` Fewest ${named(e[0], e[0].cuts_mean.toFixed(2))}, most ` +
             `${named(e[1], e[1].cuts_mean.toFixed(2))}.` : "");
    }
    case "depth": {
      const cut = P.filter(p => p.nc > 0 && p.cd != null);
      const silent = P.filter(p => p.nc === 0 && p.va != null && p.va < -0.005);
      if (!cut.length) return `No published cuts ${where}.`;
      const e = level === 2 ? null : ends("cut_size_median", true);
      return `The <b>${cut.length}</b> listings that cut ${where} dropped the ask a median of ` +
        `<b>${med(cut.map(p => p.cd * 100)).toFixed(2)}%</b>, then conceded a further ` +
        `<b>${med(cut.map(p => p.ng * 100)).toFixed(2)}%</b> at the table. A separate ` +
        `<b>${silent.length}</b> never cut and still sold under the ask.` +
        (e ? ` Deepest ${named(e[0], e[0].cut_size_median.toFixed(1) + "%")}.` : "");
    }
    case "price": {
      const v = withAsk.map(p => p.sp);
      const e = level === 2 ? null : ends("median_price", true);
      return `Median <b>${fmt.median_price(med(v))}</b> ${where}, over ` +
        `${n.toLocaleString()} sales, spanning ${fmt.median_price(Math.min(...v))} to ` +
        `${fmt.median_price(Math.max(...v))}.` +
        (e ? ` Most affordable ${named(e[0], fmt.median_price(e[0].median_price))}, ` +
             `dearest ${named(e[1], fmt.median_price(e[1].median_price))}.` : "");
    }
    case "ppsf": {
      const v = P.filter(p => p.sq).map(p => p.sp / p.sq);
      const e = level === 2 ? null : ends("median_ppsf", true);
      return `Median <b>$${Math.round(med(v)).toLocaleString()}</b> per square foot ${where}, ` +
        `over ${v.length.toLocaleString()} sales with a recorded size.` +
        (e ? ` Cheapest ${named(e[0], "$" + e[0].median_ppsf)}, dearest ` +
             `${named(e[1], "$" + e[1].median_ppsf)}.` : "");
    }
  }
  return "";
}

function fastSplit(){
  /* The three-way split restricted to sales that went pending within 10 days. It belongs
     on this tab because it is the answer to what the tab asks: fast sales run 47/40/14
     with a +0.10% median while slower ones run 2/8/90 at -5.77%. Per-ZIP counts are thin
     -- several ZIPs have 2 to 4 fast sales and one has none -- so the count travels with
     every row and anything under 5 is dimmed rather than presented as a reading. */
  const R = ramp();
  const AT = R.grey[1];
  const cols = {above: R.warm[2], at: AT, below: R.cool[0]};
  document.getElementById("chartTitle").innerHTML =
    "<span>Fast sales only \u2014 pending within 10 days</span>" +
    '<span class="key">homes above \u00b7 at \u00b7 below ask, ' +
    'among those pending within 10 days</span>';
  const rows = units().filter(r => r.fast_n > 0)
    .sort((a, b) => b.fast_over_pct - a.fast_over_pct);
  const none = units().filter(r => !r.fast_n);
  document.getElementById("chartRows").innerHTML = rows.map(r => {
    const seg = (w, c, cls) => w <= 0 ? "" :
      `<span class="seg2 ${cls}" style="width:${w}%;background:${c}"></span>`;
    const thin = r.fast_n < MIN_N;
    return `<div class="row comp${thin ? " faint" : ""}" data-zip="${r.zip}"
        title="${r.members || ""} \u00b7 ${r.fast_n} of ${r.n} went pending in under 10 days">
      <span class="z">${r.zip}</span>
      <span class="stack">
        ${seg(r.fast_over_pct, cols.above, "a")}
        ${seg(r.fast_at_pct, cols.at, "b")}
        ${seg(r.fast_below_pct, cols.below, "c")}
      </span>
      <span class="v">${r.fast_over_n}<em class="sl">/</em>${r.fast_at_n}<em
        class="sl">/</em>${r.fast_below_n}</span>
    </div>`;
  }).join("") + none.map(r => `
    <div class="row comp faint" data-zip="${r.zip}">
      <span class="z">${r.zip}</span>
      <span class="stack"></span>
      <span class="v"><em class="nb">none</em></span>
    </div>`).join("");
  wireRows();
}

function cutDepth(){
  /* Median total reduction among the homes that cut, and the median number of cuts it
     took to get there. Restricted to cutters on purpose: including the 67% that never
     cut would drag every ZIP to 0.00% and hide the whole distribution. */
  const R = ramp();
  const rows = units().filter(r => r.cut_size_median != null);
  const deepest = Math.min(...rows.map(r => r.cut_size_median)) || -1;
  document.getElementById("chartTitle").innerHTML =
    "<span>How far the ask fell, among homes that cut</span>" +
    '<span class="key">median cut \u00b7 cuts taken \u00b7 cutters</span>';
  const sorted = [...rows].sort((a, b) => a.cut_size_median - b.cut_size_median);
  document.getElementById("chartRows").innerHTML = sorted.map(r => {
    const w = Math.abs(r.cut_size_median) / Math.abs(deepest) * 100;
    /* Cool arm: a deeper cut is buyer-favourable, the same direction as "below ask". */
    const t = Math.min(2, Math.floor(Math.abs(r.cut_size_median) / Math.abs(deepest) * 3));
    /* Dimmed on the same rule the map hatches on: a -10.9% median across 3 cutters is
       arithmetic, not a market reading. */
    return `<div class="row cuts${r.cutters_n < MIN_N ? " faint" : ""}" data-zip="${r.zip}"
        title="${r.members || ""} \u00b7 ${r.cutters_n} of ${r.n} cut">
      <span class="z">${r.zip}</span>
      <span class="track"><span class="bar neg" style="left:${100 - w}%;
        width:${Math.max(w, 0.8)}%;background:${R.cool[2 - t]}"></span></span>
      <span class="v"><b>${r.cut_size_median.toFixed(1)}%</b><em class="sl">\u00b7</em>${
        r.cuts_median_among_cutters.toFixed(0)}<em class="sl">\u00b7</em>${
        r.cutters_n}/${r.n}</span>
    </div>`;
  }).join("");
  wireRows();
}

function cutsList(){
  const R = ramp(), color = scaleFor("cuts_mean");
  const vals = units().map(r => r.cuts_mean);
  const max = Math.max(...vals) || 1;
  document.getElementById("chartTitle").innerHTML =
    "<span>Price cuts per listing</span>" +
    '<span class="key">mean \u00b7 median \u00b7 share that cut</span>';
  const sorted = [...units()].sort((a, b) => b.cuts_mean - a.cuts_mean);
  document.getElementById("chartRows").innerHTML = sorted.map(r => `
    <div class="row cuts" data-zip="${r.zip}" title="${r.members || ""} \u00b7 ${r.n} sales">
      <span class="z">${r.zip}</span>
      <span class="track"><span class="bar pos" style="left:0;
        width:${Math.max(r.cuts_mean / max * 100, 0.8)}%;
        background:${color(r.cuts_mean)}"></span></span>
      <span class="v"><b>${r.cuts_mean.toFixed(2)}</b><em class="sl">\u00b7</em>${
        r.cuts_median.toFixed(0)}<em class="sl">\u00b7</em>${Math.round(r.cut_pct)}%</span>
    </div>`).join("");
  wireRows();
}

function legend(){
  const R = ramp(), m = META[metric];
  /* Inverted metrics paint the *low* end dark, so the legend has to flip with them.
     Caught by rendering: "days to pending" showed fast ZIPs dark on the map while the
     legend put light at the fast end. */
  const armName = m.arm || "cool";
  const armSrc = armName === "warm" ? [...R.warm].reverse() : R[armName];
  /* Darkest cool at the far left, through the neutral, to darkest warm at the far right.
     Keyed off `diverging` rather than the metric name so a second diverging metric cannot
     silently fall through to the sequential branch. */
  let sw = m.diverging
    ? [R.cool[0], R.cool[1], R.cool[2], R.neutral, R.warm[0], R.warm[1], R.warm[2]]
    : [armSrc[2], armSrc[1], armSrc[0]];
  if (m.invert) sw = [...sw].reverse();
  document.getElementById("swatches").innerHTML =
    sw.map(c => `<span class="sw" style="background:${c}"></span>`).join("");
  document.getElementById("legendTitle").textContent = m.label;
  /* Same domain as the ramp, or the end labels would name values the colours never reach. */
  const vals = colourable().map(r => r[metric]).filter(v => v != null);
  document.getElementById("lo").textContent =
    m.diverging ? m.lo : `${m.lo} (${fmt[metric](Math.min(...vals))})`;
  document.getElementById("hi").textContent =
    m.diverging ? m.hi : `${m.hi} (${fmt[metric](Math.max(...vals))})`;
  document.getElementById("legendNote").textContent =
    (m.diverging ? "grey = sold at ask \u00b7 " : "") +
    `hatched = under ${MIN_N} ${view.baseNoun || "sales"}`;
  /* Two paragraphs: what this view actually says, computed; then how to read it, fixed. */
  document.getElementById("summary").innerHTML = summarise();
  document.getElementById("howto").innerHTML = HOWTO[view.id] +
    " Click a region for its ZIP codes, a ZIP for its homes, a home for its listing. " +
    "A sale is only measured when its own campaign has a priced opening; those that do not " +
    "are excluded rather than measured against an older listing. Units under " + MIN_N +
    " sales are hatched on the map and kept out of the leaderboards.";
}

function table(){
  document.getElementById("thUnit").textContent = level === 0 ? "Region" : "ZIP";
  document.getElementById("thMembers").textContent = level === 0 ? "Market areas" : "City";
  document.getElementById("tbody").innerHTML = units().map(r => `<tr>
    <td>${r.zip}</td><td class="zl">${r.members || ""}</td><td>${r.n}</td>
    <td>${fmt.median_vs_ask(r.median_vs_ask)}</td>
    <td>${r.over_ask_pct}%</td><td>${r.at_ask_pct}%</td>
    <td>${r.below_ask_pct}%</td>
    <td>${fmt.median_days(r.median_days)}</td>
    <td>${r.fast_pct}%</td><td>${r.cut_pct}%</td>
    <td>${r.cut_size_median == null ? "n/a" : r.cut_size_median + "%"}</td>
    <td>${r.negotiated_median}%</td>
    <td>$${r.median_price.toLocaleString()}</td>
    <td>${fmt.median_ppsf(r.median_ppsf)}</td></tr>`).join("");
}

document.querySelectorAll("#tabSeg button").forEach(b => b.onclick = () => {
  document.querySelectorAll("#tabSeg button")
    .forEach(x => x.setAttribute("aria-pressed", String(x === b)));
  view = VIEWS.find(v => v.id === b.dataset.v);
  metric = view.metric;
  draw();
});
document.getElementById("toggleTable").onclick = e => {
  const w = document.getElementById("tableWrap");
  const open = w.classList.toggle("hidden") === false;
  e.target.textContent = open ? "Hide table" : "Show table";
  e.target.setAttribute("aria-pressed", String(open));
};
document.getElementById("toggleTheme").onclick = e => {
  const dark = !isDark();
  document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
  e.target.textContent = dark ? "Light" : "Dark";
  addTiles(); draw();
};
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
  if (!document.documentElement.getAttribute("data-theme")) { addTiles(); draw(); }
});
/* ---- the price band ---- */
const pMoney = v => v >= 1_000_000
  ? "$" + (v / 1_000_000).toFixed(v % 1_000_000 ? 2 : 1).replace(/\.?0+$/, "") + "M"
  : "$" + Math.round(v / 1000) + "k";
/* One bar per interval between stops, so the bars line up with what the thumbs can select.
   Heights are square-rooted: the busiest bucket holds an order of magnitude more than the
   tail, and on a linear scale every bucket over $2M would render as a single pixel. */
let HIST = [];
function priceHist(){
  const last = STEPS.length - 2;
  const inS = scopeSales();
  HIST = STEPS.slice(0, -1).map((v, i) =>
    inS.filter(p => p.sp >= v && (i === last || p.sp < STEPS[i + 1])).length);
  const top = Math.max(...HIST) || 1;
  document.getElementById("pHist").innerHTML = HIST.map((c, i) =>
    `<i data-b="${i}" style="height:${Math.max(Math.sqrt(c / top) * 100, c ? 6 : 1)}%"
        title="${pMoney(STEPS[i])}${i === HIST.length - 1 ? "+"
          : "\u2013" + pMoney(STEPS[i + 1])}: ${c} homes"></i>`).join("");
  const span = STEPS.length - 1;
  document.getElementById("pTicks").innerHTML =
    [0, 500_000, 1_000_000, 1_500_000, 2_000_000, 3_000_000, 5_000_000].map(v => {
      const i = v === 0 ? 0 : STEPS.indexOf(v);
      if (i < 0) return "";
      const label = v === 0 ? "any" : pMoney(v) + (i === span ? "+" : "");
      return `<span style="left:${i / span * 100}%">${label}</span>`;
    }).join("");
}
/* ---- property type and window ---- */
function scopeWire(){
  const paint = () => {
    document.querySelectorAll("#ptSeg button").forEach(b =>
      b.setAttribute("aria-pressed", SCOPE.types.has(b.dataset.pt)));
    document.querySelectorAll("#winSeg button").forEach(b =>
      b.setAttribute("aria-pressed", +b.dataset.win === SCOPE.months));
  };
  document.querySelectorAll("#ptSeg button").forEach(b => b.onclick = () => {
    const t = b.dataset.pt;
    /* Never let the last type be switched off: an empty scope has no answer to give, and the
       whole report would go blank with no indication why. */
    if (SCOPE.types.has(t) && SCOPE.types.size > 1) SCOPE.types.delete(t);
    else SCOPE.types.add(t);
    paint(); rescope();
  });
  document.querySelectorAll("#winSeg button").forEach(b => b.onclick = () => {
    SCOPE.months = +b.dataset.win;
    paint(); rescope();
  });
  paint();
}
/* The price distribution differs by type and window -- condos cluster far below houses -- so
   the histogram is rebuilt whenever the scope changes, and the band is clamped back inside
   whatever range still has sales. */
function rescope(){ priceHist(); draw(); }

function scopeOut(){
  const inS = scopeSales();
  const withAsk = inS.filter(p => p.oa != null).length;
  const mix = {};
  for (const p of inS) mix[p.pt] = (mix[p.pt] || 0) + 1;
  const parts = ["s", "t", "c"].filter(t => SCOPE.types.has(t))
    .map(t => `${(mix[t] || 0).toLocaleString()} ${PT_LABEL[t]}`);
  const from = dayStr(Math.max(cutoff() + 1, DATA.window[0]));
  document.getElementById("sOut").innerHTML =
    `<b>${withAsk.toLocaleString()}</b> measurable sales \u00b7 ${parts.join(", ")} ` +
    `\u00b7 ${from} to ${dayStr(WIN_END)}`;
}

function priceWire(){
  const lo = document.getElementById("pLo"), hi = document.getElementById("pHi");
  lo.max = hi.max = STEPS.length - 1;
  lo.value = 0; hi.value = STEPS.length - 1;
  const apply = () => {
    /* Push the other thumb rather than snapping back, which would silently undo the drag
       just made. Stacked inputs both cover the whole track, so without this the thumbs can
       be dragged past one another. */
    if (+lo.value > +hi.value){
      if (document.activeElement === lo) hi.value = lo.value; else lo.value = hi.value;
    }
    PRICE.lo = +lo.value === 0 ? null : STEPS[+lo.value];
    PRICE.hi = +hi.value === STEPS.length - 1 ? null : STEPS[+hi.value];
    draw();
  };
  lo.oninput = hi.oninput = apply;
  document.getElementById("pReset").onclick = () => {
    lo.value = 0; hi.value = STEPS.length - 1; apply();
  };
  /* Whichever thumb is nearer the pointer takes the press: with two inputs stacked, the one
     on top would otherwise always win and the lower thumb would be unreachable past halfway. */
  document.querySelector(".prange").onpointerdown = e => {
    const r = e.currentTarget.getBoundingClientRect();
    const at = (e.clientX - r.left) / r.width * (STEPS.length - 1);
    const nearHi = Math.abs(at - +hi.value) <= Math.abs(at - +lo.value);
    lo.style.zIndex = nearHi ? 1 : 2;
    hi.style.zIndex = nearHi ? 2 : 1;
  };
  priceHist();
}
/* The readout states the cost of the filter at the moment it is applied: how many sales are
   left, and how many units at each tier still clear the five-sale floor. A 600k band drops ZIP
   coverage from 86 into the high forties, and that belongs on screen while dragging rather
   than being discovered later as a mostly hatched map. */
function priceOut(){
  const el = document.getElementById("pOut");
  const band = PRICE.lo == null && PRICE.hi == null ? "all prices"
    : PRICE.lo != null && PRICE.hi != null ? `${pMoney(PRICE.lo)} \u2013 ${pMoney(PRICE.hi)}`
    : PRICE.lo != null ? `${pMoney(PRICE.lo)} and up` : `up to ${pMoney(PRICE.hi)}`;
  const sold = activeSales().filter(p => p.oa != null).length;
  const ok = k => UNITS[k].filter(r => r.n >= MIN_N).length;
  /* Denominators come from the metadata, not from what survived: a unit with no sales at all
     in the band has to read as 11/12, not 11/11, or it simply disappears. */
  const tot = k => Object.keys(DATA.meta[k]).length;
  /* Two different states, named separately: a ZIP with three sales in the band is hatched,
     one with none is simply absent from the map. Reporting them as a single number said
     "39 hatched" when only 14 were. */
  const thin = UNITS.zip.length - ok("zip");
  const empty = tot("zip") - UNITS.zip.length;
  const notes = [thin ? `${thin} too thin` : null,
                 empty ? `${empty} with no sales in band` : null].filter(Boolean);
  el.innerHTML = `<b>${band}</b> \u00b7 <b>${sold.toLocaleString()}</b> sales \u00b7 ` +
    `${ok("region")}/${tot("region")} regions, ${ok("zip")}/${tot("zip")} ZIPs ` +
    `above the floor` +
    (notes.length ? ` <span class="warn">\u00b7 ${notes.join(", ")}</span>` : "");
  /* Paint the selection onto the track and light the buckets inside it, so the band is legible
     against the distribution rather than only as two numbers. */
  const a = +document.getElementById("pLo").value;
  const b = +document.getElementById("pHi").value;
  const span = STEPS.length - 1;
  const sel = document.getElementById("pSel");
  sel.style.left = (a / span * 100) + "%";
  sel.style.width = ((b - a) / span * 100) + "%";
  /* A bar is lit when it holds at least one selected sale, not when its index falls between
     the thumbs. The band is inclusive of both ends while the bins are half-open, so seven
     sales priced at exactly $1,500,000 sit inside a "$900k - $1.5M" band and in the bin above
     it -- an index test left them counted but unlit. */
  const filled = new Set();
  for (const p of activeSales()){
    let i = 0;
    while (i < STEPS.length - 2 && p.sp >= STEPS[i + 1]) i++;
    filled.add(i);
  }
  document.querySelectorAll("#pHist i").forEach(bar =>
    bar.classList.toggle("on", filled.has(+bar.dataset.b)));
}
document.getElementById("backBtn").onclick = undrill;
document.addEventListener("keydown", e => { if (e.key === "Escape") undrill(); });
scopeWire(); priceWire(); addTiles(); draw();
document.getElementById("toggleTheme").textContent = isDark() ? "Light" : "Dark";
</script></div></body></html>
"""

html = (HTML
        .replace("__NREG__", str(len(payload["meta"]["region"])))
        .replace("__NZIP__", str(len(payload["meta"]["zip"])))
        .replace("__NAREA__", str(len(payload["meta"]["area"])))

        .replace("__STEPS__", json.dumps(price_steps(payload)))
        .replace("__PAYLOAD__", json.dumps(payload, separators=(",", ":")))
        .replace("NEUTRAL_L", payload["ramp"]["light"]["neutral"])
        .replace("NEUTRAL_D", payload["ramp"]["dark"]["neutral"]))
# index.html so GitHub Pages serves it at the bare repo URL with no redirect.
OUT = "index.html"
open(OUT, "w").write(html)
import os
print(f"wrote {OUT} ({os.path.getsize(OUT)/1024:.0f} kB)")
