"""The parts of the payload that are not sales and not ZIP shapes.

`ramp` (the validated colour steps), `labels` (city names for orientation), `context` (the
surrounding ZCTAs drawn as hairlines) and `water` (TIGER AREAWATER for King and Snohomish).

This stage exists because the pipeline could not previously rebuild from nothing: build_geo3
wrote `geo` and `zipgeo` into an existing payload and assumed these four were already there,
which held only as long as the working directory survived. It did not. Recovered from the
published report and written to the cache so a rebuild from an empty cache now works.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import paths  # noqa: E402

BASE = paths.p("base.json")


def load() -> dict:
    """The four static layers, or a clear failure rather than a half-built map."""
    if not os.path.exists(BASE):
        raise SystemExit(
            f"missing {BASE}.\nIt holds the colour ramp, city labels, context ZCTAs and water "
            f"polygons. Recover it from a published index.html with:\n"
            f"  python -c \"import json,re,pathlib,sys; sys.path.insert(0,'pipeline'); "
            f"import paths; "
            f"D=json.loads(re.search(r'const DATA = (\\\\{{.*?\\\\}});\\\\n', "
            f"pathlib.Path('index.html').read_text(), re.S).group(1)); "
            f"json.dump({{k:D[k] for k in ('ramp','labels','context','water')}}, "
            f"open(paths.p('base.json'),'w'))\"")
    return json.load(open(BASE))


def main():
    base = load()
    payload = (json.load(open(paths.PAYLOAD))
               if os.path.exists(paths.PAYLOAD) else {})
    payload.update(base)
    json.dump(payload, open(paths.PAYLOAD, "w"), separators=(",", ":"))
    print(f"seeded {', '.join(sorted(base))} into {paths.PAYLOAD}")


if __name__ == "__main__":
    main()
