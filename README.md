# Dublin Pubs

Two brothers on a mission to visit the pubs of Dublin.

- [Explore the map](https://irishshagua.github.io/dublin-pubs-map)
- [View the pub list](postgres-pubs-dump.txt)
- [View the GeoJSON map](dublin-pubs.geojson)

## Adding or updating pubs

Edit `postgres-pubs-dump.txt`. Each line contains latitude, longitude, name and review, separated by tabs. Then run from the repository root:

```sh
python3 validate_pubs.py
python3 convertToGeoJson.py
```

Review shared-coordinate warnings and include the pub list and regenerated GeoJSON. The website reads the visit list from the default branch; its source is on `gh-pages`.

## Refreshing the licence list

The published `remaining-pubs.json` comes from Revenue's [register of renewed liquor licences](https://www.revenue.ie/en/corporate/information-about-revenue/statistics/excise/licences/liquor-licences.aspx). It includes **only** rows whose description is exactly `Publican's Licence (7-Day Ordinary)` and whose county field is exactly either `CO. DUBLIN` or `DUBLIN CITY`. Both are needed for Dublin city and county. It is a licence register, not a complete directory of open pubs: premises with another county label, new or unrenewed licences, closures, and licence changes may be absent. The date is Revenue's register date, not the download date. A premises may have renewed after that date.

To refresh the displayed licence total, install Python 3 and the workbook reader, then run:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python3 refresh_licences.py
```

The script downloads the current [Revenue XLS](https://www.revenue.ie/en/corporate/documents/statistics/excise/liquor-licences.xls), validates its headers and date, and writes `remaining-pubs.json`, `licence-review.csv` and `licence-source.json` with the source URL, register date and workbook SHA-256. The initial published data uses Revenue's 2026-11-03 register (2026/2027), downloaded 2026-11-23, SHA-256 `b37f55aa1d6457d373daade85c861196d1fb0a83948e7abc0ee9d401a7c6563b`. To reproduce an older refresh, retain the original workbook and pass `--xls /path/to/liquor-licences.xls`; local input must be verified against Revenue separately. Include the output files and any changed overrides or location cache together in the repository. No reviews are changed by this process.

## Paused: matching and route planner

The website no longer shows a remaining-pubs list or route planner. The Revenue count is independent of historical visits and counts licences, not necessarily distinct pubs. Matching results in the generated files are experimental and must not be treated as a verified remaining list.

The November 2026 snapshot contained 639 licences, 450 historical visits and 503 licences without verified coordinates. A rough offline OpenStreetMap address experiment identified 85 unlocated entries with a potentially matching street and house number near a visit; these were not verified matches. Nearby or shared addresses can refer to different pubs, and Revenue trading names may differ from visit names. Address-to-location matching and stronger name/location evidence may improve coverage; keep uncertain matches separate from verified visits.

The previous prototype is available in the `gh-pages` commit `c6a0586`. The retained `refresh_licences.py`, `osm-locations.json`, `licence-review.csv` and overrides document the current matching attempt and can be revisited later.

### Experimental matching details

Inspect `licence-review.csv`, Revenue's address, and the existing visit before deciding. The candidate list is a hint, not a match. Edit `licence-overrides.json`, keyed by Revenue licence reference. To link a visit, copy its **exact** name and coordinates from the tab-separated visit list. For example, replace `<licence reference>` with the correct reference after verifying the premises:

```json
{
  "<licence reference>": {
    "visit": {"name": "Dawson Lounge", "latitude": 53.33972, "longitude": -6.25886}
  }
}
```

A visit selector must identify exactly one row and cannot be linked to two current licences. The visit's coordinates are used unless a location override is supplied. To decide a record is not visited, needs further review, or should be excluded (for example, a hotel), use `"decision": "remaining"`, `"review"`, or `"excluded"` instead of `visit`. Hotels are **not** automatically excluded. Hotel-named records default to review; manually inspect other records as needed. Decisions survive refreshes by licence reference; references missing from a later workbook are reported and retained for inspection. A changed or removed visit must have its override updated.

If a remaining decision conflicts with a visit that you have checked is a different pub, add `"dismissed_visits"` to that override as a list of visit selectors using the same name/latitude/longitude format above. Only those specific visits are dismissed; new possible matches still return the licence to review.

To add a verified location, add `"location": {"latitude": 53.33972, "longitude": -6.25886, "source": "<link or description of evidence>"}` to the appropriate override after checking that it is the actual premises. It can accompany either a visit or a decision. Do not estimate or guess coordinates. Run the refresh again and review the changed CSV and JSON. Do not add a home address to these files.

### OpenStreetMap locations

The checked-in `osm-locations.json` caches locations derived from [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors, via the [BBBike Dublin extract](https://download.bbbike.org/osm/bbbike/Dublin/), initially dated 2026-11-21. Each entry links to its OSM node or closed way and records the extract date and Revenue name and address; a changed name or address invalidates the match. Only unique pub/bar features with an exact normalized trading name and corroborating address are accepted: a distinctive matching street, a matching street and house number or locality, or a matching non-generic locality when OSM has no street. For valid closed ways the point is the polygon centroid, or an interior point if the centroid falls outside. Multiple matching OSM features remain unresolved. No bulk geocoder is used; unmapped and uncertain entries have null coordinates. OSM data is available under the [ODbL](https://opendatacommons.org/licenses/odbl/).

To rebuild the cache, download `Dublin.osm.pbf` from BBBike, note its snapshot date, install the optional `osmium` and `shapely` Python packages, and run:

```sh
pip install osmium shapely
python3 refresh_licences.py --osm-pbf /path/to/Dublin.osm.pbf --osm-date YYYY-MM-DD
```

This replaces the cache; manual overrides are retained. Regular refreshes reuse the checked-in cache and need only `xlrd`.
